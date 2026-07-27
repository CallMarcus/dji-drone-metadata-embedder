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
    _wait_patch(page, True)      # present before the seek, or "cleared" is
                                  # meaningless -- its sibling above asserts
                                  # this too
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


_BEAM_JS = ("() => beamFor(flights[0], pb.sample,"
            " gazeRing(flights[0], pb.sample).ring).map(f => f.properties)")


def test_beam_is_four_continuous_rays(serve_map, page):
    """Four corner rays of 16 prisms each, and neighbours must share the
    boundary height -- otherwise the silhouette is a ladder with gaps."""
    track = _flight("DJI_0001", 10.0, 20.0, [50.0] * 5,
                    yaws=[90.0] * 5, pitches=[-50.0] * 5, focal=24.0)
    serve_map(flights_to_3d_html([track], "trip"))
    _ready(page)
    steps = page.evaluate("() => GAZE_BEAM_STEPS")
    props = page.evaluate(_BEAM_JS)
    assert len(props) == 4 * steps
    for r in range(4):
        ray = props[r * steps:(r + 1) * steps]
        for a, b in zip(ray, ray[1:]):
            assert abs(a["base"] - b["hgt"]) < 1e-6, f"gap in ray {r}"
        # Terrain is off in this run, so the extrusion measures from sea level
        # and the camera end sits at raw AGL.
        assert abs(ray[0]["hgt"] - 50.0) < 1e-6
        assert abs(ray[-1]["base"]) < 1e-6


def test_beam_heights_survive_the_elevation_conversion(serve_map, page):
    """A constant-elevation DEM must give the SAME heights as no DEM at all.
    Skipping the takeoff/local conversion breaks this. (Interpolating the
    local surface end to end, rather than sampling it per boundary, does
    NOT break this: on a constant-elevation DEM the two formulas collapse to
    the identical h(s) = (A - E_cam)(1 - s) -- see beamFor's own comment.
    test_beam_stops_at_a_cliff is the test that would actually catch that
    defect, on a DEM where the two formulas diverge.)"""
    track = _flight("DJI_0001", 10.0, 20.0, [50.0] * 5,
                    yaws=[90.0] * 5, pitches=[-50.0] * 5, focal=24.0)
    html = flights_to_3d_html([track], "trip")
    serve_map(html, terrain_stub=100.0)
    _ready(page)
    # queryTerrainElevation decodes through float32, so a constant-100 stub
    # comes back as 100.00000000000182, never exactly 100 -- compare with a
    # tolerance rather than equality.
    page.wait_for_function(
        "() => Math.abs(terrainElevAt(map.getCenter()) - 100) < 1e-6",
        timeout=15000)
    page.evaluate("() => renderGaze()")
    props = page.evaluate(_BEAM_JS)
    steps = page.evaluate("() => GAZE_BEAM_STEPS")
    for r in range(4):
        ray = props[r * steps:(r + 1) * steps]
        assert abs(ray[0]["hgt"] - 50.0) < 0.5
        assert abs(ray[-1]["base"]) < 1e-6


