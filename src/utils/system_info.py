"""Utility functions for gathering basic system information."""

from __future__ import annotations

import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Dict


def get_windows_version() -> str:
    """Return the detected Windows version or ``"Unknown"``.

    Uses ``sys.getwindowsversion`` on Windows and safely falls back to
    ``"Unknown"`` on other platforms.
    """
    if platform.system() != "Windows" or not hasattr(sys, "getwindowsversion"):
        return "Unknown"

    ver = sys.getwindowsversion()  # type: ignore[attr-defined]
    if ver.major == 10:
        # Windows 10 or 11 share major version 10
        return "11" if ver.build >= 22000 else "10"
    if ver.major == 6 and ver.minor == 1:
        return "7"
    return "Unknown"


def get_python_info() -> Dict[str, str]:
    """Return the current Python executable path and version."""
    return {"version": platform.python_version(), "path": sys.executable}


def get_disk_space(path: Path) -> int:
    """Return free disk space for ``path`` in bytes."""
    usage = shutil.disk_usage(path)
    return usage.free


def has_admin_privileges() -> bool:
    """Return ``True`` if the current process has administrative rights."""
    if os.name == "nt":
        try:
            import ctypes

            if hasattr(ctypes, "windll"):
                return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
            return False
        except Exception:  # noqa: BLE001
            return False
    return os.geteuid() == 0


def get_system_architecture() -> str:
    """Return the system architecture string."""
    arch = platform.architecture()[0]
    return "64-bit" if arch.startswith("64") else "32-bit"


def get_system_summary() -> Dict[str, str | int]:
    """Return summary information about the current system."""
    return {
        "windows_version": get_windows_version(),
        "python_version": platform.python_version(),
        "python_path": sys.executable,
        "architecture": get_system_architecture(),
        "admin": has_admin_privileges(),
    }

