"""
Build standalone Windows executable for DJI Metadata Embedder
Creates dji-embed.exe with all dependencies bundled
"""

import os
import sys
import shutil
from pathlib import Path
import PyInstaller.__main__


def build_executable():
    """Build the Windows executable using PyInstaller"""

    # Ensure we're in the project root
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    # Clean previous builds
    for path in ['build', 'dist']:
        if Path(path).exists():
            shutil.rmtree(path)

    # PyInstaller arguments
    args = [
        'src/dji_metadata_embedder/__main__.py',  # Entry point
        '--name=dji-embed',                        # Output name
        '--onefile',                               # Single executable
        '--console',                               # Console application
        '--icon=assets/icon.ico',                  # Icon (if exists)
        '--add-data=src/dji_metadata_embedder/templates;templates',
        '--hidden-import=dji_metadata_embedder',
        '--hidden-import=dji_metadata_embedder.cli',
        '--hidden-import=dji_metadata_embedder.core',
        '--hidden-import=dji_metadata_embedder.parsers',
        '--hidden-import=dji_metadata_embedder.telemetry_converter',
        '--hidden-import=dji_metadata_embedder.metadata_check',
        '--hidden-import=dji_metadata_embedder.wizard',
        '--collect-all=dji_metadata_embedder',
        '--distpath=dist',
        '--workpath=build',
        '--clean',
    ]

    # Run PyInstaller
    PyInstaller.__main__.run(args)

    print(f"✅ Executable built: dist/dji-embed.exe")

    # Calculate SHA256
    import hashlib
    exe_path = Path('dist/dji-embed.exe')
    if exe_path.exists():
        sha256 = hashlib.sha256(exe_path.read_bytes()).hexdigest()
        print(f"📊 SHA256: {sha256}")
        return sha256
    else:
        raise FileNotFoundError("Executable not created")


if __name__ == "__main__":
    build_executable()
