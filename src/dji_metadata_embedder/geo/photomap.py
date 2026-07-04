"""Still-photo location model and exporters (GeoJSON, KML).

One batch ExifTool scan of a photo directory (JPG/JPEG/DNG) yields a
:class:`PhotoPoint` list — the single model every photomap writer consumes:
GeoJSON and KML here, the clustered HTML map in :mod:`.photomap_html`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from ..utilities import is_gps_fix

logger = logging.getLogger(__name__)


@dataclass
class PhotoPoint:
    """One GPS-tagged photo: WGS84 lat/lon, altitude (m, 0.0 when the EXIF has
    none), source filename, and optional capture metadata for popups."""

    lat: float
    lon: float
    alt: float
    name: str
    timestamp: str | None = None
    model: str | None = None
    iso: int | None = None
    exposure: float | None = None
    fnum: float | None = None
    thumbnail_b64: str | None = None


def _display_datetime(value: object) -> str | None:
    """EXIF ``2026:06:15 12:30:45`` -> ``2026-06-15 12:30:45`` (display only)."""
    if not isinstance(value, str) or not value:
        return None
    date, _, time = value.partition(" ")
    return f"{date.replace(':', '-')} {time}".strip()


def _maybe_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return None


def _maybe_float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def format_exposure(exposure: float | None) -> str | None:
    """Format ExposureTime seconds for display: ``0.001`` -> ``1/1000 s``."""
    if not exposure or exposure <= 0:
        return None
    if exposure < 1:
        return f"1/{round(1 / exposure)} s"
    return f"{exposure:g} s"


def camera_summary(p: PhotoPoint) -> str:
    """One display line, e.g. ``FC8482 · ISO 100 · 1/1000 s · f/1.7``.

    Missing parts are omitted; all-missing yields an empty string."""
    parts = [
        p.model,
        f"ISO {p.iso}" if p.iso is not None else None,
        format_exposure(p.exposure),
        f"f/{p.fnum:g}" if p.fnum is not None else None,
    ]
    return " · ".join(x for x in parts if x)


def points_from_exiftool_json(data: list[dict]) -> tuple[list[PhotoPoint], list[str]]:
    """Map an ExifTool ``-json`` scan to ``(points, skipped_names)``.

    Photos without a usable GPS fix (missing tags, or the (0, 0) no-fix
    placeholder) go to ``skipped_names``. Both lists are sorted by filename so
    output is deterministic regardless of scan order.
    """
    points: list[PhotoPoint] = []
    skipped: list[str] = []
    for entry in data:
        name = Path(str(entry.get("SourceFile", "?"))).name
        lat = _maybe_float(entry.get("GPSLatitude"))
        lon = _maybe_float(entry.get("GPSLongitude"))
        if lat is None or lon is None or not is_gps_fix(lat, lon):
            skipped.append(name)
            continue
        thumb = entry.get("ThumbnailImage")
        thumb_b64 = (
            thumb[len("base64:"):]
            if isinstance(thumb, str) and thumb.startswith("base64:")
            else None
        )
        points.append(
            PhotoPoint(
                lat=lat,
                lon=lon,
                alt=_maybe_float(entry.get("GPSAltitude")) or 0.0,
                name=name,
                timestamp=_display_datetime(entry.get("DateTimeOriginal")),
                model=entry.get("Model"),
                iso=_maybe_int(entry.get("ISO")),
                exposure=_maybe_float(entry.get("ExposureTime")),
                fnum=_maybe_float(entry.get("FNumber")),
                thumbnail_b64=thumb_b64,
            )
        )
    points.sort(key=lambda p: p.name)
    skipped.sort()
    return points, skipped
