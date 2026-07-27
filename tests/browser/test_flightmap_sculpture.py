"""Flight sculpture (#375): AGL curtain + true-altitude ribbon in 3D."""

from datetime import datetime, timedelta

import pytest

pytest.importorskip("playwright")

from dji_metadata_embedder.geo.flightmap3d_html import flights_to_3d_html  # noqa: E402
from dji_metadata_embedder.geo.track import Track, TrackPoint  # noqa: E402

pytestmark = pytest.mark.browser

TILE_DEG = 360 / 2 ** 15   # z15 tile width; DEM cliff sits at each midpoint


def _flight(name: str, lat: float, lon: float, agls: list[float | None],
            step: float = 0.0006) -> Track:
    """Synthetic flight; ``agls[i]`` becomes point i's rel_alt (AGL)."""
    t0 = datetime(2026, 6, 15, 12, 0, 0)
    return Track(name=name, points=[
        TrackPoint(lat=lat, lon=lon + i * step, alt=100.0 + (a or 0),
                   timestamp=f"00:00:{i:02d},000",
                   utc=t0 + timedelta(seconds=i * 1.0), rel_alt=a)
        for i, a in enumerate(agls)
    ])


_PROBE_JS = """
(() => {
  window.__probe = (lon, lat) => {
    map.addSource('probe', { type: 'geojson', data: {
      type: 'Feature', properties: {},
      geometry: { type: 'Polygon', coordinates: [[
        [lon - 0.001, lat - 0.001], [lon + 0.001, lat - 0.001],
        [lon + 0.001, lat + 0.001], [lon - 0.001, lat + 0.001],
        [lon - 0.001, lat - 0.001]]] } } });
    // Pure green: no PALETTE entry can be mistaken for it, so a flight's
    // own sculpture cannot pollute the count.
    map.addLayer({ id: 'probe', type: 'fill-extrusion', source: 'probe',
      paint: { 'fill-extrusion-color': '#00ff00',
               'fill-extrusion-base': 0, 'fill-extrusion-height': 100,
               'fill-extrusion-opacity': 1 } });
  };
  window.__probeCount = () => {
    const gc = map.getCanvas();
    const c = document.createElement('canvas');
    c.width = gc.width; c.height = gc.height;
    c.getContext('2d').drawImage(gc, 0, 0);
    const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
    let n = 0;
    for (let i = 0; i < d.length; i += 4) {
      if (d[i] < 60 && d[i + 1] > 200 && d[i + 2] < 60) n++;
    }
    return n;
  };
})();
"""

_PRESERVE_JS = """
(() => {
  const orig = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (type, attrs) {
    if (type && type.indexOf('webgl') === 0) {
      attrs = Object.assign({}, attrs, { preserveDrawingBuffer: true });
    }
    return orig.call(this, type, attrs);
  };
})();
"""


def test_terrain_occludes_fill_extrusion(serve_map, page):
    """A 600 m cliff between camera and target must hide the target."""
    lat = 10.0
    tile_lon = TILE_DEG * 1660          # an arbitrary tile's left edge
    cam_lon = tile_lon + TILE_DEG * 0.2      # low half of this tile
    target_lon = tile_lon + TILE_DEG * 1.2   # low half of the NEXT tile
    page.add_init_script(_PRESERVE_JS)
    html = flights_to_3d_html([_flight("DJI_0001", lat, cam_lon, [10.0] * 5)],
                              "trip")
    serve_map(html, terrain_steps=(0.0, 600.0))
    page.wait_for_function(
        "() => typeof map !== 'undefined' && map && map.isStyleLoaded()",
        timeout=20000)
    page.evaluate(_PROBE_JS)
    page.evaluate("a => window.__probe(a[0], a[1])", [target_lon, lat])
    # Stand at 20 m in the valley and look horizontally down it.
    page.evaluate(
        "a => { map.setMaxPitch(100); map.jumpTo("
        "map.calculateCameraOptionsFromCameraLngLatAltRotation("
        "[a[0], a[1]], 20, 90, 88, 0)); }", [cam_lon, lat])
    page.wait_for_function("() => map.loaded() && !map.isMoving()",
                           timeout=20000)
    page.wait_for_timeout(2000)
    occluded = page.evaluate("() => window.__probeCount()")

    map_off = "() => { map.setTerrain(null); map.triggerRepaint(); }"
    page.evaluate(map_off)
    page.wait_for_timeout(2000)
    visible = page.evaluate("() => window.__probeCount()")

    print(f"\nOCCLUSION PROBE: terrain on={occluded} px, off={visible} px")
    assert visible > 0, "control failed: target invisible even without terrain"
    assert occluded == 0, (
        f"terrain did NOT occlude the extrusion ({occluded} px visible "
        "behind a 600 m cliff)"
    )


