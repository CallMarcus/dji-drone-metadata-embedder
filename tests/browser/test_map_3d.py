"""The combined map's 3D variant (#514) in a real headless Chromium.

Photo and pano pins are MapLibre circle layers over a clustered GeoJSON
source; tracks draw exactly as on the flightmap 3D page. The harness aborts
the Mapterhorn fetch, so every test runs on the flat-terrain fallback path
unless it opts into ``terrain_stub``; pins do not need terrain to render.
"""

import base64
import io
import re
from datetime import datetime, timedelta

import pytest

pytest.importorskip("playwright")
from PIL import Image
from playwright.sync_api import expect

from dji_metadata_embedder.geo.map_html import mixed_to_3d_html
from dji_metadata_embedder.geo.photomap import PhotoPoint
from dji_metadata_embedder.geo.track import Track, TrackPoint

pytestmark = pytest.mark.browser


def _jpeg_b64(width: int, height: int) -> str:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (30, 90, 160)).save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


_T0 = datetime(2026, 6, 15, 12, 0, 0)
LAT, LON = 34.0567, -84.1234
PHOTO = PhotoPoint(
    lat=LAT, lon=LON, alt=95.3, name="church.jpg", thumbnail_b64=_jpeg_b64(240, 120)
)
PANO = PhotoPoint(
    lat=LAT + 0.004,
    lon=LON + 0.004,
    alt=90.0,
    name="sky.jpg",
    thumbnail_b64=_jpeg_b64(240, 120),
    is_pano=True,
)
TRACK = Track(
    name="DJI_0001",
    points=[
        TrackPoint(
            lat=LAT + 0.001 + i * 0.0005,
            lon=LON + i * 0.0001,
            alt=5.0 + i,
            timestamp=f"00:00:{i:02d},000",
            utc=_T0 + timedelta(seconds=30 * i),
        )
        for i in range(4)
    ],
)

_READY = "() => typeof map !== 'undefined' && map && map.loaded()"


def _rendered(page, layer: str) -> int:
    return page.evaluate(
        "l => map.queryRenderedFeatures({ layers: [l] }).length", layer
    )


def _serve(serve_map, page, points, tracks, **kw):
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    serve_map(mixed_to_3d_html(points, tracks, "trip", **kw))
    page.wait_for_function(_READY, timeout=20000)
    return errors


def test_pins_and_track_render_together(serve_map, page):
    errors = _serve(serve_map, page, [PHOTO, PANO], [TRACK])
    page.wait_for_function(
        "() => map.getLayer('photo-pins') && "
        "map.queryRenderedFeatures({ layers: ['photo-pins'] }).length === 1",
        timeout=15000,
    )
    assert _rendered(page, "pano-pins") == 1
    assert page.evaluate("() => flights.length === 1 && !!map.getLayer('flight-0')")
    assert errors == []


def test_type_rows_toggle_the_pins(serve_map, page):
    _serve(serve_map, page, [PHOTO, PANO], [TRACK])
    page.wait_for_function(
        "() => map.getLayer('photo-pins') && "
        "map.queryRenderedFeatures({ layers: ['photo-pins'] }).length === 1",
        timeout=15000,
    )
    expect(page.locator("#photo-toggle")).to_be_checked()
    expect(page.locator("#pano-toggle")).to_be_checked()
    page.locator("#photo-toggle").uncheck()
    page.wait_for_function(
        "() => map.queryRenderedFeatures({ layers: ['photo-pins'] }).length === 0",
        timeout=10000,
    )
    assert _rendered(page, "pano-pins") == 1
    page.locator("#photo-toggle").check()
    page.wait_for_function(
        "() => map.queryRenderedFeatures({ layers: ['photo-pins'] }).length === 1",
        timeout=10000,
    )


