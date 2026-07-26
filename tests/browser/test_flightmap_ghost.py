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


def test_ghost_cold_cache_resamples_takeoff_elevation(serve_map, page):
    # Pin the cold-DEM branch: with tiles reported unloaded and the first
    # elevation query returning 0 (what MapLibre does pre-load), the pose
    # must start from the wrong height and converge once the timer
    # re-sample sees the real elevation.
    html = flights_to_3d_html(
        [_flight(gyaw=90.0, gpitch=-60.0, agl_base=50.0)], "trip"
    )
    _boot(serve_map, page, html, terrain_stub=100.0)
    page.wait_for_function(
        "() => map.queryTerrainElevation"
        " && Math.abs(map.queryTerrainElevation([20.0, 10.0]) - 100) < 2",
        timeout=20000,
    )
    # Wait for a known-quiescent map before faking a cold cache: makes the
    # override's first read deterministic (cold -> exactly 0) independent
    # of any loading still in flight from the waits above.
    page.wait_for_function(
        "() => map.loaded() && !map.isMoving()", timeout=10000
    )
    first = page.evaluate(
        """() => {
      map.areTilesLoaded = () => false;
      const real = map.queryTerrainElevation.bind(map);
      let cold = true;
      map.queryTerrainElevation = ll => (cold ? (cold = false, 0) : real(ll));
      ghostEnter(0, 2);
      return ghost.applied.altitude;
    }"""
    )
    assert first == 52  # cold: fake takeoff elev 0 + rel_alt (50 + 2)
    page.wait_for_function(
        "() => Math.abs(ghost.applied.altitude - 152) < 2", timeout=20000
    )


def test_ghost_hud_content_and_buttons(serve_map, page):
    html = flights_to_3d_html(
        [_flight(gyaw=90.0, gpitch=-60.0, agl_base=50.0)], "trip"
    )
    _boot(serve_map, page, html)
    page.evaluate("() => ghostEnter(0, 0)")
    hud = page.locator("#ghost-hud")
    expect(hud).to_be_visible(timeout=10000)
    expect(hud).to_contain_text("DJI_0001")
    expect(hud).to_contain_text("m above takeoff")
    lon0 = page.evaluate("() => ghost.applied.lng")
    page.locator("#ghost-next").click()
    page.wait_for_function(
        f"() => ghost.applied.lng > {lon0} + 0.0001",
        timeout=10000,
    )
    page.locator("#ghost-exit").click()
    page.wait_for_function("() => map.dragPan.isEnabled()", timeout=10000)
    expect(page.locator("#ghost-hud")).to_have_count(0)


def test_ghost_badges(serve_map, page):
    # No gimbal data -> estimated badge; +20 deg gimbal wants pitch 110 ->
    # clamped badge; redact="fuzz" -> fuzzed badge.
    html = flights_to_3d_html(
        [_flight(name="NOGIMBAL"), _flight(name="UPWARD", gpitch=20.0)],
        "trip", redact="fuzz",
    )
    _boot(serve_map, page, html)
    page.evaluate("() => ghostEnter(0, 0)")
    expect(page.locator("#ghost-badges")).to_contain_text(
        "estimated view", timeout=10000
    )
    expect(page.locator("#ghost-badges")).to_contain_text("fuzzed")
    page.evaluate("() => ghostExit()")
    page.evaluate("() => ghostEnter(1, 0)")
    expect(page.locator("#ghost-badges")).to_contain_text(
        "pitch clamped", timeout=10000
    )


def test_ghost_hud_logged_altitude_label(serve_map, page):
    # No rel_alt -> the HUD must label the height "(as logged)".
    html = flights_to_3d_html([_flight(gyaw=90.0, gpitch=-60.0)], "trip")
    _boot(serve_map, page, html)
    page.evaluate("() => ghostEnter(0, 0)")
    expect(page.locator("#ghost-hud")).to_contain_text(
        "(as logged)", timeout=10000
    )


def test_ghost_rapid_reenter_keeps_lock_and_original_view(serve_map, page):
    # MapLibre fires moveend for interrupted eases too: exiting and
    # immediately re-entering must not run the stale exit-restore inside
    # the new session (camera unlock), and the eventual exit must restore
    # the ORIGINAL pre-ghost view, not a mid-transition one.
    html = flights_to_3d_html([_flight(gyaw=90.0, gpitch=-60.0)], "trip")
    _boot(serve_map, page, html)
    before = page.evaluate(
        "() => ({p: map.getPitch(), b: map.getBearing(),"
        " mp: map.getMaxPitch()})"
    )
    page.evaluate("() => ghostEnter(0, 0)")
    page.wait_for_function(
        "() => Math.abs(map.getBearing() - 90) < 0.5", timeout=10000
    )
    page.evaluate("() => { ghostExit(); ghostEnter(0, 2); }")
    # The stale moveend (if unguarded) fires synchronously inside the
    # re-enter's easeTo, so these asserts are deterministic.
    assert page.evaluate("() => map.dragPan.isEnabled()") is False
    assert page.evaluate("() => map.getMaxPitch()") == 100
    page.evaluate("() => ghostExit()")
    page.wait_for_function(
        f"() => map.dragPan.isEnabled()"
        f" && Math.abs(map.getPitch() - {before['p']}) < 0.5"
        f" && Math.abs(map.getBearing() - {before['b']}) < 0.5"
        f" && map.getMaxPitch() === {before['mp']}",
        timeout=10000,
    )
