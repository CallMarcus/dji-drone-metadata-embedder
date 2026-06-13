"""Tests for sun/UTC columns in CSV export (issue #216)."""

import csv
from datetime import timedelta

from dji_metadata_embedder.telemetry_converter import extract_telemetry_to_csv

_DAY_SRT = (
    "1\n00:00:00,000 --> 00:00:00,033\n"
    "<font size='36'>SrtCnt : 1, DiffTime : 33ms\n"
    "2024-01-01 12:00:00,000\n"
    "[iso : 100] [latitude: 59.0] [longitude: 18.0] [rel_alt: 1.0 abs_alt: 100.0]</font>\n"
)


def _read(path):
    return list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))


def test_csv_has_sun_columns(tmp_path):
    srt = tmp_path / "clip.SRT"
    srt.write_text(_DAY_SRT)
    out = tmp_path / "clip.csv"
    extract_telemetry_to_csv(srt, out, tz_offset=timedelta(hours=2))
    rows = _read(out)
    assert rows[0]["datetime_utc"] == "2024-01-01T10:00:00Z"
    assert abs(float(rows[0]["sun_azimuth"]) - 168.117) < 0.2
    assert abs(float(rows[0]["sun_elevation"]) - 7.291) < 0.2
    # Existing columns intact.
    assert rows[0]["latitude"] == "59.0"
    assert rows[0]["iso"] == "100"


def test_csv_sun_blank_without_datetime(tmp_path):
    srt = tmp_path / "nodt.SRT"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:00,033\n"
        "[iso : 100] [latitude: 59.0] [longitude: 18.0] [rel_alt: 1.0 abs_alt: 100.0]\n"
    )
    out = tmp_path / "nodt.csv"
    extract_telemetry_to_csv(srt, out)
    rows = _read(out)
    assert rows[0]["datetime_utc"] == ""
    assert rows[0]["sun_azimuth"] == ""
    assert rows[0]["sun_elevation"] == ""
    assert rows[0]["latitude"] == "59.0"


def test_csv_sun_blank_for_no_fix_frame(tmp_path):
    # A (0,0) pre-lock frame keeps datetime_utc (time is valid) but no sun angles.
    srt = tmp_path / "withnofix.SRT"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:00,033\n"
        "<font size='36'>SrtCnt : 1\n2024-01-01 12:00:00,000\n"
        "[latitude: 0.0] [longitude: 0.0] [rel_alt: 0.0 abs_alt: 0.0]</font>\n\n"
        "2\n00:00:00,033 --> 00:00:00,066\n"
        "<font size='36'>SrtCnt : 2\n2024-01-01 12:00:33,000\n"
        "[latitude: 59.0] [longitude: 18.0] [rel_alt: 1.0 abs_alt: 100.0]</font>\n"
    )
    out = tmp_path / "withnofix.csv"
    extract_telemetry_to_csv(srt, out, tz_offset=timedelta(hours=2))
    rows = _read(out)
    # Row 0 = (0,0) no-fix: datetime resolved, but sun blank.
    assert rows[0]["datetime_utc"] == "2024-01-01T10:00:00Z"
    assert rows[0]["sun_azimuth"] == ""
    assert rows[0]["sun_elevation"] == ""
    # Row 1 = real fix: sun computed.
    assert rows[1]["sun_azimuth"] != ""
    assert rows[1]["sun_elevation"] != ""