def test_beam_stops_at_a_cliff(serve_map, page):
    """A ray aimed past a 600 m wall must END at the wall, not tunnel through
    it: every prism beyond the crossing is below the rendered surface, and
    fill-extrusion cannot draw below terrain at all.

    The drone sits ~60 m west of the wall rather than a quarter tile, so the
    crossing falls early in the ray and the drop rule is exercised on roughly
    half the prisms. At a quarter tile the crossing lands at s~0.9 and only
    2 of 64 prisms drop -- the assertion passes while proving almost nothing.

    Known limitation this test deliberately does NOT assert away: gazeRing
    projects onto a FLAT ground plane at the drone's height datum, so where
    terrain rises into the frustum the far corner lands past the real hit
    point and the ray climbs toward it. Fixing that needs DEM ray-marching,
    which would change the patch too and is out of scope here (see the design
    spec's flat-ground-plane note).
    """
    # MapLibre resolves DEM tiles one zoom COARSER than the source maxzoom, so
    # the stub's left/right split lands at the z14 tile midpoint, NOT at
    # the z15 tile's east edge -- those only coincide when the z15 tile is
    # the WESTERN half of its z14 parent (true for lon 20.0, but not in
    # general). Derive the midpoint on the z14 grid directly.
    parent = 2 * TILE_DEG
    cliff = -180 + math.floor((20.0 + 180) / parent) * parent + TILE_DEG
    lon = cliff - TILE_DEG * 0.05      # ~60 m west of the wall
    track = _flight("DJI_0001", 10.0, lon, [50.0] * 5,
                    yaws=[90.0] * 5, pitches=[-20.0] * 5, focal=24.0,
                    step=0.0)
    serve_map(flights_to_3d_html([track], "trip"), terrain_steps=(50.0, 650.0))
    _ready(page)
    # 50 (not 0) is the unambiguous "loaded" signal on the low side: 0 is
    # indistinguishable from a cold tile (terrainElevAt's own contract).
    page.wait_for_function(
        "() => Math.abs(terrainElevAt(map.getCenter()) - 50) < 1e-6",
        timeout=15000)
    page.evaluate("() => renderGaze()")
    props = page.evaluate(_BEAM_JS)
    steps = page.evaluate("() => GAZE_BEAM_STEPS")
    assert props, "the beam vanished entirely"
    dropped = 4 * steps - len(props)
    assert dropped >= 8, (
        f"only {dropped} of {4 * steps} prisms dropped at the wall -- the "
        "geometry is degenerate and this test proves little")
    # Exercises the Math.max(0, ...) clamp on base: the prism straddling the
    # wall has a lower boundary height around -34 m in this fixture, and
    # fill-extrusion-base has a style-spec minimum of 0. Without the clamp
    # this fails.
    assert all(p["base"] >= 0 for p in props)

    # The real claim: no surviving prism sits meaningfully past the wall.
    # A centroid can land at most half a step past the crossing -- the
    # straddling step is kept whenever its western end is still above
    # ground, and the step after it is dropped -- so 0.5 steps of slack
    # is the tightest bound that cannot false-positive on the straddler
    # while still catching a surviving prism a full step beyond it.
    centroids = page.evaluate(
        "() => beamFor(flights[0], pb.sample,"
        " gazeRing(flights[0], pb.sample).ring).map(f => {"
        "   const r = f.geometry.coordinates[0];"
        "   return r.slice(0, 4).reduce((a, p) => a + p[0] / 4, 0); })")
    ray_len_deg = page.evaluate(
        "() => { const r = gazeRing(flights[0], pb.sample).ring;"
        " return Math.max(...r.slice(0, 4).map(p => p[0]))"
        "      - flights[0].pts[pb.sample][0]; }")
    slack = ray_len_deg / steps * 0.5
    beyond = [c for c in centroids if c > cliff + slack]
    assert not beyond, (
        f"{len(beyond)} prisms sit past the wall at {cliff:.6f}: "
        f"{[round(c, 6) for c in beyond[:5]]}")


# Capture what renderGaze() actually hands the beam source. querySourceFeatures
# cannot be used to measure prism width: a prism is a few metres across, and
# MapLibre's geojson-vt tessellation simplifies a feature that small to under 4
# points at low zoom. The source's `_data` holds the same thing, but it is a
# private field and this project pins MapLibre by version + SRI -- a deliberate
# bump would then fail here looking like a beam bug. Wrapping the public
# setData is equivalent, survives version bumps, and additionally records
# *whether the rebuild fired at all*, which is the behaviour under test.
# Patching browser internals from a test is the established idiom in this
# suite; see conftest's hillshade accessor trap and getContext patch.
_BEAM_SPY_JS = """
(() => {
  const src = map.getSource('beam');
  const orig = src.setData.bind(src);
  window.__beamSets = 0;
  window.__lastBeam = null;
  src.setData = d => { window.__beamSets++; window.__lastBeam = d; return orig(d); };
})();
"""


