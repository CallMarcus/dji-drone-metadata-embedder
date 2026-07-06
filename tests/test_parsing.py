from pathlib import Path
import subprocess

from dji_metadata_embedder import DJIMetadataEmbedder


# Helper to run parser on provided SRT string
def _parse_from_string(tmp_path, text):
    srt_file = tmp_path / "test.srt"
    srt_file.write_text(text, encoding="utf-8")
    embedder = DJIMetadataEmbedder(tmp_path)
    return embedder.parse_dji_srt(srt_file)


def test_parse_format1(tmp_path):
    srt = """1
00:00:00,000 --> 00:00:00,033
[latitude: 59.302335] [longitude: 18.203059] [rel_alt: 1.300 abs_alt: 132.860] [iso : 100] [shutter : 1/30.0] [fnum : 170]

2
00:00:00,033 --> 00:00:00,066
[latitude: 59.302336] [longitude: 18.203060] [rel_alt: 1.400 abs_alt: 132.960] [iso : 100] [shutter : 1/30.0] [fnum : 170]
"""
    t = _parse_from_string(tmp_path, srt)
    assert t["first_gps"] == (59.302335, 18.203059)
    assert t["max_altitude"] == 132.960
    assert t["camera_settings"]["iso"] == "100"


def test_parse_format2(tmp_path):
    srt = """1
00:00:00,000 --> 00:00:00,033
GPS(39.906217,116.391305,69.800) BAROMETER(91.2) HOME(39.906206,116.391400) D=5.2m H=1.5m
"""
    t = _parse_from_string(tmp_path, srt)
    assert t["first_gps"] == (39.906217, 116.391305)
    assert t["altitudes"] == []
    assert t["max_altitude"] is None


def test_parse_format3(tmp_path):
    srt = """1
00:00:00,000 --> 00:00:00,033
<font size='36'>SrtCnt : 1, DiffTime : 33ms
2024-01-15 14:30:22,123
[iso : 100] [shutter : 1/1000] [fnum : 280] [latitude: 59.302335] [longitude: 18.203059] [rel_alt: 10.200 abs_alt: 142.760]</font>
"""
    t = _parse_from_string(tmp_path, srt)
    assert t["first_gps"] == (59.302335, 18.203059)
    assert t["max_altitude"] == 142.760
    assert t["camera_settings"]["shutter"] == "1/1000"


def test_parse_m300_legacy_unit(tmp_path):
    """M300 GPS regex must tolerate altitude unit suffix (``0.0M``)."""
    srt = """1
00:00:00,000 --> 00:00:00,033
GPS(36.6146,-6.1120,0.0M) BAROMETER:0.3M

2
00:00:00,033 --> 00:00:00,066
GPS(36.6147,-6.1121,0.1M) BAROMETER:0.4M
"""
    t = _parse_from_string(tmp_path, srt)
    assert t["first_gps"] == (36.6146, -6.1120)
    assert len(t["gps_coords"]) == 2


def test_parse_bracket_decimal_fnum(tmp_path):
    """Modern DJI bracket format reports a decimal aperture, e.g. ``[fnum: 1.9]``.

    The original regex only matched integers (the legacy f-number*100 encoding,
    ``[fnum : 170]``), so decimal apertures emitted by current models (Avata
    360, Mini 5 Pro, and others) were silently dropped.
    """
    srt = """1
00:00:00,000 --> 00:00:00,041
<font size="28">FrameCnt: 1, DiffTime: 41ms, FrameId: 4787
2026-05-27 13:10:00.015
[iso: 200] [shutter: 1/6400.0] [fnum: 1.9] [ev: 0] [ct: 5845] [color_md: dlog_m] [focal_len: 28.00] [latitude: 53.365080] [longitude: 6.460739] [rel_alt: 5.400 abs_alt: -124.744]</font>
"""
    t = _parse_from_string(tmp_path, srt)
    assert t["camera_settings"]["fnum"] == "1.9"


def test_parse_p4rtk_compact(tmp_path):
    """P4 RTK compact single-line: free-standing camera tokens + ``GPS (...)``."""
    srt = """1
00:00:00,000 --> 00:00:00,033
F/5.6, SS 400, ISO 100, EV 0, GPS (-58.851745, -34.237922, 15), HOME (-58.847509, -34.232707, -57.98m), D 698.70m, H 85.80m, H.S 0.00m/s, V.S 0.00m/s, F.PRY (2.7°, -7.0°, 110.1°), G.PRY (-24.4°, 0.0°, 110.4°)
"""
    t = _parse_from_string(tmp_path, srt)
    assert t["first_gps"] == (-58.851745, -34.237922)
    assert t["camera_settings"]["iso"] == "100"
    assert t["camera_settings"]["shutter"] == "400"
    assert t["camera_settings"]["fnum"] == "5.6"
    assert t["camera_settings"]["ev"] == "0"


def test_parse_framecnt_counter(tmp_path):
    """Newer firmware (Neo, Mini 5 Pro, Avata 360) emits ``FrameCnt`` rather
    than ``SrtCnt``; the counter must still be captured (issue #204)."""
    srt = """1
00:00:00,000 --> 00:00:00,041
<font size="28">FrameCnt: 1, DiffTime: 41ms
2026-05-27 13:10:00.015
[iso: 200] [latitude: 53.365080] [longitude: 6.460739] [rel_alt: 5.400 abs_alt: -124.744]</font>

2
00:00:00,041 --> 00:00:00,082
<font size="28">FrameCnt: 2, DiffTime: 41ms
2026-05-27 13:10:00.056
[iso: 200] [latitude: 53.365080] [longitude: 6.460739] [rel_alt: 5.400 abs_alt: -124.744]</font>
"""
    t = _parse_from_string(tmp_path, srt)
    assert t["srt_counts"] == [1, 2]


