"""CLI smoke tests for dji-embed verify-sun (issue #216)."""

import json
from pathlib import Path

from click.testing import CliRunner

from dji_metadata_embedder.cli import main

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
CLIP = SAMPLES / "air3S" / "clip.SRT"


def test_verify_sun_json():
    runner = CliRunner()
    result = runner.invoke(
        main, ["verify-sun", str(CLIP), "--tz-offset", "0", "--format", "json", "-q"]
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["sun_computed"] > 0
    assert "flags" in data
    assert isinstance(data["elevation_max"], float)


def test_verify_sun_text():
    runner = CliRunner()
    result = runner.invoke(main, ["verify-sun", str(CLIP), "--tz-offset", "0"])
    assert result.exit_code == 0, result.output
    assert "Sun elevation" in result.output


def test_verify_sun_no_datetime(tmp_path):
    srt = tmp_path / "nodt.SRT"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:00,033\n"
        "[latitude: 59.0] [longitude: 18.0] [rel_alt: 1.0 abs_alt: 100.0]\n"
    )
    runner = CliRunner()
    result = runner.invoke(main, ["verify-sun", str(srt), "--format", "json", "-q"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["flags"] == ["sun_not_computable"]