def test_beam_width_tracks_zoom(serve_map, page):
    track = _flight("DJI_0001", 10.0, 20.0, [50.0] * 5,
                    yaws=[90.0] * 5, pitches=[-50.0] * 5, focal=24.0)
    serve_map(flights_to_3d_html([track], "trip"))
    _ready(page)

    def _beam_width():
        # Cross-ray width of a prism: the gap between its two camera-side
        # corners, r[0] and r[3] (the ring closes back to r[0]).
        return page.evaluate(
            "() => { const r = window.__lastBeam"
            ".features[0].geometry.coordinates[0];"
            " return Math.hypot(r[0][0] - r[3][0], r[0][1] - r[3][1]); }")

    page.evaluate("() => map.jumpTo({zoom: 16})")
    page.wait_for_function("() => !map.isMoving()", timeout=15000)
    page.evaluate(_BEAM_SPY_JS)
    page.evaluate("() => renderGaze()")      # seed the spy with a known build
    near = page.evaluate("() => sculptWidthM()")
    near_beam = _beam_width()
    page.evaluate("() => { window.__beamSets = 0; map.jumpTo({zoom: 11}); }")
    page.wait_for_function("() => !map.isMoving()", timeout=15000)
    far = page.evaluate("() => sculptWidthM()")
    assert far > near

    # Two claims, and the first is the one the old `length > 0` assertion
    # missed entirely: the zoomend rebuild must actually FIRE (delete the
    # renderGaze() hook in rebuildSculpture and __beamSets stays 0), and what
    # it hands the source must be rebuilt at the new width rather than the one
    # it had on load.
    # wait_for_function, not a synchronous read: 'zoomend' can be dispatched
    # a tick after isMoving() itself flips false, and sampling the instant
    # after a state change is a flake -- the same class _wait_patch guards
    # against elsewhere in this file. If the hook is truly gone this still
    # fails, just as a timeout instead of an immediate assertion.
    page.wait_for_function("() => window.__beamSets > 0", timeout=15000)
    assert _beam_width() > near_beam


def _click_at(page, lng, lat):
    """Click the map canvas at a geographic point."""
    pt = page.evaluate("([lng, lat]) => { const p = map.project([lng, lat]);"
                       " return [p.x, p.y]; }", [lng, lat])
    page.mouse.click(pt[0], pt[1])


def _click_inside_ring(page, sample: int):
    """Click inside sample's footprint but clear of the flight line.

    Two traps, both of which made these tests prove nothing:

    A nadir footprint's centroid IS the track vertex. At pitch exactly -90
    frustum_ground_ring has fwd_n == 0 and up_z == 0, so the four corners sit
    at (+/-tan_h*agl, +/-tan_v*agl) and average back to the camera position --
    clicking there hits the flight line, gazeLookup correctly bails, and the
    flight's own popup answers instead. Blending halfway to a corner moves the
    click off-axis.

    And these fixtures are tiny on screen: a ~200 m track under the map's
    fitBounds/maxZoom 15 spans ~40 px, so the whole 75 m footprint is ~16 px
    wide and every point in it is within a few pixels of the line. Zooming in
    is what actually buys the clearance; an off-nadir pitch alone would move
    the axis ~2 px.

    The precondition assertion is the point: it turns a silent bail into a
    loud failure if this geometry ever drifts again.
    """
    pt = page.evaluate(
        "(s) => { const r = gazeRing(flights[0], s).ring;"
        " const c = r.slice(0, 4).reduce("
        "   (a, p) => [a[0] + p[0] / 4, a[1] + p[1] / 4], [0, 0]);"
        " return [c[0] + (r[0][0] - c[0]) * 0.5,"
        "         c[1] + (r[0][1] - c[1]) * 0.5]; }", sample)
    page.evaluate("(p) => map.jumpTo({center: p, zoom: 17})", pt)
    page.wait_for_function("() => !map.isMoving()", timeout=15000)
    px = page.evaluate(
        "(p) => { const q = map.project(p); return [q.x, q.y]; }", pt)
    on_line = page.evaluate(
        "([x, y]) => map.queryRenderedFeatures([x, y],"
        " {layers: flights.map(f => f.id).filter(id => map.getLayer(id))})"
        ".length", px)
    assert on_line == 0, (
        "click point sits on the flight line, so gazeLookup would bail and "
        "this test would prove nothing")
    page.mouse.click(px[0], px[1])
    return pt


