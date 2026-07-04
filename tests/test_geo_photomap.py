import subprocess

import pytest

from dji_metadata_embedder.geo.photomap import (
    PhotoPoint,
    PhotomapError,
    camera_summary,
    format_exposure,
    points_from_exiftool_json,
    scan_photos,
)

# Shape verified against a real `exiftool -json -n -b` run.
CANNED = [
    {
        "SourceFile": "photos/church2.jpg",
        "GPSLatitude": 60.173047,
        "GPSLongitude": 24.92515,
        "GPSAltitude": 88.1,
        "DateTimeOriginal": "2026:06:15 13:05:10",
        "Model": "FC8482",
        "ISO": 100,
        "ExposureTime": 0.0005,
        "FNumber": 1.7,
        "ThumbnailImage": "base64:/9j/THUMB2",
    },
    {
        "SourceFile": "photos/church1.jpg",
        "GPSLatitude": 60.170278,
        "GPSLongitude": 24.952222,
        "GPSAltitude": 95.3,
        "DateTimeOriginal": "2026:06:15 12:30:45",
        "Model": "FC8482",
        "ISO": 100,
        "ExposureTime": 0.001,
        "FNumber": 1.7,
        # no ThumbnailImage -> pin without preview
    },
    {"SourceFile": "photos/no_gps.jpg", "DateTimeOriginal": "2026:06:15 12:31:00"},
    {"SourceFile": "photos/zero_fix.jpg", "GPSLatitude": 0.0, "GPSLongitude": 0.0},
]


def test_parses_gps_photos_and_skips_the_rest():
    points, skipped = points_from_exiftool_json(CANNED)
    assert [p.name for p in points] == ["church1.jpg", "church2.jpg"]  # sorted
    assert skipped == ["no_gps.jpg", "zero_fix.jpg"]  # sorted
    p = points[0]
    assert p.lat == 60.170278 and p.lon == 24.952222 and p.alt == 95.3
    assert p.timestamp == "2026-06-15 12:30:45"  # EXIF colons -> display dashes
    assert p.model == "FC8482" and p.iso == 100
    assert p.exposure == 0.001 and p.fnum == 1.7


def test_thumbnail_base64_prefix_is_stripped():
    points, _ = points_from_exiftool_json(CANNED)
    by_name = {p.name: p for p in points}
    assert by_name["church2.jpg"].thumbnail_b64 == "/9j/THUMB2"
    assert by_name["church1.jpg"].thumbnail_b64 is None


def test_missing_altitude_defaults_to_zero():
    points, _ = points_from_exiftool_json(
        [{"SourceFile": "a.jpg", "GPSLatitude": 1.0, "GPSLongitude": 2.0}]
    )
    assert points[0].alt == 0.0
    assert points[0].timestamp is None


def test_unparseable_numeric_fields_become_none():
    points, _ = points_from_exiftool_json(
        [{
            "SourceFile": "a.jpg", "GPSLatitude": 1.0, "GPSLongitude": 2.0,
            "ISO": "100, 100", "ExposureTime": "n/a", "FNumber": None,
        }]
    )
    assert points[0].iso is None
    assert points[0].exposure is None
    assert points[0].fnum is None


def test_format_exposure():
    assert format_exposure(0.001) == "1/1000 s"
    assert format_exposure(0.0005) == "1/2000 s"
    assert format_exposure(2.5) == "2.5 s"
    assert format_exposure(None) is None
    assert format_exposure(0) is None
    assert format_exposure(0.7) == "0.7 s"
    assert format_exposure(0.5) == "1/2 s"
    assert format_exposure(0.6) == "0.6 s"


def test_missing_sourcefile_falls_back_to_question_mark():
    points, _ = points_from_exiftool_json([{"GPSLatitude": 1.0, "GPSLongitude": 2.0}])
    assert points[0].name == "?"


def test_camera_summary_joins_available_parts():
    p = PhotoPoint(lat=0, lon=0, alt=0, name="a.jpg", model="FC8482",
                   iso=100, exposure=0.001, fnum=1.7)
    assert camera_summary(p) == "FC8482 · ISO 100 · 1/1000 s · f/1.7"
    bare = PhotoPoint(lat=0, lon=0, alt=0, name="a.jpg")
    assert camera_summary(bare) == ""


class _Proc:
    def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def test_scan_photos_builds_command_and_parses(monkeypatch, tmp_path):
    seen: dict = {}

    def fake_run(args, **kwargs):
        seen["args"] = args
        import json as _json
        return _Proc(stdout=_json.dumps(CANNED))

    monkeypatch.setattr(subprocess, "run", fake_run)
    points, skipped = scan_photos(tmp_path)
    assert [p.name for p in points] == ["church1.jpg", "church2.jpg"]
    assert skipped == ["no_gps.jpg", "zero_fix.jpg"]
    args = seen["args"]
    assert args[1:4] == ["-json", "-n", "-b"]
    assert "-r" not in args
    assert "-Composite:GPSLatitude" in args
    assert "-EXIF:ThumbnailImage" in args
    for ext in ("jpg", "jpeg", "dng"):
        i = args.index(ext)
        assert args[i - 1] == "-ext"
    assert args[-1] == str(tmp_path)


def test_scan_photos_recursive_adds_r(monkeypatch, tmp_path):
    seen: dict = {}

    def fake_run(args, **kwargs):
        seen["args"] = args
        return _Proc(stdout="[]")

    monkeypatch.setattr(subprocess, "run", fake_run)
    scan_photos(tmp_path, recursive=True)
    assert "-r" in seen["args"]


def test_scan_photos_empty_stdout_means_no_photos(monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Proc(stdout=""))
    assert scan_photos(tmp_path) == ([], [])


def test_scan_photos_missing_exiftool_raises_hint(monkeypatch, tmp_path):
    def raise_fnf(*a, **k):
        raise FileNotFoundError()

    monkeypatch.setattr(subprocess, "run", raise_fnf)
    with pytest.raises(PhotomapError, match="doctor"):
        scan_photos(tmp_path)


def test_scan_photos_hard_failure_raises_stderr(monkeypatch, tmp_path):
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: _Proc(stdout="", stderr="boom", returncode=1),
    )
    with pytest.raises(PhotomapError, match="boom"):
        scan_photos(tmp_path)


def test_scan_photos_bad_json_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Proc(stdout="{nope"))
    with pytest.raises(PhotomapError, match="JSON"):
        scan_photos(tmp_path)


def test_scan_photos_partial_failure_still_parses(monkeypatch, tmp_path):
    import json as _json
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: _Proc(
            stdout=_json.dumps(CANNED), stderr="Error: bad.jpg", returncode=1
        ),
    )
    points, skipped = scan_photos(tmp_path)
    assert [p.name for p in points] == ["church1.jpg", "church2.jpg"]


def test_scan_photos_non_list_json_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Proc(stdout="{}"))
    with pytest.raises(PhotomapError, match="shape"):
        scan_photos(tmp_path)
