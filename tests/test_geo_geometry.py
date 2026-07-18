import math
from datetime import datetime, timedelta

from dji_metadata_embedder.geo.geometry import (
    haversine_m,
    initial_bearing_deg,
    downsample_by_time,
    point_utc,
)
from dji_metadata_embedder.geo.track import TrackPoint


def _p(lat, lon, secs):
    base = datetime(2026, 1, 1, 0, 0, 0)
    return TrackPoint(lat=lat, lon=lon, alt=0.0, timestamp="", utc=base + timedelta(seconds=secs))


def test_haversine_known_distance():
    # 0.001 deg latitude ~= 111.32 m.
    assert abs(haversine_m(0.0, 0.0, 0.001, 0.0) - 111.32) < 0.5


def test_initial_bearing_due_east():
    assert abs(initial_bearing_deg(0.0, 0.0, 0.0, 1.0) - 90.0) < 1e-6


def test_downsample_keeps_first_and_last():
    pts = [_p(0.0, 0.0, s) for s in (0, 1, 2, 3, 4)]
    kept = downsample_by_time(pts, 2.0)
    # First, one >=2s later, and the final point.
    assert [round((point_utc(p) - point_utc(pts[0])).total_seconds()) for p in kept] == [0, 2, 4]


# Oblique view-frustum ground projection (#265). The 45-degree-pitch cases
# have exact closed forms with the 24mm/4:3 lens (tan(HFOV/2) = 0.75,
# tan(VFOV/2) = 0.5625): the cosines cancel, so the far edge sits at
# 100 * (1 + 0.5625) / (1 - 0.5625) = 357.142857... m and the near edge at
# 100 * (1 - 0.5625) / (1 + 0.5625) = 28.0 m for a 100 m AGL camera.

M_PER_DEG = 111320.0
HFOV = math.degrees(2 * math.atan(0.75))
VFOV = math.degrees(2 * math.atan(0.5625))


def _ring_en(ring):
    """Ring [(lon, lat), ...] -> open list of (east_m, north_m) offsets."""
    return [(lon * M_PER_DEG, lat * M_PER_DEG) for lon, lat in ring[:-1]]


def test_frustum_nadir_matches_rectangle():
    from dji_metadata_embedder.geo.geometry import frustum_ground_ring
    ring = frustum_ground_ring(0.0, 0.0, 100.0, 0.0, -90.0, HFOV, VFOV, 10000.0)
    assert len(ring) == 5 and ring[0] == ring[-1]
    en = _ring_en(ring)
    assert max(abs(abs(e) - 75.0) for e, _ in en) < 1e-6
    assert max(abs(abs(n) - 56.25) for _, n in en) < 1e-6


def test_frustum_oblique_45_exact_trapezoid():
    from dji_metadata_embedder.geo.geometry import frustum_ground_ring
    ring = frustum_ground_ring(0.0, 0.0, 100.0, 0.0, -45.0, HFOV, VFOV, 10000.0)
    en = _ring_en(ring)
    norths = sorted(n for _, n in en)
    # Near corners at 28.0 m, far corners at 2500/7 = 357.142857 m north.
    assert abs(norths[0] - 28.0) < 1e-6 and abs(norths[1] - 28.0) < 1e-6
    assert abs(norths[2] - 2500.0 / 7.0) < 1e-6
    assert abs(norths[3] - 2500.0 / 7.0) < 1e-6
    # The far edge is wider across-track than the near edge (a trapezoid).
    far_w = max(abs(e) for e, n in en if n > 100)
    near_w = max(abs(e) for e, n in en if n < 100)
    assert far_w > near_w > 0


def test_frustum_clamps_rays_at_or_above_horizon():
    from dji_metadata_embedder.geo.geometry import frustum_ground_ring
    # Pitch -20 deg puts the top frustum corners ~9.4 deg ABOVE the horizon:
    # they never meet the ground, so they clamp to max_range along their
    # azimuth instead of shooting to infinity.
    ring = frustum_ground_ring(0.0, 0.0, 100.0, 0.0, -20.0, HFOV, VFOV, 500.0)
    dists = [math.hypot(e, n) for e, n in _ring_en(ring)]
    assert max(dists) < 500.0 + 1e-6
    assert sum(1 for d in dists if abs(d - 500.0) < 1e-6) == 2  # both far corners


def test_frustum_caps_finite_but_distant_corners():
    from dji_metadata_embedder.geo.geometry import frustum_ground_ring
    # At -45 deg everything hits the ground, but a 200 m cap still binds the
    # 357 m far corners.
    ring = frustum_ground_ring(0.0, 0.0, 100.0, 0.0, -45.0, HFOV, VFOV, 200.0)
    dists = [math.hypot(e, n) for e, n in _ring_en(ring)]
    assert max(dists) < 200.0 + 1e-6


def test_frustum_rotates_with_heading():
    from dji_metadata_embedder.geo.geometry import frustum_ground_ring
    north = frustum_ground_ring(0.0, 0.0, 100.0, 0.0, -45.0, HFOV, VFOV, 1000.0)
    east = frustum_ground_ring(0.0, 0.0, 100.0, 90.0, -45.0, HFOV, VFOV, 1000.0)
    # Heading east moves the far edge from +north onto +east.
    assert abs(max(n for _, n in _ring_en(north)) -
               max(e for e, _ in _ring_en(east))) < 1e-6
