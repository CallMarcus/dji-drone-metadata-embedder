from itertools import pairwise

from dji_metadata_embedder.geo.motion import (
    build_motion,
    decimal_quantum,
    unwrap_degrees,
)
from tests._series import series


def _between(s, lo, hi, values):
    return [v for c, v in zip(s.cue, values) if lo <= c <= hi and v is not None]


def test_unwrap_crosses_the_seam_and_skips_gaps():
    assert unwrap_degrees([170.0, 179.0, -179.0, -170.0, None, -160.0]) == [
        170.0,
        179.0,
        181.0,
        190.0,
        None,
        200.0,
    ]


def test_decimal_quantum():
    assert decimal_quantum([10.000001, 10.000003, 10.5]) == 1e-6
    assert decimal_quantum([10.0001, 10.0003]) == 1e-4
    assert decimal_quantum([45.0, 45.0]) == 0.0


def test_yaw_is_unwrapped_before_resampling():
    s = build_motion(series(10, yaw=lambda t: 170 + 4 * t))  # crosses +180 at 2.5 s
    yaws = [y for y in s.yaw if y is not None]
    assert max(abs(b - a) for a, b in pairwise(yaws)) < 1.0
    assert abs(yaws[-1] - yaws[0] - 40) < 0.5


def test_quantum_metres_six_vs_four_decimals():
    assert build_motion(series(10, east=lambda t: 3 * t)).h_quantum < 0.15
    assert (
        build_motion(series(10, east=lambda t: 3 * t, quantum_deg=1e-4)).h_quantum > 5.0
    )


def test_gps_gap_splits_runs():
    s = build_motion(series(20, east=lambda t: 7 * t, drop=lambda t: 8 <= t < 11))
    (_, a1), (b0, _) = s.runs()
    assert s.cue[a1] < 8.0 and s.cue[b0] >= 11.0 - 1e-9


def test_one_hz_source_is_not_all_gaps():
    s = build_motion(series(30, hz=1.0, east=lambda t: 5 * t))
    assert s.runs() == [(0, len(s.cue) - 1)]


def test_quantised_slow_drift_is_not_acceleration():
    s = build_motion(series(20, east=lambda t: 0.03 * t))
    acc = [a for a in s.accel if a is not None]
    assert acc and max(acc) < 0.3


def test_glide_speed_and_course():
    s = build_motion(series(20, east=lambda t: 7 * t))
    assert all(abs(v - 7) < 0.2 for v in _between(s, 3, 17, s.speed))
    assert all(abs(c - 90) < 1 for c in _between(s, 3, 17, s.course))


def test_slow_motion_speeds_are_real_time():
    s = build_motion(series(80, east=lambda t: 4 * t, factor=8), factor=8.0)
    assert all(abs(v - 4) < 0.2 for v in _between(s, 20, 60, s.speed))


def test_gimbal_rate_in_degrees_per_real_second():
    s = build_motion(series(10, pitch=lambda t: -60 + 5 * t))
    assert all(abs(r - 5) < 0.2 for r in _between(s, 2, 8, s.pitch_rate))


def test_relative_height_preferred_absolute_fallback():
    rel = build_motion(series(10))
    absolute = build_motion(series(10, rel_alt=False))
    assert rel.height_is_relative and not absolute.height_is_relative
    assert abs(rel.height[50] - 45.0) < 1e-6 and abs(absolute.height[50] - 145.0) < 1e-6


def test_duplicate_and_unordered_cues():  # Review Focus 3
    samples = series(10, east=lambda t: 2 * t)
    s = build_motion(samples[::-1] + samples[:30])
    assert all(b > a for a, b in pairwise(s.cue))
    assert len(s.cue) == len(build_motion(samples).cue)


def test_one_sample_gives_an_empty_series():
    s = build_motion(series(0))
    assert s.cue == [] and s.runs() == [] and not s.gimbal_known
