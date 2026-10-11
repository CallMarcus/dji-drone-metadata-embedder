"""ClipFacts from canned `exiftool -j -G1 -n` output. Tag layouts follow
real Air 3S and Mavic 4 Pro probes (2026-10-11); DJI files carry three
tracks, so the video track's tags must win over the metadata tracks'."""

from datetime import datetime
from fractions import Fraction
from pathlib import Path

import pytest

from dji_metadata_embedder.geo.clipprobe import (
    ClipProbeError,
    exact_rate,
    facts_from_tags,
    parse_qt_date,
)

P = Path("DJI_20260815141932_0001_D.MP4")

AIR3S = {
    "SourceFile": str(P),
    "QuickTime:Duration": 307.07,
    "QuickTime:CreateDate": "2026:08:15 12:19:32",
    "Track1:HandlerType": "vide",
    "Track1:VideoFrameRate": 29.97002997,
    "Track1:TrackDuration": 307.0734333,
    "Track1:ImageWidth": 3840,
    "Track1:ImageHeight": 2160,
    "Track2:HandlerType": "meta",
    "Track2:MetaFormat": "djmd",
    "Track2:ImageWidth": 0,
    "Track2:VideoFrameRate": 1.0,
    "Track2:Category": "pb_file:dvtm_Air3s.proto;model_name:FC9113",
    "Track3:HandlerType": "meta",
    "Track3:MetaFormat": "dbgi",
    "Composite:Rotation": 0,
}


def test_air3s_facts():
    f = facts_from_tags(P, AIR3S)
    assert f.rate == Fraction(30000, 1001)
    assert f.frames == 9203
    assert (f.width, f.height) == (3840, 2160)
    assert f.has_audio is False
    assert f.created_utc == datetime(2026, 8, 15, 12, 19, 32)
    assert f.schema is not None and f.schema.startswith("dvtm_Air3s.proto")
    assert f.tc_start is None and f.tc_note is None
    assert f.duration == Fraction(9203) / Fraction(30000, 1001)


def test_rotation_90_swaps_to_displayed_size():
    tags = dict(
        AIR3S,
        **{
            "Track1:ImageWidth": 3384,
            "Track1:ImageHeight": 6016,
            "Composite:Rotation": 90,
        },
    )
    f = facts_from_tags(P, tags)
    assert (f.width, f.height) == (6016, 3384)


def test_frames_round_not_floor():
    tags = dict(
        AIR3S,
        **{"Track1:VideoFrameRate": 59.94005994, "Track1:TrackDuration": 20.67065},
    )
    assert facts_from_tags(P, tags).frames == 1239


def test_unknown_rate_is_rejected_by_name():
    with pytest.raises(ClipProbeError, match="27.500"):
        facts_from_tags(P, dict(AIR3S, **{"Track1:VideoFrameRate": 27.5}))


@pytest.mark.parametrize(
    "fps, expected",
    [
        (23.976, Fraction(24000, 1001)),
        (25.0, Fraction(25)),
        (29.97, Fraction(30000, 1001)),
        (30.0, Fraction(30)),
        (59.94, Fraction(60000, 1001)),
        (119.88, Fraction(120000, 1001)),
    ],
)
def test_exact_rate_table(fps, expected):
    assert exact_rate(fps) == expected


def test_audio_track_detected():
    assert facts_from_tags(P, dict(AIR3S, **{"Track4:HandlerType": "soun"})).has_audio


def test_no_video_track_is_an_error():
    tags = {k: v for k, v in AIR3S.items() if not k.startswith("Track1:")}
    with pytest.raises(ClipProbeError, match="no video track"):
        facts_from_tags(P, tags)


def test_timecode_track_read_when_present():
    tags = dict(
        AIR3S,
        **{
            "Track1:VideoFrameRate": 25.0,
            "Track4:HandlerType": "tmcd",
            "Track4:TimeCode": "01:00:00:00",
        },
    )
    f = facts_from_tags(P, tags)
    assert f.tc_start == Fraction(3600)


def test_unreadable_timecode_track_sets_note():
    tags = dict(AIR3S, **{"Track4:HandlerType": "tmcd"})
    f = facts_from_tags(P, tags)
    assert f.tc_start is None and "timecode" in (f.tc_note or "")


def test_parrot_schema():
    tags = dict(AIR3S)
    for k in ("Track2:MetaFormat", "Track2:Category", "Track3:MetaFormat"):
        tags.pop(k)
    tags["Track3:MetaType"] = "application/octet-stream;type=com.parrot.videometadata3"
    assert facts_from_tags(P, tags).schema == "parrot:videometadata3"


@pytest.mark.parametrize(
    "value, expected",
    [
        ("2026:08:15 12:19:32", datetime(2026, 8, 15, 12, 19, 32)),
        ("2026:08:15 14:19:32+02:00", datetime(2026, 8, 15, 12, 19, 32)),
        ("2026:08:15 12:19:32Z", datetime(2026, 8, 15, 12, 19, 32)),
        ("0000:00:00 00:00:00", None),
        ("", None),
        (None, None),
        ("garbage", None),
    ],
)
def test_parse_qt_date(value, expected):
    assert parse_qt_date(value) == expected