def test_sculpture_layers_exist(serve_map, page):
    html = flights_to_3d_html(
        [_flight("DJI_0001", 10.0, 20.0, [5.0, 20.0, 45.0, 30.0, 12.0])],
        "trip")
    serve_map(html)
    page.wait_for_function(
        "() => typeof map !== 'undefined' && map"
        " && map.getLayer('sculpt-0-curtain')", timeout=15000)
    assert page.evaluate(
        "() => map.getLayer('sculpt-0-curtain').type") == "fill-extrusion"
    assert page.evaluate(
        "() => map.getLayer('sculpt-0-ribbon').type") == "fill-extrusion"


def test_source_is_populated_from_the_flight(serve_map, page):
    """The planks actually reach the map source, not just the builder."""
    html = flights_to_3d_html(
        [_flight("DJI_0001", 10.0, 20.0, [5.0, 20.0, 45.0, 30.0, 12.0])],
        "trip")
    serve_map(html)
    page.wait_for_function(
        "() => typeof map !== 'undefined' && map"
        " && map.getLayer('sculpt-0-curtain')", timeout=15000)
    page.wait_for_function(
        "() => map.querySourceFeatures('sculpt-0').length > 0", timeout=15000)


def test_curtain_height_tracks_agl(serve_map, page):
    agls = [5.0, 20.0, 45.0, 30.0, 12.0]
    html = flights_to_3d_html([_flight("DJI_0001", 10.0, 20.0, agls)], "trip")
    serve_map(html)
    page.wait_for_function(
        "() => typeof map !== 'undefined' && map"
        " && map.getLayer('sculpt-0-curtain')", timeout=15000)
    # planksFor is called directly rather than querySourceFeatures, which
    # can return the same plank once per covering tile.
    peak = page.evaluate(
        "() => Math.max.apply(null,"
        " planksFor(flights[0], 10).map(f => f.properties.hgt))")
    # Segment AGL is the mean of its endpoints, so the tallest plank is the
    # mean of the two highest adjacent samples: (20+45)/2 and (45+30)/2 -> 37.5
    assert abs(peak - 37.5) < 0.1


def test_ribbon_base_never_negative(serve_map, page):
    """A hover below the ribbon thickness must not compute a negative base."""
    html = flights_to_3d_html(
        [_flight("DJI_0001", 10.0, 20.0, [1.0, 2.0, 1.5, 2.5, 1.0])], "trip")
    serve_map(html)
    page.wait_for_function(
        "() => typeof map !== 'undefined' && map"
        " && map.getLayer('sculpt-0-curtain')", timeout=15000)
    lo = page.evaluate(
        "() => Math.min.apply(null,"
        " planksFor(flights[0], 10).map(f => f.properties.rbase))")
    assert lo == 0


def test_flight_without_agl_gets_no_sculpture(serve_map, page):
    html = flights_to_3d_html(
        [_flight("DJI_0001", 10.0, 20.0, [None] * 5)], "trip")
    serve_map(html)
    page.wait_for_function(
        "() => typeof map !== 'undefined' && map && map.getLayer('flight-0')",
        timeout=15000)
    assert page.evaluate("() => !!map.getLayer('sculpt-0-curtain')") is False


