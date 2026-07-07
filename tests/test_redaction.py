import csv as _csv
from pathlib import Path

from dji_metadata_embedder.telemetry_converter import (
    extract_telemetry_to_csv,
    extract_telemetry_to_gpx,
)
from dji_metadata_embedder.utilities import apply_redaction


def test_redact_drop():
    telemetry = {
        "gps_coords": [(59.123456, 18.654321)],
        "first_gps": (59.123456, 18.654321),
        "avg_gps": (59.123456, 18.654321),
    }
    apply_redaction(telemetry, "drop")
    assert telemetry["gps_coords"] == []
    assert telemetry["first_gps"] is None
    assert telemetry["avg_gps"] is None


def test_redact_fuzz():
    telemetry = {
        "gps_coords": [(59.123456, 18.654321)],
        "first_gps": (59.123456, 18.654321),
        "avg_gps": (59.123456, 18.654321),
    }
    apply_redaction(telemetry, "fuzz")
    assert telemetry["gps_coords"] == [(59.123, 18.654)]
    assert telemetry["first_gps"] == (59.123, 18.654)
    assert telemetry["avg_gps"] == (59.123, 18.654)


# ---------------------------------------------------------------------------
# Track redaction in the gpx/csv exporters (#248). Fixture style mirrors
# tests/test_home_point.py.

TRACK_SRT = (
    "1\n00:00:00,000 --> 00:00:00,033\n"
    "HOME(39.906206,116.391400) [latitude: 39.123456] [longitude: 116.654321] "
    "[rel_alt: 1.5 abs_alt: 100.0] [iso : 100] [shutter : 1/1000]\n\n"
    "2\n00:00:00,033 --> 00:00:00,066\n"
    "HOME(39.906206,116.391400) [latitude: 39.123789] [longitude: 116.654987] "
    "[rel_alt: 1.6 abs_alt: 101.0] [iso : 100] [shutter : 1/1000]\n"
)


def _write_srt(tmp_path: Path) -> Path:
    srt = tmp_path / "f.SRT"
    srt.write_text(TRACK_SRT, encoding="utf-8")
    return srt


def test_gpx_drop_writes_no_trackpoints(tmp_path):
    out = extract_telemetry_to_gpx(_write_srt(tmp_path), tmp_path / "f.gpx", redact="drop")
    text = out.read_text(encoding="utf-8")
    assert "<trkpt" not in text
    assert "<trkseg>" in text  # still valid GPX structure


def test_gpx_fuzz_coarsens_trackpoints(tmp_path):
    out = extract_telemetry_to_gpx(_write_srt(tmp_path), tmp_path / "f.gpx", redact="fuzz")
    text = out.read_text(encoding="utf-8")
    assert '<trkpt lat="39.123" lon="116.654">' in text
    assert "39.123456" not in text
    assert "116.654987" not in text


def test_gpx_none_unchanged(tmp_path):
    out = extract_telemetry_to_gpx(_write_srt(tmp_path), tmp_path / "f.gpx")
    text = out.read_text(encoding="utf-8")
    assert '<trkpt lat="39.123456" lon="116.654321">' in text
    assert '<trkpt lat="39.123789" lon="116.654987">' in text
