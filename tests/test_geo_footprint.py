import math

from dji_metadata_embedder.geo.footprint import (
    DEFAULT_LENS,
    FOV_TABLE,
    LensSpec,
    fov_degrees,
    ground_footprint,
)

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
