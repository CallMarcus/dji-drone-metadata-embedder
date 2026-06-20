from pathlib import Path

from dji_metadata_embedder.utilities import parse_telemetry_samples

SAMPLES = Path(__file__).resolve().parents[1] / "samples"


def test_air3_has_rel_alt_no_focal_no_gimbal():
    s = parse_telemetry_samples(SAMPLES / "air3" / "clip.SRT")[0]
    assert s.rel_alt == 5.0
    assert s.focal_len is None
    assert s.gimbal_yaw is None
    assert s.gimbal_pitch is None


def test_avata360_has_focal_and_gimbal():
    s = parse_telemetry_samples(SAMPLES / "Avata360" / "clip.SRT")[0]
    assert s.focal_len == 28.0
    assert s.gimbal_yaw == -162.8
    assert s.gimbal_pitch == 0.0


def test_avata2_gps_format_has_no_rel_alt():
    s = parse_telemetry_samples(SAMPLES / "avata2" / "clip.SRT")[0]
    assert s.rel_alt is None


def test_legacy_focal_len_times_ten_is_normalized():
    srt = SAMPLES / "air3S" / "DJI_20260516195553_0001_D.SRT"
    samples = parse_telemetry_samples(srt)
    for s in samples:
        if s.focal_len is not None:
            assert s.focal_len < 100.0