def test_single_fix_flight_gets_no_sculpture(serve_map, page):
    """A one-point flight is a Point feature: no segments, no sculpture."""
    html = flights_to_3d_html([_flight("DJI_0001", 10.0, 20.0, [12.0])],
                              "trip")
    serve_map(html)
    page.wait_for_function(
        "() => typeof map !== 'undefined' && map && map.getLayer('flight-0')",
        timeout=15000)
    assert page.evaluate("() => !!map.getLayer('sculpt-0-curtain')") is False


def test_null_agl_point_breaks_the_curtain(serve_map, page):
    """A null AGL splits the curtain rather than interpolating across it."""
    html = flights_to_3d_html(
        [_flight("DJI_0001", 10.0, 20.0, [10.0, 10.0, None, 10.0, 10.0])],
        "trip")
    serve_map(html)
    page.wait_for_function(
        "() => typeof map !== 'undefined' && map"
        " && map.getLayer('sculpt-0-curtain')", timeout=15000)
    # 4 possible segments; the two touching the null point are dropped.
    assert page.evaluate("() => planksFor(flights[0], 10).length") == 2


def test_sculpture_paint_properties_are_wired_correctly(serve_map, page):
    """Pin the actual paint expressions, not just that the layers exist."""
    html = flights_to_3d_html(
        [_flight("DJI_0001", 10.0, 20.0, [5.0, 20.0, 45.0, 30.0, 12.0])],
        "trip")
    serve_map(html)
    page.wait_for_function(
        "() => typeof map !== 'undefined' && map"
        " && map.getLayer('sculpt-0-curtain')", timeout=15000)
    curtain_base = page.evaluate(
        "() => map.getPaintProperty('sculpt-0-curtain', 'fill-extrusion-base')")
    curtain_height = page.evaluate(
        "() => map.getPaintProperty('sculpt-0-curtain', 'fill-extrusion-height')")
    ribbon_base = page.evaluate(
        "() => map.getPaintProperty('sculpt-0-ribbon', 'fill-extrusion-base')")
    ribbon_height = page.evaluate(
        "() => map.getPaintProperty('sculpt-0-ribbon', 'fill-extrusion-height')")
    # opacity and vertical-gradient are the only two paint properties that
    # distinguish the translucent curtain from the solid ribbon: without
    # pinning them, swapping the two layers' paint would still pass every
    # other assertion in this test.
    curtain_opacity = page.evaluate(
        "() => map.getPaintProperty("
        "'sculpt-0-curtain', 'fill-extrusion-opacity')")
    curtain_gradient = page.evaluate(
        "() => map.getPaintProperty("
        "'sculpt-0-curtain', 'fill-extrusion-vertical-gradient')")
    ribbon_opacity = page.evaluate(
        "() => map.getPaintProperty("
        "'sculpt-0-ribbon', 'fill-extrusion-opacity')")
    ribbon_gradient = page.evaluate(
        "() => map.getPaintProperty("
        "'sculpt-0-ribbon', 'fill-extrusion-vertical-gradient')")
    assert curtain_base == 0
    assert curtain_height == ["get", "hgt"]
    assert ribbon_base == ["get", "rbase"]
    assert ribbon_height == ["get", "hgt"]
    assert curtain_opacity == 0.35
    assert curtain_gradient is True
    assert ribbon_opacity == 1
    assert ribbon_gradient is False


def test_ribbon_base_is_exactly_agl_minus_ribbon_thickness_when_tall(
        serve_map, page):
    """A tall segment's rbase must track hgt - 6 exactly.

    ``test_ribbon_base_never_negative`` uses a fixture where every segment
    clamps to 0, so a constant ``rbase: 0`` implementation would satisfy it.
    This picks AGLs well above the 6 m ribbon thickness so the clamp never
    engages, forcing the real formula.
    """
    agls = [50.0, 80.0, 120.0, 90.0, 60.0]
    html = flights_to_3d_html([_flight("DJI_0001", 10.0, 20.0, agls)], "trip")
    serve_map(html)
    page.wait_for_function(
        "() => typeof map !== 'undefined' && map"
        " && map.getLayer('sculpt-0-curtain')", timeout=15000)
    planks = page.evaluate("() => planksFor(flights[0], 10)")
    assert len(planks) == 4
    for plank in planks:
        props = plank["properties"]
        assert props["rbase"] == pytest.approx(props["hgt"] - 6)


