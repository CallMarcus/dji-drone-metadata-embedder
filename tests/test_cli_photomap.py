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
    assert [p.name for p in points] == ["church1.jpg", "church2.jpg", "pano.jpg"]
    assert skipped == ["no_gps.jpg"]
    by_name = {p.name: p for p in points}
    assert by_name["pano.jpg"].is_pano is True
    assert by_name["church1.jpg"].is_pano is False
    assert points[0].lat == pytest.approx(60.170278)
    assert points[0].thumbnail_b64  # embedded EXIF thumbnail extracted
    assert points[0].timestamp == "2026-06-15 12:30:45"


@needs_exiftool
def test_photomap_cli_end_to_end(tmp_path):
    for jpg in SAMPLES_PHOTOS.glob("*.jpg"):
        shutil.copy(jpg, tmp_path / jpg.name)
    res = CliRunner().invoke(
        main, ["photomap", str(tmp_path), "-f", "all", "--link-originals"]
    )
    assert res.exit_code == 0, res.output
    assert (tmp_path / "photomap.html").exists()
    assert (tmp_path / "photomap.kml").exists()
    assert (tmp_path / "photomap.geojson").exists()
    html = (tmp_path / "photomap.html").read_text(encoding="utf-8")
    assert '"thumb"' in html  # thumbnail data present in the embedded GeoJSON
    assert "pannellum@" in html  # pano.jpg triggers the 360 viewer assets


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
    # Recursive scans carry the subdirectory so per-session archives don't
    # collide on DJI's restarting basenames.
    assert [p.name for p in points] == [
        "sub/church1.jpg", "sub/church2.jpg", "sub/pano.jpg"
    ]


def _html_link_props(path: Path) -> list[str | None]:
    text = path.read_text(encoding="utf-8")
    start = text.index('id="photo-data">') + len('id="photo-data">')
    data = json.loads(text[start:text.index("</script>", start)])
    return [f["properties"].get("link") for f in data["features"]]


def test_photomap_links_are_opt_in(monkeypatch, tmp_path):
    _mock_scan(monkeypatch)
    res = CliRunner().invoke(main, ["photomap", str(tmp_path)])
    assert res.exit_code == 0, res.output
    assert _html_link_props(tmp_path / "photomap.html") == [None]


def test_photomap_link_originals_adds_links_to_html_only(monkeypatch, tmp_path):
    _mock_scan(monkeypatch)
    res = CliRunner().invoke(
        main, ["photomap", str(tmp_path), "-f", "all", "--link-originals"]
    )
    assert res.exit_code == 0, res.output
    assert _html_link_props(tmp_path / "photomap.html") == ["church1.jpg"]
    # KML and GeoJSON stay link-free (issue #253: HTML only).
    geo = json.loads((tmp_path / "photomap.geojson").read_text(encoding="utf-8"))
    assert all("link" not in f["properties"] for f in geo["features"])
    assert "church1.jpg</a>" not in (tmp_path / "photomap.kml").read_text(
        encoding="utf-8"
    )


def test_photomap_link_base_prefixes_hrefs(monkeypatch, tmp_path):
    _mock_scan(monkeypatch)
    res = CliRunner().invoke(
        main,
        ["photomap", str(tmp_path), "--link-originals", "--link-base", "../DCIM"],
    )
    assert res.exit_code == 0, res.output
    assert _html_link_props(tmp_path / "photomap.html") == ["../DCIM/church1.jpg"]


def test_photomap_link_base_without_link_originals_errors(monkeypatch, tmp_path):
    _mock_scan(monkeypatch)
    res = CliRunner().invoke(
        main, ["photomap", str(tmp_path), "--link-base", "photos/"]
    )
    assert res.exit_code != 0
    assert "--link-base requires --link-originals" in res.output
    assert not (tmp_path / "photomap.html").exists()


def test_photomap_link_originals_without_html_output_warns(monkeypatch, tmp_path):
    _mock_scan(monkeypatch)
    res = CliRunner().invoke(
        main, ["photomap", str(tmp_path), "-f", "kml", "--link-originals"]
    )
    assert res.exit_code == 0, res.output
    assert "only affects HTML output" in res.output


def test_photomap_redact_fuzz_coarsens_all_formats(monkeypatch, tmp_path):
    _mock_scan(monkeypatch)
    res = CliRunner().invoke(
        main, ["photomap", str(tmp_path), "-f", "all", "--redact", "fuzz"]
    )
    assert res.exit_code == 0, res.output
    geo = json.loads((tmp_path / "photomap.geojson").read_text(encoding="utf-8"))
    assert geo["features"][0]["geometry"]["coordinates"][:2] == [24.952, 60.17]
    assert "60.170278" not in (tmp_path / "photomap.kml").read_text(encoding="utf-8")
    assert "60.170278" not in (tmp_path / "photomap.html").read_text(encoding="utf-8")


def test_photomap_redact_fuzz_with_links_warns_about_exif(monkeypatch, tmp_path):
    _mock_scan(monkeypatch)
    res = CliRunner().invoke(
        main,
        ["photomap", str(tmp_path), "--redact", "fuzz", "--link-originals"],
    )
    assert res.exit_code == 0, res.output
    assert "exact GPS" in res.output


def test_photomap_redact_default_none_keeps_exact_coords(monkeypatch, tmp_path):
    _mock_scan(monkeypatch)
    res = CliRunner().invoke(main, ["photomap", str(tmp_path)])
    assert res.exit_code == 0, res.output
    html = (tmp_path / "photomap.html").read_text(encoding="utf-8")
    assert "60.170278" in html


