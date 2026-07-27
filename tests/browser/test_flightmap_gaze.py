"""Camera's Gaze (#378): footprint projection, patch, beam and lookup."""

import math
from datetime import datetime, timedelta

import pytest

pytest.importorskip("playwright")

from dji_metadata_embedder.geo.flightmap3d_html import flights_to_3d_html  # noqa: E402
from dji_metadata_embedder.geo.footprint import DEFAULT_LENS, fov_degrees  # noqa: E402
from dji_metadata_embedder.geo.geometry import frustum_ground_ring  # noqa: E402
from dji_metadata_embedder.geo.track import Track, TrackPoint  # noqa: E402

pytestmark = pytest.mark.browser

TILE_DEG = 360 / 2 ** 15   # z15 tile width; the DEM cliff sits at each midpoint


def _flight(name: str, lat: float, lon: float, agls: list[float | None], *,
            yaws: list[float | None] | None = None,
            pitches: list[float | None] | None = None,
            focal: float | None = None, step: float = 0.0006) -> Track:
    """Synthetic flight: ``agls[i]`` is point i's rel_alt, one sample a second."""
    t0 = datetime(2026, 6, 15, 12, 0, 0)
    return Track(name=name, points=[
        TrackPoint(lat=lat, lon=lon + i * step, alt=100.0 + (a or 0),
                   timestamp=f"00:00:{i:02d},000",
                   utc=t0 + timedelta(seconds=i), rel_alt=a, focal_len=focal,
                   gimbal_yaw=None if yaws is None else yaws[i],
                   gimbal_pitch=None if pitches is None else pitches[i])
        for i, a in enumerate(agls)
    ])


def _ready(page):
    page.wait_for_selector("#flights-panel", timeout=15000)


def test_gaze_ring_matches_the_python_projection(serve_map, page):
    """The JS port must agree with geometry.frustum_ground_ring corner by
    corner. This is the only thing standing between a hand-ported projection
    and silent drift from the Python that ships in --footprint exports."""
    track = _flight("DJI_0001", 10.0, 20.0, [50.0] * 3,
                    yaws=[35.0] * 3, pitches=[-40.0] * 3, focal=24.0)
    serve_map(flights_to_3d_html([track], "trip"))
    _ready(page)
    got = page.evaluate("() => gazeRing(flights[0], 1)")
    assert got["reason"] is None
    assert got["estimated"] is False
    # Read the FOV back off the page: it is rounded to 0.1 deg on the way into
    # the GeoJSON, so handing Python the unrounded value would compare two
    # different lenses and the parity claim would be meaningless.
    hfov = page.evaluate("() => flights[0].hfov")
    vfov = page.evaluate("() => flights[0].vfov")
    lon, lat = page.evaluate("() => flights[0].pts[1].slice(0, 2)")
    expected = frustum_ground_ring(lat, lon, 50.0, 35.0, -40.0, hfov, vfov,
                                   8.0 * 50.0)
    assert len(got["ring"]) == len(expected) == 5
    for (gx, gy), (ex, ey) in zip(got["ring"], expected):
        assert abs(gx - ex) < 1e-9, f"lon {gx} != {ex}"
        assert abs(gy - ey) < 1e-9, f"lat {gy} != {ey}"


def test_gaze_ring_clamps_a_near_horizon_frame(serve_map, page):
    """A 2-degree down-tilt would reach the horizon; the ring must stay inside
    8 x AGL, matching MAX_RANGE_AGL_FACTOR."""
    track = _flight("DJI_0001", 10.0, 20.0, [50.0] * 3,
                    yaws=[0.0] * 3, pitches=[-2.0] * 3, focal=24.0)
    serve_map(flights_to_3d_html([track], "trip"))
    _ready(page)
    got = page.evaluate("() => gazeRing(flights[0], 1)")
    lon, lat = page.evaluate("() => flights[0].pts[1].slice(0, 2)")
    for x, y in got["ring"]:
        dx = (x - lon) * 111320 * math.cos(math.radians(lat))
        dy = (y - lat) * 111320
        assert math.hypot(dx, dy) <= 400.0 + 1e-6, "corner escaped the clamp"
    hfov = page.evaluate("() => flights[0].hfov")
    vfov = page.evaluate("() => flights[0].vfov")
    expected = frustum_ground_ring(lat, lon, 50.0, 0.0, -2.0, hfov, vfov, 400.0)
    for (gx, gy), (ex, ey) in zip(got["ring"], expected):
        assert abs(gx - ex) < 1e-9 and abs(gy - ey) < 1e-9


def test_no_ring_without_altitude(serve_map, page):
    track = _flight("DJI_0001", 10.0, 20.0, [None, None, None],
                    yaws=[0.0] * 3, pitches=[-45.0] * 3, focal=24.0)
    serve_map(flights_to_3d_html([track], "trip"))
    _ready(page)
    got = page.evaluate("() => gazeRing(flights[0], 1)")
    assert got["ring"] is None
    assert got["reason"] == "no altitude"


def test_no_ring_above_the_horizon(serve_map, page):
    """footprint.py skips a frame whose camera is at or above the horizon; so
    must the viewer, rather than drawing a trapezoid to the clamp distance."""
    track = _flight("DJI_0001", 10.0, 20.0, [50.0] * 3,
                    yaws=[0.0] * 3, pitches=[5.0] * 3, focal=24.0)
    serve_map(flights_to_3d_html([track], "trip"))
    _ready(page)
    got = page.evaluate("() => gazeRing(flights[0], 1)")
    assert got["ring"] is None
    assert got["reason"] == "camera above horizon"


def test_missing_attitude_is_estimated_not_hidden(serve_map, page):
    track = _flight("DJI_0001", 10.0, 20.0, [50.0] * 3)   # no gimbal, no focal
    serve_map(flights_to_3d_html([track], "trip"))
    _ready(page)
    got = page.evaluate("() => gazeRing(flights[0], 1)")
    assert got["ring"] is not None
    assert got["estimated"] is True
    assert set(got["estNotes"]) == {"no gimbal pitch", "no gimbal yaw",
                                    "assumed lens"}
    # The estimate must be the SAME down-tilt the cockpit assumes, or the two
    # views disagree in one frame.
    assert page.evaluate("() => GHOST_EST_PITCH") == -30


def test_fallback_lens_matches_the_python_default(serve_map, page):
    track = _flight("DJI_0001", 10.0, 20.0, [50.0] * 3)
    serve_map(flights_to_3d_html([track], "trip"))
    _ready(page)
    hfov, vfov = fov_degrees(DEFAULT_LENS, None)
    assert page.evaluate("() => GAZE_FALLBACK_HFOV") == round(hfov, 1)
    assert page.evaluate("() => GAZE_FALLBACK_VFOV") == round(vfov, 1)
