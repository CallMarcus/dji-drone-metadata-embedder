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


def test_legacy_focal_len_times_ten_is_normalized(tmp_path):
    # Legacy bracket format writes focal_len as x10 (350 -> 35.0 mm-equivalent).
    srt = tmp_path / "legacy.SRT"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:00,033\n"
        "<font size='36'>SrtCnt : 1, DiffTime : 33ms\n"
        "2024-01-01 12:00:00,000\n"
        "[iso : 100] [shutter : 1/1000] [fnum : 280] [focal_len : 350] "
        "[latitude: 59.30] [longitude: 18.20] [rel_alt: 10.0 abs_alt: 142.0]</font>\n",
        encoding="utf-8",
    )
    s = parse_telemetry_samples(srt)[0]
    assert s.focal_len == 35.0
