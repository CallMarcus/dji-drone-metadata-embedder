import math

from dji_metadata_embedder.geo import moments as mo
from dji_metadata_embedder.geo.moments import detect_moments
from dji_metadata_embedder.geo.motion import build_motion
from tests._series import series

STEADY = frozenset({"steady"})


def _steady(samples, factor=1.0):
    report = detect_moments(build_motion(samples, factor), STEADY)
    return [m for m in report.moments if m.kind == "steady"]


def _burst(t):  # 5 m/s, then 2 m/s² for 2 s, then 9 m/s
    if t < 10:
        return 5 * t
    if t < 12:
        return 50 + 5 * (t - 10) + (t - 10) ** 2
    return 64 + 9 * (t - 12)


def _hover_then_go(t):
    if t < 10:
        return 0.0
    if t < 12:
        return (t - 10) ** 2
    return 4 + 4 * (t - 12)


def test_hover_is_one_steady_stretch():
    (m,) = _steady(series(20))
    assert m.label.startswith("Steady ") and m.label.endswith("· hover at 45 m")
    assert 16.0 <= m.end_s - m.start_s <= 18.0
    assert "gimbal not recorded" in m.note


def test_constant_speed_glide_is_steady():
    (m,) = _steady(series(20, east=lambda t: 7 * t))
    assert "glide ≈7 m/s" in m.label


def test_acceleration_burst_splits_the_run():
    first, second = _steady(series(30, east=_burst))
    assert first.end_s < 10.0 and second.start_s > 12.0


def test_hover_then_glide_get_their_own_labels():
    hover, glide = _steady(series(30, east=_hover_then_go))
    assert "hover" in hover.label and "glide ≈4 m/s" in glide.label


def test_gentle_curve_splits_on_heading():
    v, w = 3.0, math.radians(4.0)  # centripetal 0.21 m/s², under the threshold
    ms = _steady(
        series(
            30,
            north=lambda t: v / w * math.sin(w * t),
            east=lambda t: v / w * (1 - math.cos(w * t)),
        )
    )
    assert len(ms) >= 3 and all("glide" in m.label for m in ms)


def test_quantised_slow_drift_stays_steady():
    (m,) = _steady(series(20, east=lambda t: 0.03 * t))
    assert m.end_s - m.start_s >= 10


def test_gps_gap_splits_and_is_never_steady():
    first, second = _steady(
        series(20, east=lambda t: 7 * t, drop=lambda t: 8 <= t < 11)
    )
    assert first.end_s <= 8.0 and second.start_s >= 11.0


def test_coarse_position_skips_steady_with_a_note():
    r = detect_moments(
        build_motion(series(20, east=lambda t: 7 * t, quantum_deg=1e-4)), STEADY
    )
    assert r.moments == [] and any("too coarse" in n for n in r.notes)


def test_vertical_climb_is_never_steady():
    assert _steady(series(20, height=lambda t: 45 + 2 * t)) == []


def test_gimbal_pan_breaks_steadiness():
    def yaw(t):
        return 0.0 if t < 8 else (10 * (t - 8) if t < 12 else 40.0)

    first, second = _steady(series(24, yaw=yaw, pitch=lambda t: -30.0))
    assert first.end_s < 8.5 and second.start_s > 11.5
    assert "gimbal not recorded" not in first.note


def test_slow_motion_labels_playback_and_notes_the_factor():
    (m,) = _steady(series(80, factor=8), factor=8.0)
    assert 52 <= m.end_s - m.start_s <= 60
    assert "slow motion ≈×8" in m.note


def test_longest_only_fallback(monkeypatch):
    monkeypatch.setattr(mo, "STEADY_LONGEST_ONLY", True)
    ms = _steady(series(30, east=_burst))
    assert len(ms) == 1 and ms[0].start_s > 12.0  # the 9 m/s piece is longer


def test_coverage_is_reported():
    r = detect_moments(build_motion(series(20)), STEADY)
    assert 0.8 <= r.coverage["steady"] <= 0.9


def test_tiny_clips_give_nothing():  # Review Focus 4
    one = detect_moments(build_motion(series(0)))
    assert one.moments == [] and one.notes == ["too little telemetry to detect moments"]
    assert detect_moments(build_motion(series(3))).moments == []


def test_stretch_at_takeoff_height_is_not_called_a_hover():
    """Calibration (Air 3S, 2026-10-11): before takeoff and after landing
    the drone reads ~0 m above takeoff; "hover at 0 m" overclaims."""
    (m,) = _steady(series(20, height=lambda t: 0.0))
    assert m.label.endswith("· at takeoff height")
