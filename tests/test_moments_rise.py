from dji_metadata_embedder.geo.moments import detect_moments
from dji_metadata_embedder.geo.motion import build_motion
from tests._series import series

RISE = frozenset({"rise"})


def _climb(t, start=5.0, rate=2.0, gain=12.0):
    return 20.0 if t < start else 20.0 + min(gain, rate * (t - start))


def _rises(samples, kinds=RISE):
    return [
        m
        for m in detect_moments(build_motion(samples), kinds).moments
        if m.kind == "rise"
    ]


def test_rise_of_twelve_metres():
    (m,) = _rises(series(20, height=_climb, pitch=lambda t: -5.0))
    assert m.label == "Rise 12 m"
    assert 4.0 <= m.start_s <= 5.5 and 10.5 <= m.end_s <= 12.0


def test_long_rocket_climb_is_one_rise():
    (m,) = _rises(
        series(45, height=lambda t: _climb(t, gain=60.0), pitch=lambda t: -5.0)
    )
    assert m.label == "Rise 60 m"


def test_camera_looking_down_is_not_a_rise():
    assert _rises(series(20, height=_climb, pitch=lambda t: -70.0)) == []


def test_unknown_camera_angle_is_noted():
    (m,) = _rises(series(20, height=_climb))
    assert "camera angle not recorded" in m.note


def test_slow_climb_and_descent_are_not_rises():
    assert _rises(series(60, height=lambda t: _climb(t, rate=0.5, gain=20.0))) == []
    assert _rises(series(20, height=lambda t: 40.0 - _climb(t) + 20.0)) == []


def test_a_steady_climb_is_a_rise_and_never_also_steady():
    r = detect_moments(
        build_motion(series(20, height=lambda t: 20 + 2 * t, pitch=lambda t: -5.0))
    )
    assert {m.kind for m in r.moments} == {"rise"}
