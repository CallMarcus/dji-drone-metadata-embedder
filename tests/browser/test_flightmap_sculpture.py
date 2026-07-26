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
        " planksFor(flights[0], 10).map(f => f.properties.agl))")
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