def test_clicking_inside_a_footprint_lists_the_passes(serve_map, page):
    """The provenance question: which seconds filmed this ground?"""
    track = _flight("DJI_0001", 10.0, 20.0, [50.0] * 6,
                    yaws=[90.0] * 6, pitches=[-90.0] * 6, focal=24.0)
    serve_map(flights_to_3d_html([track], "trip"))
    _ready(page)
    _click_inside_ring(page, 2)
    page.wait_for_selector(".maplibregl-popup", timeout=5000)
    text = page.locator(".maplibregl-popup").inner_text()
    assert "DJI_0001" in text
    assert "in frame" in text
    assert page.locator(".gaze-pass").count() >= 1
    page.wait_for_function(
        "() => map.querySourceFeatures('gaze-hits').length > 0", timeout=5000)


def test_clicking_empty_ground_says_so(serve_map, page):
    track = _flight("DJI_0001", 10.0, 20.0, [50.0] * 6,
                    yaws=[90.0] * 6, pitches=[-90.0] * 6, focal=24.0)
    serve_map(flights_to_3d_html([track], "trip"))
    _ready(page)
    # Centre the map on the empty point rather than guessing an offset that
    # stays on canvas: at the auto-fit zoom, 0.05 deg away projects to roughly
    # (1420, -48) in a 1280x720 viewport, so the click never reached the map
    # and the miss popup never appeared. ~330 m clears a ~75 m footprint.
    # Offset in LATITUDE: the track runs east-west from lon 20.0000 to 20.0030
    # in six 0.0006 steps, so a longitude offset of 0.003 lands exactly on the
    # last sample. 0.003 deg north is ~330 m, well clear of footprints that
    # reach ~0.00034 deg (37.5 m) across-track.
    empty = [20.0015, 10.003]
    page.evaluate("(p) => map.jumpTo({center: p, zoom: 17})", empty)
    page.wait_for_function("() => !map.isMoving()", timeout=15000)
    px = page.evaluate(
        "(p) => { const q = map.project(p); return [q.x, q.y]; }", empty)
    size = page.evaluate("() => [map.getCanvas().clientWidth,"
                         " map.getCanvas().clientHeight]")
    assert 0 <= px[0] <= size[0] and 0 <= px[1] <= size[1], (
        f"click point {px} is outside the {size} viewport; no click would fire")
    page.mouse.click(px[0], px[1])
    page.wait_for_selector(".maplibregl-popup", timeout=5000)
    assert "No footprint on this map covers this spot" in \
        page.locator(".maplibregl-popup").inner_text()
    assert page.locator(".gaze-pass").count() == 0
    # Nothing was skipped in this fixture (one flight, shown, with agl), so
    # the honesty line must not appear -- it would be noise on the common
    # case.
    assert page.locator(".gaze-skip").count() == 0


def test_a_pass_button_seeks_and_plays(serve_map, page):
    track = _flight("DJI_0001", 10.0, 20.0, [50.0] * 6,
                    yaws=[90.0] * 6, pitches=[-90.0] * 6, focal=24.0)
    serve_map(flights_to_3d_html([track], "trip"))
    _ready(page)
    _click_inside_ring(page, 4)
    page.wait_for_selector(".gaze-pass", timeout=5000)
    page.locator(".gaze-pass").first.click()
    assert page.evaluate("() => pb.t") >= 3.0
    assert page.evaluate("() => pb.playing") is True


def test_pass_list_caps_at_gaze_max_passes(serve_map, page):
    """M2 (#378 whole-branch review): GAZE_MAX_PASSES and the "+N more" note
    had no test at all -- an off-by-one in the slice or a broken note would
    ship unseen.

    A hover (step=0) with altitude alternating real/None gives more than 12
    passes cheaply, and DISCONTIGUOUS ones at that: every real-altitude
    sample sits between two None-altitude samples (no ring, so no hit), so
    each real sample closes its own one-sample pass instead of merging into
    a single long run.
    """
    n = 30
    agls = [50.0 if i % 2 == 0 else None for i in range(n)]
    real_hits = sum(1 for a in agls if a is not None)
    track = _flight("DJI_0001", 10.0, 20.0, agls,
                    yaws=[90.0] * n, pitches=[-90.0] * n, focal=24.0,
                    step=0.0)                       # hover: all rings coincide
    serve_map(flights_to_3d_html([track], "trip"))
    _ready(page)
    max_passes = page.evaluate("() => GAZE_MAX_PASSES")
    assert max_passes == 12
    assert real_hits > max_passes, "fixture must exceed the cap to test it"
    _click_inside_ring(page, 0)
    page.wait_for_selector(".maplibregl-popup", timeout=5000)
    assert page.locator(".gaze-pass").count() == max_passes
    text = page.locator(".maplibregl-popup").inner_text()
    assert f"+{real_hits - max_passes} more" in text, text


