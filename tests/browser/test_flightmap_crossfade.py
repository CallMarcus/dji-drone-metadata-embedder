"""Media crossfade (#380): blend the reconstruction into the footage."""

from datetime import datetime, timedelta

import pytest

pytest.importorskip("playwright")

from dji_metadata_embedder.geo.flightmap3d_html import flights_to_3d_html  # noqa: E402
from dji_metadata_embedder.geo.track import Track, TrackPoint  # noqa: E402

pytestmark = pytest.mark.browser

VIDEO_NAME = "clip.webm"


def _flight(name: str, points: int = 6, *, media=None, segments=None,
            seg_of=None) -> Track:
    """Synthetic flight, one sample a second, gimbal and lens present."""
    t0 = datetime(2026, 6, 15, 12, 0, 0)
    track = Track(name=name, points=[
        TrackPoint(lat=10.0, lon=20.0 + i * 0.0006, alt=150.0,
                   timestamp=f"00:00:{i:02d},000",
                   utc=t0 + timedelta(seconds=i), rel_alt=50.0,
                   focal_len=24.0, gimbal_yaw=90.0, gimbal_pitch=-45.0,
                   segment=0 if seg_of is None else seg_of[i])
        for i in range(points)
    ])
    track.segments = segments
    track.media = media
    return track


def _ready(page):
    page.wait_for_selector("#flights-panel", timeout=15000)


def _serve_with_video(serve_map, recorded_webm, track, **kw):
    return serve_map(flights_to_3d_html([track], "trip", **kw),
                     extra_files={VIDEO_NAME: recorded_webm})


def test_no_video_element_without_linked_media(serve_map, page):
    serve_map(flights_to_3d_html([_flight("DJI_0001")], "trip"))
    _ready(page)
    page.evaluate("() => ghostEnter(0, 0)")
    assert page.locator("#ghost-video").count() == 0
    assert page.locator("#ghost-blend").count() == 0


def test_video_and_slider_appear_in_the_cockpit(serve_map, page,
                                                recorded_webm):
    _serve_with_video(serve_map, recorded_webm,
                      _flight("DJI_0001", media=[VIDEO_NAME]))
    _ready(page)
    assert page.locator("#ghost-video").count() == 0   # cockpit only
    page.evaluate("() => ghostEnter(0, 0)")
    assert page.locator("#ghost-video").count() == 1
    assert page.locator("#ghost-blend").count() == 1
    # Starts fully on the reconstruction: the video is opt-in, not a surprise.
    assert page.evaluate(
        "() => Number(document.getElementById('ghost-video').style.opacity)"
    ) == 0


def test_slider_drives_opacity(serve_map, page, recorded_webm):
    _serve_with_video(serve_map, recorded_webm,
                      _flight("DJI_0001", media=[VIDEO_NAME]))
    _ready(page)
    page.evaluate("() => ghostEnter(0, 0)")
    page.evaluate("() => { const s = document.getElementById('ghost-blend');"
                  " s.value = '60'; s.dispatchEvent(new Event('input')); }")
    assert abs(page.evaluate(
        "() => Number(document.getElementById('ghost-video').style.opacity)")
        - 0.6) < 1e-6


def test_v_key_toggles_the_extremes(serve_map, page, recorded_webm):
    _serve_with_video(serve_map, recorded_webm,
                      _flight("DJI_0001", media=[VIDEO_NAME]))
    _ready(page)
    page.evaluate("() => ghostEnter(0, 0)")
    op = "() => Number(document.getElementById('ghost-video').style.opacity)"
    assert page.evaluate(op) == 0
    page.keyboard.press("v")
    assert page.evaluate(op) == 1
    page.keyboard.press("v")
    assert page.evaluate(op) == 0


