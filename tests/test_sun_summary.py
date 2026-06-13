"""Tests for summarize_sun (issue #216)."""

from datetime import timedelta

from dji_metadata_embedder.telemetry_converter import summarize_sun

_DAY_SRT = (
    "1\n00:00:00,000 --> 00:00:00,033\n"
    "<font size='36'>SrtCnt : 1, DiffTime : 33ms\n"
    "2024-01-01 12:00:00,000\n"
    "[latitude: 59.0] [longitude: 18.0] [rel_alt: 1.0 abs_alt: 100.0]</font>\n\n"
    "2\n00:00:00,033 --> 00:00:00,066\n"
    "<font size='36'>SrtCnt : 2, DiffTime : 33ms\n"
    "2024-01-01 12:00:33,000\n"
    "[latitude: 59.0] [longitude: 18.0] [rel_alt: 1.0 abs_alt: 100.0]</font>\n"
)


def test_summarize_sun_basic(tmp_path):
    srt = tmp_path / "clip.SRT"
    srt.write_text(_DAY_SRT)
    s = summarize_sun(srt, tz_offset=timedelta(hours=2))
    assert s["points"] == 2
    assert s["sun_computed"] == 2
    assert s["utc_start"] == "2024-01-01T10:00:00Z"
    assert abs(s["azimuth_start"] - 168.117) < 0.2
    assert abs(s["elevation_max"] - 7.291) < 0.3
    assert s["flags"] == []  # 7.3 deg: above horizon and above the 5 deg floor


def test_summarize_sun_night_flag(tmp_path):
    srt = tmp_path / "night.SRT"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:00,033\n"
        "<font size='36'>SrtCnt : 1\n2024-01-01 00:30:00,000\n"
        "[latitude: 59.0] [longitude: 18.0] [rel_alt: 1.0 abs_alt: 100.0]</font>\n"
    )
    s = summarize_sun(srt, tz_offset=timedelta(hours=1))
    assert s["sun_computed"] == 1
    assert s["elevation_max"] < 0
    assert s["flags"] == ["night"]


def test_summarize_sun_very_low_sun_flag(tmp_path):
    srt = tmp_path / "lowsun.SRT"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:00,033\n"
        "<font size='36'>SrtCnt : 1\n2024-12-21 12:00:00,000\n"
        "[latitude: 63.0] [longitude: 18.0] [rel_alt: 1.0 abs_alt: 100.0]</font>\n"
    )
    s = summarize_sun(srt, tz_offset=timedelta(hours=1))
    assert s["sun_computed"] == 1
    assert 0 < s["elevation_max"] < 5
    assert s["flags"] == ["very_low_sun"]


def test_summarize_sun_not_computable(tmp_path):
    srt = tmp_path / "nodt.SRT"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:00,033\n"
        "[latitude: 59.0] [longitude: 18.0] [rel_alt: 1.0 abs_alt: 100.0]\n"
    )
    s = summarize_sun(srt)
    assert s["sun_computed"] == 0
    assert s["flags"] == ["sun_not_computable"]
    assert s["elevation_max"] is None


def test_summarize_sun_skips_no_fix_frames(tmp_path):
    # First block is a pre-GPS-lock (0,0) frame; only the real fix counts.
    srt = tmp_path / "withnofix.SRT"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:00,033\n"
        "<font size='36'>SrtCnt : 1\n2024-01-01 12:00:00,000\n"
        "[latitude: 0.0] [longitude: 0.0] [rel_alt: 0.0 abs_alt: 0.0]</font>\n\n"
        "2\n00:00:00,033 --> 00:00:00,066\n"
        "<font size='36'>SrtCnt : 2\n2024-01-01 12:00:33,000\n"
        "[latitude: 59.0] [longitude: 18.0] [rel_alt: 1.0 abs_alt: 100.0]</font>\n"
    )
    s = summarize_sun(srt, tz_offset=timedelta(hours=2))
    assert s["points"] == 2          # both GPS-bearing lines parsed
    assert s["sun_computed"] == 1    # only the genuine fix gets a sun angle
