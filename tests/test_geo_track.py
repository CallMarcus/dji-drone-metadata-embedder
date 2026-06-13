from datetime import datetime, timedelta
from pathlib import Path

from dji_metadata_embedder.geo.track import build_track

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
CLIP = SAMPLES / "air3S" / "clip.SRT"


def test_build_track_reads_all_points():
    track = build_track(CLIP)
    assert track.name == "clip"
    assert len(track.points) == 5
    p = track.points[0]
    assert (p.lat, p.lon, p.alt) == (34.270373, -84.176160, 302.208)
    assert p.timestamp != ""


def test_build_track_redact_drop_empties_track():
    track = build_track(CLIP, redact="drop")
    assert track.points == []


def test_build_track_redact_fuzz_rounds_coords():
    track = build_track(CLIP, redact="fuzz")
    assert len(track.points) == 5
    p = track.points[0]
    assert (p.lat, p.lon) == (34.27, -84.176)
    # Altitude and timestamp are preserved, only coordinates are coarsened.
    assert p.alt == 302.208


# Bracket format WITHOUT an absolute datetime line, cue times 1s apart.
NODT_SRT = (
    "1\n00:00:00,000 --> 00:00:01,000\n"
    '<font size="28">[latitude: 10.0] [longitude: 20.0] '
    "[rel_alt: 0.000 abs_alt: 5.0]</font>\n\n"
    "2\n00:00:01,000 --> 00:00:02,000\n"
    '<font size="28">[latitude: 11.0] [longitude: 21.0] '
    "[rel_alt: 0.000 abs_alt: 6.0]</font>\n"
)


def test_build_track_sets_utc_from_explicit_offset():
    # First block local datetime is 2026-05-17 08:28:30.219; -2h -> 06:28:30.219.
    track = build_track(CLIP, tz_offset=timedelta(hours=2))
    assert track.points[0].utc == datetime(2026, 5, 17, 6, 28, 30, 219000)


def test_build_track_synthesizes_utc_without_datetime(tmp_path):
    srt = tmp_path / "nodt.SRT"
    srt.write_text(NODT_SRT, encoding="utf-8")
    track = build_track(srt)
    assert track.points[0].utc is not None
    # Cue times are 1s apart -> synthesized UTC preserves that spacing.
    delta = track.points[1].utc - track.points[0].utc
    assert delta.total_seconds() == 1.0
