"""Playback in the 3D map (#378): the flat map's animator, MapLibre-side."""

from datetime import datetime, timedelta

import pytest

pytest.importorskip("playwright")

from dji_metadata_embedder.geo.flightmap3d_html import flights_to_3d_html  # noqa: E402
from dji_metadata_embedder.geo.track import Track, TrackPoint  # noqa: E402

pytestmark = pytest.mark.browser


def _flight(name: str, lat: float, lon: float, points: int,
            step: float = 0.0006) -> Track:
    """Synthetic flight, one sample a second, AGL 50 m throughout."""
    t0 = datetime(2026, 6, 15, 12, 0, 0)
    return Track(name=name, points=[
        TrackPoint(lat=lat, lon=lon + i * step, alt=150.0,
                   timestamp=f"00:00:{i:02d},000",
                   utc=t0 + timedelta(seconds=i), rel_alt=50.0,
                   focal_len=24.0, gimbal_yaw=90.0, gimbal_pitch=-45.0)
        for i in range(points)
    ])


def _flight_yaws(name: str, lat: float, lon: float, yaws: list) -> Track:
    """Like `_flight`, but with a per-point gimbal yaw instead of a constant
    one -- `_flight`'s constant 90.0 makes every posePlayback interpolation
    run with `d == 0`, which never exercises the shortest-arc branch."""
    t0 = datetime(2026, 6, 15, 12, 0, 0)
    return Track(name=name, points=[
        TrackPoint(lat=lat, lon=lon + i * 0.0006, alt=150.0,
                   timestamp=f"00:00:{i:02d},000",
                   utc=t0 + timedelta(seconds=i), rel_alt=50.0,
                   focal_len=24.0, gimbal_yaw=yaw, gimbal_pitch=-45.0)
        for i, yaw in enumerate(yaws)
    ])


def _ready(page):
    page.wait_for_selector("#flights-panel", timeout=15000)


def test_control_mounts_with_a_playable_flight(serve_map, page):
    serve_map(flights_to_3d_html([_flight("DJI_0001", 10.0, 20.0, 6)], "trip"))
    _ready(page)
    assert page.locator("#playback").count() == 1
    assert page.locator("#pb-play").count() == 1
    assert page.locator("#pb-slider").count() == 1
    # One flight: no picker.
    assert page.locator("#pb-flight").count() == 0
    assert page.evaluate("() => Number(document.getElementById("
                         "'pb-slider').max)") == 5.0
    assert page.evaluate("() => !!map.getLayer('gaze-cursor-dot')")


def test_no_control_without_times(serve_map, page):
    """A single-fix clip has no LineString and no times: there is no clock to
    offer, so the control must not appear at all."""
    t0 = datetime(2026, 6, 15, 12, 0, 0)
    track = Track(name="DJI_0002", points=[
        TrackPoint(lat=10.0, lon=20.0, alt=150.0, timestamp="00:00:00,000",
                   utc=t0, rel_alt=50.0)])
    serve_map(flights_to_3d_html([track], "trip"))
    page.wait_for_function("() => typeof map !== 'undefined' && map "
                           "&& map.loaded()", timeout=15000)
    assert page.locator("#playback").count() == 0
    assert page.evaluate("() => runs.length") == 0


def test_playing_advances_the_clock_and_moves_the_cursor(serve_map, page):
    serve_map(flights_to_3d_html([_flight("DJI_0001", 10.0, 20.0, 6)], "trip"))
    _ready(page)
    # GeoJSON source tiles are built asynchronously, so wait rather than
    # sampling the instant after load.
    page.wait_for_function(
        "() => map.querySourceFeatures('gaze-cursor').length > 0",
        timeout=5000)
    page.evaluate("() => { pb.speed = 5; pbPlay(); }")
    page.wait_for_function("() => pb.t > 1.5", timeout=5000)
    page.evaluate("() => pbPause()")
    assert page.evaluate("() => pb.sample") >= 1
    assert page.evaluate("() => pb.playing") is False


def test_playback_pauses_at_the_end(serve_map, page):
    serve_map(flights_to_3d_html([_flight("DJI_0001", 10.0, 20.0, 4)], "trip"))
    _ready(page)
    page.evaluate("() => { pb.speed = 60; pbPlay(); }")
    page.wait_for_function("() => !pb.playing", timeout=5000)
    assert abs(page.evaluate("() => pb.t") - 3.0) < 0.001
    # ▶ is the play glyph; written as an escape so the test file stays
    # ASCII like the JS it checks.
    assert page.evaluate("() => document.getElementById('pb-play')"
                         ".textContent") == "▶"