def test_parse_srtcnt_counter_still_works(tmp_path):
    """Regression: legacy ``SrtCnt`` spelling (Mavic 3, Air 2S) keeps working."""
    srt = """1
00:00:00,000 --> 00:00:00,033
<font size='36'>SrtCnt : 1, DiffTime : 33ms
2024-01-01 12:00:00,000
[latitude: 59.1111] [longitude: 18.2222] [rel_alt: 5.0 abs_alt: 105.0]</font>

2
00:00:00,033 --> 00:00:00,066
<font size='36'>SrtCnt : 2, DiffTime : 33ms
2024-01-01 12:00:00,033
[latitude: 59.1112] [longitude: 18.2223] [rel_alt: 5.1 abs_alt: 105.1]</font>
"""
    t = _parse_from_string(tmp_path, srt)
    assert t["srt_counts"] == [1, 2]


def test_parse_barometer_avata2_parenthesised(tmp_path):
    """Avata 2 parenthesised barometer form: ``BAROMETER(91.2)`` (issue #203)."""
    srt = """1
00:00:00,000 --> 00:00:00,033
GPS(39.906217,116.391305,69.800) BAROMETER(91.2) HOME(39.906206,116.391400)

2
00:00:00,033 --> 00:00:00,066
GPS(39.906218,116.391306,69.900) BAROMETER(91.3) HOME(39.906206,116.391400)
"""
    t = _parse_from_string(tmp_path, srt)
    assert t["barometers"] == [91.2, 91.3]


def test_parse_barometer_m300_colon_with_unit(tmp_path):
    """Matrice 300 colon form with trailing unit: ``BAROMETER:0.3M`` (issue #203)."""
    srt = """1
00:00:00,000 --> 00:00:00,033
GPS(36.6146,-6.1120,0.0M) BAROMETER:0.3M

2
00:00:00,033 --> 00:00:00,066
GPS(36.6147,-6.1121,0.1M) BAROMETER:0.4M
"""
    t = _parse_from_string(tmp_path, srt)
    assert t["barometers"] == [0.3, 0.4]


def test_embed_metadata_ffmpeg_command(tmp_path, monkeypatch):
    video = Path(tmp_path / "DJI_20240101_123456.mp4")
    srt = Path(tmp_path / "test.srt")
    video.write_text("dummy")
    srt.write_text("dummy")
    output = Path(tmp_path / "out.mp4")
    telemetry = {"first_gps": (59.302335, 18.203059), "max_altitude": 142.8}
    embedder = DJIMetadataEmbedder(tmp_path)
    called = {}

    def fake_run(cmd, capture_output=True, text=True):
        called["cmd"] = cmd

        class Res:
            returncode = 0

        return Res()

    monkeypatch.setattr(subprocess, "run", fake_run)
    success = embedder.embed_metadata_ffmpeg(video, srt, telemetry, output)
    assert success
    expected = [
        "ffmpeg",
        "-i",
        str(video),
        "-i",
        str(srt),
        "-map",
        "0",
        "-map",
        "-0:d",
        "-map",
        "1",
        "-c",
        "copy",
        "-c:s",
        "mov_text",
        "-metadata:s:s:0",
        "language=eng",
        "-metadata:s:s:0",
        "title=Telemetry Data",
        "-metadata",
        "location=+59.302335+18.203059/",
        "-metadata",
        "location-eng=+59.302335+18.203059/",
        "-metadata",
        "altitude=142.8",
        "-metadata",
        "creation_time=2024-01-01 12:34:56",
        "-y",
        str(output),
    ]
    assert called["cmd"] == expected


def test_embed_metadata_ffmpeg_mkv_preserves_data_streams(tmp_path, monkeypatch):
    """MKV container preserves proprietary djmd/dbgi data streams (issue #197).

    The MP4 muxer can't tag DJI's ``codec=none`` data streams, so the default
    mp4 path drops them with ``-map -0:d``. MKV's codec table round-trips them,
    so in mkv mode we keep every source stream (no ``-0:d`` exclusion) and use
    the Matroska-native ``srt`` subtitle codec instead of ``mov_text``.
    """
    video = Path(tmp_path / "DJI_0001.mp4")
    srt = Path(tmp_path / "DJI_0001.srt")
    video.write_text("dummy")
    srt.write_text("dummy")
    output = Path(tmp_path / "out.mkv")
    telemetry = {"first_gps": None, "max_altitude": None}
    embedder = DJIMetadataEmbedder(tmp_path, container="mkv")
    called = {}

    def fake_run(cmd, capture_output=True, text=True):
        called["cmd"] = cmd

        class Res:
            returncode = 0

        return Res()

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert embedder.embed_metadata_ffmpeg(video, srt, telemetry, output)
    cmd = called["cmd"]
    # Data streams must NOT be dropped in mkv mode.
    assert "-0:d" not in cmd
    # Only two -map args: source (0) and subtitle (1).
    assert cmd.count("-map") == 2
    assert cmd[cmd.index("-map") + 1] == "0"
    # Matroska-native subtitle codec.
    assert cmd[cmd.index("-c:s") + 1] == "srt"
