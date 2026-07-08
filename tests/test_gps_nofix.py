"""Regression tests for pre-GPS-lock ``0,0`` no-fix frames.

DJI drones emit ``[latitude: 0.000000] [longitude: 0.000000]`` for every frame
recorded before the GPS receiver acquires a fix. Treating that sentinel as a
real coordinate geotags the clip at Null Island (0 N, 0 E) and drags the
average location toward it. These tests pin the no-fix filtering using a trimmed
real-world Neo 2 fixture (contributed via mavicpilots.com) that captures the
pre-lock -> lock transition, plus a synthetic all-zero clip.
"""

from pathlib import Path

from dji_metadata_embedder import DJIMetadataEmbedder
from dji_metadata_embedder.telemetry_converter import extract_telemetry_to_gpx
from dji_metadata_embedder.utilities import parse_telemetry_points, is_gps_fix

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
NOFIX_CLIP = SAMPLES / "neo2" / "clip_nogps.SRT"

# The fixture is 6 frames: 3 no-fix (0,0) followed by 3 locked frames.
LOCKED_GPS = (32.848932, -84.861966)
LOCKED_ALT = 269.099


def test_is_gps_fix_rejects_null_island():
    assert is_gps_fix(0.0, 0.0) is False
    assert is_gps_fix(LOCKED_GPS[0], LOCKED_GPS[1]) is True


def test_first_gps_skips_no_fix_frames(tmp_path):
    t = DJIMetadataEmbedder(tmp_path).parse_dji_srt(NOFIX_CLIP)
    # All six frames carry a latitude/longitude field, so the raw list is kept.
    assert len(t["gps_coords"]) == 6
    # ...but the reported location must be the first real fix, not (0, 0).
    assert t["first_gps"] == LOCKED_GPS


def test_avg_gps_excludes_no_fix_frames(tmp_path):
    t = DJIMetadataEmbedder(tmp_path).parse_dji_srt(NOFIX_CLIP)
    # Average over the three locked frames only (all identical here).
    assert t["avg_gps"] == LOCKED_GPS


def test_telemetry_points_drop_no_fix(tmp_path):
    points = parse_telemetry_points(NOFIX_CLIP)
    # Only the three locked frames become track points.
    assert len(points) == 3
    lat, lon, alt, _ts = points[0]
    assert (lat, lon) == LOCKED_GPS
    assert alt == LOCKED_ALT


def test_gpx_track_excludes_no_fix_frames(tmp_path):
    """GPX export must not write Null Island trackpoints (issue #256)."""
    out = tmp_path / "track.gpx"
    extract_telemetry_to_gpx(NOFIX_CLIP, out)
    content = out.read_text()
    # Only the three locked frames become trackpoints.
    assert content.count("<trkpt") == 3
    assert 'lat="0.0"' not in content
    assert f'lat="{LOCKED_GPS[0]}"' in content


def _write_all_zero_srt(path: Path) -> Path:
    block = (
        "{i}\n"
        "00:00:0{i},000 --> 00:00:0{i},033\n"
        '<font size="28">FrameCnt: {i}, DiffTime: 33ms\n'
        "2026-05-31 16:15:14.448\n"
        "[iso: 350] [shutter: 1/100.0] [fnum: 2.2] "
        "[latitude: 0.000000] [longitude: 0.000000] "
        "[rel_alt: 0.000 abs_alt: 268.691]</font>"
    )
    srt = path / "allzero.SRT"
    srt.write_text("\n\n".join(block.format(i=i) for i in range(1, 4)) + "\n")
    return srt


def test_all_no_fix_clip_reports_no_location(tmp_path):
    srt = _write_all_zero_srt(tmp_path)
    t = DJIMetadataEmbedder(tmp_path).parse_dji_srt(srt)
    # No real fix anywhere -> no location metadata should be emitted.
    assert t["first_gps"] is None
    assert t["avg_gps"] is None
    assert parse_telemetry_points(srt) == []
