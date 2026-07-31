"""
Build the standalone dji-embed executable for the current platform.

Windows (release-exe.yml) and macOS arm64 (release-macos.yml) share this
script; the platform differences live in the pure helpers below so the
argument list can be unit-tested without PyInstaller installed.
"""

import os
import shutil
import sys
from pathlib import Path
from typing import List, Optional


def dist_binary(platform: str = sys.platform) -> Path:
    """Path of the built binary, relative to the project root."""
    name = "dji-embed.exe" if platform == "win32" else "dji-embed"
    return Path("dist") / name


def pyinstaller_args(
    entry_script: str,
    platform: str = sys.platform,
    icon: Optional[Path] = None,
    codesign_identity: Optional[str] = None,
) -> List[str]:
    """PyInstaller argument list for *platform*."""
    if codesign_identity and platform != "darwin":
        raise ValueError("codesign_identity is macOS-only")

    args = [
        entry_script,
        "--name=dji-embed",
        "--onefile",  # Single executable
        "--console",  # Console application
        "--paths=src",  # Add src to Python path
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
    ]

    if platform == "win32":
        # The .ico is Windows-only; macOS icons only matter for the Stage D
        # .app bundle, and a bare CLI binary has nowhere to show one.
        if icon is not None:
            args.append(f"--icon={icon}")
    elif platform == "darwin":
        # UPX-packed binaries break codesign, and every embedded dylib must
        # carry the Developer ID team ID or hardened-runtime library
        # validation kills the extracted onefile payload at runtime.
        args.append("--noupx")
        if codesign_identity:
            args.append(f"--codesign-identity={codesign_identity}")

    return args


def build_executable() -> str:
    """Build the executable with PyInstaller and return its SHA256."""
    import hashlib

    import PyInstaller.__main__

    # Ensure we're in the project root
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    # Clean previous builds
    for path in ["build", "dist", "dji-embed.spec"]:
        if Path(path).exists():
            if Path(path).is_dir():
                shutil.rmtree(path)
            else:
                Path(path).unlink()

    # Create a simple entry point script
    entry_script = Path("_pyinstaller_entry.py")
    entry_script.write_text(
        """
import sys
from dji_metadata_embedder.cli import main

if __name__ == '__main__':
    main()
"""
    )

    try:
        icon_path = Path("assets/icon.ico")
        args = pyinstaller_args(
            str(entry_script),
            icon=icon_path if icon_path.exists() else None,
            codesign_identity=(
                os.environ.get("MACOS_CODESIGN_IDENTITY")
                if sys.platform == "darwin"
                else None
            ),
        )

        print("Building executable...")
        PyInstaller.__main__.run(args)

        binary = dist_binary()
        if not binary.exists():
            raise FileNotFoundError("Executable not created")

        print(f"SUCCESS: Executable built at {binary}")
        sha256 = hashlib.sha256(binary.read_bytes()).hexdigest()
        print(f"SHA256: {sha256}")
        return sha256

    finally:
        # Clean up temporary entry script
        if entry_script.exists():
            entry_script.unlink()


if __name__ == "__main__":
    build_executable()