def test_highlight_clears_when_the_popup_closes(serve_map, page):
    track = _flight("DJI_0001", 10.0, 20.0, [50.0] * 6,
                    yaws=[90.0] * 6, pitches=[-90.0] * 6, focal=24.0)
    serve_map(flights_to_3d_html([track], "trip"))
    _ready(page)
    _click_inside_ring(page, 2)
    page.wait_for_selector(".maplibregl-popup-close-button", timeout=5000)
    # Assert the highlight is THERE before closing. Without this the test
    # passed while gazeLookup was bailing on the flight-line guard and
    # gaze-hits had been empty all along -- "empty at the end" proves nothing
    # if it was never populated.
    page.wait_for_function(
        "() => map.querySourceFeatures('gaze-hits').length > 0", timeout=5000)
    page.click(".maplibregl-popup-close-button")
    page.wait_for_function(
        "() => map.querySourceFeatures('gaze-hits').length === 0",
        timeout=5000)


def test_two_consecutive_lookups_leave_a_highlight(serve_map, page):
    """This started as a coverage-gap test (#378 whole-branch review): the
    review's theory was that MapLibre 5.24 closes the previous popup on a
    'preclick' event that fires before our own 'click' handler, and that a
    pinned-version bump could one day break that silently. Checking the
    ACTUAL bundled bundle found no 'preclick' anywhere in it: closeOnClick
    binds a plain (non-'once') 'click' listener when a popup opens. On a
    second click both listeners are registered -- gazeLookup (bound once, at
    mount, so first) and the FIRST popup's own close listener (bound after
    it, when that popup opened) -- and they fire in THAT order, so the first
    popup's belated close ran AFTER gazeLookup had already set the new
    highlight and wiped it right back out. Not a future-bump risk: a live
    bug, reproduced against the pinned version this repo actually ships.
    gazeLookup now closes the previous lookup popup itself, synchronously,
    before computing the new click's answer, which sidesteps the listener
    order question entirely -- see gazePopup's own comment.

    A wide step and far-apart samples: _click_inside_ring re-centres the
    viewport on its own click point every time, so with the default tight
    spacing the FIRST popup (still open, and repositioned by the recentre
    like any other map-anchored popup) can visually sit on top of the
    SECOND click's pixel and swallow the click itself -- proving nothing
    about MapLibre's click ordering, only about DOM overlap in the test.
    ~450 m between samples puts the two views (each a couple hundred
    metres wide at zoom 17) nowhere near each other on screen.
    """
    n = 10
    track = _flight("DJI_0001", 10.0, 20.0, [50.0] * n,
                    yaws=[90.0] * n, pitches=[-90.0] * n, focal=24.0,
                    step=0.004)
    serve_map(flights_to_3d_html([track], "trip"))
    _ready(page)
    _click_inside_ring(page, 1)
    page.wait_for_selector(".maplibregl-popup", timeout=5000)
    _click_inside_ring(page, 8)
    page.wait_for_selector(".maplibregl-popup", timeout=5000)
    assert page.locator(".maplibregl-popup").count() == 1, (
        "the first popup did not close on the second click")
    page.wait_for_function(
        "() => map.querySourceFeatures('gaze-hits').length > 0", timeout=5000)


