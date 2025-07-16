import sys
from pathlib import Path
import hashlib
import subprocess
import base64

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dji_metadata_embedder.per_frame_embedder import embed_flight_path_ffmpeg
from dji_metadata_embedder import telemetry_converter
from dji_metadata_embedder.utilities import parse_telemetry_points

SAMPLE_HASHES = {
    "mini4pro": "b5b0f199f2dd1c10a0ed42e4964e25a122cbb54288a4eeee6f8e279a3cce05b7",
    "air3": "16befdcc4e09b4690f61748324a4a7d79d4e933b6d3aaa4e9b1cb568500cae90",
    "avata2": "44e78c14cc62527a3152350ba060bcfc7c7a3d7a458bdb6013ba0b8d55a7e7f9",
}


def run_sample(name: str, tmp_path, monkeypatch):
    base = Path(__file__).resolve().parents[1] / "samples" / name
    video_b64 = base / "clip.mp4.b64"
    dat_b64 = base / "clip.DAT.b64"
    video = tmp_path / "clip.mp4"
    dat = tmp_path / "clip.DAT"
    if video_b64.exists():
        video.write_bytes(base64.b64decode(video_b64.read_text()))
    if dat_b64.exists():
        dat.write_bytes(base64.b64decode(dat_b64.read_text()))
    srt = base / "clip.SRT"
    output = tmp_path / "out.mp4"

    points = parse_telemetry_points(srt)
    calls = []

    def fake_run(cmd, capture_output=True, text=True):
        calls.append(cmd)

        class Res:
            returncode = 0
            stdout = ""

        return Res()

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert embed_flight_path_ffmpeg(video, points, output)
    gps_atoms = sum(1 for arg in calls[0] if arg.startswith("location."))
    assert gps_atoms == len(points)

    gpx_path = tmp_path / f"{name}.gpx"

    class FixedDT:
        @staticmethod
        def now():
            from datetime import datetime

            return datetime(2020, 1, 1)

    monkeypatch.setattr(telemetry_converter, "datetime", FixedDT)
    telemetry_converter.extract_telemetry_to_gpx(srt, gpx_path)
    digest = hashlib.sha256(gpx_path.read_bytes()).hexdigest()
    assert digest == SAMPLE_HASHES[name]


def test_mini4pro_sample(tmp_path, monkeypatch):
    run_sample("mini4pro", tmp_path, monkeypatch)


def test_air3_sample(tmp_path, monkeypatch):
    run_sample("air3", tmp_path, monkeypatch)


def test_avata2_sample(tmp_path, monkeypatch):
    run_sample("avata2", tmp_path, monkeypatch)