def test_zooming_out_widens_planks_in_metres(serve_map, page):
    html = flights_to_3d_html(
        [_flight("DJI_0001", 10.0, 20.0, [10.0] * 5)], "trip")
    serve_map(html)
    page.wait_for_function(
        "() => typeof map !== 'undefined' && map && map.getLayer("
        "'sculpt-0-curtain')", timeout=15000)
    page.evaluate("() => map.jumpTo({zoom: 16})")
    page.wait_for_function("() => !map.isMoving()", timeout=15000)
    near = page.evaluate("() => sculpture.widthM")
    page.evaluate("() => map.jumpTo({zoom: 11})")
    page.wait_for_function("() => !map.isMoving()", timeout=15000)
    far = page.evaluate("() => sculpture.widthM")
    assert far > near, f"planks did not widen when zooming out: {near} -> {far}"
    assert far <= 60 and near >= 4, "width escaped its clamp"


def test_negative_agl_segments_produce_no_planks(serve_map, page):
    """Finding 1 regression guard: a below-takeoff segment breaks the curtain.

    A rooftop/cliff-top launch can log a negative rel_alt (the repo's own
    golden fixture carries rel_alt: -400.0). fill-extrusion cannot render
    below the terrain surface, so a segment whose mean AGL is negative must
    be dropped exactly like a null-AGL segment is.
    """
    html = flights_to_3d_html(
        [_flight("DJI_0001", 10.0, 20.0, [10.0, -400.0, 10.0, 10.0, 10.0])],
        "trip")
    serve_map(html)
    page.wait_for_function(
        "() => typeof map !== 'undefined' && map && map.getLayer('flight-0')",
        timeout=15000)
    # 4 possible segments; the two touching the negative-mean-AGL point
    # (indices 0-1 and 1-2) are dropped, leaving 2.
    assert page.evaluate("() => planksFor(flights[0], 10).length") == 2


def test_height_converts_to_true_altitude_over_terrain(serve_map, page):
    """Crossing from a 600 m plateau into a valley must lengthen the curtain.

    The drone holds its height above takeoff, so its clearance over the
    valley floor is 600 m greater than over the plateau it launched from.
    """
    lat = 10.0
    tile_lon = TILE_DEG * 1660
    # queryTerrainElevation resolves DEM tiles one zoom level coarser than
    # the source's maxzoom (empirically verified: probing terrainElevAt
    # across this stub shows a clean 0/600 step every TWO z15 tile-widths,
    # not one), so the low/high split actually falls a full tile-width east
    # of tile_lon rather than mid-tile. Start on the high side of that
    # boundary and walk east into the low side.
    start_lon = tile_lon + TILE_DEG * 1.75          # high side
    step = TILE_DEG * 0.12                          # ~5 steps into the valley
    html = flights_to_3d_html(
        [_flight("DJI_0001", lat, start_lon, [50.0] * 6, step=step)], "trip")
    serve_map(html, terrain_steps=(0.0, 600.0))
    page.wait_for_function(
        "() => typeof map !== 'undefined' && map && map.getLayer("
        "'sculpt-0-curtain')", timeout=20000)
    page.wait_for_function(
        "() => map.getTerrain() && map.areTilesLoaded()", timeout=20000)
    page.evaluate("() => setSculptData()")
    hs = page.evaluate(
        "() => planksFor(flights[0], 10).map(f => f.properties.hgt)")
    assert hs, "no planks built"
    # Plateau segments: ~50 m of clearance. Valley segments: ~650 m.
    assert min(hs) < 200, f"no plateau-height planks: {hs}"
    assert max(hs) > 500, f"height was not converted to true altitude: {hs}"


