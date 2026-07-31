"""Tests for the platform seam in tools/build_exe.py.

The build script originally hard-coded Windows everywhere (``dist/dji-embed.exe``,
a ``.ico`` icon, implicit UPX). The macOS release leg (#414 Stage C) reuses the
same script on an arm64 runner, so the argument list and output path are built
by pure, platform-parameterized helpers that can be asserted here without
running PyInstaller — the same explicit-platform-seam pattern the GUI uses.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_module():
    path = Path(__file__).resolve().parent.parent / "tools" / "build_exe.py"
    spec = importlib.util.spec_from_file_location("build_exe", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


build_exe = _load_module()


def test_module_imports_without_pyinstaller():
    # Loading the module (as this file and tools/test_exe.py do) must not
    # require PyInstaller — only actually building does. CI installs the
    # ``build`` extra so this passes trivially there; the real guard is the
    # module-level ``_load_module()`` above, which fails collection in any
    # environment without PyInstaller (like a default dev checkout) if a
    # top-level ``import PyInstaller`` ever comes back.
    assert hasattr(build_exe, "build_executable")


def test_dist_binary_is_exe_on_windows_and_bare_elsewhere():
    assert build_exe.dist_binary("win32") == Path("dist/dji-embed.exe")
    assert build_exe.dist_binary("darwin") == Path("dist/dji-embed")
    assert build_exe.dist_binary("linux") == Path("dist/dji-embed")


def test_windows_args_are_identical_to_the_pre_macos_build():
    # Full-list equality, not membership: the Windows release leg must keep
    # producing exactly the argument list the old inline literal did.
    assert build_exe.pyinstaller_args(
        "_pyinstaller_entry.py", "win32", icon=Path("assets/icon.ico")
    ) == [
        "_pyinstaller_entry.py",
        "--name=dji-embed",
        "--onefile",
        "--console",
        "--paths=src",
        "--hidden-import=dji_metadata_embedder",
        "--hidden-import=dji_metadata_embedder.cli",
        "--hidden-import=dji_metadata_embedder.core",
        "--hidden-import=dji_metadata_embedder.telemetry_converter",
        "--hidden-import=dji_metadata_embedder.metadata_check",
        "--hidden-import=click",
        "--hidden-import=rich",
        "--distpath=dist",
        "--workpath=build",
        "--clean",
        f"--icon={Path('assets/icon.ico')}",
    ]


def test_macos_args_skip_windows_icon_and_disable_upx():
    # The .ico is Windows-only, and UPX-packed binaries break codesign.
    args = build_exe.pyinstaller_args(
        "_pyinstaller_entry.py", "darwin", icon=Path("assets/icon.ico")
    )
    assert not any(a.startswith("--icon") for a in args)
    assert "--noupx" in args


def test_macos_codesign_identity_signs_collected_binaries():
    # Embedded dylibs must carry the team ID or hardened-runtime library
    # validation kills the extracted onefile payload at runtime.
    args = build_exe.pyinstaller_args(
        "_pyinstaller_entry.py",
        "darwin",
        codesign_identity="Developer ID Application",
    )
    assert "--codesign-identity=Developer ID Application" in args


def test_macos_without_identity_builds_adhoc():
    args = build_exe.pyinstaller_args("_pyinstaller_entry.py", "darwin")
    assert not any(a.startswith("--codesign-identity") for a in args)


def test_codesign_identity_rejected_off_macos():
    with pytest.raises(ValueError):
        build_exe.pyinstaller_args(
            "_pyinstaller_entry.py", "win32", codesign_identity="Developer ID"
        )
