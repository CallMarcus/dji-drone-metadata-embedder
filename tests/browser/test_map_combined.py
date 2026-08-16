"""The combined map (#322) in a real headless Chromium.

One photo pin and one playable flight on the same page: the photo popup
must open with its content, the track polyline must render, the merged
layer control must list both the type row and the flight row, and the
playback control must actually advance the clock.
"""

import base64
import io
from datetime import datetime, timedelta

import pytest

pytest.importorskip("playwright")
from PIL import Image  # noqa: E402
from playwright.sync_api import expect  # noqa: E402

from dji_metadata_embedder.geo.map_html import mixed_to_html  # noqa: E402
from dji_metadata_embedder.geo.photomap import PhotoPoint  # noqa: E402
from dji_metadata_embedder.geo.track import Track, TrackPoint  # noqa: E402

pytestmark = pytest.mark.browser


def _jpeg_b64(width: int, height: int) -> str:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (30, 90, 160)).save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


_T0 = datetime(2026, 6, 15, 12, 0, 0)
POINTS = [
    PhotoPoint(lat=34.0567, lon=-84.1234, alt=95.3, name="church.jpg",
               thumbnail_b64=_jpeg_b64(240, 120)),
]
TRACKS = [
    # lon drifts a hair each point (not held constant): a perfectly
    # north-south line gives Chromium's getBoundingClientRect() a
    # geometric width of 0 for the SVG path (stroke width is excluded
    # from that box), which makes Playwright's to_be_visible() report
    # the rendered, on-screen polyline as hidden. The drift is cosmetic
    # to the flight and keeps the visibility assertion honest.
    Track(name="DJI_0001", points=[
        TrackPoint(lat=34.0570 + i * 0.0005, lon=-84.1230 + i * 0.0001,
                   alt=5.0 + i, timestamp=f"00:00:{i:02d},000",
                   utc=_T0 + timedelta(seconds=30 * i))
        for i in range(4)
    ]),
]

HTML = mixed_to_html(POINTS, TRACKS, title="combined e2e")


def test_photo_popup_track_and_playback_share_one_page(serve_map, page):
    serve_map(HTML)

    # Track polyline rendered (Leaflet draws it as an interactive SVG path).
    expect(page.locator("path.leaflet-interactive").first).to_be_visible()

    # Photo pin opens the photomap popup with its thumbnail and name.
    page.locator(".leaflet-marker-icon").first.click()
    expect(page.locator(".photo-popup")).to_contain_text("church.jpg")

    # Merged layer control: the photo type row plus the flight row.
    # (":not(.hover-control)" excludes the separate "Hover previews"
    # toggle, which reuses the leaflet-control-layers class purely for
    # its box styling -- see photomap_js.py -- and isn't the layer list.)
    control = page.locator(".leaflet-control-layers:not(.hover-control)")
    expect(control).to_contain_text("Photos")
    expect(control).to_contain_text("DJI_0001")

    # Playback: pressing play advances the shared clock.
    expect(page.locator("#pb-play")).to_be_visible()
    page.locator("#pb-play").click()
    page.wait_for_function(
        "() => Number(document.getElementById('pb-slider').value) > 0")
