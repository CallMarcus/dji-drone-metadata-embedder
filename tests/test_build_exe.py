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
    # The dev/test environment does not install the ``build`` extra; loading
    # the module (as this file and tools/test_exe.py do) must not require
    # PyInstaller — only actually building does.
    assert hasattr(build_exe, "build_executable")


def test_dist_binary_is_exe_on_windows_and_bare_elsewhere():
    assert build_exe.dist_binary("win32") == Path("dist/dji-embed.exe")
    assert build_exe.dist_binary("darwin") == Path("dist/dji-embed")
    assert build_exe.dist_binary("linux") == Path("dist/dji-embed")


def test_windows_args_keep_the_icon_and_historic_shape():
    args = build_exe.pyinstaller_args(
        "_pyinstaller_entry.py", "win32", icon=Path("assets/icon.ico")
    )
    assert args[0] == "_pyinstaller_entry.py"
    assert "--onefile" in args
    assert "--name=dji-embed" in args
    assert f"--icon={Path('assets/icon.ico')}" in args
    assert "--hidden-import=dji_metadata_embedder.cli" in args
    assert not any(a.startswith("--codesign-identity") for a in args)
    assert "--noupx" not in args


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
