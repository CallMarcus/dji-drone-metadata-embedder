"""The combined map's 3D variant (#514) in a real headless Chromium.

Photo and pano pins are MapLibre circle layers over a clustered GeoJSON
source; tracks draw exactly as on the flightmap 3D page. The harness aborts
the Mapterhorn fetch, so every test runs on the flat-terrain fallback path
unless it opts into ``terrain_stub``; pins do not need terrain to render.
"""

import base64
import io
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
