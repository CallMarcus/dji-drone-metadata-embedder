import tempfile
from pathlib import Path
import sys
import os

sys.path.insert(0, os.path.abspath("src"))

from dji_metadata_embedder import DJIMetadataEmbedder
import telemetry_converter

FORMAT3_SRT = """1
00:00:00,000 --> 00:00:00,033
<font size="36">SrtCnt : 1, DiffTime : 33ms
2024-01-15 14:30:22,123
[iso : 100] [shutter : 1/1000] [fnum : 280] [ev : 0] [ct : 5500] [color_md : default] [focal_len : 240] [latitude: 59.302335] [longitude: 18.203059] [rel_alt: 10.200 abs_alt: 142.760]</font>

2
00:00:00,033 --> 00:00:00,066
<font size="36">SrtCnt : 2, DiffTime : 33ms
2024-01-15 14:30:22,156
[iso : 100] [shutter : 1/1000] [fnum : 280] [ev : 0] [ct : 5500] [color_md : default] [focal_len : 240] [latitude: 59.302336] [longitude: 18.203058] [rel_alt: 10.300 abs_alt: 142.860]</font>
"""

def test_parse_dji_srt_format3():
    with tempfile.TemporaryDirectory() as tmpdir:
        srt_path = Path(tmpdir) / "sample.srt"
        srt_path.write_text(FORMAT3_SRT)
        embedder = DJIMetadataEmbedder(tmpdir)
        data = embedder.parse_dji_srt(srt_path)
        assert len(data["gps_coords"]) == 2
        assert data["gps_coords"][0] == (59.302335, 18.203059)
        assert data["camera_info"][0]["ev"] == "0"
        assert data["camera_info"][0]["focal_len"] == "240"

def test_telemetry_converter_csv_format3():
    with tempfile.TemporaryDirectory() as tmpdir:
        srt_path = Path(tmpdir) / "sample.srt"
        csv_path = Path(tmpdir) / "out.csv"
        srt_path.write_text(FORMAT3_SRT)
        telemetry_converter.extract_telemetry_to_csv(srt_path, csv_path)
        content = csv_path.read_text()
        assert "59.302335" in content
        assert "focal_len" in content
