from datetime import datetime
from pathlib import Path

from dji_metadata_embedder.utilities import (
    parse_telemetry_samples,
    parse_telemetry_points,
)

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
CLIP = SAMPLES / "air3S" / "clip.SRT"

# Bracket format WITHOUT an absolute datetime line.
NODT_SRT = (
    "1\n00:00:00,000 --> 00:00:01,000\n"
    '<font size="28">[latitude: 10.0] [longitude: 20.0] '
    "[rel_alt: 0.000 abs_alt: 5.0]</font>\n\n"
    "2\n00:00:01,000 --> 00:00:02,000\n"
    '<font size="28">[latitude: 11.0] [longitude: 21.0] '
    "[rel_alt: 0.000 abs_alt: 6.0]</font>\n"
)


def test_samples_extract_absolute_datetime():
    samples = parse_telemetry_samples(CLIP)
    assert len(samples) == 5
    s = samples[0]
    assert (s.lat, s.lon, s.alt) == (34.270373, -84.176160, 302.208)
    assert s.cue == "00:00:00,000"
    # clip.SRT carries "2026-05-17 08:28:30.219" on its own line.
    assert s.dt == datetime(2026, 5, 17, 8, 28, 30, 219000)


def test_samples_datetime_none_when_absent(tmp_path):
    srt = tmp_path / "nodt.SRT"
    srt.write_text(NODT_SRT, encoding="utf-8")
    samples = parse_telemetry_samples(srt)
    assert len(samples) == 2
    assert all(s.dt is None for s in samples)


def test_parse_telemetry_points_is_unchanged_wrapper():
    # The legacy 4-tuple API must be byte-for-byte the same as before.
    pts = parse_telemetry_points(CLIP)
    assert pts == [
        (34.270373, -84.176160, 302.208, "00:00:00,000"),
        (34.270373, -84.176160, 302.208, "00:00:00,016"),
        (34.270373, -84.176160, 302.208, "00:00:00,032"),
        (34.270373, -84.176160, 302.208, "00:00:00,049"),
        (34.270373, -84.176160, 302.208, "00:00:00,066"),
    ]
