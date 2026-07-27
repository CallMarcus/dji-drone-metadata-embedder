"""Resolve the video file that belongs to each flight segment (#380).

A flight's ``name`` is its SRT stem, path-qualified on recursive scans, and a
size-split flight lists every source in ``segments``. The video sits beside
the SRT under the same stem — but DJI writes ``.MP4`` while other tools write
``.mp4`` or ``.MOV``, so the file is *looked up*, never guessed: an href to a
file that is not there is indistinguishable from a codec failure once it
reaches a ``<video>`` element.
"""

from __future__ import annotations

from pathlib import Path

from .links import link_href
from .track import Track

# Ordered by how DJI writes them. Low-res ``.LRF`` proxies are deliberately
# excluded: they sit beside the real footage and would silently win.
_VIDEO_SUFFIXES = (".MP4", ".mp4", ".MOV", ".mov")


def _find_video(root: Path, name: str) -> str | None:
    """Relative POSIX path of the video for segment *name*, or ``None``."""
    for suffix in _VIDEO_SUFFIXES:
        candidate = root / f"{name}{suffix}"
        if candidate.is_file():
            return candidate.relative_to(root).as_posix()
    return None


def resolve_media(
    tracks: list[Track], root: Path, base: str | None = None
) -> None:
    """Fill ``Track.media`` with one href per segment, in segment order.

    A segment whose video is missing contributes ``None`` and **keeps its
    slot**, because the per-point ``seg_i`` array indexes into this list. A
    track with no resolvable video at all gets ``None``, so nothing downstream
    offers a crossfade it cannot deliver.
    """
    for track in tracks:
        names = track.segments or [track.name]
        hrefs: list[str | None] = []
        for name in names:
            found = _find_video(root, name)
            hrefs.append(link_href(found, base or "") if found else None)
        track.media = hrefs if any(hrefs) else None
