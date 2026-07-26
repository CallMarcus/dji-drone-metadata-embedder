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
