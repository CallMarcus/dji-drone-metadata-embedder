"""Hover-previews toggle behaviour (#345) in a real headless Chromium.

Waits go through Playwright's polling ``expect`` — Leaflet closes tooltips
with a fade animation, so immediate DOM checks race the removal.
"""

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import expect  # noqa: E402

from dji_metadata_embedder.geo.photomap import PhotoPoint  # noqa: E402
from dji_metadata_embedder.geo.photomap_html import photos_to_html  # noqa: E402

pytestmark = pytest.mark.browser

POINTS = [
    PhotoPoint(lat=34.0567, lon=-84.1234, alt=95.3, name="DJI_0042.JPG"),
    PhotoPoint(lat=34.0592, lon=-84.1201, alt=88.1, name="DJI_0043.JPG"),
]

HTML = photos_to_html(POINTS, title="hover e2e")

PIN = ".leaflet-marker-icon"
TOOLTIP = ".leaflet-tooltip"


def test_hover_shows_nothing_until_opted_in(serve_map, page):
    serve_map(HTML)
    expect(page.locator("#hover-toggle")).not_to_be_checked()
    page.locator(PIN).first.hover()
    page.wait_for_timeout(200)          # give a wrong binding time to show
    expect(page.locator(TOOLTIP)).to_have_count(0)

    page.check("#hover-toggle")
    page.mouse.move(10, 10)             # leave and re-enter the pin
    page.locator(PIN).first.hover()
    expect(page.locator(TOOLTIP)).to_have_count(1)
    expect(page.locator(TOOLTIP)).to_contain_text(".JPG")


def test_choice_is_remembered_across_reload(serve_map, page):
    url = serve_map(HTML)
    page.check("#hover-toggle")
    page.goto(url)                      # fresh load, same browser context
    expect(page.locator("#hover-toggle")).to_be_checked()
    page.locator(PIN).first.hover()
    expect(page.locator(TOOLTIP)).to_have_count(1)

    page.uncheck("#hover-toggle")
    page.goto(url)
    expect(page.locator("#hover-toggle")).not_to_be_checked()


def test_touch_devices_get_no_toggle_at_all(serve_map, browser, playwright):
    # #295 parity: touch never had hover tooltips and must not gain a dead
    # toggle. A mobile descriptor flips the (hover/pointer) media queries
    # the map's TOUCH capability check reads.
    context = browser.new_context(**playwright.devices["iPhone 12"])
    touch_page = context.new_page()
    try:
        serve_map(HTML, on=touch_page)
        assert touch_page.evaluate(
            "() => matchMedia('(hover: none), (pointer: coarse)').matches")
        expect(touch_page.locator("#hover-toggle")).to_have_count(0)
        # The pins themselves are still there for tapping.
        expect(touch_page.locator(PIN).first).to_be_visible()
    finally:
        context.close()
