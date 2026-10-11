import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import PurePosixPath, PureWindowsPath

import pytest

from dji_metadata_embedder.geo.clipprobe import ClipFacts
from dji_metadata_embedder.geo.fcpxml import (
    GENERATOR_MARK,
    TimelineClip,
    build_fcpxml,
    fmt_time,
    is_our_fcpxml,
    media_url,
    write_fcpxml,
)
from dji_metadata_embedder.geo.moments import Moment

NTSC = Fraction(30000, 1001)
FD = 1 / NTSC


def _facts(folder, name="DJI_0001.MP4", rate=NTSC, frames=600, tc=None):
    return ClipFacts(
        path=folder / name,
        rate=rate,
        frames=frames,
        width=3840,
        height=2160,
        has_audio=False,
        created_utc=None,
        tc_start=tc,
        schema=None,
    )


def _m(start, end, label="Steady 4.0 s · hover", note="real 4.0 s"):
    return Moment("steady", start, end, label, note)


def _t(text):
    assert text.endswith("s")
    return Fraction(text[:-1])


def _root(clips, name="Flight"):
    return ET.fromstring(build_fcpxml(clips, name).encode("utf-8"))


def _seq(root):
    return root.find("library/event/project/sequence")


def test_single_clip_document(tmp_path):
    root = _root([TimelineClip(_facts(tmp_path), [_m(1.0, 5.0)])])
    assert root.tag == "fcpxml" and root.get("version") == "1.9"
    (fmt,) = root.iter("format")
    assert fmt.get("frameDuration") == "1001/30000s" and fmt.get("name") is None
    (asset,) = root.iter("asset")
    assert _t(asset.get("duration")) == Fraction(600) / NTSC
    assert asset.find("media-rep").get("src") == (tmp_path / "DJI_0001.MP4").as_uri()
    assert root.find("library/event").get("name") == "Flight"
    (clip,) = _seq(root).iter("asset-clip")
    assert clip.get("offset") == "0s" and clip.get("format") is None
    assert _t(_seq(root).get("duration")) == _t(clip.get("duration"))


def test_every_time_sits_on_the_sequence_grid(tmp_path):
    clips = [
        TimelineClip(
            _facts(tmp_path, f"DJI_000{i}.MP4"), [_m(0.123, 3.456), _m(10.01, 12.99)]
        )
        for i in (1, 2)
    ]
    for clip in _root(clips).iter("asset-clip"):
        for attr in ("offset", "duration"):
            assert (_t(clip.get(attr)) / FD).denominator == 1
        for marker in clip.iter("marker"):
            assert (_t(marker.get("start")) / FD).denominator == 1
            assert (_t(marker.get("duration")) / FD).denominator == 1


def test_markers_snap_and_stay_inside_their_clip(tmp_path):
    root = _root([TimelineClip(_facts(tmp_path), [_m(1.234, 2.0), _m(15.0, 100.0)])])
    first, second = root.iter("marker")
    assert _t(first.get("start")) == round(Fraction(1.234) / FD) * FD
    duration = _t(next(root.iter("asset-clip")).get("duration"))
    assert _t(second.get("start")) + _t(second.get("duration")) <= duration


def test_mixed_rates_conform_to_the_majority(tmp_path):
    clips = [
        TimelineClip(_facts(tmp_path, "A.MP4")),
        TimelineClip(_facts(tmp_path, "B.MP4")),
        TimelineClip(
            _facts(tmp_path, "C.MP4", rate=Fraction(60000, 1001), frames=1239)
        ),
    ]
    root = _root(clips)
    formats = {f.get("id"): f.get("frameDuration") for f in root.iter("format")}
    assert formats[_seq(root).get("format")] == "1001/30000s"
    asset_c = next(a for a in root.iter("asset") if a.get("name") == "C")
    assert _t(asset_c.get("duration")) == Fraction(1239) / Fraction(60000, 1001)
    clip_c = next(c for c in root.iter("asset-clip") if c.get("name") == "C")
    assert clip_c.get("format") == asset_c.get("format")
    assert (_t(clip_c.get("duration")) / FD).denominator == 1
    assert _t(clip_c.get("duration")) <= _t(asset_c.get("duration"))


