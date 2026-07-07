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
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Iterable
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


def _reject_unsafe(names: Iterable[str]) -> None:
    """Refuse archive members that would escape the extraction directory."""
    for name in names:
        posix = PurePosixPath(name.replace("\\", "/"))
        if (
            name.startswith(("/", "\\"))
            or re.match(r"^[A-Za-z]:", name)
            or ".." in posix.parts
        ):
            raise ProvisionError(f"Unsafe path in archive: {name!r}")


def _install_windows(archive: Path, install_dir: Path) -> Path:
    """Extract the Windows zip; rename exiftool(-k).exe; keep exiftool_files/."""
    with zipfile.ZipFile(archive) as zf:
        _reject_unsafe(zf.namelist())
        with tempfile.TemporaryDirectory(dir=install_dir.parent) as tmp:
            zf.extractall(tmp)
            exe = next(Path(tmp).rglob("exiftool(-k).exe"), None)
            if exe is None:
                raise ProvisionError("exiftool(-k).exe not found in archive")
            exe.rename(exe.parent / "exiftool.exe")
            if install_dir.exists():
                shutil.rmtree(install_dir)
            shutil.move(str(exe.parent), str(install_dir))
    return install_dir / "exiftool.exe"


def _install_unix(archive: Path, install_dir: Path) -> Path:
    """Extract the Perl distribution tarball; chmod +x the exiftool script."""
    with tarfile.open(archive, "r:gz") as tf:
        _reject_unsafe(tf.getnames())
        with tempfile.TemporaryDirectory(dir=install_dir.parent) as tmp:
            try:
                tf.extractall(tmp, filter="data")
            except TypeError:  # Python < 3.12 without extraction filters
                tf.extractall(tmp)
            top = next(Path(tmp).glob("Image-ExifTool-*"), None)
            if top is None:
                raise ProvisionError("exiftool script not found in archive")
            script = top / "exiftool"
            if not script.exists():
                raise ProvisionError("exiftool script not found in archive")
            script.chmod(
                script.stat().st_mode
                | stat.S_IXUSR
                | stat.S_IXGRP
                | stat.S_IXOTH
            )
            if install_dir.exists():
                shutil.rmtree(install_dir)
            shutil.move(str(top), str(install_dir))
    return install_dir / "exiftool"


def _smoke_version(exe: Path) -> str | None:
    """Run ``exe -ver``; return the reported version or ``None``."""
    try:
        proc = subprocess.run(
            [str(exe), "-ver"], capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.strip() or None


def provision_exiftool(root: Path | None = None, force: bool = False) -> Path:
    """Install the pinned ExifTool into the tools dir; return the executable.

    No-op (returns the existing path) when the pinned version is already
    provisioned and answers ``-ver``, unless ``force``. Raises
    :class:`ProvisionError` on any download/verify/install failure — a failed
    run never leaves a partial install behind.
    """
    root = root if root is not None else tools_dir()
    root.mkdir(parents=True, exist_ok=True)
    install_dir = root / f"exiftool-{EXIFTOOL_VERSION}"

    existing = provisioned_exiftool(root)
    if existing is not None and not force:
        if _smoke_version(existing) == EXIFTOOL_VERSION:
            logger.info(
                "ExifTool %s already provisioned at %s", EXIFTOOL_VERSION, existing
            )
            return existing
        logger.warning("Provisioned ExifTool at %s is broken; reinstalling", existing)

    windows = platform.system() == "Windows"
    if not windows and shutil.which("perl") is None:
        raise ProvisionError(
            "Perl is required to run ExifTool on this platform. Install it "
            "with your package manager (e.g. 'apt install perl'); on macOS "
            "it ships with the OS."
        )
    artifact = (
        f"exiftool-{EXIFTOOL_VERSION}_64.zip"
        if windows
        else f"Image-ExifTool-{EXIFTOOL_VERSION}.tar.gz"
    )

    tmp_archive = root / (artifact + ".part")
    try:
        _fetch_artifact(artifact, tmp_archive)
        _verify_sha256(tmp_archive, EXIFTOOL_SHA256[artifact])
        exe = (
            _install_windows(tmp_archive, install_dir)
            if windows
            else _install_unix(tmp_archive, install_dir)
        )
    finally:
        tmp_archive.unlink(missing_ok=True)

    got = _smoke_version(exe)
    if got != EXIFTOOL_VERSION:
        raise ProvisionError(
            f"Installed ExifTool reports version {got!r}, expected "
            f"{EXIFTOOL_VERSION}. Try again with --force."
        )
    logger.info("ExifTool %s installed at %s", EXIFTOOL_VERSION, exe)
    return exe
