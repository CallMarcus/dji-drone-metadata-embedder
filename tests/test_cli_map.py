import json
import re
from datetime import datetime
from pathlib import Path

from click.testing import CliRunner

import dji_metadata_embedder.cli as cli_mod
from dji_metadata_embedder.cli import main
from dji_metadata_embedder.geo.photomap import PhotoPoint, PhotomapError
from dji_metadata_embedder.geo.track import Track, TrackPoint

POINTS = [
    PhotoPoint(lat=60.170278, lon=24.952222, alt=95.3, name="church.jpg"),
]
TRACKS = [
    Track(name="DJI_0001", points=[
        TrackPoint(lat=60.19, lon=24.97, alt=5.0, timestamp="00:00:00,000",
                   utc=datetime(2026, 6, 15, 12, 0, 0)),
        TrackPoint(lat=60.191, lon=24.971, alt=6.5, timestamp="00:00:01,000",
                   utc=datetime(2026, 6, 15, 12, 1, 0)),
    ]),
]

_DATA_RE = re.compile(
    r'<script type="application/json" id="map-data">(.*?)</script>', re.DOTALL)


def _mock_scans(monkeypatch, points=POINTS, photo_skipped=(),
                tracks=TRACKS, srt_skipped=(), has_photos=True):
    calls = {}

    def fake_photos(directory, recursive=False):
        calls["photo_dir"] = Path(directory)
        calls["photo_recursive"] = recursive
        return list(points), list(photo_skipped)

    def fake_flights(directory, recursive=False, redact="none", **kwargs):
        calls["flight_recursive"] = recursive
        calls["redact"] = redact
        return [Track(name=t.name, points=list(t.points)) for t in tracks], \
            list(srt_skipped)

    monkeypatch.setattr(cli_mod, "folder_has_photos", lambda d: has_photos)
    monkeypatch.setattr(cli_mod, "scan_photos", fake_photos)
    monkeypatch.setattr(cli_mod, "scan_flights", fake_flights)
    return calls


def test_map_writes_html_with_both_types(monkeypatch, tmp_path):
    calls = _mock_scans(monkeypatch)
    res = CliRunner().invoke(main, ["map", str(tmp_path)])
    assert res.exit_code == 0, res.output
    out = tmp_path / "map.html"
    assert out.exists()
    data = json.loads(_DATA_RE.search(
        out.read_text(encoding="utf-8")).group(1))
    assert [f["properties"]["type"] for f in data["features"]] == \
        ["photo", "track"]
    assert "Mapped 1 photo and 1 flight" in res.output
    # The simple mode always scans recursively — no flag exists.
    assert calls["photo_recursive"] is True
    assert calls["flight_recursive"] is True


def test_map_photos_only_folder(monkeypatch, tmp_path):
    _mock_scans(monkeypatch, tracks=[])
    res = CliRunner().invoke(main, ["map", str(tmp_path)])
    assert res.exit_code == 0, res.output
    assert (tmp_path / "map.html").exists()


def test_map_tracks_only_folder_skips_exiftool(monkeypatch, tmp_path):
    calls = _mock_scans(monkeypatch, points=[], has_photos=False)
    res = CliRunner().invoke(main, ["map", str(tmp_path)])
    assert res.exit_code == 0, res.output
    # folder_has_photos returned False, so ExifTool was never invoked.
    assert "photo_dir" not in calls


def test_map_empty_folder_is_clean_error(monkeypatch, tmp_path):
    _mock_scans(monkeypatch, points=[], tracks=[], has_photos=False)
    res = CliRunner().invoke(main, ["map", str(tmp_path)])
    assert res.exit_code != 0
    assert "Nothing to map" in res.output
    assert res.exception is None or isinstance(res.exception, SystemExit)


