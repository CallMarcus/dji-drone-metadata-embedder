"""Camera ground-footprint polygons projected from a :class:`Track`.

Model (spec 2026-06-20): assume a nadir (straight-down) camera and size the
footprint from height-above-ground and a 35mm-equivalent field of view, rotated
to flight heading or to real gimbal yaw when the format carries it. Strongly
oblique gimbal frames are skipped, not drawn. Flat-earth equirectangular
projection (accurate at footprint scale).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# DJI gimbal pitch: 0 deg = forward/horizon, -90 deg = straight down (nadir).
NADIR_PITCH_DEG = -90.0
# Skip footprints whose gimbal pitch is more than this far off nadir.
OBLIQUE_GATE_DEG = 30.0
# Metres per degree of latitude (WGS84 mean).
_M_PER_DEG_LAT = 111320.0


@dataclass(frozen=True)
class LensSpec:
    """A camera's 35mm-equivalent native focal length and sensor readout aspect."""

    native_focal_equiv_mm: float
    aspect: tuple[int, int]


# Generic wide fallback (~84 deg HFOV, 4:3) when the model is unknown and the
# SRT carries no focal_len. First-pass estimates; confirm against fixtures.
DEFAULT_LENS = LensSpec(native_focal_equiv_mm=20.0, aspect=(4, 3))

FOV_TABLE: dict[str, LensSpec] = {
    "air3": LensSpec(native_focal_equiv_mm=24.0, aspect=(4, 3)),
    "avata2": LensSpec(native_focal_equiv_mm=12.7, aspect=(4, 3)),
    "mini4pro": LensSpec(native_focal_equiv_mm=24.0, aspect=(4, 3)),
    "avata360": LensSpec(native_focal_equiv_mm=24.0, aspect=(4, 3)),
}


def lens_for(model: str | None) -> LensSpec:
    """Return the :class:`LensSpec` for *model*, falling back to the generic wide
    default (with a warning) when the model is unknown."""
    if model is None:
        return DEFAULT_LENS
    lens = FOV_TABLE.get(model.lower())
    if lens is None:
        logger.warning(
            "Unknown --model %r; using a generic wide lens. Known: %s",
            model,
            ", ".join(sorted(FOV_TABLE)),
        )
        return DEFAULT_LENS
    return lens


def fov_degrees(lens: LensSpec, focal_len_equiv: float | None) -> tuple[float, float]:
    """Return (HFOV, VFOV) in degrees for *lens*.

    Uses *focal_len_equiv* (a 35mm-equivalent focal length from the SRT, handling
    zoom) when given, else the lens's native equivalent focal. FOV is computed
    against a full-frame (36 mm wide) reference; the reference height follows the
    lens aspect.
    """
    f = focal_len_equiv if focal_len_equiv else lens.native_focal_equiv_mm
    aw, ah = lens.aspect
    full_w = 36.0
    full_h = 36.0 * ah / aw
    hfov = math.degrees(2 * math.atan(full_w / (2 * f)))
    vfov = math.degrees(2 * math.atan(full_h / (2 * f)))
    return hfov, vfov


def ground_footprint(
    lat: float,
    lon: float,
    agl: float,
    hfov_deg: float,
    vfov_deg: float,
    bearing_deg: float,
) -> list[tuple[float, float]]:
    """Return a closed footprint ring as ``[(lon, lat), ...]``.

    The rectangle is centred under ``(lat, lon)``, sized by ``agl`` and the
    field of view, and rotated so its along-track axis points to ``bearing_deg``
    (clockwise from north).
    """
    half_w = agl * math.tan(math.radians(hfov_deg) / 2)  # across-track, metres
    half_h = agl * math.tan(math.radians(vfov_deg) / 2)  # along-track, metres
    th = math.radians(bearing_deg)
    cos_t, sin_t = math.cos(th), math.sin(th)
    m_per_deg_lon = _M_PER_DEG_LAT * max(math.cos(math.radians(lat)), 1e-6)

    ring: list[tuple[float, float]] = []
    for e0, n0 in (
        (half_w, half_h),
        (half_w, -half_h),
        (-half_w, -half_h),
        (-half_w, half_h),
    ):
        east = e0 * cos_t + n0 * sin_t
        north = -e0 * sin_t + n0 * cos_t
        ring.append((lon + east / m_per_deg_lon, lat + north / _M_PER_DEG_LAT))
    ring.append(ring[0])
    return ring