def test_video_is_removed_on_exit(serve_map, page, recorded_webm):
    _serve_with_video(serve_map, recorded_webm,
                      _flight("DJI_0001", media=[VIDEO_NAME]))
    _ready(page)
    page.evaluate("() => ghostEnter(0, 0)")
    assert page.locator("#ghost-video").count() == 1
    page.evaluate("() => ghostExit()")
    page.wait_for_function("() => !map.isMoving()", timeout=15000)
    assert page.locator("#ghost-video").count() == 0


def test_video_never_swallows_a_map_click(serve_map, page, recorded_webm):
    """pointer-events: none -- a click at full blend must still reach the
    terrain, or the gaze lookup dies whenever the video is up."""
    _serve_with_video(serve_map, recorded_webm,
                      _flight("DJI_0001", media=[VIDEO_NAME]))
    _ready(page)
    page.evaluate("() => ghostEnter(0, 0)")
    page.keyboard.press("v")
    assert page.evaluate(
        "() => getComputedStyle(document.getElementById('ghost-video'))"
        ".pointerEvents") == "none"


def _wait_video_ready(page):
    page.wait_for_function(
        "() => { const v = document.getElementById('ghost-video');"
        " return v && v.readyState >= 1 && Number.isFinite(v.duration); }",
        timeout=15000)


def test_seeks_to_the_sample_cue_time(serve_map, page, recorded_webm):
    """currentTime must track the point's own cue, which is what makes the
    overlay show the second the camera is at."""
    _serve_with_video(serve_map, recorded_webm,
                      _flight("DJI_0001", media=[VIDEO_NAME]))
    _ready(page)
    page.evaluate("() => ghostEnter(0, 0)")
    _wait_video_ready(page)
    page.evaluate("() => ghostStep(1)")
    page.wait_for_function(
        "() => Math.abs(document.getElementById('ghost-video').currentTime"
        " - 1.0) < 0.2", timeout=10000)


def test_crossing_a_segment_boundary_swaps_the_source(serve_map, page,
                                                      recorded_webm):
    """A split flight's second half plays from the second file, and the cue
    restarts near zero rather than continuing the flight clock."""
    track = _flight("DJI_0001", points=6,
                    media=["a/" + VIDEO_NAME, "b/" + VIDEO_NAME],
                    segments=["a/clip", "b/clip"],
                    seg_of=[0, 0, 0, 1, 1, 1])
    # The second segment's cues restart: rewrite them as its own file's clock.
    for i, p in enumerate(track.points):
        if p.segment == 1:
            p.timestamp = f"00:00:{i - 3:02d},000"
    serve_map(flights_to_3d_html([track], "trip"),
              extra_files={"a/" + VIDEO_NAME: recorded_webm,
                           "b/" + VIDEO_NAME: recorded_webm})
    _ready(page)
    page.evaluate("() => ghostEnter(0, 0)")
    _wait_video_ready(page)
    assert page.evaluate(
        "() => document.getElementById('ghost-video').src").endswith(
            "a/" + VIDEO_NAME)
    page.evaluate("() => { ghost.idx = 4; renderCrossfade(); }")
    page.wait_for_function(
        "() => document.getElementById('ghost-video').src.endsWith('b/"
        + VIDEO_NAME + "')", timeout=10000)
    _wait_video_ready(page)
    # The restart, not just "small": sample 4's own cue in file b (~1s) --
    # a flight-relative clock would land minutes past this clip's end.
    cue = page.evaluate("() => flights[0].cue[4]")
    page.wait_for_function(
        "() => Math.abs(document.getElementById('ghost-video').currentTime"
        f" - {cue}) < 0.3", timeout=10000)


def test_a_segment_without_video_disables_the_blend(serve_map, page,
                                                    recorded_webm):
    track = _flight("DJI_0001", points=6, media=[VIDEO_NAME, None],
                    segments=["clip", "missing"], seg_of=[0, 0, 0, 1, 1, 1])
    _serve_with_video(serve_map, recorded_webm, track)
    _ready(page)
    page.evaluate("() => ghostEnter(0, 0)")
    _wait_video_ready(page)
    page.evaluate("() => { ghost.idx = 4; renderCrossfade(); }")
    assert page.evaluate(
        "() => document.getElementById('ghost-blend').disabled") is True
    assert page.evaluate(
        "() => getComputedStyle(document.getElementById('ghost-video'))"
        ".display") == "none"


