"""Playback marker at the drone's true altitude (#553).

The draped cursor dot is the aircraft's SHADOW; nothing marked the aircraft
itself at height, so the beams looked like they hung down from the ribbon
with no body at the top. The marker is a small fill-extrusion prism centred
on the current position at the drone's true altitude, converted through the
#548 ground reference exactly as the sculpture is.
"""
from datetime import datetime, timedelta

import pytest

from dji_metadata_embedder.geo.flightmap3d_html import flights_to_3d_html  # noqa: E402
from dji_metadata_embedder.geo.track import Track, TrackPoint  # noqa: E402

pytestmark = pytest.mark.browser

TILE_DEG = 360 / 2 ** 15   # z15 tile width; the DEM cliff sits at each midpoint


def _flight(name: str, lat: float, lon: float, agls: list[float | None], *,
            step: float = 0.0006) -> Track:
    """Synthetic playable flight: ``agls[i]`` is point i's rel_alt, one
    sample a second, attitude fixed so the gaze layers have something."""
    t0 = datetime(2026, 6, 15, 12, 0, 0)
    return Track(name=name, points=[
        TrackPoint(lat=lat, lon=lon + i * step, alt=100.0 + (a or 0),
                   timestamp=f"00:00:{i:02d},000",
                   utc=t0 + timedelta(seconds=i), rel_alt=a,
                   focal_len=24.0, gimbal_yaw=90.0, gimbal_pitch=-45.0)
        for i, a in enumerate(agls)
    ])


def _ready(page):
    page.wait_for_selector("#flights-panel", timeout=15000)


_MARKER_JS = ("() => map.getSource('gaze-marker').serialize().data.features"
              ".map(f => ({base: f.properties.base, hgt: f.properties.hgt,"
              " ring: f.geometry.coordinates[0]}))")

_VIS = "(id) => map.getLayoutProperty(id, 'visibility') || 'visible'"


def _centre(ring):
    xs = [p[0] for p in ring[:-1]]
    ys = [p[1] for p in ring[:-1]]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def test_marker_layer_mounts_with_the_cursor_dot(serve_map, page):
    serve_map(flights_to_3d_html([_flight("DJI_0001", 10.0, 20.0, [50.0] * 6)],
                                 "trip"))
    _ready(page)
    assert page.evaluate("() => !!map.getLayer('gaze-cursor-dot')")
    assert page.evaluate("() => map.getLayer('gaze-marker-body').type") \
        == "fill-extrusion"


def test_marker_follows_the_slider_at_the_drones_height(serve_map, page):
    """Terrain off: the extrusion measures from sea level, so the prism must
    be centred on raw AGL, and its footprint on the interpolated position."""
    serve_map(flights_to_3d_html([_flight("DJI_0001", 10.0, 20.0, [50.0] * 6)],
                                 "trip"))
    _ready(page)
    page.evaluate("() => { pb.t = 2.5; pbRender(); }")
    feats = page.evaluate(_MARKER_JS)
    assert len(feats) == 1, feats
    f = feats[0]
    assert f["hgt"] > f["base"] >= 0
    assert abs((f["base"] + f["hgt"]) / 2 - 50.0) < 0.01, f
    want = page.evaluate("() => positionAt(pb.run, 2.5)")
    cx, cy = _centre(f["ring"])
    assert abs(cx - want[0]) < 1e-6 and abs(cy - want[1]) < 1e-6
    page.evaluate("() => { pb.t = 4; pbRender(); }")
    moved = _centre(page.evaluate(_MARKER_JS)[0]["ring"])
    assert moved[0] > cx, "marker did not move with the slider"


