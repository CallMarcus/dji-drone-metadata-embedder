"""Tests for the clean-room NOAA solar-position helper (issue #216)."""

# Expected az/el values were cross-checked against the solar-noon physical
# invariant (az~180, el~90-lat at equinox) — see test_solar_noon_invariant_equinox.

from datetime import datetime

from dji_metadata_embedder.geo.solar import sun_position


def _close(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol


def test_sun_position_stockholm_winter():
    az, el = sun_position(59.0, 18.0, datetime(2024, 1, 1, 10, 0, 0))
    assert _close(az, 168.117, 0.2)
    assert _close(el, 7.291, 0.2)


def test_sun_position_southern_hemisphere():
    az, el = sun_position(-33.87, 151.21, datetime(2024, 12, 21, 2, 0, 0))
    assert _close(az, 351.534, 0.2)
    assert _close(el, 79.465, 0.2)


def test_sun_position_high_latitude():
    az, el = sun_position(69.65, 18.96, datetime(2024, 6, 21, 10, 0, 0))
    assert _close(az, 165.427, 0.2)
    assert _close(el, 43.280, 0.2)


def test_solar_noon_invariant_equinox():
    # Independent physics anchor: at local solar noon on the equinox the sun is
    # due south (az ~180) and elevation ~ 90 - latitude.
    az, el = sun_position(40.0, 0.0, datetime(2024, 3, 20, 12, 7, 0))
    assert _close(az, 180.0, 0.3)
    assert _close(el, 90.0 - 40.0, 0.5)
