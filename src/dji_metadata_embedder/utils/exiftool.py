"""Shared ExifTool executable resolver.

A single place to resolve the ExifTool binary so every call site (MP4 timed
metadata, the photomap scan, and any future consumer) agrees on the same
semantics: ``DJIEMBED_EXIFTOOL_PATH`` when it points at a real file, else the
copy provisioned by ``dji-embed doctor --install exiftool``, else ``exiftool``
on ``PATH``.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .provision import provisioned_exiftool


def exiftool_exe() -> str:
    """Resolve the ExifTool executable (env override → provisioned → PATH)."""
    env = os.environ.get("DJIEMBED_EXIFTOOL_PATH")
    if env and Path(env).exists():
        return env
    provisioned = provisioned_exiftool()
    if provisioned is not None:
        return str(provisioned)
    return "exiftool"


def exiftool_source() -> str:
    """How :func:`exiftool_exe` resolved: ``env``, ``provisioned``, or ``PATH``."""
    env = os.environ.get("DJIEMBED_EXIFTOOL_PATH")
    if env and Path(env).exists():
        return "env"
    if provisioned_exiftool() is not None:
        return "provisioned"
    return "PATH"


def exiftool_version(exe: str | None = None) -> str | None:
    """``-ver`` output of the resolved (or given) ExifTool, or ``None``."""
    try:
        proc = subprocess.run(
            [exe or exiftool_exe(), "-ver"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.strip() or None


# Minimum ExifTool release that decodes DJI djmd/dbgi timed metadata at all.
EXIFTOOL_BASELINE = "13.05"

# Per-model floors: schema key (matched against probe()'s pb_file string)
# -> (human model name, minimum ExifTool release that decodes it).
EXIFTOOL_FLOORS: dict[str, tuple[str, str]] = {
    "dvtm_NEO.proto": ("Neo", "13.35"),
    "dvtm_Air3s.proto": ("Air 3S", "13.39"),
    "dvtm_Mini5Pro.proto": ("Mini 5 Pro", "13.52"),
}

_INSTALL_HINT = "run: dji-embed doctor --install exiftool"


def version_key(ver: str) -> tuple[int, int]:
    """Sort key for ExifTool ``MAJOR.MINOR`` versions ("13.5" sorts below "13.39")."""
    major, _, minor = ver.strip().partition(".")
    try:
        return int(major), int(minor or 0)
    except ValueError:
        return (0, 0)


def decode_floor(schema: str | None) -> str:
    """Minimum ExifTool version needed to decode ``schema`` (baseline if unknown)."""
    if schema:
        for key, (_model, floor) in EXIFTOOL_FLOORS.items():
            if key in schema:
                return floor
    return EXIFTOOL_BASELINE


def describe_decode_capability(ver: str) -> str:
    """One-line doctor verdict for MP4 timed-metadata decoding at version ``ver``."""
    if version_key(ver) < version_key(EXIFTOOL_BASELINE):
        return (
            f"UNAVAILABLE — {ver} is below the {EXIFTOOL_BASELINE} baseline; "
            f"{_INSTALL_HINT}"
        )
    lagging = [
        (model, floor)
        for model, floor in EXIFTOOL_FLOORS.values()
        if version_key(ver) < version_key(floor)
    ]
    if lagging:
        detail = ", ".join(f"{model} needs >= {floor}" for model, floor in lagging)
        return f"LIMITED — {ver}: {detail}; {_INSTALL_HINT}"
    newest = max((floor for _model, floor in EXIFTOOL_FLOORS.values()), key=version_key)
    return f"OK ({ver} >= {newest}, covers all supported models)"