def test_photos_only_page_boots_without_errors(serve_map, page):
    errors = _serve(serve_map, page, [PHOTO], [])
    expect(page.locator("#flights-panel")).to_be_visible(timeout=15000)
    assert page.locator("#flights-panel input[type=checkbox]").count() == 1
    expect(page.locator("#pano-toggle")).to_have_count(0)
    page.wait_for_function(
        "() => map.getLayer('photo-pins') && "
        "map.queryRenderedFeatures({ layers: ['photo-pins'] }).length === 1",
        timeout=15000,
    )
    # fitBounds landed on the pin, not on the (0, 20) world view.
    c = page.evaluate("() => map.getCenter()")
    assert abs(c["lat"] - LAT) < 0.01 and abs(c["lng"] - LON) < 0.01
    assert errors == []


def test_tracks_only_page_has_no_photo_rows(serve_map, page):
    _serve(serve_map, page, [], [TRACK])
    expect(page.locator("#flights-panel")).to_be_visible(timeout=15000)
    expect(page.locator("#photo-toggle")).to_have_count(0)
    assert page.evaluate("() => map.getSource('photos') === undefined")


def _click_feature(page, layer: str) -> None:
    """Click the screen position of the first rendered feature on *layer*."""
    pt = page.evaluate(
        "l => { const f = map.queryRenderedFeatures({ layers: [l] })[0];"
        " if (!f) throw new Error('no rendered feature on ' + l);"
        " const p = map.project(f.geometry.coordinates); return [p.x, p.y]; }",
        layer,
    )
    box = page.locator("#map canvas").first.bounding_box()
    page.mouse.click(box["x"] + pt[0], box["y"] + pt[1])


def test_photo_popup_shows_thumbnail_and_name(serve_map, page):
    _serve(serve_map, page, [PHOTO], [TRACK])
    page.wait_for_function(
        "() => map.getLayer('photo-pins') && "
        "map.queryRenderedFeatures({ layers: ['photo-pins'] }).length === 1",
        timeout=15000,
    )
    _click_feature(page, "photo-pins")
    popup = page.locator(".maplibregl-popup .photo-popup")
    expect(popup).to_be_visible(timeout=10000)
    expect(popup.locator("img")).to_have_attribute(
        "src", re.compile(r"^data:image/jpeg;base64,")
    )
    expect(popup).to_contain_text("church.jpg")


def test_cluster_expands_on_click(serve_map, page):
    # ~70 m apart: close enough to start as one cluster at the page's
    # opening (fitBounds) zoom, far enough that it fully expands at zoom 16
    # (well within CLUSTER_MAX_ZOOM), so this exercises the plain ease-in
    # path (#514 I2 only diverts a click when the expansion zoom lands
    # *past* that cap, covered separately by the co-located-photo tests
    # below).
    near = [
        PhotoPoint(lat=LAT, lon=LON, alt=1.0, name="a.jpg"),
        PhotoPoint(lat=LAT + 70 / 111320, lon=LON, alt=1.0, name="b.jpg"),
    ]
    _serve(serve_map, page, near, [])
    page.wait_for_function(
        "() => map.getLayer('photo-clusters') && "
        "map.queryRenderedFeatures({ layers: ['photo-clusters'] }).length === 1",
        timeout=15000,
    )
    assert _rendered(page, "photo-pins") == 0
    zoom_before = page.evaluate("() => map.getZoom()")
    _click_feature(page, "photo-clusters")
    page.wait_for_function(
        "() => !map.isMoving() && "
        "map.queryRenderedFeatures({ layers: ['photo-pins'] }).length === 2",
        timeout=15000,
    )
    assert page.evaluate("() => map.getZoom()") > zoom_before
    # The ease path opens no popup; that's reserved for the cluster-can't-
    # expand case.
    assert page.locator(".maplibregl-popup").count() == 0


def test_photo_click_does_not_also_open_the_flight_popup(serve_map, page):
    # A drone photo taken mid-flight sits on the track by construction; this
    # pins one exactly on TRACK's first point (#514 I1).
    on_track = PhotoPoint(
        lat=TRACK.points[0].lat,
        lon=TRACK.points[0].lon,
        alt=1.0,
        name="ontrack.jpg",
    )
    _serve(serve_map, page, [on_track], [TRACK])
    page.wait_for_function(
        "() => map.getLayer('photo-pins') && "
        "map.queryRenderedFeatures({ layers: ['photo-pins'] }).length === 1",
        timeout=15000,
    )
    _click_feature(page, "photo-pins")
    expect(page.locator(".maplibregl-popup")).to_have_count(1)
    expect(page.locator(".maplibregl-popup .photo-popup")).to_be_visible(timeout=10000)


