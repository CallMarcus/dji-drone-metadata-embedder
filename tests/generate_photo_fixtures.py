"""One-shot generator for the samples/photos/ fixtures.

Creates three tiny (under 1 KB) JPEGs: two GPS-tagged over Helsinki churches
(with an embedded EXIF thumbnail) and one without GPS. Requires ExifTool.
Run from the repo root:  uv run python tests/generate_photo_fixtures.py
"""

from __future__ import annotations

import base64
import shutil
import subprocess
import sys
from pathlib import Path

from dji_metadata_embedder.mp4_telemetry import _exiftool_exe

# Minimal valid 1x1 grey baseline JPEG (140 bytes, no EXIF).
_MINIMAL_JPEG_B64 = (
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////"
    "////////////////////////////////////////////////////////////wgALCAAB"
    "AAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="
)

_PHOTOS = Path(__file__).resolve().parents[1] / "samples" / "photos"

# name -> (lat, lon, alt) — Helsinki Cathedral and Temppeliaukio Church.
_GPS = {
    "church1.jpg": (60.170278, 24.952222, 95.3),
    "church2.jpg": (60.173047, 24.925150, 88.1),
}


def main() -> None:
    exiftool = _exiftool_exe()
    if shutil.which(exiftool) is None and not Path(exiftool).is_file():
        sys.exit("ExifTool required to regenerate fixtures — see https://exiftool.org")
    _PHOTOS.mkdir(parents=True, exist_ok=True)
    blob = base64.b64decode(_MINIMAL_JPEG_B64)
    thumb = _PHOTOS / "_thumb.jpg"
    thumb.write_bytes(blob)
    try:
        for name in (*_GPS, "no_gps.jpg"):
            (_PHOTOS / name).write_bytes(blob)
        for name, (lat, lon, alt) in _GPS.items():
            subprocess.run(
                [
                    exiftool, "-overwrite_original", "-n",
                    f"-GPSLatitude={lat}", "-GPSLatitudeRef=N",
                    f"-GPSLongitude={lon}", "-GPSLongitudeRef=E",
                    f"-GPSAltitude={alt}", "-GPSAltitudeRef=0",
                    "-DateTimeOriginal=2026:06:15 12:30:45",
                    "-Make=DJI", "-Model=FC8482",
                    "-ISO=100", "-ExposureTime=0.001", "-FNumber=1.7",
                    f"-ThumbnailImage<={thumb}",
                    str(_PHOTOS / name),
                ],
                check=True,
            )
        subprocess.run(
            [
                exiftool, "-overwrite_original",
                "-DateTimeOriginal=2026:06:15 12:31:00",
                "-Make=DJI", "-Model=FC8482",
                str(_PHOTOS / "no_gps.jpg"),
            ],
            check=True,
        )
    finally:
        thumb.unlink(missing_ok=True)
    for p in sorted(_PHOTOS.glob("*.jpg")):
        print(f"{p} ({p.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
