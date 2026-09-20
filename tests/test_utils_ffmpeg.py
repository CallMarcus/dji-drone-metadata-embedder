"""FFmpeg resolution + version helpers (#579): all subprocess calls faked."""

import subprocess

from dji_metadata_embedder.utils import ffmpeg as ffmpeg_utils

GYAN_BANNER = (
    "ffmpeg version 9.0.2-essentials_build-www.gyan.dev "
    "Copyright (c) 2000-2026 the FFmpeg developers\n"
    "built with gcc 15.2.0 (Rev8, Built by MSYS2 project)\n"
)


def test_ffmpeg_exe_prefers_env_override(monkeypatch, tmp_path):
    exe = tmp_path / "ffmpeg.exe"
    exe.write_text("stub")
    monkeypatch.setenv("DJIEMBED_FFMPEG_PATH", str(exe))
    monkeypatch.setattr(ffmpeg_utils.shutil, "which", lambda *a, **k: "/usr/bin/ffmpeg")
    assert ffmpeg_utils.ffmpeg_exe() == str(exe)


def test_ffmpeg_exe_falls_back_to_path_lookup(monkeypatch):
    monkeypatch.delenv("DJIEMBED_FFMPEG_PATH", raising=False)
    monkeypatch.setattr(ffmpeg_utils.shutil, "which", lambda *a, **k: "/usr/bin/ffmpeg")
    assert ffmpeg_utils.ffmpeg_exe() == "/usr/bin/ffmpeg"


def test_ffmpeg_exe_none_when_absent(monkeypatch):
    monkeypatch.delenv("DJIEMBED_FFMPEG_PATH", raising=False)
    monkeypatch.setattr(ffmpeg_utils.shutil, "which", lambda *a, **k: None)
    assert ffmpeg_utils.ffmpeg_exe() is None


def test_ffmpeg_version_parses_the_banner(monkeypatch):
    monkeypatch.delenv("DJIEMBED_FFMPEG_PATH", raising=False)
    monkeypatch.setattr(ffmpeg_utils.shutil, "which", lambda *a, **k: "/opt/ff/ffmpeg")
    seen = []

    def fake_run(cmd, **kwargs):
        seen.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout=GYAN_BANNER, stderr="")

    monkeypatch.setattr(ffmpeg_utils.subprocess, "run", fake_run)
    assert ffmpeg_utils.ffmpeg_version() == "9.0.2-essentials_build-www.gyan.dev"
    assert seen == [["/opt/ff/ffmpeg", "-version"]]


def test_ffmpeg_version_none_when_absent(monkeypatch):
    monkeypatch.delenv("DJIEMBED_FFMPEG_PATH", raising=False)
    monkeypatch.setattr(ffmpeg_utils.shutil, "which", lambda *a, **k: None)

    def never(*a, **k):
        raise AssertionError("must not spawn a process without an executable")

    monkeypatch.setattr(ffmpeg_utils.subprocess, "run", never)
    assert ffmpeg_utils.ffmpeg_version() is None


def test_ffmpeg_version_none_on_garbage_or_failure(monkeypatch):
    monkeypatch.delenv("DJIEMBED_FFMPEG_PATH", raising=False)
    monkeypatch.setattr(ffmpeg_utils.shutil, "which", lambda *a, **k: "/opt/ff/ffmpeg")
    monkeypatch.setattr(
        ffmpeg_utils.subprocess,
        "run",
        lambda cmd, **k: subprocess.CompletedProcess(cmd, 0, stdout="not ffmpeg", stderr=""),
    )
    assert ffmpeg_utils.ffmpeg_version() is None

    def boom(cmd, **k):
        raise OSError("exec format error")

    monkeypatch.setattr(ffmpeg_utils.subprocess, "run", boom)
    assert ffmpeg_utils.ffmpeg_version() is None
