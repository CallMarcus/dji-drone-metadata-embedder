"""Locate FFmpeg and read its version, for ``doctor`` (#579).

Mirrors :mod:`.exiftool`: the resolution order is the same one the
dependency check and the embedder use (``DJIEMBED_FFMPEG_PATH`` override,
then the ``PATH`` lookup), so ``doctor`` reports the copy that will
actually run. On Windows several copies commonly coexist (the bootstrap
script's ``%LOCALAPPDATA%\\dji-embed\\bin``, the installer's ``tools\\``, a
winget install), which is why the resolved path is reported next to the
version.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

# The first line of ``ffmpeg -version`` is "ffmpeg version <token> Copyright
# ...". The token is whatever the packager put there: "9.0.2" from a distro
# build, "9.0.2-essentials_build-www.gyan.dev" from gyan.dev, or
# "N-12345-gabcdef" from a git snapshot. Capture it whole.
_VERSION_RE = re.compile(r"^ffmpeg version (\S+)", re.MULTILINE)


def ffmpeg_exe() -> str | None:
    """Resolve the FFmpeg executable (env override → PATH), or ``None``."""
    env = os.environ.get("DJIEMBED_FFMPEG_PATH")
    if env and Path(env).exists():
        return env
    return shutil.which("ffmpeg")


def ffmpeg_version(exe: str | None = None) -> str | None:
    """Version token from the ``-version`` banner of the resolved (or given)
    FFmpeg, or ``None`` when it is absent, fails, or prints something else."""
    exe = exe or ffmpeg_exe()
    if exe is None:
        return None
    try:
        proc = subprocess.run(
            [exe, "-version"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    match = _VERSION_RE.search(proc.stdout or proc.stderr or "")
    return match.group(1) if match else None
