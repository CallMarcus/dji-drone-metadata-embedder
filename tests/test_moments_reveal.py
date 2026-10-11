import math

from dji_metadata_embedder.geo.moments import detect_moments
from dji_metadata_embedder.geo.motion import build_motion
from tests._series import series

REVEAL = frozenset({"reveal"})


def _found(samples):
    return detect_moments(build_motion(samples), REVEAL)


def _ramp(t, t0, t1, a, b):
    if t < t0:
        return a
    if t < t1:
        return a + (b - a) * (t - t0) / (t1 - t0)
    return b


def test_reveal_tilt_up_to_the_horizon():
    (m,) = _found(
        series(20, yaw=lambda t: 0.0, pitch=lambda t: _ramp(t, 5, 9, -80, -5))
    ).moments
    assert (m.kind, m.label) == ("reveal", "Reveal · tilt up 75°")
    assert abs(m.start_s - 5) < 0.3 and abs(m.end_s - 9) < 0.3


def test_tilt_down():
    (m,) = _found(
        series(20, yaw=lambda t: 0.0, pitch=lambda t: _ramp(t, 5, 9, -10, -50))
    ).moments
    assert (m.kind, m.label) == ("tilt", "Tilt down 40°")


def test_small_or_slow_tilts_are_ignored():
    assert (
        _found(
            series(20, yaw=lambda t: 0.0, pitch=lambda t: _ramp(t, 5, 9, -30, -15))
        ).moments
        == []
    )
    assert (
        _found(
            series(30, yaw=lambda t: 0.0, pitch=lambda t: _ramp(t, 5, 25, -60, -30))
        ).moments
        == []
    )


def test_pan_across_the_seam():
    (m,) = _found(
        series(20, yaw=lambda t: _ramp(t, 5, 11, 150, 210), pitch=lambda t: -20.0)
    ).moments
    assert (m.kind, m.label) == ("pan", "Pan right 60°")


def test_slow_long_pan_has_no_upper_bound():
    (m,) = _found(
        series(24, yaw=lambda t: _ramp(t, 0, 20, 0, 90), pitch=lambda t: -20.0)
    ).moments
    assert m.label == "Pan right 90°"


def test_orbit_is_one_long_pan():
    (m,) = _found(
        series(40, yaw=lambda t: _ramp(t, 0, 36, 0, -360), pitch=lambda t: -20.0)
    ).moments
    assert m.label == "Pan left 360°"


def test_jitter_does_not_split_a_reveal():
    def pitch(t):
        return _ramp(t, 5, 9, -80, -5) + 0.4 * math.sin(7 * t)

    (m,) = _found(series(20, yaw=lambda t: 0.0, pitch=pitch)).moments
    assert m.label.startswith("Reveal · tilt up") and abs(m.start_s - 5) < 0.5


def test_no_gimbal_skips_the_family_with_a_note():
    r = _found(series(20))
    assert (
        r.moments == [] and "no gimbal data: reveals, tilts and pans skipped" in r.notes
    )


def test_pan_ends_where_the_turning_stops():
    """Calibration (Air 3S, 2026-10-11): a slow creep after a pan kept the
    marker open over seconds of near-stillness. The marker ends where the
    camera stops turning at pan speed; the label keeps the full turn."""

    def yaw(t):
        if t < 5:
            return 0.0
        if t < 14:
            return 10.0 * (t - 5)  # 10 °/s pan
        return 90.0 + 1.0 * (t - 14)  # 1 °/s creep, slower than steady's limit

    (m,) = _found(series(26, yaw=yaw, pitch=lambda t: -20.0)).moments
    assert m.label == "Pan right 102°"  # 90° pan + 12 s of 1 °/s creep
    assert abs(m.start_s - 5) < 0.6 and m.end_s < 15.0
