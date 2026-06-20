import json
import xml.etree.ElementTree as ET
from pathlib import Path

from click.testing import CliRunner

from dji_metadata_embedder.cli import main

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
CLIP = SAMPLES / "air3S" / "clip.SRT"


def test_convert_geojson_cli(tmp_path):
    out = tmp_path / "clip.geojson"
    runner = CliRunner()
    result = runner.invoke(main, ["convert", "geojson", str(CLIP), "-o", str(out)])
    assert result.exit_code == 0, result.output
    data = json.loads(out.read_text())
    assert data["type"] == "FeatureCollection"


def test_convert_kml_cli(tmp_path):
    out = tmp_path / "clip.kml"
    runner = CliRunner()
    result = runner.invoke(main, ["convert", "kml", str(CLIP), "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert "<kml" in out.read_text()


def test_convert_html_cli(tmp_path):
    out = tmp_path / "clip.html"
    runner = CliRunner()
    result = runner.invoke(main, ["convert", "html", str(CLIP), "-o", str(out)])
    assert result.exit_code == 0, result.output
    text = out.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in text
    assert "leaflet@1.9.4" in text


def test_convert_html_redact_drop_still_valid(tmp_path):
    out = tmp_path / "clip.html"
    runner = CliRunner()
    result = runner.invoke(
        main, ["convert", "html", str(CLIP), "-o", str(out), "--redact", "drop"]
    )
    assert result.exit_code == 0, result.output
    assert "<!DOCTYPE html>" in out.read_text(encoding="utf-8")


def test_convert_geojson_redact_drop_empties_track(tmp_path):
    out = tmp_path / "clip.geojson"
    runner = CliRunner()
    result = runner.invoke(
        main, ["convert", "geojson", str(CLIP), "-o", str(out), "--redact", "drop"]
    )
    assert result.exit_code == 0, result.output
    data = json.loads(out.read_text())
    # Drop leaves a single null-geometry feature (no valid LineString is
    # possible without coordinates) and no Point features.
    assert len(data["features"]) == 1
    assert data["features"][0]["geometry"] is None
    assert all(f["geometry"] is None for f in data["features"])


def test_convert_cot_cli(tmp_path):
    out = tmp_path / "clip.cot.xml"
    runner = CliRunner()
    result = runner.invoke(main, ["convert", "cot", str(CLIP), "-o", str(out)])
    assert result.exit_code == 0, result.output
    root = ET.fromstring(out.read_text(encoding="utf-8"))
    assert root.tag == "events"
    assert any(e.get("type") == "a-n-A" for e in root)


def test_convert_cot_type_override_cli(tmp_path):
    out = tmp_path / "clip.cot.xml"
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["convert", "cot", str(CLIP), "-o", str(out), "--cot-type", "a-f-A-M-H-Q"],
    )
    assert result.exit_code == 0, result.output
    root = ET.fromstring(out.read_text(encoding="utf-8"))
    assert any(e.get("type") == "a-f-A-M-H-Q" for e in root)


def test_convert_cot_redact_drop_empties_events(tmp_path):
    out = tmp_path / "clip.cot.xml"
    runner = CliRunner()
    result = runner.invoke(
        main, ["convert", "cot", str(CLIP), "-o", str(out), "--redact", "drop"]
    )
    assert result.exit_code == 0, result.output
    root = ET.fromstring(out.read_text(encoding="utf-8"))
    assert len(root) == 0


AIR3 = SAMPLES / "air3" / "clip.SRT"


def test_convert_geojson_footprint_cli(tmp_path):
    out = tmp_path / "clip.geojson"
    runner = CliRunner()
    result = runner.invoke(
        main, ["convert", "geojson", str(AIR3), "-o", str(out), "--footprint",
                "--footprint-interval", "0"]
    )
    assert result.exit_code == 0, result.output
    data = json.loads(out.read_text())
    polys = [f for f in data["features"]
             if f["geometry"] and f["geometry"]["type"] == "Polygon"]
    assert polys and polys[0]["properties"]["kind"] == "footprint"


def test_convert_kml_footprint_cli(tmp_path):
    out = tmp_path / "clip.kml"
    runner = CliRunner()
    result = runner.invoke(
        main, ["convert", "kml", str(AIR3), "-o", str(out), "--footprint"]
    )
    assert result.exit_code == 0, result.output
    assert "Camera footprints" in out.read_text()


def test_convert_geojson_footprint_suppressed_by_redaction(tmp_path):
    out = tmp_path / "clip.geojson"
    runner = CliRunner()
    result = runner.invoke(
        main, ["convert", "geojson", str(AIR3), "-o", str(out),
                "--footprint", "--redact", "fuzz"]
    )
    assert result.exit_code == 0, result.output
    data = json.loads(out.read_text())
    assert not [f for f in data["features"]
                if f["geometry"] and f["geometry"]["type"] == "Polygon"]
