"""Golden-fixture tests for the Avata 360 and Mini 5 Pro sample submissions.

Both models emit the HTML-wrapped bracket telemetry format. These tests pin
the parser, telemetry-point extraction, and format detection against the
trimmed ``clip.SRT`` fixtures shipped under ``samples/``. They also lock the
decimal-aperture fix (``[fnum: 1.9]``) on real data — see
``test_parsing.test_parse_bracket_decimal_fnum`` for the focused regression.
"""

from pathlib import Path

import pytest

from dji_metadata_embedder import DJIMetadataEmbedder
from dji_metadata_embedder.core.validator import validate_srt_format
from dji_metadata_embedder.utilities import parse_telemetry_points

SAMPLES = Path(__file__).resolve().parents[1] / "samples"


@pytest.mark.parametrize(
    "model, first_gps, abs_alt, fnum, focal_len",
    [
        ("Avata360", (53.365080, 6.460739), -124.744, "1.9", "28.00"),
        ("Mini5PRO", (53.365108, 6.460719), -122.769, "1.8", "24.00"),
    ],
)
def test_new_model_clip_parses(
    tmp_path, model, first_gps, abs_alt, fnum, focal_len
):
    srt = SAMPLES / model / "clip.SRT"
    embedder = DJIMetadataEmbedder(tmp_path)
    t = embedder.parse_dji_srt(srt)

    assert len(t["gps_coords"]) == 5
    assert t["first_gps"] == first_gps
    assert t["max_altitude"] == abs_alt
    # Decimal aperture must survive parsing (was dropped before the fix).
    assert t["camera_settings"]["fnum"] == fnum
    assert t["camera_settings"]["focal_len"] == focal_len
    assert t["camera_settings"]["color_md"] == "dlog_m"


@pytest.mark.parametrize("model", ["Avata360", "Mini5PRO"])
def test_new_model_telemetry_points(model):
    srt = SAMPLES / model / "clip.SRT"
    points = parse_telemetry_points(srt)
    assert len(points) == 5
    # Each point is (lat, lon, abs_alt, timestamp).
    assert all(len(p) == 4 for p in points)


@pytest.mark.parametrize("model", ["Avata360", "Mini5PRO"])
def test_new_model_format_detected_html_extended(model):
    srt = SAMPLES / model / "clip.SRT"
    validation = validate_srt_format(srt, lenient=True)
    assert validation["valid"]
    assert validation["format_detected"] == "html_extended"
    assert validation["telemetry_points"] == 5