def test_true_altitude_reaches_the_source(serve_map, page):
    """The converted heights must land in the map source, not just planksFor.

    ``test_height_converts_to_true_altitude_over_terrain`` reads planksFor(...)
    directly, which proves the conversion formula but not that it actually
    reaches map.getSource(...). querySourceFeatures can return the same plank
    once per covering tile, but that does not matter for a max().
    """
    lat = 10.0
    tile_lon = TILE_DEG * 1660
    start_lon = tile_lon + TILE_DEG * 1.75          # high side
    step = TILE_DEG * 0.12                          # ~5 steps into the valley
    html = flights_to_3d_html(
        [_flight("DJI_0001", lat, start_lon, [50.0] * 6, step=step)], "trip")
    serve_map(html, terrain_steps=(0.0, 600.0))
    page.wait_for_function(
        "() => typeof map !== 'undefined' && map && map.getLayer("
        "'sculpt-0-curtain')", timeout=20000)
    page.wait_for_function(
        "() => map.getTerrain() && map.areTilesLoaded()", timeout=20000)
    page.evaluate("() => setSculptData()")
    hs = page.evaluate(
        "() => map.querySourceFeatures('sculpt-0')"
        ".map(f => f.properties.hgt)")
    assert hs, "no features in source"
    assert max(hs) > 500, f"true altitude did not reach the source: {hs}"


def _vis(page, layer="sculpt-0-curtain"):
    return page.evaluate(
        "id => map.getLayoutProperty(id, 'visibility') || 'visible'", layer)


def test_global_toggle_hides_and_restores_sculpture(serve_map, page):
    html = flights_to_3d_html(
        [_flight("DJI_0001", 10.0, 20.0, [10.0] * 5)], "trip")
    serve_map(html)
    page.wait_for_selector("#sculpture-toggle", timeout=15000)
    assert _vis(page) == "visible"
    page.locator("#sculpture-toggle").uncheck()
    assert _vis(page) == "none"
    assert _vis(page, "sculpt-0-ribbon") == "none"
    page.locator("#sculpture-toggle").check()
    assert _vis(page) == "visible"


def test_per_flight_checkbox_hides_its_sculpture(serve_map, page):
    html = flights_to_3d_html(
        [_flight("DJI_0001", 10.0, 20.0, [10.0] * 5),
         _flight("DJI_0002", 11.0, 21.0, [10.0] * 5)], "trip")
    serve_map(html)
    page.wait_for_selector("#sculpture-toggle", timeout=15000)
    page.locator("#flights-panel input[type=checkbox]").first.uncheck()
    assert _vis(page, "sculpt-0-curtain") == "none"
    assert _vis(page, "sculpt-1-curtain") == "visible"


def test_per_flight_state_survives_a_global_cycle(serve_map, page):
    """Re-enabling the sculpture must not un-hide an unchecked flight."""
    html = flights_to_3d_html(
        [_flight("DJI_0001", 10.0, 20.0, [10.0] * 5),
         _flight("DJI_0002", 11.0, 21.0, [10.0] * 5)], "trip")
    serve_map(html)
    page.wait_for_selector("#sculpture-toggle", timeout=15000)
    page.locator("#flights-panel input[type=checkbox]").first.uncheck()
    page.locator("#sculpture-toggle").uncheck()
    page.locator("#sculpture-toggle").check()
    assert _vis(page, "sculpt-0-curtain") == "none"
    assert _vis(page, "sculpt-1-curtain") == "visible"


def test_no_toggle_when_no_flight_has_agl(serve_map, page):
    html = flights_to_3d_html(
        [_flight("DJI_0001", 10.0, 20.0, [None] * 5)], "trip")
    serve_map(html)
    page.wait_for_selector("#flights-panel", timeout=15000)
    assert page.locator("#sculpture-toggle").count() == 0


