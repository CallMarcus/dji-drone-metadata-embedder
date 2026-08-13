"""Popup thumbnail layout (#472) in a real headless Chromium.

The field bug: ``buildPopup`` emitted the base64 thumbnail ``<img>`` with no
``width``/``height`` attributes, so Leaflet measured the popup before the
image decoded (data URIs still decode async). A short filename left a narrow
text-only box with the tip anchored to it, and the image then overflowed to
the right — the reported popup-offset. Explicit dimension attributes make the
pre-decode layout correct.
"""

import base64
import io

import pytest

pytest.importorskip("playwright")
from PIL import Image  # noqa: E402
from playwright.sync_api import expect  # noqa: E402

from dji_metadata_embedder.geo.photomap import PhotoPoint  # noqa: E402
from dji_metadata_embedder.geo.photomap_html import photos_to_html  # noqa: E402

pytestmark = pytest.mark.browser

PIN = ".leaflet-marker-icon"
POPUP_IMG = ".leaflet-popup-content img"


def _jpeg_b64(width: int, height: int) -> str:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (30, 90, 160)).save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


# The short single-character name is the trigger: the text line alone measures
# far narrower than the 240 px thumbnail above it.
POINTS = [
    PhotoPoint(lat=34.0567, lon=-84.1234, alt=95.3, name="a",
               thumbnail_b64=_jpeg_b64(240, 120)),
]

HTML = photos_to_html(POINTS, title="popup layout e2e")


def test_popup_thumbnail_stays_inside_the_popup_box(serve_map, page):
    serve_map(HTML)
    page.locator(PIN).first.click()
    img = page.locator(POPUP_IMG)
    expect(img).to_be_visible()

    # The generator knows the JPEG's pixel size and must say so up front,
    # so Leaflet's pre-decode measurement is already right.
    assert img.get_attribute("width") == "240"
    assert img.get_attribute("height") == "120"

    # Wait for the actual decode, then the rendered image must sit inside
    # the popup content box instead of overflowing it (the field symptom).
    page.wait_for_function(
        "() => { const i = document.querySelector('.leaflet-popup-content img');"
        " return i && i.complete && i.naturalWidth > 0; }"
    )
    boxes = page.evaluate(
        "() => { const i = document.querySelector('.leaflet-popup-content img');"
        " const c = document.querySelector('.leaflet-popup-content');"
        " return { img: i.getBoundingClientRect(), box: c.getBoundingClientRect() }; }"
    )
    assert boxes["img"]["right"] <= boxes["box"]["right"] + 1
    assert boxes["img"]["width"] > 100  # the image really rendered wide
