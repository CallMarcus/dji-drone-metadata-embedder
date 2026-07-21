"""Playback behaviour (#267/#327) in a real headless Chromium.

The string-level tests in test_geo_flightmap_html.py pin what the emitted
source *says*; these pin what the page *does*. Assertions are JS-evaluation
probes (element text, path counts, parsed SVG coordinates) — never screen
pixels: a geographically small flight renders ~12 px wide and pixel
positions cannot resolve it, so the fixture flight spans ~500 m and probes
read Leaflet's own SVG geometry.
"""

from datetime import datetime, timedelta

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import expect  # noqa: E402

from dji_metadata_embedder.geo.flightmap_html import flights_to_html  # noqa: E402
from dji_metadata_embedder.geo.track import Track, TrackPoint  # noqa: E402

pytestmark = pytest.mark.browser


def _flight(name: str, lat: float, lon: float, points: int,
            step_lon: float, step_s: float) -> Track:
    t0 = datetime(2026, 6, 15, 12, 0, 0)
    return Track(name=name, points=[
        TrackPoint(lat=lat, lon=lon + i * step_lon, alt=100.0 + i,
                   timestamp=f"00:00:{i:02d},000",
                   utc=t0 + timedelta(seconds=i * step_s))
        for i in range(points)
    ])


# Flight A: 11 fixes over 100 s heading due east across ~550 m — wide enough
# that interpolated positions differ meaningfully. Flight B: short and
# nearby, so the map still frames both.
TRACKS = [
    _flight("DJI_0001", 34.05, -84.30, 11, 0.0006, 10.0),
    _flight("DJI_0002", 34.06, -84.30, 3, 0.0002, 5.0),
]

HTML = flights_to_html(TRACKS, "playback e2e")

# The playback dot is the only white-stroked circleMarker on the map.
DOTS = 'document.querySelectorAll("#map path[stroke=\'#fff\']")'


def _dot_x(page) -> float:
    """The dot's SVG x coordinate — parsed from its own path geometry."""
    return page.evaluate(
        f"() => Number({DOTS}[0].getAttribute('d').split(/[ ,]/)[0].slice(1))"
    )


def _scrub(page, t: float) -> None:
    page.evaluate(
        """(t) => {
            const s = document.getElementById('pb-slider');
            s.value = t;
            s.dispatchEvent(new Event('input'));
        }""",
        t,
    )


def test_scrub_positions_the_dot_along_the_flight(serve_map, page):
    serve_map(HTML)
    _scrub(page, 10)
    x_early = _dot_x(page)
    _scrub(page, 90)
    x_late = _dot_x(page)
    # Due-east flight: later in time is further right in SVG space.
    assert x_late > x_early + 50
    assert page.evaluate(f"() => {DOTS}.length") == 1


def test_play_advances_the_dot_and_the_clock(serve_map, page):
    serve_map(HTML)
    page.click("#pb-play")
    expect(page.locator("#pb-play")).to_have_text("❚❚")
    # rAF-driven at 1x: within a couple of real seconds the clock moves.
    expect(page.locator("#pb-time")).not_to_have_text("0:00 / 1:40")
    assert float(page.eval_on_selector("#pb-slider", "s => s.value")) > 0
    page.click("#pb-play")   # pause
    expect(page.locator("#pb-play")).to_have_text("▶")


def test_speed_button_cycles_and_wraps(serve_map, page):
    serve_map(HTML)
    speeds = []
    for _ in range(5):
        speeds.append(page.locator("#pb-speed").inner_text())
        page.click("#pb-speed")
    assert speeds == ["1×", "5×", "20×", "60×", "1×"]


def test_compare_mode_shows_one_dot_per_flight(serve_map, page):
    serve_map(HTML)
    _scrub(page, 1)
    assert page.evaluate(f"() => {DOTS}.length") == 1
    page.select_option("#pb-flight", "all")
    _scrub(page, 1)
    assert page.evaluate(f"() => {DOTS}.length") == 2


def test_layer_untick_removes_that_flights_paths(serve_map, page):
    serve_map(HTML)
    before = page.evaluate("() => document.querySelectorAll('#map path').length")
    # Flightmap's layer control is collapsed until hovered (photomap's
    # legend variant is the always-expanded one).
    page.hover(".leaflet-control-layers")
    page.locator(".leaflet-control-layers-overlays input").first.uncheck()
    after = page.evaluate("() => document.querySelectorAll('#map path').length")
    # Flight A contributes its polyline and its start marker.
    assert before - after == 2


def test_reaching_the_end_flips_play_into_replay(serve_map, page):
    serve_map(HTML)
    for _ in range(3):                    # 1x -> 60x
        page.click("#pb-speed")
    _scrub(page, 95)                      # 5 s from the end at 60x
    page.click("#pb-play")
    expect(page.locator("#pb-play")).to_have_text("▶")
    slider = page.locator("#pb-slider")
    assert float(slider.evaluate("s => s.value")) == float(
        slider.evaluate("s => s.max"))
