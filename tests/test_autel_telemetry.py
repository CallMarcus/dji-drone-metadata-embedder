"""Autel EVO telemetry: tx3g samples inside the MP4, and .ass sidecars (#324).

The coordinate fixtures are the two published records, not files from a drone:
the 2019 .ass line from the autelpilots write-up, and the 2023 EVO II text
ExifTool quotes in Process_tx3g. Nothing here was read from a real recording.
"""

import json
import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from dji_metadata_embedder import mp4_telemetry as mt
from dji_metadata_embedder.embedder import DJIMetadataEmbedder
from dji_metadata_embedder.geo.flightmap import scan_flights
from dji_metadata_embedder.geo.track import build_track
from dji_metadata_embedder.telemetry_converter import (
    extract_telemetry_to_csv,
    extract_telemetry_to_gpx,
)
from dji_metadata_embedder.utilities import Home, load_samples, parse_home

FIXTURES = Path(__file__).parent / "fixtures" / "mp4_telemetry"

# 2019 sidecar (autelpilots): signed, longitude first, and the firmware bug
# that writes an extra minus after the decimal (``-117.-9605``).
ASS_2019 = (
    "[Script Info]\n"
    "ScriptType: v4.00+\n"
    "\n"
    "[V4+ Styles]\n"
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
    "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
    "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
    "MarginL, MarginR, MarginV, Encoding\n"
    "Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,"
    "0,0,100,100,0,0,1,2,2,2,10,10,10,1\n"
    "\n"
    "[Events]\n"
    "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
    "Effect, Text\n"
    "Dialogue: 0,0:00:00.00,0:00:00.50,Default,,0,0,0,,"
    "HOME(-117.9606, 33.6324) 2019.9.8 16:49:24\\N"
    "GPS(W: -117.-9605, N: 33.6323, -37) ReH:0 \\N"
    "ISO:100 SHUTTER:1000 EV:0 F-NUM:2.8\n"
)

# 2023 embedded-style payload, as a sidecar would carry it: hemisphere
# letters, unsigned magnitudes, altitude with an m suffix, gimbal PRY.
ASS_2023 = (
    "[Events]\n"
    "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
    "Effect, Text\n"
    "Dialogue: 0,0:00:01.50,0:00:02.08,Default,,0,0,0,,"
    "HOME(W: 109.318642, N: 40.769371) 2023-09-12 10:28:07\\N"
    "GPS(W: 109.339287, N: 40.768574, 2371.76m)\\N"
    "G.PRY (-51.1°, 0.0°, -58.9°)\n"
)


def _load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _autel_video(monkeypatch, tmp_path, mtime):
    video = tmp_path / "evo.mp4"
    video.write_bytes(b"\x00")
    os.utime(video, (mtime, mtime))
    monkeypatch.setattr(
        mt, "_run_exiftool_json", lambda p: _load("autel_evo2_g3j.json")
    )
    return video


# --- embedded tx3g (ExifTool JSON) ---


def test_samples_from_exiftool_maps_autel_evo2():
    samples, saw = mt._samples_from_exiftool(_load("autel_evo2_g3j.json"))
    assert saw is True
    assert len(samples) == 2
    first, second = samples
    # ExifTool has already applied the hemisphere letters.
    assert (first.lat, first.lon) == (40.768574, -109.339287)
    assert first.alt == 2371.76  # GPSAltitude, metres, not DJI AbsoluteAltitude
    assert first.cue == "00:00:00,000"
    assert first.dt == datetime(2023, 9, 12, 10, 28, 7)
    # Local wall clock. DJI/Parrot samples are true UTC; this one is not.
    assert getattr(first, "dt_is_utc", True) is False
    # G.PRY is (pitch, roll, yaw). ExifTool stores that order under the
    # names GimbalYaw, GimbalPitch, GimbalRoll. Footprints need real pitch
    # (down is negative) and real yaw (the component that matches F.PRY).
    assert first.gimbal_pitch == pytest.approx(-51.1)
    assert first.gimbal_yaw == pytest.approx(-58.9)
    assert first.rel_alt is None
    assert second.cue == "00:00:01,000"
    assert second.gimbal_pitch == pytest.approx(-50.0)
    assert second.gimbal_yaw == pytest.approx(-58.0)
    assert second.dt == datetime(2023, 9, 12, 10, 28, 8)


