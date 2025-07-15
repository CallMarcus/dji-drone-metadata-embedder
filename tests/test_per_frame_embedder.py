import sys
from pathlib import Path
import subprocess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dji_metadata_embedder import embed_flight_path, extract_frame_locations


def test_per_frame_embedder(monkeypatch, tmp_path):
    video = tmp_path / "video.mp4"
    srt = tmp_path / "flight.srt"
    output = tmp_path / "out.mp4"
    video.write_text("dummy")
    srt.write_text(
        """1
00:00:00,000 --> 00:00:00,033
[latitude: 59.1] [longitude: 18.2] [rel_alt: 1.0 abs_alt: 2.0]

2
00:00:00,033 --> 00:00:00,066
[latitude: 59.2] [longitude: 18.3] [rel_alt: 2.0 abs_alt: 3.0]
"""
    )

    calls = []

    def fake_run(cmd, capture_output=True, text=True):
        calls.append(cmd)
        class Res:
            returncode = 0
            stdout = "\n".join([
                "TAG:location.0.ISO6709=+59.1000+018.2000+0002.0/",
                "TAG:location.1.ISO6709=+59.2000+018.3000+0003.0/",
            ]) if cmd[0] == "ffprobe" else ""
        return Res()

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert embed_flight_path(video, srt, output)
    tags = extract_frame_locations(output)
    assert tags == [
        "+59.1000+018.2000+0002.0/",
        "+59.2000+018.3000+0003.0/",
    ]
    assert calls[0][0] == "ffmpeg"
    assert calls[1][0] == "ffprobe"

