"""End-to-end ExifTool extraction. Skipped unless a recent ExifTool and a local
DJI MP4 fixture are both available (never runs in CI).

Run locally with, e.g.:
    DJIEMBED_EXIFTOOL_PATH=~/.local/dji-tools/Image-ExifTool-13.55/exiftool \\
    DJI_MP4_FIXTURE=/path/to/air3s.mp4 uv run pytest tests/test_mp4_telemetry_integration.py -v
"""

import os
from pathlib import Path

import pytest

from dji_metadata_embedder import mp4_telemetry as mt

_FIXTURE = os.environ.get("DJI_MP4_FIXTURE")


def _exiftool_ok() -> bool:
    try:
        ver = mt.exiftool_version()
    except Exception:
        return False
    if not ver:
        return False
    try:
        major, minor = (int(x) for x in ver.split(".")[:2])
    except ValueError:
        return False
    return (major, minor) >= (13, 39)


pytestmark = pytest.mark.skipif(
    not (_FIXTURE and Path(_FIXTURE).is_file() and _exiftool_ok()),
    reason="needs DJI_MP4_FIXTURE and ExifTool >= 13.39",
)


def test_extract_real_mp4():
    samples = mt.extract_samples(Path(_FIXTURE))
    assert samples, "expected a non-empty track from the real MP4"
    s = samples[0]
    assert -90 <= s.lat <= 90 and -180 <= s.lon <= 180
    assert s.dt is not None  # GPSDateTime present


def test_probe_real_mp4():
    assert mt.probe(Path(_FIXTURE)) is not None