def test_colocated_photos_open_together_from_cluster(serve_map, page):
    same = [
        PhotoPoint(lat=LAT, lon=LON, alt=1.0, name="a.jpg"),
        PhotoPoint(lat=LAT, lon=LON, alt=1.0, name="b.jpg"),
    ]
    _serve(serve_map, page, same, [])
    page.wait_for_function(
        "() => map.getLayer('photo-clusters') && "
        "map.queryRenderedFeatures({ layers: ['photo-clusters'] }).length === 1",
        timeout=15000,
    )
    _click_feature(page, "photo-clusters")
    popup = page.locator(".maplibregl-popup")
    expect(popup.locator(".photo-popup")).to_have_count(2, timeout=10000)
    expect(popup).to_contain_text("2 photos here")
    # Identical points never separate, however far the cluster is asked to
    # expand, so the fix must list them rather than ease past clusterMaxZoom.
    assert page.evaluate("() => map.getZoom()") <= 17


def test_colocated_photos_open_together_from_pins(serve_map, page):
    same = [
        PhotoPoint(lat=LAT, lon=LON, alt=1.0, name="a.jpg"),
        PhotoPoint(lat=LAT, lon=LON, alt=1.0, name="b.jpg"),
    ]
    _serve(serve_map, page, same, [])
    page.wait_for_function("() => map.getLayer('photo-clusters')", timeout=15000)
    # Past clusterMaxZoom the source stops clustering, so both identical
    # points render as separate photo-pins features stacked on one pixel.
    page.evaluate(
        "([lon, lat]) => map.jumpTo({ center: [lon, lat], zoom: 19 })",
        [LON, LAT],
    )
    page.wait_for_function(
        "() => map.getLayer('photo-pins') && "
        "map.queryRenderedFeatures({ layers: ['photo-pins'] }).length === 2",
        timeout=15000,
    )
    _click_feature(page, "photo-pins")
    popup = page.locator(".maplibregl-popup")
    expect(popup.locator(".photo-popup")).to_have_count(2, timeout=10000)


def test_colocated_photo_and_pano_open_in_one_popup(serve_map, page):
    """A photo and a pano at the same point live on different pin layers;
    one click must still open one popup listing both, not one per layer."""
    same = [
        PhotoPoint(lat=LAT, lon=LON, alt=1.0, name="a.jpg"),
        PhotoPoint(lat=LAT, lon=LON, alt=1.0, name="b.jpg", is_pano=True),
    ]
    _serve(serve_map, page, same, [])
    page.wait_for_function("() => map.getLayer('photo-clusters')", timeout=15000)
    page.evaluate(
        "([lon, lat]) => map.jumpTo({ center: [lon, lat], zoom: 19 })",
        [LON, LAT],
    )
    page.wait_for_function(
        "() => map.getLayer('pano-pins') && "
        "map.queryRenderedFeatures({ layers: ['photo-pins', 'pano-pins'] })"
        ".length === 2",
        timeout=15000,
    )
    _click_feature(page, "pano-pins")
    expect(page.locator(".maplibregl-popup")).to_have_count(1, timeout=10000)
    popup = page.locator(".maplibregl-popup")
    expect(popup.locator(".photo-popup")).to_have_count(2)
    expect(popup).to_contain_text("2 photos here")


def test_pano_popup_opens_the_viewer_overlay(serve_map, page):
    _serve(serve_map, page, [PANO], [], link_base="")
    page.wait_for_function(
        "() => map.getLayer('pano-pins') && "
        "map.queryRenderedFeatures({ layers: ['pano-pins'] }).length === 1",
        timeout=15000,
    )
    _click_feature(page, "pano-pins")
    anchor = page.locator(".maplibregl-popup a.pano-open")
    expect(anchor).to_be_visible(timeout=10000)
    anchor.click()
    expect(page.locator("#pano-overlay")).to_be_visible(timeout=10000)
    page.keyboard.press("Escape")
    expect(page.locator("#pano-overlay")).to_be_hidden()