def test_estimated_badge_covers_every_matched_sample(serve_map, page):
    """A clip can lose gimbal attitude partway through, so the warning has to
    reflect the weakest frame on offer -- not whichever sample happens to come
    first. Reading one sample's flag let the popup answer with extrapolated
    footprints and no warning at all, which is the one thing this feature must
    never do.

    Sample 0 keeps its real gimbal; the rest are dropped. The REAL sample
    must come first: the defect read passes[0].i0, so a fixture whose first
    matched sample was estimated would have shown the badge anyway and proved
    nothing. Its pitch is set to
    GHOST_EST_PITCH's own -30 so the geometry is identical across all four
    samples -- what varies is only whether the attitude was recorded or
    assumed. A nadir real sample would sit ~87 m from the estimated ones'
    footprints and the click would match just one of them, testing nothing.
    Combined with a hover (step=0), every ring covers the same ground, so one
    click matches both a real and an estimated sample.
    """
    track = _flight("DJI_0001", 10.0, 20.0, [50.0] * 4,
                    yaws=[90.0, 90.0, 90.0, 90.0],
                    pitches=[-30.0, None, None, None], focal=24.0,
                    step=0.0)                       # hover: all rings coincide
    serve_map(flights_to_3d_html([track], "trip"))
    _ready(page)
    est = page.evaluate(
        "() => [0, 1, 2, 3].map(i => gazeRing(flights[0], i).estimated)")
    assert est == [False, True, True, True], (
        f"fixture does not mix real and estimated attitude: {est}")
    _click_inside_ring(page, 0)
    page.wait_for_selector(".maplibregl-popup", timeout=5000)
    assert page.locator(".gaze-est").count() == 1, (
        "no estimated warning, though matched samples were extrapolated")
    # Yaw is real throughout this fixture (only pitch is dropped), so the
    # badge's reason must name pitch specifically -- not the old hardcoded
    # "no gimbal data", which would be true here by coincidence and would
    # stay wrong the moment yaw was the missing one instead.
    text = page.locator(".gaze-est").inner_text()
    assert "no gimbal pitch" in text
    assert "no gimbal yaw" not in text
    assert "assumed lens" not in text


def test_no_estimated_badge_when_every_sample_is_real(serve_map, page):
    """The mirror: a warning that always fires teaches users to ignore it."""
    track = _flight("DJI_0001", 10.0, 20.0, [50.0] * 4,
                    yaws=[90.0] * 4, pitches=[-90.0] * 4, focal=24.0,
                    step=0.0)
    serve_map(flights_to_3d_html([track], "trip"))
    _ready(page)
    _click_inside_ring(page, 2)
    page.wait_for_selector(".maplibregl-popup", timeout=5000)
    assert page.locator(".gaze-pass").count() >= 1   # the lookup really ran
    assert page.locator(".gaze-est").count() == 0


def test_clicking_the_track_still_opens_the_flight_popup(serve_map, page):
    """The flight line owns its own popup with View from here; the lookup must
    not fire a second popup on top of it."""
    track = _flight("DJI_0001", 10.0, 20.0, [50.0] * 6,
                    yaws=[90.0] * 6, pitches=[-90.0] * 6, focal=24.0)
    serve_map(flights_to_3d_html([track], "trip"))
    _ready(page)
    _click_at(page, *page.evaluate("() => flights[0].pts[3].slice(0, 2)"))
    page.wait_for_selector(".maplibregl-popup", timeout=5000)
    assert page.locator(".maplibregl-popup").count() == 1
    assert page.locator(".ghost-open").count() == 1
    assert page.locator(".gaze-pass").count() == 0


def test_fuzzed_positions_get_no_gaze_but_keep_playback(serve_map, page):
    """A footprint projected from a coordinate moved ~100 m is a confident
    claim about ground that was never filmed. --footprint already refuses
    redacted exports; so does the viewer."""
    track = _flight("DJI_0001", 10.0, 20.0, [50.0] * 6,
                    yaws=[90.0] * 6, pitches=[-90.0] * 6, focal=24.0)
    serve_map(flights_to_3d_html([track], "trip", redact="fuzz"))
    _ready(page)
    for layer in ("gaze-fill", "gaze-edge", "beam-ray", "gaze-hits-line"):
        assert page.evaluate("(id) => !map.getLayer(id)", layer), layer
    assert page.locator("#playback").count() == 1
    assert page.evaluate("() => !!map.getLayer('gaze-cursor-dot')")
    assert "gaze" in page.locator("#flights-panel").inner_text().lower()
    # A due-east, constant-latitude fixture line puts (20.001, 10.0) exactly
    # on the rendered flight line, so a plain _click_at would open the
    # flight's own (gaze-unrelated) popup and prove nothing about the gate.
    # _click_inside_ring's off-line point works here too: it is derived from
    # gazeRing(), which stays defined and callable even when the gate never
    # wires it into a layer or a click handler.
    _click_inside_ring(page, 2)
    assert page.locator(".maplibregl-popup").count() == 0


