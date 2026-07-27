"""Resolving the video file behind each flight segment (#380)."""

from dji_metadata_embedder.geo.links import link_href
from dji_metadata_embedder.geo.media import resolve_media
from dji_metadata_embedder.geo.track import Track, TrackPoint


def _track(name: str, segments: list[str] | None = None) -> Track:
    t = Track(name=name, points=[
        TrackPoint(lat=10.0, lon=20.0, alt=100.0, timestamp="00:00:00,000")])
    t.segments = segments
    return t


def test_resolves_uppercase_mp4(tmp_path):
    (tmp_path / "DJI_0001.MP4").write_bytes(b"x")
    track = _track("DJI_0001")
    resolve_media([track], tmp_path)
    assert track.media == ["DJI_0001.MP4"]


def test_resolves_lowercase_and_mov(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"x")
    (tmp_path / "b.MOV").write_bytes(b"x")
    ta, tb = _track("a"), _track("b")
    resolve_media([ta, tb], tmp_path)
    assert ta.media == ["a.mp4"]
    assert tb.media == ["b.MOV"]


def test_missing_video_is_none_not_a_guess(tmp_path):
    """Never emit an href for a file that is not there -- a dead <video> src
    is indistinguishable from a codec failure to the user."""
    track = _track("DJI_0001")
    resolve_media([track], tmp_path)
    assert track.media is None


def test_one_href_per_segment_in_order(tmp_path):
    for n in ("DJI_0001", "DJI_0002", "DJI_0003"):
        (tmp_path / f"{n}.MP4").write_bytes(b"x")
    track = _track("DJI_0001", segments=["DJI_0001", "DJI_0002", "DJI_0003"])
    resolve_media([track], tmp_path)
    assert track.media == ["DJI_0001.MP4", "DJI_0002.MP4", "DJI_0003.MP4"]


def test_partial_segments_keep_their_slots(tmp_path):
    """A gap must not shift the others: seg_i indexes into this list."""
    (tmp_path / "DJI_0001.MP4").write_bytes(b"x")
    (tmp_path / "DJI_0003.MP4").write_bytes(b"x")
    track = _track("DJI_0001", segments=["DJI_0001", "DJI_0002", "DJI_0003"])
    resolve_media([track], tmp_path)
    assert track.media == ["DJI_0001.MP4", None, "DJI_0003.MP4"]


def test_recursive_names_keep_their_subdirectory(tmp_path):
    (tmp_path / "session1").mkdir()
    (tmp_path / "session1" / "DJI_0001.MP4").write_bytes(b"x")
    track = _track("session1/DJI_0001")
    resolve_media([track], tmp_path)
    assert track.media == ["session1/DJI_0001.MP4"]


def test_link_base_prefixes_every_href(tmp_path):
    (tmp_path / "DJI_0001.MP4").write_bytes(b"x")
    track = _track("DJI_0001")
    resolve_media([track], tmp_path, base="../footage")
    assert track.media == ["../footage/DJI_0001.MP4"]


def test_link_href_percent_encodes_segments_but_not_separators():
    assert link_href("a b/c#d.MP4", "") == "a%20b/c%23d.MP4"
    assert link_href("x.MP4", "https://example.test/v") == \
        "https://example.test/v/x.MP4"
