"""3D --airspace zone volumes (#424) in a real headless Chromium."""

from datetime import datetime, timedelta

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import expect  # noqa: E402

from dji_metadata_embedder.geo.flightmap3d_html import flights_to_3d_html  # noqa: E402
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


def _zone(upper="120 m AGL", upper_m=120.0, upper_ref="AGL", entered=None):
    return {
        "id": "Z1", "name": "Test zone", "restriction": "CEILING",
        "lower": None, "upper": upper, "applicability": [],
        "polygons": [[[19.999, 9.999], [20.01, 9.999], [20.01, 10.01],
                      [19.999, 10.01], [19.999, 9.999]]],
        "holes": [],
        "upper_m": upper_m, "upper_ref": upper_ref,
        "source": {"feed": "Test feed", "license": "CC0",
                   "fetched": "2026-08-06"},
        "entered": entered or [],
    }


def _overlay(zones, notes=None):
    return {"zones": zones,
            "notes": notes if notes is not None
            else ["Airspace: Test feed, fetched 2026-08-06"],
            "covered": True}


def _vol_features(page):
    return page.evaluate(
        "() => map.getSource('airspace-vol').serialize().data.features")


def _flat_features(page):
    return page.evaluate(
        "() => map.getSource('airspace-flat').serialize().data.features")


def _wait_layers(page):
    page.wait_for_function(
        "() => typeof map !== 'undefined' && map && map.getLayer"
        " && !!map.getLayer('airspace-volume')", timeout=20000)


def test_agl_ceiling_is_an_exact_volume(serve_map, page):
    html = flights_to_3d_html(
        [_flight()], "t", airspace_json=_overlay([_zone()]))
    serve_map(html, terrain_stub=100.0)
    _wait_layers(page)
    feats = _vol_features(page)
    assert len(feats) == 1
    # AGL never touches terrainElevAt: exact by construction, even before
    # DEM tiles are warm.
    assert feats[0]["properties"]["hgt"] == 120.0
    assert _flat_features(page) == []


def test_amsl_ceiling_settles_to_terrain_relative_height(serve_map, page):
    zone = _zone(upper="250 m AMSL", upper_m=250.0, upper_ref="AMSL")
    html = flights_to_3d_html(
        [_flight()], "t", airspace_json=_overlay([zone]))
    serve_map(html, terrain_stub=100.0)
    _wait_layers(page)
    # airspaceSettle re-samples once the 100 m DEM firms up: 250 - 100.
    page.wait_for_function(
        "() => { const s = map.getSource('airspace-vol');"
        " if (!s) return false;"
        " const f = s.serialize().data.features;"
        " return f.length === 1 && Math.abs(f[0].properties.hgt - 150) < 2; }",
        timeout=20000)
    expect(page.locator("#airspace-notes")).to_contain_text("AMSL")


def test_no_ceiling_zone_renders_flat(serve_map, page):
    zone = _zone(upper=None, upper_m=None, upper_ref=None)
    html = flights_to_3d_html(
        [_flight()], "t", airspace_json=_overlay([zone]))
    serve_map(html, terrain_stub=100.0)
    _wait_layers(page)
    assert _vol_features(page) == []
    assert len(_flat_features(page)) == 1
    # No AMSL volume on the map: the approximation note must not appear.
    note = page.locator("#airspace-notes")
    expect(note).not_to_contain_text("AMSL")


def test_zone_click_opens_published_facts_popup(serve_map, page):
    zone = _zone(upper=None, upper_m=None, upper_ref=None)
    html = flights_to_3d_html(
        [_flight()], "t", airspace_json=_overlay([zone]))
    serve_map(html, terrain_stub=100.0)
    _wait_layers(page)
    # Layer existence is not renderedness: on the CI software renderer the
    # click can beat the first frame that makes the footprint hit-testable,
    # and a click that queryRenderedFeatures can't see opens no popup.
    page.wait_for_function(
        "() => map.queryRenderedFeatures({layers: ['airspace-footprint']})"
        ".length > 0",
        timeout=20000,
    )
    pos = page.evaluate(
        "() => { const p = map.project([20.005, 10.005]);"
        " return { x: p.x, y: p.y }; }")
    page.mouse.click(pos["x"], pos["y"])
    expect(page.locator(".flight-popup")).to_contain_text(
        "Test zone", timeout=10000)
    expect(page.locator(".flight-popup")).to_contain_text(
        "upper limit: not stated", timeout=10000)


def test_entered_zone_lands_in_the_entered_layer(serve_map, page):
    entered = [{"flight": "DJI_0001", "entry_utc": "2026-06-15 12:00:10 UTC",
                "exit_utc": "2026-06-15 12:00:30 UTC",
                "max_rel_alt_m": 45.0, "max_amsl_m": 145.0, "time_note": None}]
    html = flights_to_3d_html(
        [_flight()], "t", airspace_json=_overlay([_zone(entered=entered)]))
    serve_map(html, terrain_stub=100.0)
    _wait_layers(page)
    feats = _vol_features(page)
    assert len(feats) == 1
    assert feats[0]["properties"]["entered"] is True
    # The twin-layer filters partition the source on `entered`: assert the
    # filter expressions directly rather than queryRenderedFeatures, which
    # can read empty under SwiftShader's cold-render timing in CI and would
    # then pass regardless of whether the filters were swapped or wrong.
    assert page.evaluate(
        "() => map.getFilter('airspace-volume-entered')"
    ) == ["get", "entered"]
    assert page.evaluate(
        "() => map.getFilter('airspace-volume')"
    ) == ["!", ["get", "entered"]]


def test_long_airspace_notes_wrap_inside_a_capped_panel(serve_map, page):
    # #542: each note is one long sentence; uncapped, the panel grew to
    # the width of the longest one (nearly the whole browser on a real
    # Swedish folder). The cap makes the notes wrap instead.
    long_note = ("Airspace note: Published by LFV with Transportstyrelsen "
                 "as data provider. Some zones apply only during scheduled "
                 "hours within their validity window; the schedule is in "
                 "the zone's published data and is not evaluated here.")
    html = flights_to_3d_html(
        [_flight()], "t",
        airspace_json=_overlay([_zone()], notes=[
            "Airspace: Sweden UAS geographical zones (ED-318, LFV), "
            "fetched 2026-08-22T12:44:39Z", long_note]))
    page.set_viewport_size({"width": 1600, "height": 900})
    serve_map(html, terrain_stub=100.0)
    _wait_layers(page)
    panel = page.locator("#flights-panel")
    expect(panel).to_contain_text("not evaluated here")
    width = panel.bounding_box()["width"]
    assert width <= 360 + 2, width               # the cap, not the note
    note = page.locator("#airspace-notes div").nth(1)
    assert note.bounding_box()["height"] > 30       # wrapped onto lines


def test_airspace_toggle_hides_all_layers(serve_map, page):
    html = flights_to_3d_html(
        [_flight()], "t", airspace_json=_overlay([_zone()]))
    serve_map(html, terrain_stub=100.0)
    _wait_layers(page)
    page.locator("#airspace-toggle").uncheck()
    for layer in ("airspace-volume", "airspace-volume-entered",
                  "airspace-footprint"):
        assert page.evaluate(
            f"() => map.getLayoutProperty('{layer}', 'visibility')"
        ) == "none"
