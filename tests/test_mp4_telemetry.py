import json
from datetime import datetime
from pathlib import Path

import pytest

from dji_metadata_embedder import mp4_telemetry as mt
from dji_metadata_embedder.utilities import load_samples

FIXTURES = Path(__file__).parent / "fixtures" / "mp4_telemetry"


def _load(name):
    return json.loads((FIXTURES / name).read_text())


@pytest.mark.parametrize(
    "seconds, expected",
    [
        (0, "00:00:00,000"),
        (0.0166833333333333, "00:00:00,016"),
        (41.5248166666667, "00:00:41,524"),
        (3661.5, "01:01:01,500"),
    ],
)
def test_sample_time_to_cue(seconds, expected):
    assert mt._sample_time_to_cue(seconds) == expected


def test_parse_gps_datetime_utc_naive():
    dt = mt._parse_gps_datetime("2026:05:16 23:55:53.017Z")
    assert dt == datetime(2026, 5, 16, 23, 55, 53, 17000)
    assert dt.tzinfo is None  # naive, matches the SRT dt convention


def test_parse_gps_datetime_none_on_garbage():
    assert mt._parse_gps_datetime("") is None
    assert mt._parse_gps_datetime("not-a-date") is None


def test_samples_from_exiftool_maps_air3s():
    samples, saw = mt._samples_from_exiftool(_load("air3s_g3j.json"))
    assert saw is True
    assert len(samples) == 4
    first, last = samples[0], samples[-1]
    assert (round(first.lat, 4), round(first.lon, 4)) == (51.4778, -0.0014)
    assert first.alt == 325.591
    assert first.cue == "00:00:00,000"
    assert first.dt == datetime(2026, 5, 16, 23, 55, 53, 0)
    assert first.gimbal_yaw == -7.1
    # sparse early sample: optional fields absent
    assert first.rel_alt is None and first.gimbal_pitch is None
    # rich mid-flight sample: optional fields present
    assert last.rel_alt == 5.4
    assert last.gimbal_pitch == -90
    assert last.focal_len is None  # stream carries no focal length


def test_samples_from_exiftool_undecoded_sets_saw_false():
    samples, saw = mt._samples_from_exiftool(_load("neo2_undecoded_g3j.json"))
    assert samples == []
    assert saw is False  # only SampleTime present -> nothing decoded


def test_samples_from_exiftool_filters_null_island():
    data = [{"Doc1": {"SampleTime": 0, "GPSLatitude": 0.0, "GPSLongitude": 0.0,
                      "AbsoluteAltitude": 10.0}}]
    samples, saw = mt._samples_from_exiftool(data)
    assert samples == []      # (0,0) no-fix dropped
    assert saw is True        # but telemetry WAS decoded (AbsoluteAltitude)


def test_extract_samples_happy(monkeypatch, tmp_path):
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"\x00")
    monkeypatch.setattr(mt, "_run_exiftool_json", lambda p: _load("air3s_g3j.json"))
    samples = mt.extract_samples(f)
    assert len(samples) == 4
    assert samples[0].dt == datetime(2026, 5, 16, 23, 55, 53, 0)


def test_extract_samples_undecoded_raises(monkeypatch, tmp_path):
    f = tmp_path / "neo2.mp4"
    f.write_bytes(b"\x00")
    monkeypatch.setattr(mt, "_run_exiftool_json", lambda p: _load("neo2_undecoded_g3j.json"))
    monkeypatch.setattr(mt, "probe", lambda p: "dvtm_NEO2.proto;model_name:FC9470")
    monkeypatch.setattr(mt, "_exiftool_version", lambda: "13.55")
    with pytest.raises(mt.Mp4TelemetryError) as exc:
        mt.extract_samples(f)
    assert "dvtm_NEO2.proto" in str(exc.value)
    assert "13.55" in str(exc.value)


def test_extract_samples_no_stream_raises(monkeypatch, tmp_path):
    f = tmp_path / "plain.mp4"
    f.write_bytes(b"\x00")
    monkeypatch.setattr(mt, "_run_exiftool_json", lambda p: [{"SourceFile": str(f)}])
    monkeypatch.setattr(mt, "probe", lambda p: None)
    with pytest.raises(mt.Mp4TelemetryError) as exc:
        mt.extract_samples(f)
    assert "sidecar" in str(exc.value).lower()


def test_extract_samples_decoded_but_no_fix_returns_empty(monkeypatch, tmp_path):
    f = tmp_path / "nofix.mp4"
    f.write_bytes(b"\x00")
    data = [{"Doc1": {"SampleTime": 0, "AbsoluteAltitude": 5.0,
                      "GPSLatitude": 0.0, "GPSLongitude": 0.0}}]
    monkeypatch.setattr(mt, "_run_exiftool_json", lambda p: data)
    monkeypatch.setattr(mt, "probe", lambda p: "dvtm_Air3s.proto")
    assert mt.extract_samples(f) == []  # decoded, just no fix -> not an error


def test_load_samples_dispatches_video(monkeypatch, tmp_path):
    f = tmp_path / "clip.MP4"
    f.write_bytes(b"\x00")
    monkeypatch.setattr(mt, "_run_exiftool_json", lambda p: _load("air3s_g3j.json"))
    samples = load_samples(f)
    assert len(samples) == 4


def test_load_samples_dispatches_srt(tmp_path):
    srt = tmp_path / "clip.SRT"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:00,033\n"
        "[latitude: 51.4778] [longitude: -0.0014] [rel_alt: 0.0 abs_alt: 10.0]\n",
        encoding="utf-8",
    )
    samples = load_samples(srt)
    assert len(samples) == 1
    assert round(samples[0].lat, 4) == 51.4778
