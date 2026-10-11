"""One playback/real factor per clip. Verified on a real Air 3S 8x clip
(2026-10-11): SRT datetimes stall in a ~33 Hz staircase under 240 Hz
blocks; djmd GPSDateTime is CreateDate + SampleTime (playback time); djmd
TimeStamp is the real clock. These series reproduce those shapes."""

from datetime import datetime, timedelta

import pytest

from dji_metadata_embedder.geo.slowmo import slowmo_factor
from dji_metadata_embedder.utilities import TelemetrySample

BASE = datetime(2026, 8, 15, 14, 19, 32)


def _cue(sec):
    ms = round(sec * 1000)
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _sample(cue_s, dt=None, real_s=None):
    return TelemetrySample(10.0, 20.0, 100.0, _cue(cue_s), dt, real_s=real_s)


def _staircase_srt(seconds_real=20.0, factor=8, fps=30.0, clock_hz=33.0):
    n = int(seconds_real * factor * fps)
    out = []
    for i in range(n):
        cue = i / fps
        stepped = int(cue / factor * clock_hz) / clock_hz
        out.append(_sample(cue, dt=BASE + timedelta(seconds=stepped)))
    return out


def test_srt_datetime_staircase_gives_eight():
    r = slowmo_factor(_staircase_srt(), use_datetimes=True)
    assert (r.factor, r.source, r.in_range, r.is_slowmo) == (
        8.0,
        "datetime",
        True,
        True,
    )


def test_djmd_timestamp_gives_eight_despite_playback_datetimes():
    samples = [
        _sample(i / 30, dt=BASE + timedelta(seconds=i / 30), real_s=44.0 + i / 30 / 8)
        for i in range(4800)
    ]
    r = slowmo_factor(samples, use_datetimes=False)
    assert (r.factor, r.source) == (8.0, "timestamp")


def test_djmd_without_timestamp_is_unknown_not_one_x():
    samples = [_sample(i / 30, dt=BASE + timedelta(seconds=i / 30)) for i in range(900)]
    r = slowmo_factor(samples, use_datetimes=False)
    assert (r.factor, r.source, r.in_range) == (1.0, "none", True)


def test_normal_speed_srt_is_one():
    samples = [_sample(i / 30, dt=BASE + timedelta(seconds=i / 30)) for i in range(900)]
    r = slowmo_factor(samples, use_datetimes=True)
    assert (r.factor, r.source, r.is_slowmo) == (1.0, "datetime", False)


def test_short_real_span_is_unknown():
    samples = [_sample(i / 30, dt=BASE + timedelta(seconds=i / 30)) for i in range(30)]
    assert slowmo_factor(samples, use_datetimes=True).source == "none"


def test_non_dji_ratio_is_kept_as_measured():
    samples = [_sample(i / 30, dt=BASE + timedelta(seconds=i / 90)) for i in range(900)]
    # Cues carry milliseconds and datetimes microseconds: not exactly 3.
    assert slowmo_factor(samples, use_datetimes=True).factor == pytest.approx(
        3.0, rel=1e-3
    )


def test_out_of_range_factor_is_flagged():
    samples = [
        _sample(i / 30, dt=BASE + timedelta(seconds=i / 900)) for i in range(2700)
    ]
    r = slowmo_factor(samples, use_datetimes=True)
    assert r.factor == pytest.approx(30.0, rel=1e-3) and not r.in_range


def test_fewer_than_two_samples():
    assert slowmo_factor([_sample(0.0, dt=BASE)], use_datetimes=True).source == "none"
