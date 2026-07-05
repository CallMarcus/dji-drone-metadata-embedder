import json
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from dji_metadata_embedder.cli import main
from dji_metadata_embedder.geo import photomap as pm
from dji_metadata_embedder.geo.photomap import PhotomapError

CANNED = [
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
        "ThumbnailImage": "base64:/9j/THUMB1",
    },
    {"SourceFile": "photos/no_gps.jpg"},
]


def _mock_scan(monkeypatch, data=CANNED):
    calls = {}

    def fake(directory, recursive):
        calls["directory"] = Path(directory)
        calls["recursive"] = recursive
        return data

    monkeypatch.setattr(pm, "_run_exiftool_scan", fake)
    return calls


def test_photomap_default_writes_html_into_directory(monkeypatch, tmp_path):
    calls = _mock_scan(monkeypatch)
    res = CliRunner().invoke(main, ["photomap", str(tmp_path)])
    assert res.exit_code == 0, res.output
    out = tmp_path / "photomap.html"
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "leaflet.markercluster@1.5.3" in text
    assert tmp_path.resolve().name in text  # default title = directory name
    assert "Mapped 1 of 2 photos" in res.output
    assert calls["recursive"] is False


def test_photomap_recursive_flag_passed_through(monkeypatch, tmp_path):
    calls = _mock_scan(monkeypatch)
    res = CliRunner().invoke(main, ["photomap", str(tmp_path), "-r"])
    assert res.exit_code == 0, res.output
    assert calls["recursive"] is True


def test_photomap_all_formats_share_base_name(monkeypatch, tmp_path):
    _mock_scan(monkeypatch)
    out_base = tmp_path / "churches.html"
    res = CliRunner().invoke(
        main, ["photomap", str(tmp_path), "-f", "all", "-o", str(out_base)]
    )
    assert res.exit_code == 0, res.output
    for suffix in (".html", ".kml", ".geojson"):
        assert out_base.with_suffix(suffix).exists(), suffix
    data = json.loads(out_base.with_suffix(".geojson").read_text(encoding="utf-8"))
    # The GeoJSON file must not carry thumbnails (HTML-only).
    assert all("thumb" not in f["properties"] for f in data["features"])


def test_photomap_kml_format_and_title(monkeypatch, tmp_path):
    _mock_scan(monkeypatch)
    res = CliRunner().invoke(
        main, ["photomap", str(tmp_path), "-f", "kml", "--title", "Kirkot"]
    )
    assert res.exit_code == 0, res.output
    text = (tmp_path / "photomap.kml").read_text(encoding="utf-8")
    assert "<kml" in text and "Kirkot" in text


def test_photomap_verbose_lists_skipped(monkeypatch, tmp_path):
    _mock_scan(monkeypatch)
    res = CliRunner().invoke(main, ["photomap", str(tmp_path), "-v"])
    assert res.exit_code == 0, res.output
    assert "no_gps.jpg" in res.output


def test_photomap_no_photos_is_clean_error(monkeypatch, tmp_path):
    _mock_scan(monkeypatch, data=[])
    res = CliRunner().invoke(main, ["photomap", str(tmp_path)])
    assert res.exit_code != 0
    assert "No photos" in res.output
    assert res.exception is None or isinstance(res.exception, SystemExit)


def test_photomap_no_gps_photos_is_clean_error(monkeypatch, tmp_path):
    _mock_scan(monkeypatch, data=[{"SourceFile": "a.jpg"}, {"SourceFile": "b.jpg"}])
    res = CliRunner().invoke(main, ["photomap", str(tmp_path)])
    assert res.exit_code != 0
    assert "GPS" in res.output


def test_photomap_single_format_output_honored_verbatim(monkeypatch, tmp_path):
    _mock_scan(monkeypatch)
    out = tmp_path / "report.json"
    res = CliRunner().invoke(
        main, ["photomap", str(tmp_path), "-f", "geojson", "-o", str(out)]
    )
    assert res.exit_code == 0, res.output
    assert out.exists()  # extension NOT rewritten
    assert not (tmp_path / "report.geojson").exists()


def test_photomap_write_failure_is_clean_error(monkeypatch, tmp_path):
    _mock_scan(monkeypatch)
    res = CliRunner().invoke(
        main,
        ["photomap", str(tmp_path), "-o", str(tmp_path / "no_such_dir" / "m.html")],
    )
    assert res.exit_code != 0
    assert "Could not write" in res.output
    assert res.exception is None or isinstance(res.exception, SystemExit)


def test_photomap_quiet_suppresses_stdout(monkeypatch, tmp_path):
    _mock_scan(monkeypatch)
    res = CliRunner().invoke(main, ["photomap", str(tmp_path), "-q"])
    assert res.exit_code == 0, res.output
    assert res.output.strip() == ""


def test_photomap_missing_exiftool_is_clean_error(monkeypatch, tmp_path):
    def raise_err(directory, recursive):
        raise PhotomapError("ExifTool not found ... dji-embed doctor")

    monkeypatch.setattr(pm, "_run_exiftool_scan", raise_err)
    res = CliRunner().invoke(main, ["photomap", str(tmp_path)])
    assert res.exit_code != 0
    assert not isinstance(res.exception, PhotomapError)  # no raw traceback
    assert "ExifTool" in res.output


SAMPLES_PHOTOS = Path(__file__).resolve().parents[1] / "samples" / "photos"

needs_exiftool = pytest.mark.skipif(
    shutil.which("exiftool") is None, reason="ExifTool not installed"
)


@needs_exiftool
def test_photomap_real_exiftool_scan():
    from dji_metadata_embedder.geo.photomap import scan_photos

    points, skipped = scan_photos(SAMPLES_PHOTOS)
    assert [p.name for p in points] == ["church1.jpg", "church2.jpg"]
    assert skipped == ["no_gps.jpg"]
    assert points[0].lat == pytest.approx(60.170278)
    assert points[0].thumbnail_b64  # embedded EXIF thumbnail extracted
    assert points[0].timestamp == "2026-06-15 12:30:45"


@needs_exiftool
def test_photomap_cli_end_to_end(tmp_path):
    for jpg in SAMPLES_PHOTOS.glob("*.jpg"):
        shutil.copy(jpg, tmp_path / jpg.name)
    res = CliRunner().invoke(main, ["photomap", str(tmp_path), "-f", "all"])
    assert res.exit_code == 0, res.output
    assert (tmp_path / "photomap.html").exists()
    assert (tmp_path / "photomap.kml").exists()
    assert (tmp_path / "photomap.geojson").exists()
    html = (tmp_path / "photomap.html").read_text(encoding="utf-8")
    assert '"thumb"' in html  # thumbnail data present in the embedded GeoJSON


@needs_exiftool
def test_photomap_recursive_real_scan(tmp_path):
    from dji_metadata_embedder.geo.photomap import scan_photos

    sub = tmp_path / "sub"
    sub.mkdir()
    for jpg in SAMPLES_PHOTOS.glob("*.jpg"):
        shutil.copy(jpg, sub / jpg.name)
    points, _ = scan_photos(tmp_path)
    assert points == []
    points, skipped = scan_photos(tmp_path, recursive=True)
    assert [p.name for p in points] == ["church1.jpg", "church2.jpg"]