def test_marker_sits_at_true_altitude_over_the_terrain(serve_map, page):
    """Recording started airborne over a 600 m plateau, rel_alt 700 (the
    launch site is the valley floor, where the clip lands). The prism must
    be 100 m above the plateau: through the #548 ground reference, not the
    600 m under sample 0, which would put it 700 m up."""
    lat = 10.0
    tile_lon = TILE_DEG * 1660
    start_lon = tile_lon + TILE_DEG * 1.75          # high (600 m) side
    step = TILE_DEG * 0.12                          # walks east into the valley
    html = flights_to_3d_html(
        [_flight("DJI_0001", lat, start_lon,
                 [700.0, 700.0, 700.0, 3.0, 0.0, 0.0], step=step)], "trip")
    serve_map(html, terrain_steps=(0.0, 600.0))
    _ready(page)
    page.wait_for_function(
        "() => map.getTerrain() && map.areTilesLoaded()", timeout=20000)
    page.wait_for_function(
        "() => terrainElevAt(flights[0].pts[0]) > 599"
        " && Math.abs(groundRef(flights[0]).elev) < 1", timeout=20000)
    page.evaluate("() => { pb.t = 0; pbRender(); }")
    feats = page.evaluate(_MARKER_JS)
    assert len(feats) == 1, feats
    f = feats[0]
    assert abs((f["base"] + f["hgt"]) / 2 - 100.0) < 1.0, f


def test_marker_hides_in_the_cockpit(serve_map, page):
    """A block at your own eye would fill the frame, like the ribbon and the
    beam; it comes back on exit."""
    serve_map(flights_to_3d_html([_flight("DJI_0001", 10.0, 20.0, [50.0] * 6)],
                                 "trip"))
    _ready(page)
    assert page.evaluate(_VIS, "gaze-marker-body") == "visible"
    page.evaluate("() => ghostEnter(0, 2)")
    assert page.evaluate(_VIS, "gaze-marker-body") == "none"
    assert page.evaluate(_VIS, "gaze-cursor-dot") == "visible"
    page.evaluate("() => ghostExit()")
    page.wait_for_function("() => !map.isMoving()", timeout=15000)
    assert page.evaluate(_VIS, "gaze-marker-body") == "visible"


def test_marker_stays_up_when_riding_a_different_flight(serve_map, page):
    serve_map(flights_to_3d_html(
        [_flight("DJI_0001", 10.0, 20.0, [50.0] * 6),
         _flight("DJI_0002", 10.05, 20.05, [50.0] * 6)], "trip"))
    _ready(page)
    assert page.evaluate("() => pb.run === flights[0]") is True
    page.evaluate("() => ghostEnter(1, 0)")
    assert page.evaluate(_VIS, "gaze-marker-body") == "visible"


def test_marker_recolours_with_the_picked_flight(serve_map, page):
    serve_map(flights_to_3d_html(
        [_flight("DJI_0001", 10.0, 20.0, [50.0] * 6),
         _flight("DJI_0002", 10.05, 20.05, [50.0] * 6)], "trip"))
    _ready(page)
    page.select_option("#pb-flight", "1")
    colour = page.evaluate(
        "() => map.getPaintProperty('gaze-marker-body', 'fill-extrusion-color')")
    assert colour == page.evaluate("() => flights[1].color")


def test_no_marker_without_altitude(serve_map, page):
    """No AGL, no height claim: the shadow dot alone carries the position."""
    serve_map(flights_to_3d_html([_flight("DJI_0001", 10.0, 20.0, [None] * 6)],
                                 "trip"))
    _ready(page)
    page.evaluate("() => { pb.t = 2; pbRender(); }")
    assert page.evaluate(_MARKER_JS) == []
    assert page.evaluate(
        "() => map.getSource('gaze-cursor').serialize().data.geometry.type"
    ) == "Point"


def test_marker_follows_the_dot_under_fuzz(serve_map, page):
    """Fuzzed coordinates gate the gaze (a claim about filmed ground) but not
    the dot, and the marker claims no more than the dot does."""
    serve_map(flights_to_3d_html([_flight("DJI_0001", 10.0, 20.0, [50.0] * 6)],
                                 "trip", redact="fuzz"))
    _ready(page)
    assert page.evaluate("() => !map.getLayer('beam-ray')")
    assert page.evaluate("() => !!map.getLayer('gaze-marker-body')")
    page.evaluate("() => { pb.t = 2; pbRender(); }")
    assert len(page.evaluate(_MARKER_JS)) == 1
