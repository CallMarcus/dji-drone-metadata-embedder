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
