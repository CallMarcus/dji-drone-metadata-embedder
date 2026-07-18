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
# Metres per degree of latitude (WGS84 mean), shared by the flat-earth
# footprint projections.
M_PER_DEG_LAT = 111320.0


def frustum_ground_ring(
    lat: float,
    lon: float,
    agl: float,
    heading_deg: float,
    pitch_deg: float,
    hfov_deg: float,
    vfov_deg: float,
    max_range_m: float,
) -> list[tuple[float, float]]:
    """Project the four camera-frustum corner rays onto flat ground (#265).

    The camera sits ``agl`` metres above the ground plane, yawed to
    ``heading_deg`` (clockwise from north) and pitched ``pitch_deg`` (DJI
    convention: 0 = horizon, -90 = nadir). Corner rays that meet the ground
    are projected exactly; rays at or above the horizon — and ground hits
    beyond ``max_range_m`` — clamp to ``max_range_m`` along their azimuth, so
    a near-horizon frame degrades to a capped trapezoid instead of an
    unbounded one. Returns a closed ``[(lon, lat), ...]`` ring
    (far-left, far-right, near-right, near-left in image terms).
    """
    th = math.radians(pitch_deg)
    tan_h = math.tan(math.radians(hfov_deg) / 2)
    tan_v = math.tan(math.radians(vfov_deg) / 2)
    fwd_n, fwd_z = math.cos(th), math.sin(th)  # optical axis, pre-yaw
    up_n, up_z = -math.sin(th), math.cos(th)   # camera-up, pre-yaw
    psi = math.radians(heading_deg)
    cos_p, sin_p = math.cos(psi), math.sin(psi)
    m_per_deg_lon = M_PER_DEG_LAT * max(math.cos(math.radians(lat)), 1e-6)

    ring: list[tuple[float, float]] = []
    for sh, sv in ((-1, 1), (1, 1), (1, -1), (-1, -1)):
        de = sh * tan_h                        # east component, pre-yaw
        dn = fwd_n + sv * tan_v * up_n
        dz = fwd_z + sv * tan_v * up_z
        horiz = math.hypot(de, dn)
        if dz < 0:
            dist = min(agl / -dz * horiz, max_range_m)
        else:
            dist = max_range_m                 # ray at/above the horizon
        if horiz > 1e-12:
            east0, north0 = de / horiz * dist, dn / horiz * dist
        else:
            east0, north0 = 0.0, 0.0           # ray straight down
        east = east0 * cos_p + north0 * sin_p
        north = -east0 * sin_p + north0 * cos_p
        ring.append((lon + east / m_per_deg_lon, lat + north / M_PER_DEG_LAT))
    ring.append(ring[0])
    return ring


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
