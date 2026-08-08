"""Interactive opening-view editor for GPano panoramas (#440).

Scans a folder for equirectangular panoramas, serves a localhost Pannellum
editor page, and writes the composed view back as the three GPano
initial-view tags via ExifTool (default ``_original`` backup kept). The
compass heading written is ``PoseHeadingDegrees + viewer yaw`` — the exact
inverse of the read-side mapping in :func:`.photomap._pano_view`.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..utils.exiftool import exiftool_exe
from .photomap import _maybe_float, _pano_view

_EXIFTOOL_INSTALL_HINT = (
    "ExifTool not found. Run: dji-embed doctor --install exiftool "
    "(downloads a pinned, checksum-verified copy; no admin rights needed). "
    "Alternatively install it from https://exiftool.org or set "
    "DJIEMBED_EXIFTOOL_PATH to the executable."
)

# The read half of the editor: pose anchors compass headings to the image
# frame; the three InitialView* tags are what Save writes back.
_SCAN_TAGS = [
    "-XMP-GPano:ProjectionType",
    "-XMP-GPano:PoseHeadingDegrees",
    "-XMP-GPano:InitialViewHeadingDegrees",
    "-XMP-GPano:InitialViewPitchDegrees",
    "-XMP-GPano:InitialHorizontalFOVDegrees",
]
_PANO_EXTS = ("jpg", "jpeg")


class PanoEditError(Exception):
    """A panoedit failure with a user-facing message."""


@dataclass
class PanoFile:
    """One editable panorama: absolute path, display name, pose heading
    (0.0 when the stitcher wrote none), and the current viewer-ready
    initial view (``None`` where tags are absent)."""

    path: Path
    name: str
    pose: float
    yaw: float | None
    pitch: float | None
    hfov: float | None


def compass_heading(pose: float, yaw: float) -> float:
    """Viewer yaw -> the compass ``InitialViewHeadingDegrees`` to write."""
    return (pose + yaw) % 360.0


def _run_scan(directory: Path, recursive: bool) -> list[dict]:
    args = [exiftool_exe(), "-json", "-n"]
    if recursive:
        args.append("-r")
    args += _SCAN_TAGS
    for ext in _PANO_EXTS:
        args += ["-ext", ext]
    args.append(str(directory))
    try:
        proc = subprocess.run(
            args, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
    except FileNotFoundError:
        raise PanoEditError(_EXIFTOOL_INSTALL_HINT) from None
    out = proc.stdout.strip()
    if not out:
        if proc.returncode != 0:
            stderr = proc.stderr.strip()[-300:]
            raise PanoEditError(
                f"ExifTool scan of {directory} failed "
                f"(exit {proc.returncode}): {stderr or 'no error output'}"
            )
        return []
    try:
        data = json.loads(out)
    except json.JSONDecodeError as exc:
        raise PanoEditError(f"Could not parse ExifTool JSON: {exc}") from exc
    if not isinstance(data, list):
        raise PanoEditError("Unexpected ExifTool JSON shape (expected a list)")
    return data


def scan_panos(directory: Path, recursive: bool = False) -> list[PanoFile]:
    """Scan *directory* and return its equirectangular panoramas, sorted.

    Raises :class:`PanoEditError` when the folder holds no panoramas — the
    editor has nothing to edit, and a blank page would look like a bug.
    """
    entries = _run_scan(directory, recursive)
    files: list[PanoFile] = []
    for entry in entries:
        proj = entry.get("ProjectionType")
        if not (isinstance(proj, str)
                and proj.strip().lower() == "equirectangular"):
            continue
        path = Path(str(entry.get("SourceFile", "?")))
        yaw, pitch, hfov = _pano_view(entry)
        files.append(PanoFile(
            path=path,
            name=path.name,
            pose=_maybe_float(entry.get("PoseHeadingDegrees")) or 0.0,
            yaw=yaw, pitch=pitch, hfov=hfov,
        ))
    if not files:
        raise PanoEditError(
            f"No 360-degree panoramas found in {directory} "
            f"({len(entries)} JPEGs scanned; a panorama carries "
            "XMP-GPano:ProjectionType=equirectangular)"
        )
    files.sort(key=lambda f: f.name)
    return files


def write_initial_view(
    path: Path, heading: float, pitch: float, hfov: float
) -> dict:
    """Write the three initial-view tags to *path* and read them back.

    ExifTool's default sidecar backup (``<name>_original``) is deliberately
    kept — batch editing must never be able to destroy an original. The
    read-back is the write verification: what the map will see is what the
    caller gets.
    """
    exe = exiftool_exe()
    write_args = [
        exe, "-n",
        f"-XMP-GPano:InitialViewHeadingDegrees={heading}",
        f"-XMP-GPano:InitialViewPitchDegrees={pitch}",
        f"-XMP-GPano:InitialHorizontalFOVDegrees={hfov}",
        str(path),
    ]
    try:
        proc = subprocess.run(
            write_args, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
    except FileNotFoundError:
        raise PanoEditError(_EXIFTOOL_INSTALL_HINT) from None
    if proc.returncode != 0:
        stderr = proc.stderr.strip()[-300:]
        raise PanoEditError(
            f"ExifTool could not write {path.name}: "
            f"{stderr or 'no error output'}"
        )
    read_args = [exe, "-json", "-n", *_SCAN_TAGS[1:], str(path)]
    proc = subprocess.run(
        read_args, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    try:
        entry = json.loads(proc.stdout)[0]
    except (json.JSONDecodeError, IndexError) as exc:
        raise PanoEditError(
            f"Could not verify the write to {path.name}: {exc}"
        ) from exc
    return {
        "heading": _maybe_float(entry.get("InitialViewHeadingDegrees")),
        "pitch": _maybe_float(entry.get("InitialViewPitchDegrees")),
        "hfov": _maybe_float(entry.get("InitialHorizontalFOVDegrees")),
        "pose": _maybe_float(entry.get("PoseHeadingDegrees")) or 0.0,
    }
