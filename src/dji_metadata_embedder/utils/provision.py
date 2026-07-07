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

import hashlib
import logging
import os
import platform
import shutil
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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


def _download(url: str, dest: Path) -> None:
    """Stream ``url`` to ``dest`` (no checksum here — see _verify_sha256)."""
    req = Request(url, headers={"User-Agent": "dji-embed"})
    with urlopen(req, timeout=60) as response, open(dest, "wb") as out:
        shutil.copyfileobj(response, out)


def _fetch_artifact(artifact: str, dest: Path) -> None:
    """Download ``artifact`` from the first mirror that responds."""
    errors: list[str] = []
    for mirror in _MIRRORS:
        url = mirror.format(artifact=artifact)
        try:
            logger.info("Downloading %s", url)
            _download(url, dest)
            return
        except (URLError, HTTPError, OSError) as exc:
            errors.append(f"{url}: {exc}")
    raise ProvisionError(
        "Could not download ExifTool from any mirror:\n  " + "\n  ".join(errors)
    )


def _verify_sha256(path: Path, expected: str) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        raise ProvisionError(
            f"Checksum mismatch for {path.name}: expected {expected}, got "
            f"{digest}. The download is corrupted or tampered with — "
            "nothing was installed."
        )
