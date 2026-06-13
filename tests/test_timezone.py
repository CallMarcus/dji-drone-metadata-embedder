"""Tests for SRT timezone auto-detection (issue #202).

DJI SRT wall-clock timestamps are local with no timezone; the file mtime is
UTC. ``estimate_utc_offset`` recovers the local offset by testing both
"mtime = recording start" and "mtime = recording end" hypotheses and keeping
whichever lands closest to a quarter-hour boundary.
"""

import os
from datetime import datetime, timedelta, timezone

import pytest

from dji_metadata_embedder.telemetry_converter import (
    estimate_utc_offset,
    extract_telemetry_to_gpx,
    parse_utc_offset,
)

_HTML_SRT = (
    "1\n00:00:00,000 --> 00:00:00,033\n"
    "<font size='36'>SrtCnt : 1, DiffTime : 33ms\n"
    "2024-01-01 12:00:00,000\n"
    "[latitude: 59.0] [longitude: 18.0] [rel_alt: 1.0 abs_alt: 100.0]</font>\n\n"
    "2\n00:00:00,033 --> 00:00:00,066\n"
    "<font size='36'>SrtCnt : 2, DiffTime : 33ms\n"
    "2024-01-01 12:00:33,000\n"
    "[latitude: 59.0] [longitude: 18.0] [rel_alt: 1.0 abs_alt: 100.0]</font>\n"
)


def test_whole_hour_offset_mtime_is_recording_end():
    """UTC+2, file written at recording end."""
    first = datetime(2024, 6, 1, 14, 0, 0)
    last = datetime(2024, 6, 1, 14, 10, 0)
    mtime_utc = datetime(2024, 6, 1, 12, 10, 0)  # last - 2h
    assert estimate_utc_offset(first, last, mtime_utc) == timedelta(hours=2)


def test_india_half_hour_offset_mtime_is_recording_start():
    """UTC+5:30 (India), file written at recording start."""
    first = datetime(2024, 6, 1, 10, 0, 0)
    last = datetime(2024, 6, 1, 10, 5, 0)
    mtime_utc = datetime(2024, 6, 1, 4, 30, 0)  # first - 5:30
    assert estimate_utc_offset(first, last, mtime_utc) == timedelta(hours=5, minutes=30)


def test_nepal_quarter_hour_offset_mtime_is_recording_end():
    """UTC+5:45 (Nepal), file written at recording end."""
    first = datetime(2024, 6, 1, 12, 0, 0)
    last = datetime(2024, 6, 1, 12, 20, 0)
    mtime_utc = datetime(2024, 6, 1, 6, 35, 0)  # last - 5:45
    assert estimate_utc_offset(first, last, mtime_utc) == timedelta(hours=5, minutes=45)


def test_negative_offset_us_pacific():
    """UTC-8 (US Pacific), file written at recording start."""
    first = datetime(2024, 6, 1, 9, 0, 0)
    last = datetime(2024, 6, 1, 9, 30, 0)
    mtime_utc = datetime(2024, 6, 1, 17, 0, 0)  # first + 8h
    assert estimate_utc_offset(first, last, mtime_utc) == timedelta(hours=-8)


def test_rounds_noisy_offset_to_nearest_quarter_hour():
    """A few seconds of mtime jitter must still resolve to a clean offset."""
    first = datetime(2024, 6, 1, 14, 0, 3)
    last = datetime(2024, 6, 1, 14, 10, 0)
    mtime_utc = datetime(2024, 6, 1, 12, 10, 0)  # last - ~2h, first off by 3s
    assert estimate_utc_offset(first, last, mtime_utc) == timedelta(hours=2)


@pytest.mark.parametrize(
    "value, expected",
    [
        ("auto", None),
        ("", None),
        (None, None),
        ("+05:30", timedelta(hours=5, minutes=30)),
        ("5:45", timedelta(hours=5, minutes=45)),
        ("-8", timedelta(hours=-8)),
        ("-5:30", timedelta(hours=-5, minutes=-30)),
        ("+0", timedelta(0)),
    ],
)
def test_parse_utc_offset(value, expected):
    assert parse_utc_offset(value) == expected


def test_parse_utc_offset_rejects_garbage():
    with pytest.raises(ValueError):
        parse_utc_offset("nonsense")


def test_gpx_uses_utc_time_with_explicit_offset(tmp_path):
    """An explicit tz offset converts local SRT time to UTC in the GPX."""
    srt = tmp_path / "clip.SRT"
    srt.write_text(_HTML_SRT)
    out = tmp_path / "clip.gpx"
    extract_telemetry_to_gpx(srt, out, tz_offset=timedelta(hours=2))
    text = out.read_text()
    # Local 12:00:00 at UTC+2 -> 10:00:00Z.
    assert "<time>2024-01-01T10:00:00Z</time>" in text
    assert "<time>2024-01-01T10:00:33Z</time>" in text
    # Metadata <time> is the first point's UTC, not datetime.now().
    assert "<time>2024-01-01T10:00:00Z</time>" in text.split("<trk>")[0]


def test_gpx_autodetects_offset_from_mtime(tmp_path):
    """With no explicit offset, the offset is recovered from the file mtime."""
    srt = tmp_path / "clip.SRT"
    srt.write_text(_HTML_SRT)
    # mtime = recording end in UTC for a UTC+2 local clock: 12:00:33 - 2h.
    mtime = datetime(2024, 1, 1, 10, 0, 33, tzinfo=timezone.utc).timestamp()
    os.utime(srt, (mtime, mtime))
    out = tmp_path / "clip.gpx"
    extract_telemetry_to_gpx(srt, out)
    text = out.read_text()
    assert "<time>2024-01-01T10:00:00Z</time>" in text


def test_gpx_falls_back_when_no_absolute_datetime(tmp_path):
    """Formats without a wall-clock datetime keep the cue timestamp (no crash)."""
    srt = tmp_path / "clip.SRT"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:00,033\n"
        "[latitude: 59.0] [longitude: 18.0] [rel_alt: 1.0 abs_alt: 100.0]\n"
    )
    out = tmp_path / "clip.gpx"
    extract_telemetry_to_gpx(srt, out)
    text = out.read_text()
    assert "<trkpt" in text
    assert "00:00:00,000" in text


def test_resolve_utc_offset_explicit_wins():
    from dji_metadata_embedder.telemetry_converter import resolve_utc_offset

    off = resolve_utc_offset(
        [datetime(2024, 1, 1, 12, 0, 0)],
        timedelta(hours=2),
        datetime(2024, 1, 1, 9, 0, 0),
    )
    assert off == timedelta(hours=2)


def test_resolve_utc_offset_none_without_abs_times():
    from dji_metadata_embedder.telemetry_converter import resolve_utc_offset

    assert resolve_utc_offset([], None, datetime(2024, 1, 1, 9, 0, 0)) is None


def test_resolve_utc_offset_autodetects_from_mtime():
    from dji_metadata_embedder.telemetry_converter import resolve_utc_offset

    # mtime = recording end in UTC for a UTC+2 local clock.
    off = resolve_utc_offset(
        [datetime(2024, 1, 1, 12, 0, 0), datetime(2024, 1, 1, 12, 0, 30)],
        None,
        datetime(2024, 1, 1, 10, 0, 30),
    )
    assert off == timedelta(hours=2)
