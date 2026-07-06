"""Shared ExifTool executable resolver.

A single place to resolve the ExifTool binary so every call site (MP4 timed
metadata, the photomap scan, and any future consumer) agrees on the same
override semantics: honour ``DJIEMBED_EXIFTOOL_PATH`` when it points at a real
file, otherwise fall back to ``exiftool`` on ``PATH``.
"""

from __future__ import annotations

import os
from pathlib import Path


def exiftool_exe() -> str:
    """Resolve the ExifTool executable (env override, else PATH ``exiftool``)."""
    env = os.environ.get("DJIEMBED_EXIFTOOL_PATH")
    if env and Path(env).exists():
        return env
    return "exiftool"