def test_hiding_the_flight_hides_its_gaze(serve_map, page):
    track = _flight("DJI_0001", 10.0, 20.0, [50.0] * 6,
                    yaws=[90.0] * 6, pitches=[-90.0] * 6, focal=24.0)
    serve_map(flights_to_3d_html([track], "trip"))
    _ready(page)
    vis = "(id) => map.getLayoutProperty(id, 'visibility') || 'visible'"
    assert page.evaluate(vis, "gaze-fill") == "visible"
    page.locator("#flights-panel input[type=checkbox]").first.uncheck()
    assert page.evaluate(vis, "gaze-fill") == "none"
    assert page.evaluate(vis, "beam-ray") == "none"
    assert page.evaluate(vis, "gaze-cursor-dot") == "none"
    page.locator("#flights-panel input[type=checkbox]").first.check()
    assert page.evaluate(vis, "gaze-fill") == "visible"


def test_switching_the_picker_reapplies_gaze_visibility(serve_map, page):
    """I2 (#378 whole-branch review): applyGazeVisibility derives visibility
    from pb.run.shown but was never re-run when pb.run itself changes. Hide
    flight A (the flight the picker starts on) -- every gaze layer goes
    'none'. Switch the picker to flight B, which is still shown: without the
    fix, pbRecolour() (called from the picker's own change handler) leaves
    the layers exactly as hiding A set them, and B's gaze looks dead even
    though B is visible."""
    a = _flight("DJI_0001", 10.0, 20.0, [50.0] * 4,
                yaws=[90.0] * 4, pitches=[-45.0] * 4, focal=24.0)
    b = _flight("DJI_0002", 10.01, 20.0, [50.0] * 4,
                yaws=[90.0] * 4, pitches=[-45.0] * 4, focal=24.0)
    serve_map(flights_to_3d_html([a, b], "trip"))
    _ready(page)
    vis = "(id) => map.getLayoutProperty(id, 'visibility') || 'visible'"
    assert page.evaluate("() => pb.run.name") == "DJI_0001"
    page.locator("#flights-panel input[type=checkbox]").first.uncheck()
    assert page.evaluate(vis, "gaze-fill") == "none"
    page.evaluate("() => { const s = document.getElementById('pb-flight');"
                 " s.value = '1'; s.dispatchEvent(new Event('change')); }")
    assert page.evaluate("() => pb.run.name") == "DJI_0002"
    assert page.evaluate(vis, "gaze-fill") == "visible", (
        "gaze-fill stayed 'none' after switching to a shown flight")
    assert page.evaluate(vis, "gaze-edge") == "visible"
    assert page.evaluate(vis, "gaze-cursor-dot") == "visible"


def test_hiding_any_flight_clears_an_onscreen_highlight(serve_map, page):
    """M1 (#378 whole-branch review): gaze-hits-line has no single pb.run to
    follow -- a lookup highlight can span several flights at once, so tying
    its visibility to whichever flight is selected in the picker either
    hides a highlight that still belongs to a visible flight, or leaves one
    drawn for a flight the user just hid. This project's chosen fix is the
    simple one the review explicitly sanctions: any panel toggle clears the
    highlight outright rather than trying to work out which of its passes
    still belong to a shown flight. It can always be reopened by clicking
    the spot again."""
    track = _flight("DJI_0001", 10.0, 20.0, [50.0] * 6,
                    yaws=[90.0] * 6, pitches=[-90.0] * 6, focal=24.0)
    serve_map(flights_to_3d_html([track], "trip"))
    _ready(page)
    _click_inside_ring(page, 2)
    page.wait_for_selector(".maplibregl-popup", timeout=5000)
    page.wait_for_function(
        "() => map.querySourceFeatures('gaze-hits').length > 0", timeout=5000)
    page.locator("#flights-panel input[type=checkbox]").first.uncheck()
    # GeoJSON source tiles build asynchronously (see _wait_patch above), so
    # wait rather than sampling the instant after setData.
    page.wait_for_function(
        "() => map.querySourceFeatures('gaze-hits').length === 0",
        timeout=5000)
