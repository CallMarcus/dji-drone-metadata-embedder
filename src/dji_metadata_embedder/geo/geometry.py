"""Shared great-circle and time-downsampling helpers for the geo exporters.

Extracted from ``cot.py`` so the CoT and footprint paths share one
implementation of bearing/distance/downsampling.
"""

from __future__ import annotations

import math
from datetime import datetime

from .track import TrackPoint

# Mean Earth radius (m, IUGG) for the haversine helpers.
EARTH_R = 6371008.8


def point_utc(p: TrackPoint) -> datetime:
    """Return *p*'s resolved UTC, or raise if a hand-built track skipped it."""
    if p.utc is None:
        raise ValueError(
            "TrackPoint.utc is None; this export requires build_track to "
            "populate it (got a Track built another way)"
        )
    return p.utc


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres between two WGS84 points."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(a))


def initial_bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial great-circle bearing (degrees, 0..360) from point 1 to point 2."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def downsample_by_time(points: list[TrackPoint], interval: float) -> list[TrackPoint]:
    """Keep the first point, then each point at least ``interval`` s after the
    last kept one (by ``utc``), always keeping the final point."""
    if not points:
        return []
    kept = [points[0]]
    last = point_utc(points[0])
    for p in points[1:-1]:
        if (point_utc(p) - last).total_seconds() >= interval:
            kept.append(p)
            last = point_utc(p)
    if len(points) > 1:
        kept.append(points[-1])
    return kept