def test_ghost_mode_hides_sculpture_and_exit_restores_it(serve_map, page):
    html = flights_to_3d_html(
        [_flight("DJI_0001", 10.0, 20.0, [10.0] * 5)], "trip")
    serve_map(html)
    page.wait_for_selector("#sculpture-toggle", timeout=15000)
    assert _vis(page) == "visible"
    page.evaluate("() => ghostEnter(0, 2)")
    assert _vis(page) == "none"
    page.evaluate("() => ghostExit()")
    # The exit ease still has the camera up at the drone's altitude; the
    # ribbon must not pop back until that ease actually finishes.
    assert _vis(page) == "none"
    page.wait_for_function("() => !map.isMoving()", timeout=15000)
    assert _vis(page) == "visible"


def test_sculpt_settle_repopulates_a_wiped_source_within_budget(serve_map, page):
    """sculptSettle() must rebuild a wiped source with converted heights
    inside its own 5 s retry budget.

    This drives the loop deterministically rather than reproducing genuinely
    cold DEM tiles: a real delayed-tile fixture (``time.sleep`` in the
    Playwright route handler that serves DEM tiles) was tried first and
    abandoned, because Playwright's sync route handlers share one dispatcher
    thread, so sleeping in one stalls every other intercepted request on the
    page -- reproducibly, across three runs, a single 3 s per-tile delay
    stalled unrelated Playwright calls (e.g. a plain ``queryTerrainElevation``
    evaluate) for ~40 s and blew past the loop's real 5 s wall-clock budget
    before the delayed tile ever arrived, so the source stayed permanently
    in flat mode and the "recovers from cold tiles" behaviour was never
    actually observed. This test instead proves the loop runs, terminates,
    and rebuilds once the terrain is already warm -- it does NOT prove it
    recovers from genuinely cold tiles.
    """
    lat = 10.0
    tile_lon = TILE_DEG * 1660
    # Same longitudes and 600 m signal as
    # test_height_converts_to_true_altitude_over_terrain: start_lon sits on
    # the 600 m plateau, so a warm probe there reads a non-zero elevation --
    # the same signal sculptSettle() itself uses to know it can stop
    # retrying (a genuine 0 m reading is treated as still-cold).
    start_lon = tile_lon + TILE_DEG * 1.75          # high side (plateau)
    step = TILE_DEG * 0.12                          # ~5 steps into the valley
    html = flights_to_3d_html(
        [_flight("DJI_0001", lat, start_lon, [50.0] * 6, step=step)], "trip")
    serve_map(html, terrain_steps=(0.0, 600.0))
    page.wait_for_function(
        "() => typeof map !== 'undefined' && map && map.getLayer("
        "'sculpt-0-curtain')", timeout=20000)
    page.wait_for_function(
        "() => map.getTerrain() && map.areTilesLoaded()", timeout=20000)
    page.evaluate("() => setSculptData()")
    hs_before = page.evaluate(
        "() => map.querySourceFeatures('sculpt-0')"
        ".map(f => f.properties.hgt)")
    assert hs_before and max(hs_before) > 500, (
        f"fixture was not warm before the wipe: {hs_before}")

    page.evaluate(
        "() => map.getSource('sculpt-0')"
        ".setData({type: 'FeatureCollection', features: []})")
    page.wait_for_function(
        "() => map.querySourceFeatures('sculpt-0').length === 0",
        timeout=5000)

    page.evaluate("() => sculptSettle()")
    # sculptSettle's own budget is 20 tries x 250 ms = 5 s; assert the
    # rebuild lands inside that budget rather than polling indefinitely.
    page.wait_for_function(
        "() => map.querySourceFeatures('sculpt-0').length > 0", timeout=5500)
    hs_after = page.evaluate(
        "() => map.querySourceFeatures('sculpt-0')"
        ".map(f => f.properties.hgt)")
    assert hs_after, "settle did not repopulate the source"
    assert max(hs_after) > 500, (
        f"settle rebuilt without converting to true altitude: {hs_after}")


def test_ghost_exit_respects_a_disabled_sculpture(serve_map, page):
    """Leaving ghost mode must not switch a hidden sculpture back on."""
    html = flights_to_3d_html(
        [_flight("DJI_0001", 10.0, 20.0, [10.0] * 5)], "trip")
    serve_map(html)
    page.wait_for_selector("#sculpture-toggle", timeout=15000)
    page.locator("#sculpture-toggle").uncheck()
    page.evaluate("() => ghostEnter(0, 2)")
    page.evaluate("() => ghostExit()")
    assert _vis(page) == "none"


