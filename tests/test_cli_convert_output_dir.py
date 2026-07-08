"""``convert ... -o <existing directory>`` writes ``<stem>.<ext>`` into it (#257).

``embed -o`` takes a directory, so users reasonably pass one to ``convert``
too; it must not crash with a raw ``IsADirectoryError`` traceback.
"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from dji_metadata_embedder.cli import main

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
CLIP = SAMPLES / "air3S" / "clip.SRT"


@pytest.mark.parametrize(
    "fmt, expected_name",
    [
        ("gpx", "clip.gpx"),
        ("csv", "clip.csv"),
        ("geojson", "clip.geojson"),
        ("kml", "clip.kml"),
        ("html", "clip.html"),
        ("cot", "clip.cot.xml"),
    ],
)
def test_convert_output_directory_writes_stem_file(tmp_path, fmt, expected_name):
    runner = CliRunner()
    result = runner.invoke(main, ["convert", fmt, str(CLIP), "-o", str(tmp_path)])
    assert result.exit_code == 0, result.output
    out = tmp_path / expected_name
    assert out.exists(), f"expected {out} to be created"
    assert out.stat().st_size > 0
