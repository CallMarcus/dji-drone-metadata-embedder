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


def _read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(_csv.DictReader(f))


def test_csv_drop_blanks_gps_and_sun_but_keeps_rows(tmp_path):
    out = extract_telemetry_to_csv(_write_srt(tmp_path), tmp_path / "f.csv", redact="drop")
    rows = _read_csv(out)
    assert len(rows) == 2  # rows kept — camera log still shareable
    for row in rows:
        assert row["latitude"] == ""
        assert row["longitude"] == ""
        assert row["sun_azimuth"] == ""
        assert row["sun_elevation"] == ""
        # non-location telemetry intact
        assert row["iso"] == "100"
        assert row["rel_altitude"] != ""
        assert row["timestamp"] != ""


def test_csv_fuzz_coarsens_gps(tmp_path):
    out = extract_telemetry_to_csv(_write_srt(tmp_path), tmp_path / "f.csv", redact="fuzz")
    rows = _read_csv(out)
    assert rows[0]["latitude"] == "39.123"
    assert rows[0]["longitude"] == "116.654"
    assert rows[1]["latitude"] == "39.124"  # 39.123789 rounds up


def test_csv_none_unchanged(tmp_path):
    out = extract_telemetry_to_csv(_write_srt(tmp_path), tmp_path / "f.csv")
    rows = _read_csv(out)
    assert rows[0]["latitude"] == "39.123456"
    assert rows[1]["longitude"] == "116.654987"


# Fixture WITH an absolute datetime (regex needs milliseconds) so the
# datetime_utc / sun-column policy under redaction is actually exercised.
TRACK_SRT_DT = (
    "1\n00:00:00,000 --> 00:00:00,033\n"
    "2026-07-01 12:00:00.000 [latitude: 39.123456] [longitude: 116.654321] "
    "[rel_alt: 1.5 abs_alt: 100.0]\n"
)


def test_csv_drop_keeps_datetime_but_blanks_sun(tmp_path):
    srt = tmp_path / "g.SRT"
    srt.write_text(TRACK_SRT_DT, encoding="utf-8")
    out = extract_telemetry_to_csv(srt, tmp_path / "g.csv", redact="drop")
    row = _read_csv(out)[0]
    assert row["datetime_utc"] != ""  # timestamps reveal when, not where
    assert row["sun_azimuth"] == "" and row["sun_elevation"] == ""


def test_csv_fuzz_sun_computed_from_fuzzed_coords(tmp_path):
    from datetime import datetime

    from dji_metadata_embedder.geo.solar import sun_position

    srt = tmp_path / "g.SRT"
    srt.write_text(TRACK_SRT_DT, encoding="utf-8")
    fuzzed = _read_csv(extract_telemetry_to_csv(srt, tmp_path / "fz.csv", redact="fuzz"))[0]
    raw = _read_csv(extract_telemetry_to_csv(srt, tmp_path / "raw.csv"))[0]
    assert fuzzed["sun_azimuth"] != ""
    # Angles must match the FUZZED position, not the raw one.
    utc = datetime.strptime(raw["datetime_utc"], "%Y-%m-%dT%H:%M:%SZ")
    az, el = sun_position(39.123, 116.654, utc)
    assert fuzzed["sun_azimuth"] == f"{az:.3f}"
    assert fuzzed["sun_elevation"] == f"{el:.3f}"


def test_csv_from_mp4_honours_redact(tmp_path, monkeypatch):
    """MP4 input previously bypassed --redact entirely (#248)."""
    from datetime import datetime

    from dji_metadata_embedder import telemetry_converter as tc
    from dji_metadata_embedder.utilities import TelemetrySample

    samples = [
        TelemetrySample(
            39.123456, 116.654321, 100.0, "00:00:00,000",
            datetime(2026, 7, 1, 4, 0, 0),
        )
    ]
    monkeypatch.setattr("dji_metadata_embedder.utilities.load_samples", lambda p: samples)

    video = tmp_path / "DJI_0001.MP4"
    video.write_bytes(b"\x00")

    drop = _read_csv(tc.extract_telemetry_to_csv(video, tmp_path / "d.csv", redact="drop"))[0]
    assert drop["latitude"] == "" and drop["longitude"] == ""
    assert drop["sun_azimuth"] == "" and drop["sun_elevation"] == ""
    assert drop["datetime_utc"] != ""
    assert drop["abs_altitude"] != ""

    fuzz = _read_csv(tc.extract_telemetry_to_csv(video, tmp_path / "z.csv", redact="fuzz"))[0]
    assert fuzz["latitude"] == "39.123"
    assert fuzz["longitude"] == "116.654"
    assert fuzz["sun_azimuth"] != ""