def test_empty_build_still_gets_a_source_and_toggle(serve_map, page):
    """A flight whose build legitimately yields zero planks must not be
    stranded without a source (the canopy/DSM bug this pins).

    addSculpture() gates on the DATA (does this flight have any AGL at
    all?), not on the build's OUTPUT, precisely so a later settle can
    still repopulate an empty source -- and so the panel's global
    Sculpture checkbox (gated on `flights.some(f => f.sculptSrc)`) does
    not vanish just because every segment was momentarily unbuildable.

    Takeoff sits on the low (0 m) side of the stepped DEM with a small
    AGL -- it anchors takeoffElev. The one segment's midpoint sits on the
    high (600 m) side, so hgt = (0 + agl) - 600 is deeply negative and the
    segment is dropped: probed empirically (see below) at
    takeoff offset 2.25 -> takeoffElev == 0, segment-midpoint offset 1.75
    -> terrainElevAt == 600, planksFor(...).length == 0. The final
    assertion is what stops this test passing vacuously -- without it, a
    build that happened to produce planks would still satisfy every other
    assertion here.

    None of the above actually pins the gate fix, though: addSculpture()
    runs inside map.on('load'), right after setTerrain, while this
    fixture's DEM tiles are still cold. Cold queryTerrainElevation answers
    0 (not null), so tElev == lElev == 0 there and the conversion collapses
    to hgt = agl -- positive for this fixture's AGL. That load-time build
    is therefore never actually empty, so the source/layer/toggle
    assertions above pass identically whether or not the old
    `if (!feats.length) return;` bail is present. To pin the fix itself,
    this also calls addSculpture() directly -- once terrain has genuinely
    warmed -- on a synthetic flight object (reusing flight 0's own
    geometry, which by then yields zero planks) at an unused index,
    exercising the gate against a build that is provably empty. This
    proves addSculpture()'s gate directly rather than through the load
    path; it does not exercise the panel toggle's survival of an empty
    build, because the panel is built once at load time, when the build is
    never empty -- that path remains unproven.
    """
    lat = 10.0
    tile_lon = TILE_DEG * 1660
    # Offsets probed directly against this stub: [1.0, 2.0) tile-widths
    # read 600 m, [2.0, 3.0) read 0 m, repeating every two z15 tile-widths
    # (same stepping test_height_converts_to_true_altitude_over_terrain
    # relies on). Takeoff at offset 2.25 sits 0.25 inside the low band;
    # walking to offset 1.25 puts the only segment's midpoint at 1.75,
    # 0.25 inside the high band -- the same margin already proven robust
    # by that other test's own start_lon.
    takeoff_lon = tile_lon + TILE_DEG * 2.25   # low (0 m) side
    step = TILE_DEG * (1.25 - 2.25)            # negative: walk to the high side
    html = flights_to_3d_html(
        [_flight("DJI_0001", lat, takeoff_lon, [5.0, 5.0], step=step)],
        "trip")
    serve_map(html, terrain_steps=(0.0, 600.0))
    page.wait_for_function(
        "() => typeof map !== 'undefined' && map && map.getLayer("
        "'sculpt-0-curtain')", timeout=20000)
    page.wait_for_function(
        "() => map.getTerrain() && map.areTilesLoaded()", timeout=20000)
    assert page.evaluate("() => !!map.getSource('sculpt-0')")
    assert page.evaluate("() => !!map.getLayer('sculpt-0-curtain')")
    assert page.evaluate("() => !!map.getLayer('sculpt-0-ribbon')")
    assert page.locator("#sculpture-toggle").count() == 1
    assert page.evaluate("() => planksFor(flights[0], 10).length") == 0

    # Pin the gate itself: the load-time build above was never actually
    # empty (see docstring), so call addSculpture() again now that terrain
    # is warm, on a synthetic flight reusing flight 0's own now-empty
    # geometry at an unused index. This does not touch the global `flights`
    # array or any DOM/panel state -- addSculpture() is self-contained.
    page.evaluate(
        "() => addSculpture("
        "{pts: flights[0].pts, agl: flights[0].agl, color: '#ff0000'}, 9)")
    assert page.evaluate("() => !!map.getSource('sculpt-9')")
    assert page.evaluate("() => !!map.getLayer('sculpt-9-curtain')")
    assert page.evaluate("() => !!map.getLayer('sculpt-9-ribbon')")