def test_plays_in_sync_at_normal_speed(serve_map, page, recorded_webm):
    _serve_with_video(serve_map, recorded_webm,
                      _flight("DJI_0001", media=[VIDEO_NAME]))
    _ready(page)
    page.evaluate("() => ghostEnter(0, 0)")
    _wait_video_ready(page)
    page.evaluate("() => { pb.speed = 1; pbPlay(); }")
    page.wait_for_function(
        "() => !document.getElementById('ghost-video').paused", timeout=10000)
    assert page.evaluate(
        "() => document.getElementById('ghost-video').playbackRate") == 1
    page.evaluate("() => pbPause()")
    page.wait_for_function(
        "() => document.getElementById('ghost-video').paused", timeout=10000)


def test_fast_playback_seeks_instead_of_playing(serve_map, page,
                                                recorded_webm):
    """Above CROSSFADE_MAX_RATE a decoder silently falls behind and shows the
    wrong second, so the video stays paused and steps instead."""
    _serve_with_video(serve_map, recorded_webm,
                      _flight("DJI_0001", media=[VIDEO_NAME]))
    _ready(page)
    page.evaluate("() => ghostEnter(0, 0)")
    _wait_video_ready(page)
    page.evaluate("() => { pb.speed = 60; pbPlay(); }")
    page.wait_for_function("() => pb.t > 2", timeout=10000)
    assert page.evaluate(
        "() => document.getElementById('ghost-video').paused") is True


def test_a_broken_video_disables_the_blend_and_names_the_file(serve_map, page):
    """Spec section 8: a moved or undecodable file must not leave a blank
    overlay that reads as 'the camera saw nothing here'."""
    serve_map(flights_to_3d_html(
        [_flight("DJI_0001", media=["gone.webm"])], "trip"))
    _ready(page)
    page.evaluate("() => ghostEnter(0, 0)")
    page.wait_for_function(
        "() => document.getElementById('ghost-blend').disabled === true",
        timeout=10000)
    note = page.locator("#ghost-badges").inner_text()
    assert "gone.webm" in note


def test_missing_focal_length_marks_the_alignment_approximate(serve_map, page,
                                                              recorded_webm):
    """Spec section 8: without a focal length the map's own field of view is
    an estimate, so a mismatch is not evidence the telemetry is wrong."""
    track = _flight("DJI_0001", media=[VIDEO_NAME])
    for p in track.points:
        p.focal_len = None
    _serve_with_video(serve_map, recorded_webm, track)
    _ready(page)
    page.evaluate("() => ghostEnter(0, 0)")
    assert page.evaluate("() => flights[0].vfov") is None
    assert "alignment approximate" in page.locator("#ghost-badges").inner_text()


def test_no_crossfade_under_fuzz(serve_map, page, recorded_webm):
    """Positions are coarsened ~100 m, so an overlay would invite a
    comparison against geometry we know is wrong. Linking is still allowed --
    photomap permits the same pair -- so the media property is present and it
    is the blend that is withheld."""
    _serve_with_video(serve_map, recorded_webm,
                      _flight("DJI_0001", media=[VIDEO_NAME]), redact="fuzz")
    _ready(page)
    page.evaluate("() => ghostEnter(0, 0)")
    assert page.locator("#ghost-video").count() == 0
    assert page.locator("#ghost-blend").count() == 0
    # The data is still there; only the feature is gated.
    assert page.evaluate("() => flights[0].media")[0] == VIDEO_NAME
    # And the cockpit itself still works.
    assert page.evaluate("() => ghost.active") is True
