"""
Build standalone Windows executable for DJI Metadata Embedder
Creates dji-embed.exe with all dependencies bundled
"""

import os
import shutil
from pathlib import Path
import PyInstaller.__main__


def build_executable():
    """Build the Windows executable using PyInstaller"""

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
        # PyInstaller arguments
        args = [
            str(entry_script),  # Entry point
            "--name=dji-embed",  # Output name
            "--onefile",  # Single executable
            "--console",  # Console application
            "--paths=src",  # Add src to Python path
            "--hidden-import=dji_metadata_embedder",
            "--hidden-import=dji_metadata_embedder.cli",
            "--hidden-import=dji_metadata_embedder.core",
            "--hidden-import=dji_metadata_embedder.parsers",
            "--hidden-import=dji_metadata_embedder.telemetry_converter",
            "--hidden-import=dji_metadata_embedder.metadata_check",
            "--hidden-import=dji_metadata_embedder.wizard",
            "--hidden-import=click",
            "--hidden-import=rich",
            "--hidden-import=tqdm",
            "--distpath=dist",
            "--workpath=build",
            "--clean",
        ]

        # Add icon if it exists
        icon_path = Path("assets/icon.ico")
        if icon_path.exists():
            args.append(f"--icon={icon_path}")

        # Run PyInstaller
        print("Building executable...")
        PyInstaller.__main__.run(args)

        print("Executable built: dist/dji-embed.exe")

        # Calculate SHA256
        import hashlib

        exe_path = Path("dist/dji-embed.exe")
        if exe_path.exists():
            sha256 = hashlib.sha256(exe_path.read_bytes()).hexdigest()
            print(f"SHA256: {sha256}")
            return sha256
        else:
            raise FileNotFoundError("Executable not created")

    finally:
        # Clean up temporary entry script
        if entry_script.exists():
            entry_script.unlink()


if __name__ == "__main__":
    build_executable()
