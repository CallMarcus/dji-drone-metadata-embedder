from datetime import datetime, timedelta

from dji_metadata_embedder.geo.footprint import (
    DEFAULT_LENS,
    FOV_TABLE,
    Footprint,
    LensSpec,
    build_footprints,
    fov_degrees,
    ground_footprint,
)
from dji_metadata_embedder.geo.track import Track, TrackPoint

M_PER_DEG = 111320.0


def test_fov_24mm_fullframe_4x3():
    hfov, vfov = fov_degrees(LensSpec(24.0, (4, 3)), None)
    assert abs(hfov - 73.7398) < 1e-3
    assert abs(vfov - 58.7155) < 1e-3


def test_fov_uses_srt_focal_when_present():
    # 12 mm-equivalent is wider than the 24 mm native focal.
    wide, _ = fov_degrees(LensSpec(24.0, (4, 3)), 12.0)
    native, _ = fov_degrees(LensSpec(24.0, (4, 3)), None)
    assert wide > native


def test_ground_footprint_nadir_north_aligned():
    # 100 m AGL, 24mm/4:3 -> half_width 75.0 m, half_height 56.25 m.
    hfov, vfov = fov_degrees(LensSpec(24.0, (4, 3)), None)
    ring = ground_footprint(0.0, 0.0, 100.0, hfov, vfov, 0.0)
    assert len(ring) == 5
    assert ring[0] == ring[-1]
    lon, lat = ring[0]
    assert abs(lon - 75.0 / M_PER_DEG) < 1e-6
    assert abs(lat - 56.25 / M_PER_DEG) < 1e-6


def test_ground_footprint_rotates_with_bearing():
    hfov, vfov = fov_degrees(LensSpec(24.0, (4, 3)), None)
    nadir = ground_footprint(0.0, 0.0, 100.0, hfov, vfov, 0.0)
    east = ground_footprint(0.0, 0.0, 100.0, hfov, vfov, 90.0)
    # Rotating by 90 deg moves the along-track (north) extent onto east.
    assert abs(max(lon for lon, _ in east) - 56.25 / M_PER_DEG) < 1e-6
    assert abs(max(lon for lon, _ in nadir) - 75.0 / M_PER_DEG) < 1e-6


def test_default_lens_and_table_present():
    assert isinstance(DEFAULT_LENS, LensSpec)
    assert "air3" in FOV_TABLE


def _pt(lat, lon, secs, **kw):
    base = datetime(2026, 1, 1)
    return TrackPoint(lat=lat, lon=lon, alt=kw.pop("alt", 100.0), timestamp=f"{secs}",
                      utc=base + timedelta(seconds=secs), **kw)


def test_build_footprints_uses_rel_alt():
    pts = [_pt(0.0, 0.0, 0, rel_alt=50.0), _pt(0.0001, 0.0, 1, rel_alt=50.0)]
    fps = build_footprints(Track("t", pts), interval=0.0)
    assert len(fps) == 2
    assert all(isinstance(f, Footprint) for f in fps)
    assert fps[0].agl == 50.0


def test_build_footprints_agl_fallback_to_abs_minus_ground():
    # No rel_alt -> AGL = abs_alt - first abs_alt. Ground ref 100 -> AGL 20.
    pts = [_pt(0.0, 0.0, 0, alt=100.0), _pt(0.0001, 0.0, 1, alt=120.0)]
    fps = build_footprints(Track("t", pts), interval=0.0)
    # First point AGL is 0 -> skipped; second is 20.
    assert [f.agl for f in fps] == [20.0]


def test_build_footprints_skips_oblique_gimbal():
    pts = [_pt(0.0, 0.0, 0, rel_alt=50.0, gimbal_pitch=0.0),
           _pt(0.0001, 0.0, 1, rel_alt=50.0, gimbal_pitch=0.0)]
    assert build_footprints(Track("t", pts), interval=0.0) == []


def test_build_footprints_uses_gimbal_yaw_when_present():
    # Single-point tracks so heading comes purely from gimbal_yaw.
    p0 = [_pt(0.0, 0.0, 0, rel_alt=50.0, gimbal_pitch=-90.0, gimbal_yaw=0.0)]
    p90 = [_pt(0.0, 0.0, 0, rel_alt=50.0, gimbal_pitch=-90.0, gimbal_yaw=90.0)]
    fp0 = build_footprints(Track("t", p0), interval=0.0)[0]
    fp90 = build_footprints(Track("t", p90), interval=0.0)[0]
    lat_extent_0 = max(lat for _, lat in fp0.ring) - min(lat for _, lat in fp0.ring)
    lat_extent_90 = max(lat for _, lat in fp90.ring) - min(lat for _, lat in fp90.ring)
    # Default lens HFOV != VFOV, so a 90 deg yaw changes the N-S extent.
    assert abs(lat_extent_0 - lat_extent_90) > 1e-7