def test_autel_video_time_uses_mtime_offset_not_true_utc(monkeypatch, tmp_path):
    # Sample clock 10:28:07, file mtime 02:28:07 UTC → +08:00 (the sample's
    # longitude is in China). A DJI-style zero offset would leave 10:28Z.
    mtime = datetime(2023, 9, 12, 2, 28, 7, tzinfo=UTC).timestamp()
    video = _autel_video(monkeypatch, tmp_path, mtime)
    track = build_track(video)
    assert track.points[0].utc == datetime(2023, 9, 12, 2, 28, 7)
    assert track.local_offset == timedelta(hours=8)
    assert track.points[0].gimbal_pitch == pytest.approx(-51.1)


def test_autel_video_honours_explicit_tz_offset(monkeypatch, tmp_path):
    video = _autel_video(monkeypatch, tmp_path, mtime=0)
    track = build_track(video, tz_offset=timedelta(hours=8))
    assert track.points[0].utc == datetime(2023, 9, 12, 2, 28, 7)
    assert track.local_offset == timedelta(hours=8)


def test_gpx_from_autel_mp4_shifts_local_clock(monkeypatch, tmp_path):
    mtime = datetime(2023, 9, 12, 2, 28, 7, tzinfo=UTC).timestamp()
    video = _autel_video(monkeypatch, tmp_path, mtime)
    text = extract_telemetry_to_gpx(video, tmp_path / "evo.gpx").read_text()
    assert "2023-09-12T02:28:07Z" in text
    assert "2023-09-12T10:28:07Z" not in text


def test_csv_from_autel_mp4_shifts_local_clock(monkeypatch, tmp_path):
    mtime = datetime(2023, 9, 12, 2, 28, 7, tzinfo=UTC).timestamp()
    video = _autel_video(monkeypatch, tmp_path, mtime)
    import csv

    rows = list(csv.DictReader(extract_telemetry_to_csv(video).open()))
    assert rows[0]["datetime_utc"] == "2023-09-12T02:28:07Z"
    assert rows[0]["abs_altitude"] == "2371.76"


def test_scan_flights_treats_autel_tx3g_time_as_local(monkeypatch, tmp_path):
    from dji_metadata_embedder.geo import flightmap as fm

    monkeypatch.setattr(fm, "exiftool_available", lambda: True)
    mtime = datetime(2023, 9, 12, 2, 28, 7, tzinfo=UTC).timestamp()
    _autel_video(monkeypatch, tmp_path, mtime)
    tracks, skipped = scan_flights(tmp_path, probe_video=lambda p: "autel:tx3g")
    assert skipped == []
    assert tracks[0].points[0].utc == datetime(2023, 9, 12, 2, 28, 7)
    assert tracks[0].local_offset == timedelta(hours=8)


def test_probe_recognises_autel_tx3g_track(monkeypatch, tmp_path):
    out = (
        "MetaFormat                      : tx3g\n"
        "HandlerType                     : sbtl\n"
    )
    monkeypatch.setattr(
        mt, "_run", lambda args: subprocess.CompletedProcess([], 0, out, "")
    )
    video = tmp_path / "evo.mp4"
    video.write_bytes(b"\x00")
    assert mt.probe(video) == "autel:tx3g"


def test_clip_probe_schema_recognises_tx3g():
    from dji_metadata_embedder.geo.clipprobe import _schema

    assert _schema({"Track2": {"MetaFormat": "tx3g"}}) == "autel:tx3g"


def test_autel_decode_floor_is_13_00():
    from dji_metadata_embedder.utils.exiftool import decode_floor

    assert decode_floor("autel:tx3g") == "13.00"


