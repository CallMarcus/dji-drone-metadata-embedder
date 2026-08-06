"""2D --airspace zoom-gated ceiling labels (#424) in headless Chromium."""

from datetime import datetime, timedelta

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import expect  # noqa: E402

from dji_metadata_embedder.geo.flightmap_html import flights_to_html  # noqa: E402
from dji_metadata_embedder.geo.track import Track, TrackPoint  # noqa: E402

pytestmark = pytest.mark.browser


def _flight() -> Track:
    t0 = datetime(2026, 6, 15, 12, 0, 0)
    return Track(name="DJI_0001", points=[
        TrackPoint(lat=10.0, lon=20.0 + i * 0.0006, alt=100.0 + i,
                   timestamp=f"00:00:{i:02d},000",
                   utc=t0 + timedelta(seconds=i * 10.0))
        for i in range(5)
    ])


def _zone(upper="120 m AGL", upper_m=120.0, upper_ref="AGL"):
    return {
        "id": "Z1", "name": "Test zone", "restriction": "CEILING",
        "lower": None, "upper": upper, "applicability": [],
        "polygons": [[[19.999, 9.999], [20.01, 9.999], [20.01, 10.01],
                      [19.999, 10.01], [19.999, 9.999]]],
        "holes": [],
        "upper_m": upper_m, "upper_ref": upper_ref,
        "source": {"feed": "Test feed", "license": "CC0",
                   "fetched": "2026-08-06"},
        "entered": [],
    }


def _overlay(zones):
    return {"zones": zones,
            "notes": ["Airspace: Test feed, fetched 2026-08-06"],
            "covered": True}


def test_ceiling_labels_gate_on_zoom(serve_map, page):
    html = flights_to_html([_flight()], "trip",
                           airspace_json=_overlay([_zone()]))
    serve_map(html)
    # fitBounds on a ~30 m flight lands at maxZoom 17: labels visible.
    expect(page.locator(".airspace-label")).to_have_count(1, timeout=15000)
    expect(page.locator(".airspace-label")).to_contain_text("120 m AGL")
    page.evaluate("() => map.setZoom(9)")
    expect(page.locator(".airspace-label")).to_have_count(0, timeout=15000)
    page.evaluate("() => map.setZoom(12)")
    expect(page.locator(".airspace-label")).to_have_count(1, timeout=15000)


def test_no_ceiling_zone_gets_no_label(serve_map, page):
    zone = _zone(upper=None, upper_m=None, upper_ref=None)
    html = flights_to_html([_flight()], "trip",
                           airspace_json=_overlay([zone]))
    serve_map(html)
    # The zone polygon is on the map (popup says "not stated") but no label
    # may claim a ceiling. Wait for the map to settle on the flight first.
    page.wait_for_function(
        "() => typeof map !== 'undefined' && map.getZoom() > 11",
        timeout=15000,
    )
    assert page.locator(".airspace-label").count() == 0