def test_rapid_ghost_cycle_restores_correctly(serve_map, page):
    """Re-entering ghost mid-exit-ease must not corrupt the eventual restore.

    #375 fixed a real defect where the sculpture restore ran synchronously
    at the top of ghostExit(), popping the ribbon back into view while the
    camera was still up at drone altitude mid-ease. The fix defers the
    restore into the exit ease's own 'moveend', guarded by
    `if (ghost.active) return` so the stale moveend from an ease that a
    rapid re-entry aborts cannot fire the restore early. This drives
    exactly that interleaving: enter, exit, re-enter while the first 1.2 s
    exit ease is still running, exit again, then let it genuinely settle.

    The exit, the isMoving()/visibility capture, and the re-entering
    ghostEnter() are collapsed into a single page.evaluate() rather than
    three separate Python round-trips. easeTo() starts its ease
    synchronously, so isMoving() is guaranteed true immediately after
    ghostExit() returns within the same JS turn -- but a Python round-trip
    between the calls opens a real timing window (observed to flake under
    CPU contention -- see task-2-report.md) in which the 1.2 s exit ease
    can finish before the re-entry lands, so the test would stop exercising
    the interrupted-moveend path it exists to pin.
    """
    html = flights_to_3d_html(
        [_flight("DJI_0001", 10.0, 20.0, [10.0] * 5)], "trip")
    serve_map(html)
    page.wait_for_selector("#sculpture-toggle", timeout=15000)
    assert _vis(page) == "visible"

    page.evaluate("() => ghostEnter(0, 2)")
    assert _vis(page) == "none"

    # Single evaluate: exit, capture visibility + isMoving, then re-enter --
    # no Python round-trip can open a window between the exit ease starting
    # and the re-entry landing inside it. The visibility read inlines what
    # _vis() does, because _vis() cannot be called from inside this JS turn.
    result = page.evaluate(
        "() => { ghostExit();"
        " const visAfterExit = map.getLayoutProperty("
        "'sculpt-0-curtain', 'visibility') || 'visible';"
        " const wasMoving = map.isMoving();"
        " ghostEnter(0, 2);"
        " return { visAfterExit, wasMoving }; }")
    # The restore is deferred to moveend, so it must still be hidden here.
    assert result["visAfterExit"] == "none"
    # The interleaving needs no timing luck: easeTo() has the ease running
    # before ghostExit() returns, and nothing else can run before the
    # re-entry inside one synchronous evaluate. This guards the narrower
    # case that would make the whole sequence vacuous -- ghostExit()
    # early-returning on an already-inactive ghost, leaving no ease for the
    # re-entry to interrupt.
    assert result["wasMoving"], (
        "ghostExit() started no ease -- there was nothing for the "
        "re-entry to interrupt")
    assert _vis(page) == "none"

    page.evaluate("() => ghostExit()")
    assert _vis(page) == "none"

    page.wait_for_function("() => !map.isMoving()", timeout=15000)
    assert _vis(page) == "visible"
    # The interrupted first exit's stale moveend must not have re-enabled
    # the handlers early or left them disabled: confirm the genuine final
    # restore actually re-enabled camera interaction.
    assert page.evaluate(
        "() => ['dragPan', 'dragRotate', 'scrollZoom', 'keyboard',"
        " 'doubleClickZoom', 'touchZoomRotate']"
        ".every(h => map[h].isEnabled())"), (
        "camera interaction handlers were not re-enabled after settling")
