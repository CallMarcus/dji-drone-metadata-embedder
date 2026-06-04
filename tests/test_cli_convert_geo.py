import json
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