def test_format_tie_goes_to_the_first_clip(tmp_path):
    clips = [
        TimelineClip(_facts(tmp_path, "A.MP4", rate=Fraction(25), frames=500)),
        TimelineClip(_facts(tmp_path, "B.MP4")),
    ]
    root = _root(clips)
    formats = {f.get("id"): f.get("frameDuration") for f in root.iter("format")}
    assert formats[_seq(root).get("format")] == "1/25s"


def test_timecode_start_shifts_asset_clip_and_markers(tmp_path):
    clip = TimelineClip(
        _facts(tmp_path, rate=Fraction(25), frames=500, tc=Fraction(3600)),
        [_m(2.0, 4.0)],
    )
    root = _root([clip])
    assert next(root.iter("asset")).get("start") == "3600s"
    assert next(root.iter("asset-clip")).get("start") == "3600s"
    assert _t(next(root.iter("marker")).get("start")) == 3602


def test_offsets_are_cumulative(tmp_path):
    root = _root(
        [
            TimelineClip(_facts(tmp_path, "A.MP4")),
            TimelineClip(_facts(tmp_path, "B.MP4", frames=300)),
        ]
    )
    a, b = root.iter("asset-clip")
    assert _t(b.get("offset")) == _t(a.get("duration"))
    assert _t(_seq(root).get("duration")) == _t(a.get("duration")) + _t(
        b.get("duration")
    )


def test_text_is_escaped(tmp_path):
    clip = TimelineClip(
        _facts(tmp_path, "A&B 'x'.MP4"),
        [_m(1, 5, label="Rise 12 m & more", note='a "b" <c>')],
    )
    root = _root([clip], name='Trip "Alps" & <more>')
    assert root.find("library/event").get("name") == 'Trip "Alps" & <more>'
    marker = next(root.iter("marker"))
    assert (
        marker.get("value") == "Rise 12 m & more" and marker.get("note") == 'a "b" <c>'
    )
    assert next(root.iter("asset")).get("name") == "A&B 'x'"


def test_media_urls():
    assert (
        media_url(PureWindowsPath("C:/Footage/Flug ä.MP4"))
        == "file:///C:/Footage/Flug%20%C3%A4.MP4"
    )
    assert (
        media_url(PureWindowsPath("//nas/drone/DJI 1.MP4"))
        == "file://nas/drone/DJI%201.MP4"
    )
    assert (
        media_url(PurePosixPath("/home/pilot/a b/x.MP4"))
        == "file:///home/pilot/a%20b/x.MP4"
    )


def test_generator_comment_and_ownership_check(tmp_path):
    out = write_fcpxml(
        [TimelineClip(_facts(tmp_path))], "Flight", tmp_path / "Flight.fcpxml"
    )
    text = out.read_text(encoding="utf-8")
    assert text.startswith(
        '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n<!-- '
        + GENERATOR_MARK
    )
    assert is_our_fcpxml(out)
    foreign = tmp_path / "edited.fcpxml"
    foreign.write_text(
        '<?xml version="1.0"?><fcpxml version="1.10"/>', encoding="utf-8"
    )
    assert not is_our_fcpxml(foreign)
    assert not is_our_fcpxml(tmp_path / "missing.fcpxml")


def test_clip_without_moments_has_no_children(tmp_path):
    assert list(next(_root([TimelineClip(_facts(tmp_path))]).iter("asset-clip"))) == []


def test_fmt_time():
    assert (
        fmt_time(Fraction(0)),
        fmt_time(Fraction(5)),
        fmt_time(Fraction(1001, 30000)),
    ) == (
        "0s",
        "5s",
        "1001/30000s",
    )


def test_empty_timeline_is_refused():
    with pytest.raises(ValueError):
        build_fcpxml([], "Flight")


def test_markers_starting_after_the_clip_are_dropped(tmp_path):
    """Telemetry can outlast the video (SRT longer than the MP4): a marker
    for footage that doesn't exist must not be squeezed onto the last frame."""
    clip = TimelineClip(
        _facts(tmp_path), [_m(5.0, 8.0), _m(25.0, 30.0)]
    )  # clip is 20.02 s
    markers = list(_root([clip]).iter("marker"))
    assert len(markers) == 1 and _t(markers[0].get("start")) < 6