def test_map_gpsless_files_only_is_clean_error(monkeypatch, tmp_path):
    _mock_scans(monkeypatch, points=[], photo_skipped=["no_gps.jpg"],
                tracks=[], srt_skipped=["cam.srt"])
    res = CliRunner().invoke(main, ["map", str(tmp_path)])
    assert res.exit_code != 0
    assert "none with GPS" in res.output


def test_map_output_flag_honoured(monkeypatch, tmp_path):
    _mock_scans(monkeypatch)
    out = tmp_path / "everything.html"
    res = CliRunner().invoke(main, ["map", str(tmp_path), "-o", str(out)])
    assert res.exit_code == 0, res.output
    assert out.exists()


def test_map_redact_fuzz_applies_to_both_pipelines(monkeypatch, tmp_path):
    calls = _mock_scans(monkeypatch)
    res = CliRunner().invoke(main, ["map", str(tmp_path), "--redact", "fuzz"])
    assert res.exit_code == 0, res.output
    assert calls["redact"] == "fuzz"          # tracks: fuzzed inside the scan
    data = json.loads(_DATA_RE.search(
        (tmp_path / "map.html").read_text(encoding="utf-8")).group(1))
    photo = next(f for f in data["features"]
                 if f["properties"]["type"] == "photo")
    lon, lat = photo["geometry"]["coordinates"][:2]
    assert (lat, lon) != (60.170278, 24.952222)   # photos: fuzzed post-scan
    assert data["redacted"] == "fuzz"


def test_map_scan_error_is_clean(monkeypatch, tmp_path):
    _mock_scans(monkeypatch)

    def boom(directory, recursive=False):
        raise PhotomapError("ExifTool not found")

    monkeypatch.setattr(cli_mod, "scan_photos", boom)
    res = CliRunner().invoke(main, ["map", str(tmp_path)])
    assert res.exit_code != 0
    assert "ExifTool" in res.output


def test_map_serve_conflicts_with_jsonl(monkeypatch, tmp_path):
    _mock_scans(monkeypatch)
    res = CliRunner().invoke(
        main, ["map", str(tmp_path), "--serve", "--progress", "jsonl"])
    assert res.exit_code != 0
    assert "--serve" in res.output


def test_map_verbose_lists_skipped(monkeypatch, tmp_path):
    _mock_scans(monkeypatch, photo_skipped=["no_gps.jpg"],
                srt_skipped=["cam.srt"])
    res = CliRunner().invoke(main, ["map", str(tmp_path), "-v"])
    assert res.exit_code == 0, res.output
    assert "no_gps.jpg" in res.output
    assert "cam.srt" in res.output


def test_map_pano_thumbs_render_automatically(monkeypatch, tmp_path):
    pano = [PhotoPoint(lat=60.17, lon=24.95, alt=None, name="sphere.jpg",
                       is_pano=True, pano_yaw=45.0)]
    _mock_scans(monkeypatch, points=pano, tracks=[])
    import dji_metadata_embedder.geo.panorender as pr
    monkeypatch.setattr(pr, "apply_view_thumbnails", lambda pts, root: 1)
    res = CliRunner().invoke(main, ["map", str(tmp_path)])
    assert res.exit_code == 0, res.output
    assert "Rendered 1 opening-view thumbnail" in res.output


def test_map_pano_thumbs_degrade_without_pillow(monkeypatch, tmp_path):
    pano = [PhotoPoint(lat=60.17, lon=24.95, alt=None, name="sphere.jpg",
                       is_pano=True, pano_yaw=45.0)]
    _mock_scans(monkeypatch, points=pano, tracks=[])
    import dji_metadata_embedder.geo.panorender as pr

    def unavailable(pts, root):
        raise pr.PanorenderUnavailable("Pillow is missing")

    monkeypatch.setattr(pr, "apply_view_thumbnails", unavailable)
    res = CliRunner().invoke(main, ["map", str(tmp_path)])
    assert res.exit_code == 0, res.output          # degradation, not an error
    assert (tmp_path / "map.html").exists()