def _mock_serve(monkeypatch):
    calls = {}

    def fake(directory, filename, **kwargs):
        calls["directory"] = Path(directory)
        calls["filename"] = filename
        calls["kwargs"] = kwargs

    monkeypatch.setattr("dji_metadata_embedder.cli.serve_directory", fake)
    return calls


def test_photomap_serve_implies_links_and_serves_html_folder(monkeypatch, tmp_path):
    _mock_scan(monkeypatch)
    calls = _mock_serve(monkeypatch)
    res = CliRunner().invoke(main, ["photomap", str(tmp_path), "--serve"])
    assert res.exit_code == 0, res.output
    assert _html_link_props(tmp_path / "photomap.html") == ["church1.jpg"]
    assert calls["directory"] == tmp_path
    assert calls["filename"] == "photomap.html"
    assert calls["kwargs"]["quiet"] is False
    assert calls["kwargs"]["log_requests"] is False


def test_photomap_serve_requires_html_format(monkeypatch, tmp_path):
    _mock_scan(monkeypatch)
    calls = _mock_serve(monkeypatch)
    res = CliRunner().invoke(main, ["photomap", str(tmp_path), "--serve", "-f", "kml"])
    assert res.exit_code != 0
    assert "--serve requires the HTML map" in res.output
    assert calls == {}


def test_photomap_serve_format_all_serves_the_html_output(monkeypatch, tmp_path):
    _mock_scan(monkeypatch)
    calls = _mock_serve(monkeypatch)
    res = CliRunner().invoke(main, ["photomap", str(tmp_path), "--serve", "-f", "all"])
    assert res.exit_code == 0, res.output
    assert calls["filename"] == "photomap.html"


def test_photomap_serve_with_link_base_warns(monkeypatch, tmp_path):
    _mock_scan(monkeypatch)
    _mock_serve(monkeypatch)
    res = CliRunner().invoke(
        main,
        ["photomap", str(tmp_path), "--serve", "--link-base", "https://example.com/p/"],
    )
    assert res.exit_code == 0, res.output
    assert "--link-base" in res.output and "may not resolve" in res.output


def test_photomap_serve_verbose_enables_request_logging(monkeypatch, tmp_path):
    _mock_scan(monkeypatch)
    calls = _mock_serve(monkeypatch)
    res = CliRunner().invoke(main, ["photomap", str(tmp_path), "--serve", "-v"])
    assert res.exit_code == 0, res.output
    assert calls["kwargs"]["log_requests"] is True


def test_photomap_serve_with_redact_fuzz_still_warns_about_exif(monkeypatch, tmp_path):
    _mock_scan(monkeypatch)
    _mock_serve(monkeypatch)
    res = CliRunner().invoke(
        main, ["photomap", str(tmp_path), "--serve", "--redact", "fuzz"]
    )
    assert res.exit_code == 0, res.output
    assert "still carry exact GPS" in res.output


def test_photomap_no_serve_never_starts_server(monkeypatch, tmp_path):
    _mock_scan(monkeypatch)
    calls = _mock_serve(monkeypatch)
    res = CliRunner().invoke(main, ["photomap", str(tmp_path)])
    assert res.exit_code == 0, res.output
    assert calls == {}


# --popup-fields (issue #296): the user decides what a shared map discloses,
# without touching the original photos' EXIF.


def test_photomap_popup_fields_none_strips_details_from_html(monkeypatch, tmp_path):
    _mock_scan(monkeypatch)
    res = CliRunner().invoke(
        main, ["photomap", str(tmp_path), "--popup-fields", "none"])
    assert res.exit_code == 0, res.output
    text = (tmp_path / "photomap.html").read_text(encoding="utf-8")
    assert "church1.jpg" not in text   # filename stripped from embedded data
    assert "FC8482" not in text        # camera stripped
    assert "12:30:45" not in text      # timestamp stripped
    assert "/9j/THUMB1" in text        # the photo itself still shows


def test_photomap_popup_fields_selective_list(monkeypatch, tmp_path):
    _mock_scan(monkeypatch)
    res = CliRunner().invoke(
        main, ["photomap", str(tmp_path), "--popup-fields", "name,altitude"])
    assert res.exit_code == 0, res.output
    text = (tmp_path / "photomap.html").read_text(encoding="utf-8")
    assert "church1.jpg" in text
    assert "FC8482" not in text


def test_photomap_popup_fields_invalid_value_names_valid_fields(monkeypatch, tmp_path):
    _mock_scan(monkeypatch)
    res = CliRunner().invoke(
        main, ["photomap", str(tmp_path), "--popup-fields", "shutter"])
    assert res.exit_code == 2
    assert "shutter" in res.output
    for valid in ("name", "timestamp", "camera", "altitude"):
        assert valid in res.output


def test_photomap_popup_fields_without_html_output_warns(monkeypatch, tmp_path):
    _mock_scan(monkeypatch)
    res = CliRunner().invoke(
        main,
        ["photomap", str(tmp_path), "-f", "geojson", "--popup-fields", "none"])
    assert res.exit_code == 0, res.output
    assert "only affects HTML" in res.output


def test_photomap_tile_style_selects_basemap(monkeypatch, tmp_path):
    _mock_scan(monkeypatch)
    res = CliRunner().invoke(
        main, ["photomap", str(tmp_path), "--tile-style", "osm-hot"]
    )
    assert res.exit_code == 0, res.output
    text = (tmp_path / "photomap.html").read_text(encoding="utf-8")
    assert "tile.openstreetmap.fr/hot" in text
    assert "Humanitarian" in text
