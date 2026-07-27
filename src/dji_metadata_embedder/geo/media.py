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
    """Relative POSIX path of the video for segment *name*, or ``None``.

    Scans the real directory entries rather than probing guessed filenames.
    Probing (``(root / f"{name}{suffix}").is_file()``) is wrong on a
    case-insensitive filesystem (Windows, default macOS): a real
    ``flight.mov`` also answers ``is_file()`` for the guessed ``flight.MOV``,
    so the href would carry a case the directory entry does not actually
    have -- working locally, and 404ing the moment the folder is served from
    a case-sensitive host (#380 whole-branch review M1).
    """
    target = root / name
    parent, stem = target.parent, target.name
    if not parent.is_dir():
        return None
    rank = {suffix.lower(): i for i, suffix in enumerate(_VIDEO_SUFFIXES)}
    best: tuple[int, Path] | None = None
    for entry in parent.iterdir():
        if entry.is_file() and entry.stem == stem:
            r = rank.get(entry.suffix.lower())
            if r is not None and (best is None or r < best[0]):
                best = (r, entry)
    return best[1].relative_to(root).as_posix() if best else None


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
