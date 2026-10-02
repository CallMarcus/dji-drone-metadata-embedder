"""2D --airspace zoom-gated ceiling labels (#424) in headless Chromium."""

from datetime import datetime, timedelta

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import expect

from dji_metadata_embedder.geo.flightmap_html import flights_to_html
from dji_metadata_embedder.geo.track import Track, TrackPoint

pytestmark = pytest.mark.browser


def _flight() -> Track:
    t0 = datetime(2026, 6, 15, 12, 0, 0)
    return Track(
        name="DJI_0001",
        points=[
            TrackPoint(
                lat=10.0,
                lon=20.0 + i * 0.0006,
                alt=100.0 + i,
                timestamp=f"00:00:{i:02d},000",
                utc=t0 + timedelta(seconds=i * 10.0),
            )
            for i in range(5)
        ],
    )


def _zone(upper="120 m AGL", upper_m=120.0, upper_ref="AGL"):
    return {
        "id": "Z1",
        "name": "Test zone",
        "restriction": "CEILING",
        "lower": None,
        "upper": upper,
        "applicability": [],
        "polygons": [
            [
                [19.999, 9.999],
                [20.01, 9.999],
                [20.01, 10.01],
                [19.999, 10.01],
                [19.999, 9.999],
            ]
        ],
        "holes": [],
        "upper_m": upper_m,
        "upper_ref": upper_ref,
        "source": {"feed": "Test feed", "license": "CC0", "fetched": "2026-08-06"},
        "entered": [],
    }


def _overlay(zones):
    return {
        "zones": zones,
        "notes": ["Airspace: Test feed, fetched 2026-08-06"],
        "covered": True,
    }


def test_ceiling_labels_gate_on_zoom(serve_map, page):
    html = flights_to_html([_flight()], "trip", airspace_json=_overlay([_zone()]))
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
    html = flights_to_html([_flight()], "trip", airspace_json=_overlay([zone]))
    serve_map(html)
    # The zone polygon is on the map (popup says "not stated") but no label
    # may claim a ceiling. Wait for the map to settle on the flight first.
    page.wait_for_function(
        "() => typeof map !== 'undefined' && map.getZoom() > 11",
        timeout=15000,
    )
    assert page.locator(".airspace-label").count() == 0


# #593: a two-part zone. Part A carries a hole; part B is an island inside
# that hole. Each exterior must carry only its own holes.
_A = [[19.99, 9.99], [20.02, 9.99], [20.02, 10.02], [19.99, 10.02], [19.99, 9.99]]
_HOLE = [[20.0, 10.0], [20.01, 10.0], [20.01, 10.01], [20.0, 10.01], [20.0, 10.0]]
_B = [
    [20.004, 10.004],
    [20.006, 10.004],
    [20.006, 10.006],
    [20.004, 10.006],
    [20.004, 10.004],
]


def _parted_zone(**over):
    zone = _zone(**over)
    zone["polygons"] = [_A, _B]
    zone["holes"] = [_HOLE]
    zone["part_holes"] = [[_HOLE], []]
    return zone


def test_each_part_carries_only_its_own_holes(serve_map, page):
    html = flights_to_html(
        [_flight()], "trip", airspace_json=_overlay([_parted_zone()])
    )
    serve_map(html)
    page.wait_for_function(
        "() => typeof zoneGroup !== 'undefined' && zoneGroup.getLayers().length === 2",
        timeout=15000,
    )
    # Leaflet keeps [exterior, ...holes] per polygon: A has its hole, the
    # island B has none (the zone-level convention gave B A's hole too).
    ring_counts = page.evaluate(
        "() => zoneGroup.getLayers().map(l => l.getLatLngs().length)"
    )
    assert ring_counts == [2, 1]