def test_undecoded_autel_track_names_exiftool_13(monkeypatch, tmp_path):
    monkeypatch.setattr(
        mt, "_run_exiftool_json", lambda p: [{"Doc1": {"SampleTime": 0}}]
    )
    monkeypatch.setattr(mt, "probe", lambda p: "autel:tx3g")
    monkeypatch.setattr(mt, "exiftool_version", lambda: "12.76")
    video = tmp_path / "evo.mp4"
    video.write_bytes(b"\x00")
    with pytest.raises(mt.Mp4TelemetryError) as exc:
        mt.extract_samples(video)
    message = str(exc.value)
    assert "13.00" in message
    assert "12.76" in message
    assert "autel:tx3g" in message


# --- HOME: Autel is longitude-first and must be tried before the DJI regex ---


def test_autel_letter_home_is_longitude_first():
    home = parse_home("HOME(W: 109.318642, N: 40.769371) 2023-09-12 10:28:07")
    assert home == Home(lat=40.769371, lon=-109.318642, alt=None)


def test_autel_letter_home_south_and_east_follow_the_letters_not_the_order():
    # Latitude letter written first. Sign comes from the letter.
    home = parse_home("HOME(S: 33.9000, E: 18.4000)")
    assert home == Home(lat=-33.9, lon=18.4, alt=None)


def test_autel_signed_home_with_longitude_past_90_is_not_swapped():
    # The DJI regex captures this as lat=-117.9606, lon=33.6324.
    home = parse_home("HOME(-117.9606, 33.6324) 2019.9.8 16:49:24")
    assert home == Home(lat=33.6324, lon=-117.9606, alt=None)


def test_autel_signed_home_inside_90_uses_the_hemisphere_gps_line():
    text = "HOME(-10.5, 20.25) 2019.9.8 16:49:24\nGPS(W: -10.5, N: 20.25, 12)\n"
    home = parse_home(text)
    assert home == Home(lat=20.25, lon=-10.5, alt=None)


def test_signed_home_inside_90_without_autel_markers_stays_latitude_first():
    # Ambiguous with DJI Format 2. No hemisphere, ReH, or broken decimal,
    # so the existing lat-first reading stands.
    assert parse_home("HOME(-10.5, 20.25)") == Home(lat=-10.5, lon=20.25, alt=None)


# --- .ass sidecar ---


def test_load_samples_reads_2019_ass_and_normalizes_the_broken_longitude(tmp_path):
    path = tmp_path / "clip.ASS"
    path.write_text(ASS_2019, encoding="utf-8")
    samples = load_samples(path)
    assert len(samples) == 1
    sample = samples[0]
    assert sample.lat == pytest.approx(33.6323)
    assert sample.lon == pytest.approx(-117.9605)  # -117.-9605, letter W
    assert sample.alt == pytest.approx(-37)
    assert sample.rel_alt == pytest.approx(0.0)
    assert sample.cue == "00:00:00,000"
    assert sample.dt == datetime(2019, 9, 8, 16, 49, 24)
    assert getattr(sample, "dt_is_utc", True) is False
    assert sample.gimbal_yaw is None


def test_load_samples_reads_2023_style_ass_gimbal_as_pitch_roll_yaw(tmp_path):
    path = tmp_path / "clip.ass"
    path.write_text(ASS_2023, encoding="utf-8")
    sample = load_samples(path)[0]
    assert sample.lat == pytest.approx(40.768574)
    assert sample.lon == pytest.approx(-109.339287)
    assert sample.alt == pytest.approx(2371.76)
    assert sample.cue == "00:00:01,500"
    assert sample.dt == datetime(2023, 9, 12, 10, 28, 7)
    assert sample.gimbal_pitch == pytest.approx(-51.1)
    assert sample.gimbal_yaw == pytest.approx(-58.9)
    assert parse_home(path.read_text(encoding="utf-8")) == Home(
        lat=40.769371, lon=-109.318642, alt=None
    )