def test_slider_seeks(serve_map, page):
    serve_map(flights_to_3d_html([_flight("DJI_0001", 10.0, 20.0, 6)], "trip"))
    _ready(page)
    page.evaluate("() => { const s = document.getElementById('pb-slider');"
                  " s.value = '4'; s.dispatchEvent(new Event('input')); }")
    assert abs(page.evaluate("() => pb.t") - 4.0) < 0.001
    assert page.evaluate("() => pb.sample") == 4
    assert page.evaluate("() => document.getElementById('pb-time')"
                         ".textContent").startswith("0:04")


def test_speed_button_cycles(serve_map, page):
    serve_map(flights_to_3d_html([_flight("DJI_0001", 10.0, 20.0, 4)], "trip"))
    _ready(page)
    seen = []
    for _ in range(5):
        page.click("#pb-speed")
        seen.append(page.evaluate("() => pb.speed"))
    assert seen == [5, 20, 60, 1, 5]


def test_picker_switches_flight_and_resets_the_clock(serve_map, page):
    serve_map(flights_to_3d_html(
        [_flight("DJI_0001", 10.0, 20.0, 6), _flight("DJI_0002", 10.01, 20.0, 3)],
        "trip"))
    _ready(page)
    assert page.locator("#pb-flight option").count() == 2
    page.evaluate("() => { pb.t = 3; pbPlay(); }")
    page.evaluate("() => { const s = document.getElementById('pb-flight');"
                  " s.value = '1'; s.dispatchEvent(new Event('change')); }")
    assert page.evaluate("() => pb.playing") is False
    assert page.evaluate("() => pb.t") == 0
    assert page.evaluate("() => pb.run.name") == "DJI_0002"
    assert page.evaluate("() => Number(document.getElementById("
                         "'pb-slider').max)") == 2.0


def test_playing_in_the_cockpit_flies_the_recorded_path(serve_map, page):
    serve_map(flights_to_3d_html([_flight("DJI_0001", 10.0, 20.0, 6)], "trip"))
    _ready(page)
    page.evaluate("() => ghostEnter(0, 0)")
    page.wait_for_function("() => !map.isMoving()", timeout=15000)
    first = page.evaluate("() => ghost.applied.lng")
    page.evaluate("() => { pb.t = 4; pbRender(); }")
    later = page.evaluate("() => ghost.applied.lng")
    assert later > first, "the cockpit did not follow the clock"
    assert page.evaluate("() => ghost.idx") == 4
    assert page.evaluate("() => ghost.active") is True


def test_a_scrub_between_samples_interpolates(serve_map, page):
    serve_map(flights_to_3d_html([_flight("DJI_0001", 10.0, 20.0, 6)], "trip"))
    _ready(page)
    page.evaluate("() => ghostEnter(0, 0)")
    page.wait_for_function("() => !map.isMoving()", timeout=15000)
    page.evaluate("() => { pb.t = 2.5; pbRender(); }")
    got = page.evaluate("() => ghost.applied.lng")
    lo = page.evaluate("() => flights[0].pts[2][0]")
    hi = page.evaluate("() => flights[0].pts[3][0]")
    assert lo < got < hi, "pose was snapped to a sample instead of interpolated"


def test_arrow_step_pauses_playback(serve_map, page):
    """Manual control wins: an arrow key while the clock runs would otherwise
    be overwritten on the next frame."""
    serve_map(flights_to_3d_html([_flight("DJI_0001", 10.0, 20.0, 6)], "trip"))
    _ready(page)
    page.evaluate("() => ghostEnter(0, 0)")
    page.wait_for_function("() => !map.isMoving()", timeout=15000)
    page.evaluate("() => { pb.speed = 1; pbPlay(); }")
    assert page.evaluate("() => pb.playing") is True
    page.keyboard.press("ArrowRight")
    assert page.evaluate("() => pb.playing") is False


def test_entering_while_playing_jumps_instead_of_easing(serve_map, page):
    """A 1.2 s cinematic ease would be overridden by the next frame anyway,
    and eases are where this file's moveend scars are."""
    serve_map(flights_to_3d_html([_flight("DJI_0001", 10.0, 20.0, 6)], "trip"))
    _ready(page)
    page.wait_for_function("() => !map.isMoving()", timeout=15000)
    # In one round-trip: easeTo fires movestart synchronously, so isMoving()
    # is unambiguous inside the same JS turn. Splitting this across two
    # evaluate() calls would let a restored entry ease get aborted by the
    # first driven frame (~16 ms) before the assertion ever ran.
    moving = page.evaluate(
        "() => { pb.speed = 1; pbPlay(); ghostEnter(0, 0);"
        " return map.isMoving(); }")
    assert moving is False, "ghostEnter eased"
    assert page.evaluate("() => ghost.active") is True


