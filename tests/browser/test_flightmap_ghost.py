"""Ghost Camera cockpit view (#372) in headless Chromium.

Pose assertions poll via wait_for_function so they hold for both the
jump-cut implementation and the eased one added later.
"""

from datetime import datetime, timedelta

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import expect  # noqa: E402

from dji_metadata_embedder.geo.flightmap3d_html import flights_to_3d_html  # noqa: E402
from dji_metadata_embedder.geo.track import Track, TrackPoint  # noqa: E402

pytestmark = pytest.mark.browser


def _flight(name="DJI_0001", *, points=5, gyaw=None, gpitch=None,
            agl_base=None, focal=None):
    t0 = datetime(2026, 6, 15, 12, 0, 0)
    return Track(name=name, points=[
        TrackPoint(
            lat=10.0, lon=20.0 + i * 0.0006, alt=100.0 + i,
            timestamp=f"00:00:{i:02d},000",
            utc=t0 + timedelta(seconds=i * 10.0),
            gimbal_yaw=gyaw, gimbal_pitch=gpitch,
            rel_alt=None if agl_base is None else agl_base + i,
            focal_len=focal,
        )
        for i in range(points)
    ])


def _boot(serve_map, page, html, **kw):
    serve_map(html, **kw)
    expect(page.locator("#flights-panel")).to_be_visible(timeout=20000)


def test_ghost_button_in_popup_and_enters(serve_map, page):
    html = flights_to_3d_html([_flight(gyaw=90.0, gpitch=-60.0)], "trip")
    _boot(serve_map, page, html)
    xy = page.evaluate(
        "() => { const p = map.project([20.0012, 10.0]);"
        " return [p.x, p.y]; }"
    )
    page.mouse.click(xy[0], xy[1])
    btn = page.locator(".maplibregl-popup .ghost-open")
    expect(btn).to_be_visible(timeout=10000)
    btn.click()
    page.wait_for_function(
        "() => Math.abs(map.getBearing() - 90) < 0.5", timeout=10000
    )


def test_ghost_pose_flat_fallback_uses_logged_altitude(serve_map, page):
    # Terrain failed (default harness) -> getTerrain() is null ->
    # camera height falls back to the logged absolute altitude.
    html = flights_to_3d_html([_flight(gyaw=90.0, gpitch=-60.0)], "trip")
    _boot(serve_map, page, html)
    page.evaluate("() => ghostEnter(0, 2)")
    page.wait_for_function(
        "() => ghost.applied && Math.abs(ghost.applied.altitude - 102) < 0.5"
        " && Math.abs(map.getBearing() - 90) < 0.5"
        " && Math.abs(map.getPitch() - 30) < 0.5",
        timeout=10000,
    )


def test_ghost_pose_uses_terrain_plus_agl(serve_map, page):
    html = flights_to_3d_html(
        [_flight(gyaw=90.0, gpitch=-60.0, agl_base=50.0)], "trip"
    )
    _boot(serve_map, page, html, terrain_stub=100.0)
    # Poll for the stub's height: qte returns 0 (not null) pre-load.
    page.wait_for_function(
        "() => map.queryTerrainElevation"
        " && Math.abs(map.queryTerrainElevation([20.0, 10.0]) - 100) < 2",
        timeout=20000,
    )
    page.evaluate("() => ghostEnter(0, 2)")
    # takeoff terrain 100 m + rel_alt (50 + 2) = 152 m.
    page.wait_for_function(
        "() => ghost.applied && Math.abs(ghost.applied.altitude - 152) < 2",
        timeout=10000,
    )


def test_ghost_step_and_esc_restores(serve_map, page):
    html = flights_to_3d_html([_flight(gyaw=90.0, gpitch=-60.0)], "trip")
    _boot(serve_map, page, html)
    before = page.evaluate(
        "() => ({b: map.getBearing(), p: map.getPitch(), z: map.getZoom()})"
    )
    page.evaluate("() => ghostEnter(0, 0)")
    page.wait_for_function(
        "() => Math.abs(map.getBearing() - 90) < 0.5", timeout=10000
    )
    assert page.evaluate("() => map.dragPan.isEnabled()") is False
    lon0 = page.evaluate("() => ghost.applied.lng")
    page.keyboard.press("ArrowRight")
    page.wait_for_function(
        f"() => ghost.applied.lng > {lon0} + 0.0001", timeout=10000
    )
    page.keyboard.press("Escape")
    page.wait_for_function(
        f"() => map.dragPan.isEnabled()"
        f" && Math.abs(map.getPitch() - {before['p']}) < 0.5"
        f" && Math.abs(map.getBearing() - {before['b']}) < 0.5",
        timeout=10000,
    )
