"""Tests for --audio-sidecar: auto-merge Neo 2's separate .m4a audio (issue #246).

The DJI Neo 2 records video and audio as separate files (DJI_xxx.MP4 with no
audio stream + DJI_xxx.m4a). With --audio-sidecar, the paired .m4a is muxed in
as a third ffmpeg input (stream-copied, no re-encode) while the telemetry
subtitle track is preserved.
"""

import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

import dji_metadata_embedder.cli as cli
from dji_metadata_embedder.cli import main
from dji_metadata_embedder.embedder import DJIMetadataEmbedder


def _minimal_telemetry() -> dict:
    """Smallest telemetry dict embed_metadata_ffmpeg will accept."""
    return {"first_gps": None, "max_altitude": None}


def _fake_progress_class():
    """Minimal Progress-like class (conftest stubs Progress as object)."""
    class Task:
        def advance(self, _=None):
            pass

    class FakeProgress:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def add_task(self, *args, **kwargs):
            return Task()

        def update(self, task, description=None):
            pass

        def advance(self, task):
            pass

    return FakeProgress


class TestEmbedMetadataFfmpegAudio:
    """Unit tests for embed_metadata_ffmpeg's audio_path argument."""

    def test_audio_path_adds_third_input_and_maps_audio(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With audio_path set, ffmpeg gets the audio as a third input (index 2)
        and -map 2:a, while the SRT subtitle stays at -map 1 (unshifted)."""
        video = tmp_path / "DJI_0001.mp4"
        srt = tmp_path / "DJI_0001.srt"
        audio = tmp_path / "DJI_0001.m4a"
        for f in (video, srt, audio):
            f.write_bytes(b"data")
        out = tmp_path / "out.mp4"

        captured: list = []

        def fake_run(cmd, *args, **kwargs):
            captured.append(cmd)
            Path(cmd[-1]).write_bytes(b"embedded")
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        monkeypatch.setattr(subprocess, "run", fake_run)

        embedder = DJIMetadataEmbedder(str(tmp_path), output_dir=str(tmp_path / "processed"))
        ok = embedder.embed_metadata_ffmpeg(
            video, srt, _minimal_telemetry(), out, audio_path=audio
        )

        assert ok is True
        assert captured, "ffmpeg was not invoked"
        cmd = captured[0]

        # Input order: video (0), srt (1), audio (2).
        i_flags = [i for i, tok in enumerate(cmd) if tok == "-i"]
        inputs = [cmd[i + 1] for i in i_flags]
        assert inputs == [str(video), str(srt), str(audio)], (
            f"expected video, srt, audio inputs in order, got {inputs}"
        )

        # Map targets: subtitle stays at 1, audio pulled from input 2.
        map_targets = [cmd[i + 1] for i, tok in enumerate(cmd) if tok == "-map"]
        assert "1" in map_targets, f"srt subtitle map shifted: {map_targets}"
        assert "2:a" in map_targets, f"expected -map 2:a, got {map_targets}"

    def test_no_audio_path_leaves_command_unchanged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without audio_path, no third input and no audio map are added."""
        video = tmp_path / "DJI_0001.mp4"
        srt = tmp_path / "DJI_0001.srt"
        for f in (video, srt):
            f.write_bytes(b"data")
        out = tmp_path / "out.mp4"

        captured: list = []

        def fake_run(cmd, *args, **kwargs):
            captured.append(cmd)
            Path(cmd[-1]).write_bytes(b"embedded")
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        monkeypatch.setattr(subprocess, "run", fake_run)

        embedder = DJIMetadataEmbedder(str(tmp_path), output_dir=str(tmp_path / "processed"))
        embedder.embed_metadata_ffmpeg(video, srt, _minimal_telemetry(), out)

        cmd = captured[0]
        i_flags = [i for i, tok in enumerate(cmd) if tok == "-i"]
        inputs = [cmd[i + 1] for i in i_flags]
        assert inputs == [str(video), str(srt)], f"unexpected extra input: {inputs}"
        map_targets = [cmd[i + 1] for i, tok in enumerate(cmd) if tok == "-map"]
        assert "2:a" not in map_targets


def _make_run_capture(captured: list, durations: dict | None = None):
    """subprocess.run replacement: captures ffmpeg cmds (writing their output),
    and answers ffprobe duration queries. *durations* maps a filename to its
    duration; anything absent falls back to 10.0."""
    durations = durations or {}

    def fake_run(cmd, *args, **kwargs):
        ok = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        if cmd and "ffmpeg" in str(cmd[0]).lower():
            captured.append(cmd)
            Path(cmd[-1]).write_bytes(b"embedded content")
            return ok
        if cmd and "ffprobe" in str(cmd[0]).lower():
            name = Path(cmd[-1]).name
            value = durations.get(name, 10.0)
            return type("R", (), {"returncode": 0, "stdout": f"{value}\n", "stderr": ""})()
        return ok

    return fake_run


class TestProcessDirectoryAudioSidecar:
    """process_directory pairing behaviour for --audio-sidecar."""

    def _prep(self, tmp_path: Path, with_audio: bool) -> tuple[Path, Path]:
        video = tmp_path / "DJI_20240101_123456.mp4"
        srt = tmp_path / "DJI_20240101_123456.srt"
        video.write_bytes(b"fake mp4 content here")
        srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nGPS(1,2,3)")
        audio = tmp_path / "DJI_20240101_123456.m4a"
        if with_audio:
            audio.write_bytes(b"fake audio")
        out_dir = tmp_path / "processed"
        out_dir.mkdir()
        return audio, out_dir

    def test_paired_m4a_is_muxed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A same-basename .m4a next to the video is added as the audio input."""
        audio, out_dir = self._prep(tmp_path, with_audio=True)
        captured: list = []
        monkeypatch.setattr(subprocess, "run", _make_run_capture(captured))
        monkeypatch.setattr(
            "dji_metadata_embedder.embedder.Progress", _fake_progress_class()
        )

        embedder = DJIMetadataEmbedder(
            str(tmp_path), output_dir=str(out_dir), audio_sidecar=True
        )
        result = embedder.process_directory(use_exiftool=False)

        assert result["processed"] == 1
        assert captured, "ffmpeg was not invoked"
        cmd = captured[0]
        inputs = [cmd[i + 1] for i, tok in enumerate(cmd) if tok == "-i"]
        assert str(audio) in inputs, f"audio sidecar not passed to ffmpeg: {inputs}"
        map_targets = [cmd[i + 1] for i, tok in enumerate(cmd) if tok == "-map"]
        assert "2:a" in map_targets

    def test_missing_m4a_warns_and_falls_back(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No .m4a → warn-and-continue: the video still processes, no audio
        input is added, and a warning is recorded."""
        _audio, out_dir = self._prep(tmp_path, with_audio=False)
        captured: list = []
        monkeypatch.setattr(subprocess, "run", _make_run_capture(captured))
        monkeypatch.setattr(
            "dji_metadata_embedder.embedder.Progress", _fake_progress_class()
        )

        embedder = DJIMetadataEmbedder(
            str(tmp_path), output_dir=str(out_dir), audio_sidecar=True
        )
        result = embedder.process_directory(use_exiftool=False)

        assert result["processed"] == 1
        cmd = captured[0]
        inputs = [cmd[i + 1] for i, tok in enumerate(cmd) if tok == "-i"]
        assert len(inputs) == 2, f"expected no audio input, got {inputs}"
        assert any(
            "m4a" in w.lower() or "audio" in w.lower() for w in result["warnings"]
        ), f"expected a missing-sidecar warning, got {result['warnings']}"

    def test_flag_off_ignores_m4a(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without --audio-sidecar, a present .m4a is left untouched."""
        _audio, out_dir = self._prep(tmp_path, with_audio=True)
        captured: list = []
        monkeypatch.setattr(subprocess, "run", _make_run_capture(captured))
        monkeypatch.setattr(
            "dji_metadata_embedder.embedder.Progress", _fake_progress_class()
        )

        embedder = DJIMetadataEmbedder(str(tmp_path), output_dir=str(out_dir))
        embedder.process_directory(use_exiftool=False)

        cmd = captured[0]
        inputs = [cmd[i + 1] for i, tok in enumerate(cmd) if tok == "-i"]
        assert len(inputs) == 2, f"audio muxed without the flag: {inputs}"

    def test_duration_mismatch_warns_but_still_muxes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A large video/audio duration gap warns but still muxes (user opted in)."""
        audio, out_dir = self._prep(tmp_path, with_audio=True)
        captured: list = []
        # Video 60s, audio 10s — a 50s gap the sanity check should flag.
        durations = {
            "DJI_20240101_123456.mp4": 60.0,
            "DJI_20240101_123456.m4a": 10.0,
        }
        monkeypatch.setattr(
            subprocess, "run", _make_run_capture(captured, durations)
        )
        monkeypatch.setattr(
            "dji_metadata_embedder.embedder.Progress", _fake_progress_class()
        )

        embedder = DJIMetadataEmbedder(
            str(tmp_path), output_dir=str(out_dir), audio_sidecar=True
        )
        result = embedder.process_directory(use_exiftool=False)

        cmd = captured[0]
        inputs = [cmd[i + 1] for i, tok in enumerate(cmd) if tok == "-i"]
        assert str(audio) in inputs, "audio should still be muxed despite mismatch"
        assert any(
            "duration" in w.lower() for w in result["warnings"]
        ), f"expected a duration-mismatch warning, got {result['warnings']}"


class TestCliAudioSidecarFlag:
    """The embed command exposes --audio-sidecar and threads it through."""

    def test_flag_passed_to_embedder(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict = {}

        class FakeEmbedder:
            def __init__(self, *args, **kwargs):
                captured.update(kwargs)

            def process_directory(self, *args, **kwargs):
                return {"processed": 0, "warnings": []}

        monkeypatch.setattr(cli, "check_dependencies", lambda: (True, []))
        monkeypatch.setattr(cli, "DJIMetadataEmbedder", FakeEmbedder)

        runner = CliRunner()
        result = runner.invoke(main, ["embed", str(tmp_path), "--audio-sidecar"])

        assert result.exit_code == 0, result.output
        assert captured.get("audio_sidecar") is True

    def test_flag_defaults_false(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict = {}

        class FakeEmbedder:
            def __init__(self, *args, **kwargs):
                captured.update(kwargs)

            def process_directory(self, *args, **kwargs):
                return {"processed": 0, "warnings": []}

        monkeypatch.setattr(cli, "check_dependencies", lambda: (True, []))
        monkeypatch.setattr(cli, "DJIMetadataEmbedder", FakeEmbedder)

        runner = CliRunner()
        result = runner.invoke(main, ["embed", str(tmp_path)])

        assert result.exit_code == 0, result.output
        assert captured.get("audio_sidecar") is False
