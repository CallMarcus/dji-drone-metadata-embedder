import sys
from pathlib import Path
import subprocess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dji_metadata_embedder import DJIMetadataEmbedder

# Helper to run parser on provided SRT string
def _parse_from_string(tmp_path, text):
    srt_file = tmp_path / "test.srt"
    srt_file.write_text(text)
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
    assert t['first_gps'] == (59.302335, 18.203059)
    assert t['max_altitude'] == 132.960
    assert t['camera_settings']['iso'] == '100'

def test_parse_format2(tmp_path):
    srt = """1
00:00:00,000 --> 00:00:00,033
GPS(39.906217,116.391305,69.800) BAROMETER(91.2) HOME(39.906206,116.391400) D=5.2m H=1.5m
"""
    t = _parse_from_string(tmp_path, srt)
    assert t['first_gps'] == (39.906217, 116.391305)
    assert t['altitudes'] == []
    assert t['max_altitude'] is None

def test_parse_format3(tmp_path):
    srt = """1
00:00:00,000 --> 00:00:00,033
<font size='36'>SrtCnt : 1, DiffTime : 33ms
2024-01-15 14:30:22,123
[iso : 100] [shutter : 1/1000] [fnum : 280] [latitude: 59.302335] [longitude: 18.203059] [rel_alt: 10.200 abs_alt: 142.760]</font>
"""
    t = _parse_from_string(tmp_path, srt)
    assert t['first_gps'] == (59.302335, 18.203059)
    assert t['max_altitude'] == 142.760
    assert t['camera_settings']['shutter'] == '1/1000'

def test_embed_metadata_ffmpeg_command(tmp_path, monkeypatch):
    video = Path(tmp_path / "DJI_20240101_123456.mp4")
    srt = Path(tmp_path / "test.srt")
    video.write_text("dummy")
    srt.write_text("dummy")
    output = Path(tmp_path / "out.mp4")
    telemetry = {
        'first_gps': (59.302335, 18.203059),
        'max_altitude': 142.8
    }
    embedder = DJIMetadataEmbedder(tmp_path)
    called = {}

    def fake_run(cmd, capture_output=True, text=True):
        called['cmd'] = cmd
        class Res:
            returncode = 0
        return Res()

    monkeypatch.setattr(subprocess, 'run', fake_run)
    success = embedder.embed_metadata_ffmpeg(video, srt, telemetry, output)
    assert success
    expected = [
        'ffmpeg', '-i', str(video), '-i', str(srt),
        '-c', 'copy', '-c:s', 'mov_text',
        '-metadata:s:s:0', 'language=eng',
        '-metadata:s:s:0', 'title=Telemetry Data',
        '-metadata', 'location=+59.302335+18.203059/',
        '-metadata', 'location-eng=+59.302335+18.203059/',
        '-metadata', 'altitude=142.8',
        '-metadata', 'creation_time=2024-01-01 12:34:56',
        '-y', str(output)
    ]
    assert called['cmd'] == expected
