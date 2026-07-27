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


def _wait_patch(page, present: bool):
    """Wait for the gaze source to hold a ring (or not). GeoJSON source tiles
    build asynchronously, so sampling the instant after a state change is a
    flake."""
    page.wait_for_function(
        "(want) => (map.querySourceFeatures('gaze').length > 0) === want",
        arg=present, timeout=5000)


def test_patch_renders_at_the_projected_ring(serve_map, page):
    """queryRenderedFeatures at the ring's centre must hit gaze-fill: the patch
    has to be drawn where the projection says, not merely added as data."""
    track = _flight("DJI_0001", 10.0, 20.0, [50.0] * 5,
                    yaws=[90.0] * 5, pitches=[-50.0] * 5, focal=24.0)
    serve_map(flights_to_3d_html([track], "trip"))
    _ready(page)
    _wait_patch(page, True)      # present before play is ever pressed
    hit = page.evaluate(
        "() => { const r = gazeRing(flights[0], pb.sample).ring;"
        " const c = r.slice(0, 4).reduce("
        "   (a, p) => [a[0] + p[0] / 4, a[1] + p[1] / 4], [0, 0]);"
        " const q = map.project(c);"
        " return map.queryRenderedFeatures([q.x, q.y],"
        "                                  {layers: ['gaze-fill']}).length; }")
    assert hit > 0, "no gaze-fill under the ring centre"
    off = page.evaluate(
        "() => map.queryRenderedFeatures([2, 2],"
        "                                {layers: ['gaze-fill']}).length")
    assert off == 0, "gaze-fill covers a corner of the viewport it should not"


def test_patch_clears_above_the_horizon(serve_map, page):
    """A second the camera spent above the horizon must empty the source and
    say why, not freeze on the previous ring."""
    track = _flight("DJI_0001", 10.0, 20.0, [50.0] * 4,
                    yaws=[0.0] * 4, pitches=[-45.0, -45.0, 10.0, 10.0],
                    focal=24.0)
    serve_map(flights_to_3d_html([track], "trip"))
    _ready(page)
    _wait_patch(page, True)
    page.evaluate("() => { pb.t = 3; pbRender(); }")
    _wait_patch(page, False)
    assert page.evaluate("() => document.getElementById('pb-note')"
                         ".textContent") == "camera above horizon"


def test_patch_clears_without_altitude(serve_map, page):
    track = _flight("DJI_0001", 10.0, 20.0, [50.0, 50.0, None, None],
                    yaws=[0.0] * 4, pitches=[-45.0] * 4, focal=24.0)
    serve_map(flights_to_3d_html([track], "trip"))
    _ready(page)
    page.evaluate("() => { pb.t = 3; pbRender(); }")
    _wait_patch(page, False)
    assert page.evaluate("() => document.getElementById('pb-note')"
                         ".textContent") == "no altitude"


def test_a_flight_without_agl_is_playable_with_no_gaze(serve_map, page):
    """An SRT format that carries no rel_alt at all: the clock still runs, and
    the patch is simply never drawn (spec section 8)."""
    track = _flight("DJI_0001", 10.0, 20.0, [None] * 5,
                    yaws=[0.0] * 5, pitches=[-45.0] * 5, focal=24.0)
    serve_map(flights_to_3d_html([track], "trip"))
    _ready(page)
    assert page.locator("#playback").count() == 1
    assert page.evaluate("() => flights[0].agl") is None
    _wait_patch(page, False)
    page.evaluate("() => { pb.t = 3; pbRender(); }")
    _wait_patch(page, False)


def test_edge_dash_flips_both_ways(serve_map, page):
    """The dashed edge marks an estimated ring. The reset direction matters as
    much as the set: a null that failed to restore the default would leave
    every later ring looking estimated."""
    track = _flight("DJI_0001", 10.0, 20.0, [50.0] * 4,
                    yaws=[0.0, 0.0, None, None],
                    pitches=[-45.0, -45.0, -45.0, -45.0], focal=24.0)
    serve_map(flights_to_3d_html([track], "trip"))
    _ready(page)
    dash = "() => map.getPaintProperty('gaze-edge', 'line-dasharray')"
    assert not page.evaluate(dash), "sample 0 has real yaw: edge must be solid"
    page.evaluate("() => { pb.t = 3; pbRender(); }")
    assert page.evaluate(dash), "estimated ring must dash the edge"
    page.evaluate("() => { pb.t = 0; pbRender(); }")
    assert not page.evaluate(dash), "dash was never reset"


def test_note_names_the_estimate(serve_map, page):
    track = _flight("DJI_0001", 10.0, 20.0, [50.0] * 4)
    serve_map(flights_to_3d_html([track], "trip"))
    _ready(page)
    note = page.evaluate("() => document.getElementById('pb-note')"
                         ".textContent")
    assert note.startswith("estimated footprint")
    assert "no gimbal pitch" in note
