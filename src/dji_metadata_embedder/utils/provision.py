"""On-demand, checksum-verified ExifTool provisioning.

Downloads the pinned ExifTool release into a per-user tools directory so
platforms with stale system packages (e.g. Ubuntu's 12.76, which decodes no
DJI GPS) get a current decoder without admin rights. Only ever invoked
explicitly via ``dji-embed doctor --install exiftool`` — normal commands
never touch the network.

Upgrading the pin = bump ``EXIFTOOL_VERSION`` and the two SHA-256 values
from https://exiftool.org/checksums.txt. Nothing else.
"""

from __future__ import annotations

import logging
import os
import platform
from pathlib import Path

logger = logging.getLogger(__name__)

EXIFTOOL_VERSION = "13.59"

# SHA-256 pins from https://exiftool.org/checksums.txt at pin time. The
# artifact is identical on every mirror, so the checksum — not the host —
# is what we trust.
EXIFTOOL_SHA256 = {
    # Windows standalone exe bundle
    f"exiftool-{EXIFTOOL_VERSION}_64.zip": (
        "44b512b25af500724ba579d0a53c8fc5851628b692dd5e5d94ae4a15c2cba9ec"
    ),
    # Linux/macOS Perl distribution (runs wherever perl exists)
    f"Image-ExifTool-{EXIFTOOL_VERSION}.tar.gz": (
        "668ea3acececb7235fbd0f4900e72d5f12c9b07e5c778fd36cb1e9b5828fd65a"
    ),
}

# Tried in order. exiftool.org hosts only the current release (pinned URLs
# 404 once the next version ships); SourceForge keeps every version.
_MIRRORS = (
    "https://exiftool.org/{artifact}",
    "https://downloads.sourceforge.net/project/exiftool/{artifact}",
)


class ProvisionError(RuntimeError):
    """Raised when downloading, verifying, or installing ExifTool fails."""


def tools_dir() -> Path:
    """Per-user directory for provisioned tools (no admin rights needed)."""
    env = os.environ.get("DJIEMBED_TOOLS_DIR")
    if env:
        return Path(env)
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
    return base / "dji-embed" / "tools"


def provisioned_exiftool(root: Path | None = None) -> Path | None:
    """Path to the provisioned ExifTool executable, or ``None`` if absent."""
    root = root if root is not None else tools_dir()
    exe = "exiftool.exe" if platform.system() == "Windows" else "exiftool"
    path = root / f"exiftool-{EXIFTOOL_VERSION}" / exe
    return path if path.exists() else None