def test_exiting_while_playing_keeps_the_clock(serve_map, page):
    serve_map(flights_to_3d_html([_flight("DJI_0001", 10.0, 20.0, 6)], "trip"))
    _ready(page)
    page.evaluate("() => ghostEnter(0, 0)")
    page.wait_for_function("() => !map.isMoving()", timeout=15000)
    page.evaluate("() => { pb.speed = 5; pbPlay(); ghostExit(); }")
    assert page.evaluate("() => pb.playing") is True
    page.wait_for_function("() => !map.isMoving()", timeout=15000)
    assert page.evaluate("() => ghost.active") is False
    assert page.evaluate("() => ghost.saved") is None


def test_beam_hides_in_the_cockpit(serve_map, page):
    """A beam originating at your own eye would fill the frame -- the same
    reason the sculpture steps aside. The patch stays: it is the point."""
    serve_map(flights_to_3d_html([_flight("DJI_0001", 10.0, 20.0, 6)], "trip"))
    _ready(page)
    vis = ("(id) => map.getLayoutProperty(id, 'visibility') || 'visible'")
    assert page.evaluate(vis, "beam-ray") == "visible"
    page.evaluate("() => ghostEnter(0, 2)")
    assert page.evaluate(vis, "beam-ray") == "none"
    assert page.evaluate(vis, "gaze-fill") == "visible"
    page.evaluate("() => ghostExit()")
    page.wait_for_function("() => !map.isMoving()", timeout=15000)
    assert page.evaluate(vis, "beam-ray") == "visible"


def test_bearing_scrub_takes_the_short_way_round(serve_map, page):
    """posePlayback's wraparound arithmetic is the only non-obvious math in
    this task, and every other fixture in this file uses a constant yaw
    (d == 0 throughout), so it has never actually run. 350 -> 10 the short
    way passes through 360/0; the long way would sweep through 180."""
    serve_map(flights_to_3d_html(
        [_flight_yaws("DJI_0001", 10.0, 20.0, [350.0, 10.0])], "trip"))
    _ready(page)
    page.evaluate("() => ghostEnter(0, 0)")
    page.wait_for_function("() => !map.isMoving()", timeout=15000)
    page.evaluate("() => { pb.t = 0.5; pbRender(); }")
    bearing = page.evaluate("() => ghost.applied.bearing")
    assert bearing > 355 or bearing < 15, (
        f"bearing {bearing} swept through 180 instead of taking the short "
        "way round 0/360")


def test_ghost_rapid_reenter_while_playing_keeps_lock(serve_map, page):
    """The paused rapid-cycle scenario is
    test_ghost_rapid_reenter_keeps_lock_and_original_view in
    test_flightmap_ghost.py. This task adds a second way to interrupt the
    exit ease -- ghostEnter's jumpTo when pb.playing, instead of easeTo --
    so it needs its own coverage: the camera must stay locked and the saved
    view must not restore mid-session."""
    serve_map(flights_to_3d_html([_flight("DJI_0001", 10.0, 20.0, 6)], "trip"))
    _ready(page)
    before = page.evaluate(
        "() => ({p: map.getPitch(), b: map.getBearing(),"
        " mp: map.getMaxPitch()})")
    page.evaluate("() => ghostEnter(0, 0)")
    page.wait_for_function("() => !map.isMoving()", timeout=15000)
    # pbPlay() and the exit/re-enter cycle all in one round-trip: a Python
    # round-trip between them could let the first ghostExit's 1.2 s ease
    # complete for real, which would defeat the scenario.
    result = page.evaluate("""() => {
      pb.speed = 1; pbPlay();
      ghostExit(); ghostEnter(0, 2);
      return { dragPan: map.dragPan.isEnabled(),
               maxPitch: map.getMaxPitch() };
    }""")
    # The stale moveend (if unguarded) fires synchronously inside the
    # re-enter's jumpTo, same as the paused variant's easeTo, so these
    # asserts are deterministic.
    assert result["dragPan"] is False
    assert result["maxPitch"] == 100
    page.evaluate("() => ghostExit()")
    page.wait_for_function(
        f"() => map.dragPan.isEnabled()"
        f" && Math.abs(map.getPitch() - {before['p']}) < 0.5"
        f" && Math.abs(map.getBearing() - {before['b']}) < 0.5"
        f" && map.getMaxPitch() === {before['mp']}",
        timeout=15000,
    )
