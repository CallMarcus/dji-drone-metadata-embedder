"""Golden-fixture tests for recent DJI model submissions.

Avata 360, Mini 5 Pro, Neo 2, and Air 3S all emit the HTML-wrapped bracket
telemetry format (FrameCnt + decimal aperture, ``html_extended`` family). These
tests pin the parser, telemetry-point extraction, and format detection against
the trimmed ``clip.SRT`` fixtures shipped under ``samples/``. They also lock the
decimal-aperture and FrameCnt fixes on real data — see ``test_parsing`` for the
focused regressions. Air 3S additionally pins ``color_md: hlg``, the first
fixture to exercise the HLG color mode.
"""

from pathlib import Path

import pytest

from dji_metadata_embedder import DJIMetadataEmbedder
from dji_metadata_embedder.core.validator import validate_srt_format
from dji_metadata_embedder.utilities import parse_telemetry_points

SAMPLES = Path(__file__).resolve().parents[1] / "samples"

# Models with on-disk golden clip.SRT fixtures.
MODELS = ["Avata360", "Mini5PRO", "neo2", "air3S"]


@pytest.mark.parametrize(
    "model, first_gps, abs_alt, fnum, focal_len, color_md",
    [
        # focal_len is None when the model's SRT omits the field (Neo 2).
        ("Avata360", (53.365080, 6.460739), -124.744, "1.9", "28.00", "dlog_m"),
        ("Mini5PRO", (53.365108, 6.460719), -122.769, "1.8", "24.00", "dlog_m"),
        ("neo2", (45.607181, 13.753860), 114.0, "2.2", None, "default"),
        # Air 3S: first fixture exercising the HLG color mode.
        ("air3S", (34.270373, -84.176160), 302.208, "1.8", "24.00", "hlg"),
    ],
)
def test_new_model_clip_parses(
    tmp_path, model, first_gps, abs_alt, fnum, focal_len, color_md
):
    srt = SAMPLES / model / "clip.SRT"
    t = DJIMetadataEmbedder(tmp_path).parse_dji_srt(srt)

    assert len(t["gps_coords"]) == 5
    assert t["first_gps"] == first_gps
    assert t["max_altitude"] == abs_alt
    # Decimal aperture must survive parsing (was dropped before v1.4.0).
    assert t["camera_settings"]["fnum"] == fnum
    assert t["camera_settings"]["color_md"] == color_md
    # FrameCnt counter must be captured, not recorded as None (issue #204).
    assert t["srt_counts"] == [1, 2, 3, 4, 5]
    if focal_len is None:
        assert "focal_len" not in t["camera_settings"]
    else:
        assert t["camera_settings"]["focal_len"] == focal_len


@pytest.mark.parametrize("model", MODELS)
def test_new_model_telemetry_points(model):
    srt = SAMPLES / model / "clip.SRT"
    points = parse_telemetry_points(srt)
    assert len(points) == 5
    # Each point is (lat, lon, abs_alt, timestamp).
    assert all(len(p) == 4 for p in points)


@pytest.mark.parametrize("model", MODELS)
def test_new_model_format_detected_html_extended(model):
    srt = SAMPLES / model / "clip.SRT"
    validation = validate_srt_format(srt, lenient=True)
    assert validation["valid"]
    assert validation["format_detected"] == "html_extended"
    assert validation["telemetry_points"] == 5
