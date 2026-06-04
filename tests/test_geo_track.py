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
