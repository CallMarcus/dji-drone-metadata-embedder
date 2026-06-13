"""Clean-room solar-position helper for footage verification (issue #216).

Computes the sun's azimuth and elevation for a WGS84 position at a UTC instant
using the standard NOAA solar-geometry algorithm. Pure stdlib ``math`` — no new
runtime dependencies. Accuracy is comfortably under +/-0.5 degrees away from the
horizon, ample for cross-checking shadow direction and length in footage.

Implemented clean-room from the public NOAA solar equations; no code copied.
"""

from __future__ import annotations

import math
from datetime import datetime


def _julian_day(when_utc: datetime) -> float:
    """Julian Day for a UTC datetime (proleptic Gregorian)."""
    year, month = when_utc.year, when_utc.month
    day = when_utc.day + (
        when_utc.hour
        + (when_utc.minute + (when_utc.second + when_utc.microsecond / 1e6) / 60) / 60
    ) / 24
    if month <= 2:
        year -= 1
        month += 12
    a = year // 100
    b = 2 - a + a // 4
    return (
        int(365.25 * (year + 4716))
        + int(30.6001 * (month + 1))
        + day
        + b
        - 1524.5
    )


def sun_position(lat: float, lon: float, when_utc: datetime) -> tuple[float, float]:
    """Return ``(azimuth_deg, elevation_deg)`` of the sun.

    ``lat``/``lon`` are WGS84 degrees (longitude positive east). ``when_utc`` is
    treated as UTC. Azimuth is 0-360 degrees clockwise from true north; elevation
    is -90..+90 degrees (negative means the sun is below the horizon). Geometric
    position (no atmospheric-refraction correction).
    """
    jd = _julian_day(when_utc)
    t = (jd - 2451545.0) / 36525.0  # Julian centuries since J2000.0

    # Geometric mean longitude/anomaly of the sun, and orbital eccentricity.
    l0 = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360.0
    m = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    mr = math.radians(m)

    # Sun's equation of centre and apparent ecliptic longitude.
    c = (
        math.sin(mr) * (1.914602 - t * (0.004817 + 0.000014 * t))
        + math.sin(2 * mr) * (0.019993 - 0.000101 * t)
        + math.sin(3 * mr) * 0.000289
    )
    true_long = l0 + c
    omega = 125.04 - 1934.136 * t
    lam = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))

    # Obliquity of the ecliptic (corrected) and solar declination.
    obliq0 = 23 + (26 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60) / 60
    obliq = obliq0 + 0.00256 * math.cos(math.radians(omega))
    decl = math.degrees(
        math.asin(math.sin(math.radians(obliq)) * math.sin(math.radians(lam)))
    )

    # Equation of time (minutes).
    y = math.tan(math.radians(obliq / 2)) ** 2
    l0r = math.radians(l0)
    eot = 4 * math.degrees(
        y * math.sin(2 * l0r)
        - 2 * e * math.sin(mr)
        + 4 * e * y * math.sin(mr) * math.cos(2 * l0r)
        - 0.5 * y * y * math.sin(4 * l0r)
        - 1.25 * e * e * math.sin(2 * mr)
    )

    # True solar time -> hour angle (degrees).
    utc_minutes = (
        when_utc.hour * 60
        + when_utc.minute
        + when_utc.second / 60
        + when_utc.microsecond / 6e7
    )
    tst = (utc_minutes + eot + 4 * lon) % 1440.0
    ha = tst / 4.0 - 180.0

    latr, declr, har = math.radians(lat), math.radians(decl), math.radians(ha)
    cos_zenith = math.sin(latr) * math.sin(declr) + math.cos(latr) * math.cos(declr) * math.cos(har)
    cos_zenith = max(-1.0, min(1.0, cos_zenith))
    zenith = math.acos(cos_zenith)
    elevation = 90.0 - math.degrees(zenith)

    sin_zenith = math.sin(zenith)
    if abs(sin_zenith) < 1e-9:
        # Sun at zenith or nadir: azimuth is undefined; return 0 by convention.
        azimuth = 0.0
    else:
        cos_az = (math.sin(latr) * math.cos(zenith) - math.sin(declr)) / (
            math.cos(latr) * sin_zenith
        )
        cos_az = max(-1.0, min(1.0, cos_az))
        az = math.degrees(math.acos(cos_az))
        azimuth = (az + 180.0) % 360.0 if ha > 0 else (540.0 - az) % 360.0

    return azimuth, elevation
