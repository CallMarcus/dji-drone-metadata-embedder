#!/usr/bin/env python3
"""DJI Media Metadata Presence Checker

Check if video or image files already contain GPS, altitude, and creation
time metadata. Uses ``ffprobe`` and ``exiftool`` if available.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Dict, Optional
import logging

from rich.progress import Progress
from .utilities import setup_logging

CHECK = "\u2705"  # green check mark
CROSS = "\u274c"  # red cross


logger = logging.getLogger(__name__)


def run_ffprobe(path: Path) -> Optional[Dict]:
    """Return ffprobe JSON output for the media file or ``None`` on failure."""
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError):
        return None


def run_exiftool(path: Path) -> Optional[Dict]:
    """Return exiftool JSON output for the file or ``None`` on failure."""
    cmd = ["exiftool", "-j", str(path)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        return data[0] if isinstance(data, list) and data else None
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError):
        return None


def check_file(path: Path) -> Dict[str, bool]:
    """Check a single media file for common DJI metadata."""
    ffprobe_data = run_ffprobe(path) or {}
    exif_data = run_exiftool(path) or {}

    ff_tags = ffprobe_data.get("format", {}).get("tags", {})

    gps_present = (
        any(tag in exif_data for tag in ("GPSLatitude", "GPSLongitude"))
        or "location" in ff_tags
    )
    altitude_present = "GPSAltitude" in exif_data or "altitude" in ff_tags
    creation_time_present = "creation_time" in ff_tags or "CreateDate" in exif_data

    return {
        "gps": gps_present,
        "altitude": altitude_present,
        "creation_time": creation_time_present,
    }


def check_metadata(path: str | Path) -> Dict[str, bool]:
    """Public helper to check a media file for DJI metadata."""
    file_path = Path(path)
    if not file_path.exists():
        return {}
    return check_file(file_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check DJI media files for embedded flight metadata"
    )
    parser.add_argument("paths", nargs="+", help="Files or directories to check")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress info output"
    )
    args = parser.parse_args()

    setup_logging(args.verbose, args.quiet)

    files: list[Path] = []
    for p in args.paths:
        path = Path(p)
        if path.is_dir():
            files.extend(path.glob("*.mp4"))
            files.extend(path.glob("*.MP4"))
            files.extend(path.glob("*.mov"))
            files.extend(path.glob("*.MOV"))
            files.extend(path.glob("*.jpg"))
            files.extend(path.glob("*.JPG"))
        else:
            files.append(path)

    with Progress() as progress:
        task = progress.add_task("Checking", total=len(files))
        for file in files:
            result = check_file(file)
            status_parts = [
                f"{CHECK} GPS" if result["gps"] else f"{CROSS} GPS",
                f"{CHECK} altitude" if result["altitude"] else f"{CROSS} altitude",
                (
                    f"{CHECK} creation_time"
                    if result["creation_time"]
                    else f"{CROSS} creation_time"
                ),
            ]
            logger.info("%s: %s", file, ", ".join(status_parts))
            progress.advance(task)


if __name__ == "__main__":
    main()
