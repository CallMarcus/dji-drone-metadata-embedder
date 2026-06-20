"""ExifTool-backed extractor for DJI MP4 timed metadata (djmd/dbgi).

Reads the per-sample protobuf telemetry ExifTool decodes from a DJI MP4/MOV and
normalises it to the canonical :class:`~dji_metadata_embedder.utilities.TelemetrySample`
model, so the convert exporters and verify-sun work on sidecar-less footage.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


class Mp4TelemetryError(RuntimeError):
    """Raised when an MP4's timed metadata cannot be read or decoded."""


VIDEO_SUFFIXES = {".mp4", ".mov"}


def is_video(path: Path) -> bool:
    """True when ``path`` is a video we can probe for embedded telemetry."""
    return Path(path).suffix.lower() in VIDEO_SUFFIXES


def _sample_time_to_cue(seconds: float) -> str:
    """Format elapsed ``SampleTime`` seconds as an SRT-style ``HH:MM:SS,mmm`` cue."""
    total_ms = int(float(seconds) * 1000)
    ms = total_ms % 1000
    total_s = total_ms // 1000
    h, rem = divmod(total_s, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _parse_gps_datetime(value: str) -> datetime | None:
    """Parse ExifTool ``GPSDateTime`` (``2026:05:16 23:55:53.017Z``) as naive UTC.

    Returns ``None`` when the string is missing or unparseable. The result is
    timezone-naive to match the SRT ``dt`` convention; for video sources it is
    already UTC, so consumers apply a zero offset.
    """
    if not value:
        return None
    text = value.strip().rstrip("Z").strip()
    for fmt in ("%Y:%m:%d %H:%M:%S.%f", "%Y:%m:%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None
