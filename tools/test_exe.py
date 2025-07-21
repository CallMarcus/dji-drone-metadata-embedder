"""Test the built executable"""

import subprocess
import sys
from pathlib import Path


def test_executable() -> bool:
    exe_path = Path("dist/dji-embed.exe")

    if not exe_path.exists():
        print("\u274c Executable not found")
        return False

    # Test basic command
    result = subprocess.run(
        [str(exe_path), "--version"], capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"\u274c Version check failed: {result.stderr}")
        return False

    print(f"\u2705 Version: {result.stdout.strip()}")

    # Test help command
    result = subprocess.run([str(exe_path), "--help"], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"\u274c Help command failed: {result.stderr}")
        return False

    print("\u2705 Help command works")

    return True


if __name__ == "__main__":
    sys.exit(0 if test_executable() else 1)
