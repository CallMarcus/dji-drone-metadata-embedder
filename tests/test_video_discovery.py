"""Tests for video file discovery in the embedder.

Avata 360 footage ships as ``.OSV`` (360 video) plus a ``.LRF`` low-res
proxy rather than ``.MP4``; both are ISO BMFF (MP4-family) containers that
ffmpeg can mux a subtitle track into. Discovery must therefore pick them up
alongside the conventional ``.mp4``/``.MP4`` clips.
"""

from pathlib import Path

from dji_metadata_embedder.embedder import discover_video_files


def _touch(directory: Path, *names: str) -> None:
    for name in names:
        (directory / name).write_bytes(b"")


def test_discovers_mp4_case_insensitively(tmp_path: Path) -> None:
    _touch(tmp_path, "a.mp4", "B.MP4")
    found = {p.name for p in discover_video_files(tmp_path)}
    assert found == {"a.mp4", "B.MP4"}


def test_discovers_osv_and_lrf(tmp_path: Path) -> None:
    _touch(
        tmp_path,
        "clip.OSV",
        "clip.LRF",
        "lower.osv",
        "lower.lrf",
    )
    found = {p.name for p in discover_video_files(tmp_path)}
    assert found == {"clip.OSV", "clip.LRF", "lower.osv", "lower.lrf"}


def test_ignores_non_video_companions(tmp_path: Path) -> None:
    _touch(tmp_path, "clip.OSV", "clip.SRT", "clip.DAT", "notes.txt")
    found = {p.name for p in discover_video_files(tmp_path)}
    assert found == {"clip.OSV"}


def test_returns_sorted_unique_paths(tmp_path: Path) -> None:
    _touch(tmp_path, "b.OSV", "a.mp4", "c.LRF")
    found = discover_video_files(tmp_path)
    assert found == sorted(found)
    assert len(found) == len(set(found))