def test_ass_to_srt_splits_hard_breaks_and_converts_cue_times():
    from dji_metadata_embedder.utilities import autel_ass_to_srt

    text = autel_ass_to_srt(ASS_2019)
    assert "00:00:00,000 --> 00:00:00,500" in text
    assert "\\N" not in text
    assert "GPS(W: -117.-9605, N: 33.6323, -37)" in text
    # The original payload is kept; only the ASS container is rewritten.
    assert text.index("HOME(") < text.index("\nGPS(")


def test_scan_flights_reads_an_ass_sidecar_and_skips_the_paired_video(tmp_path):
    (tmp_path / "EVO_0001.ass").write_text(ASS_2019, encoding="utf-8")
    (tmp_path / "EVO_0001.MP4").write_bytes(b"")
    probed: list[Path] = []
    tracks, skipped = scan_flights(tmp_path, probe_video=lambda p: probed.append(p))
    assert probed == []
    assert skipped == []
    assert len(tracks) == 1
    assert tracks[0].name == "EVO_0001"
    assert tracks[0].points[0].lat == pytest.approx(33.6323)
    assert tracks[0].points[0].lon == pytest.approx(-117.9605)


def test_gpx_from_ass_keeps_longitude_first(tmp_path):
    path = tmp_path / "clip.ass"
    path.write_text(ASS_2019, encoding="utf-8")
    text = extract_telemetry_to_gpx(
        path, tmp_path / "clip.gpx", tz_offset=timedelta(0)
    ).read_text(encoding="utf-8")
    assert 'lat="33.6323"' in text
    assert 'lon="-117.9605"' in text


def test_csv_from_ass_keeps_longitude_first(tmp_path):
    import csv

    path = tmp_path / "clip.ass"
    path.write_text(ASS_2019, encoding="utf-8")
    rows = list(
        csv.DictReader(
            extract_telemetry_to_csv(
                path, tmp_path / "clip.csv", tz_offset=timedelta(0)
            ).open(encoding="utf-8")
        )
    )
    assert float(rows[0]["latitude"]) == pytest.approx(33.6323)
    assert float(rows[0]["longitude"]) == pytest.approx(-117.9605)
    assert float(rows[0]["abs_altitude"]) == pytest.approx(-37)
    assert rows[0]["datetime_utc"] == "2019-09-08T16:49:24Z"


def test_embedder_converts_ass_to_an_srt_track(tmp_path, monkeypatch):
    class _Progress:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def add_task(self, *args, **kwargs):
            return 0

        def update(self, *args, **kwargs):
            return None

        def advance(self, *args, **kwargs):
            return None

    video = tmp_path / "EVO_0001.mp4"
    video.write_bytes(b"fake mp4")
    (tmp_path / "EVO_0001.ass").write_text(ASS_2019, encoding="utf-8")
    out_dir = tmp_path / "processed"
    out_dir.mkdir()
    seen: list[str] = []

    def fake_run(cmd, *args, **kwargs):
        ok = subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd and "ffmpeg" in str(cmd[0]).lower():
            inputs = [cmd[i + 1] for i, arg in enumerate(cmd) if arg == "-i"]
            subtitle = Path(inputs[1])
            seen.append(subtitle.read_text(encoding="utf-8"))
            assert subtitle.suffix == ".srt"
            assert subtitle.resolve() != (tmp_path / "EVO_0001.ass").resolve()
            Path(cmd[-1]).write_bytes(b"embedded")
            return ok
        if cmd and "ffprobe" in str(cmd[0]).lower():
            return subprocess.CompletedProcess(cmd, 0, "10.0\n", "")
        return ok

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("dji_metadata_embedder.embedder.Progress", _Progress)
    embedder = DJIMetadataEmbedder(str(tmp_path), output_dir=str(out_dir))
    result = embedder.process_directory(use_exiftool=False)
    assert result["processed"] == 1
    assert seen and "-->" in seen[0] and "\\N" not in seen[0]
    summary = json.loads((out_dir / "EVO_0001_telemetry.json").read_text())
    lat, lon = summary["first_gps"]
    assert lat == pytest.approx(33.6323)
    assert lon == pytest.approx(-117.9605)
