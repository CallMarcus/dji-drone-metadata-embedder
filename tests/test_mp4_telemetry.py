import json
import subprocess
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
    # Early sample lacks RelativeAltitude and GimbalPitch, but later samples
    # carry both, so these are protobuf default omissions: the aircraft sits
    # at 0 m with a level gimbal (#546, verified on Air 3S: 182 s without a
    # pitch tag, then 0.2 appears; GimbalRoll never does because it is 0).
    assert first.rel_alt == 0.0 and first.gimbal_pitch == 0.0
    # rich mid-flight sample: optional fields present
    assert last.rel_alt == 5.4
    assert last.gimbal_pitch == -90
    assert last.focal_len is None  # stream carries no focal length


def _docs(*per_sample):
    root = {}
    for i, fields in enumerate(per_sample, start=1):
        root[f"Doc{i}"] = {"GPSLatitude": 51.0, "GPSLongitude": -0.1, **fields}
    return [root]


def test_default_omission_fills_a_field_the_stream_carries_elsewhere():
    samples, _ = mt._samples_from_exiftool(_docs(
        {"GimbalYaw": 12.5},
        {"GimbalYaw": 13.0, "GimbalPitch": -30.0, "RelativeAltitude": 0.1},
    ))
    first = samples[0]
    assert (first.gimbal_yaw, first.gimbal_pitch, first.rel_alt) == (12.5, 0.0, 0.0)


def test_fields_the_stream_never_carries_stay_unknown():
    samples, _ = mt._samples_from_exiftool(_docs(
        {"AbsoluteAltitude": 10.0}, {"AbsoluteAltitude": 11.0},
    ))
    for s in samples:
        assert (s.gimbal_yaw, s.gimbal_pitch, s.rel_alt) == (None, None, None)


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
    monkeypatch.setattr(mt, "exiftool_version", lambda: "13.55")
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


def test_probe_parses_schema_from_category(monkeypatch, tmp_path):
    out = (
        "MetaFormat                      : dbgi\n"
        "Category                        : pb_file:dvtm_Air3s.proto;"
        "model_name:FC9113;pb_version:02.00.02;\n"
    )
    monkeypatch.setattr(
        mt, "_run", lambda args: subprocess.CompletedProcess([], 0, out, "")
    )
    f = tmp_path / "x.mp4"
    f.write_bytes(b"\x00")
    schema = mt.probe(f)
    assert schema is not None
    assert schema.startswith("dvtm_Air3s.proto")


def test_probe_none_when_no_track(monkeypatch, tmp_path):
    monkeypatch.setattr(
        mt,
        "_run",
        lambda args: subprocess.CompletedProcess([], 0, "MajorBrand : MP4\n", ""),
    )
    f = tmp_path / "x.mp4"
    f.write_bytes(b"\x00")
    assert mt.probe(f) is None


def test_install_hint_names_the_doctor_command():
    from dji_metadata_embedder.mp4_telemetry import _EXIFTOOL_INSTALL_HINT

    assert "dji-embed doctor --install exiftool" in _EXIFTOOL_INSTALL_HINT


def test_undecodable_stream_error_names_model_floor(monkeypatch, tmp_path):
    import dji_metadata_embedder.mp4_telemetry as m

    video = tmp_path / "DJI_0001.MP4"
    video.write_bytes(b"\x00")
    # ExifTool "ran" but decoded nothing for this model:
    monkeypatch.setattr(m, "_run_exiftool_json", lambda path: [{"Doc1": {"SampleTime": 0.0}}])
    monkeypatch.setattr(m, "probe", lambda path: "dvtm_Air3s.proto;model_name:FC9113")
    monkeypatch.setattr(m, "exiftool_version", lambda: "12.76")

    with pytest.raises(m.Mp4TelemetryError) as err:
        m.extract_samples(video)
    text = str(err.value)
    assert ">= 13.39" in text
    assert "12.76" in text
    assert "dji-embed doctor --install exiftool" in text


# --- bundled ExifTool user config (Mavic 4 Pro gimbal block) ---


def test_bundled_config_exists_and_maps_mavic4_gimbal():
    cfg = mt.exiftool_config_path()
    assert cfg is not None and cfg.is_file()
    text = cfg.read_text(encoding="utf-8")
    assert "dvtm_Mavic4_3-4-3" in text
    assert "Image::ExifTool::DJI::GimbalInfo" in text


def test_run_prepends_config_before_every_other_argument(monkeypatch):
    seen = []

    def fake_run(argv, **kwargs):
        seen.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(mt.subprocess, "run", fake_run)
    mt._run(["-ver"])
    argv = seen[0]
    assert argv[1] == "-config"
    assert argv[2] == str(mt.exiftool_config_path())
    assert argv[3:] == ["-ver"]


def test_run_without_config_file_falls_back_to_plain_argv(monkeypatch):
    seen = []

    def fake_run(argv, **kwargs):
        seen.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(mt.subprocess, "run", fake_run)
    monkeypatch.setattr(mt, "exiftool_config_path", lambda: None)
    mt._run(["-ver"])
    assert seen[0][1:] == ["-ver"]
