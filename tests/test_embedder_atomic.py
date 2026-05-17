"""Tests for atomic write and validation (issue #162).

Ensures output is only saved after successful completion and validation,
so interrupted runs do not leave corrupted files in the destination.
"""

import subprocess
from pathlib import Path

import pytest

from dji_metadata_embedder.embedder import (
    _TEMP_SUFFIX,
    _validate_embedded_output,
    DJIMetadataEmbedder,
)


class TestValidateEmbeddedOutput:
    """Tests for _validate_embedded_output.

    The validator now compares media durations rather than file sizes — the
    size check produced false negatives once we started dropping untaggable
    data streams from real DJI footage (see embedder.py for context).
    """

    @staticmethod
    def _fake_ffprobe(durations: dict):
        """Return a subprocess.run replacement that responds to ffprobe duration
        queries by looking up the input path's stem in *durations*. Anything not
        in the map returns returncode=1 (simulates unreadable input).
        """
        def runner(cmd, *args, **kwargs):
            target = Path(cmd[-1]).name
            if target in durations:
                value = durations[target]
                if value is None:
                    return type("R", (), {"returncode": 1, "stdout": "", "stderr": "error"})()
                return type("R", (), {"returncode": 0, "stdout": f"{value}\n", "stderr": ""})()
            return type("R", (), {"returncode": 1, "stdout": "", "stderr": "unknown"})()
        return runner

    def test_returns_false_when_temp_missing(self, tmp_path: Path) -> None:
        original = tmp_path / "original.mp4"
        original.write_bytes(b"x" * 1000)
        temp_path = tmp_path / "out.mp4.tmp"
        assert not _validate_embedded_output(original, temp_path)

    def test_returns_true_when_durations_match(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        original = tmp_path / "original.mp4"
        original.write_bytes(b"x" * 1000)
        temp_path = tmp_path / "out.mp4.tmp"
        temp_path.write_bytes(b"x" * 1500)
        monkeypatch.setattr(
            subprocess, "run",
            self._fake_ffprobe({"original.mp4": 10.0, "out.mp4.tmp": 10.0}),
        )
        assert _validate_embedded_output(original, temp_path) is True

    def test_returns_true_when_output_smaller_but_duration_matches(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Output may be smaller than source after dropping data streams; that
        alone must not fail validation."""
        original = tmp_path / "original.mp4"
        original.write_bytes(b"x" * 2000)
        temp_path = tmp_path / "out.mp4.tmp"
        temp_path.write_bytes(b"x" * 1500)
        monkeypatch.setattr(
            subprocess, "run",
            self._fake_ffprobe({"original.mp4": 53.62, "out.mp4.tmp": 53.62}),
        )
        assert _validate_embedded_output(original, temp_path) is True

    def test_returns_false_when_output_duration_short(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Truncated output is what we actually want to catch."""
        original = tmp_path / "original.mp4"
        original.write_bytes(b"x" * 1000)
        temp_path = tmp_path / "out.mp4.tmp"
        temp_path.write_bytes(b"x" * 1500)
        monkeypatch.setattr(
            subprocess, "run",
            self._fake_ffprobe({"original.mp4": 60.0, "out.mp4.tmp": 5.0}),
        )
        assert _validate_embedded_output(original, temp_path) is False

    def test_returns_true_when_output_within_one_second(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sub-second drift (container rounding, subtitle padding) is allowed."""
        original = tmp_path / "original.mp4"
        original.write_bytes(b"x" * 1000)
        temp_path = tmp_path / "out.mp4.tmp"
        temp_path.write_bytes(b"x" * 1500)
        monkeypatch.setattr(
            subprocess, "run",
            self._fake_ffprobe({"original.mp4": 53.62, "out.mp4.tmp": 53.10}),
        )
        assert _validate_embedded_output(original, temp_path) is True

    def test_returns_false_when_output_unreadable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        original = tmp_path / "original.mp4"
        original.write_bytes(b"x" * 1000)
        temp_path = tmp_path / "out.mp4.tmp"
        temp_path.write_bytes(b"x" * 1500)
        monkeypatch.setattr(
            subprocess, "run",
            self._fake_ffprobe({"original.mp4": 10.0, "out.mp4.tmp": None}),
        )
        assert _validate_embedded_output(original, temp_path) is False


class TestProcessDirectoryAtomicWrite:
    """Tests that process_directory uses temp file and atomic move."""

    @staticmethod
    def _fake_progress_class():
        """Minimal Progress-like class for tests (conftest stubs Progress as object)."""
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

    def test_temp_suffix_defined(self) -> None:
        assert _TEMP_SUFFIX == ".tmp"

    def test_output_written_to_temp_then_moved(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When embed succeeds and validation passes, final path exists and temp is gone."""
        video = tmp_path / "DJI_20240101_123456.mp4"
        srt = tmp_path / "DJI_20240101_123456.srt"
        video.write_bytes(b"fake mp4 content here")
        srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nGPS(1,2,3)")

        out_dir = tmp_path / "processed"
        out_dir.mkdir()
        final_output = out_dir / "DJI_20240101_123456_metadata.mp4"
        temp_output = final_output.with_name(
            final_output.stem + _TEMP_SUFFIX + final_output.suffix
        )

        ffmpeg_called: list = []

        def fake_run(cmd: list, *args, **kwargs):
            ok = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if cmd and "ffmpeg" in str(cmd[0]).lower():
                ffmpeg_called.append(cmd)
                out_path = Path(cmd[-1])
                out_path.write_bytes(b"embedded content")
                return ok
            if cmd and "ffprobe" in str(cmd[0]).lower():
                # ffprobe duration query — return matching durations so the
                # validator's truncation check passes.
                return type("R", (), {"returncode": 0, "stdout": "10.0\n", "stderr": ""})()
            return ok

        monkeypatch.setattr(subprocess, "run", fake_run)
        monkeypatch.setattr(
            "dji_metadata_embedder.embedder.Progress",
            self._fake_progress_class(),
        )

        embedder = DJIMetadataEmbedder(str(tmp_path), output_dir=str(out_dir))
        result = embedder.process_directory(use_exiftool=False)

        assert result["processed"] == 1
        assert final_output.exists()
        assert final_output.read_bytes() == b"embedded content"
        assert not temp_output.exists()
        assert len(ffmpeg_called) >= 1
        ffmpeg_output_arg = ffmpeg_called[0][-1]
        # The temp path must keep the original extension last so ffmpeg can
        # pick the correct output muxer (issue: a trailing ".tmp" breaks it).
        assert ffmpeg_output_arg.endswith(final_output.suffix)
        assert _TEMP_SUFFIX in Path(ffmpeg_output_arg).name

    def test_ffmpeg_command_maps_streams_and_drops_data(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ffmpeg must receive -map 0 -map -0:d -map 1: keep every source
        video/audio stream and the SRT, but drop proprietary data streams
        (DJI `djmd` / `dbgi`) that the MP4 muxer cannot tag. See GH discussion
        #192 and the follow-up in embedder.py for the full context.
        """
        video = tmp_path / "DJI_20240101_123456.mp4"
        srt = tmp_path / "DJI_20240101_123456.srt"
        video.write_bytes(b"fake mp4 content here")
        srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nGPS(1,2,3)")

        out_dir = tmp_path / "processed"
        out_dir.mkdir()

        ffmpeg_called: list = []

        def fake_run(cmd: list, *args, **kwargs):
            ok = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if cmd and "ffmpeg" in str(cmd[0]).lower():
                ffmpeg_called.append(cmd)
                Path(cmd[-1]).write_bytes(b"embedded content")
                return ok
            if cmd and "ffprobe" in str(cmd[0]).lower():
                return type("R", (), {"returncode": 0, "stdout": "10.0\n", "stderr": ""})()
            return ok

        monkeypatch.setattr(subprocess, "run", fake_run)
        monkeypatch.setattr(
            "dji_metadata_embedder.embedder.Progress",
            self._fake_progress_class(),
        )

        embedder = DJIMetadataEmbedder(str(tmp_path), output_dir=str(out_dir))
        embedder.process_directory(use_exiftool=False)

        assert ffmpeg_called, "ffmpeg was not invoked"
        cmd = ffmpeg_called[0]
        map_indices = [i for i, tok in enumerate(cmd) if tok == "-map"]
        map_targets = [cmd[i + 1] for i in map_indices]
        assert "0" in map_targets, f"expected -map 0 in ffmpeg cmd, got {cmd}"
        assert "-0:d" in map_targets, f"expected -map -0:d in ffmpeg cmd, got {cmd}"
        assert "1" in map_targets, f"expected -map 1 in ffmpeg cmd, got {cmd}"

    def test_final_not_created_when_validation_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When ffprobe can't read the embedded output (truncated/corrupt),
        the final file is not created and the temp file is removed."""
        video = tmp_path / "DJI_20240101_123456.mp4"
        srt = tmp_path / "DJI_20240101_123456.srt"
        video.write_bytes(b"x" * 2000)
        srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nGPS(1,2,3)")

        out_dir = tmp_path / "processed"
        out_dir.mkdir()
        final_output = out_dir / "DJI_20240101_123456_metadata.mp4"
        temp_output = final_output.with_name(
            final_output.stem + _TEMP_SUFFIX + final_output.suffix
        )

        def fake_run(cmd: list, *args, **kwargs):
            if cmd and "ffmpeg" in str(cmd[0]).lower():
                Path(cmd[-1]).write_bytes(b"x" * 100)
                return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if cmd and "ffprobe" in str(cmd[0]).lower():
                # Output unreadable (simulates truncation/corruption).
                target = Path(cmd[-1]).name
                if _TEMP_SUFFIX in target:
                    return type("R", (), {"returncode": 1, "stdout": "", "stderr": "moov not found"})()
                return type("R", (), {"returncode": 0, "stdout": "10.0\n", "stderr": ""})()
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        monkeypatch.setattr(subprocess, "run", fake_run)
        monkeypatch.setattr(
            "dji_metadata_embedder.embedder.Progress",
            self._fake_progress_class(),
        )

        embedder = DJIMetadataEmbedder(str(tmp_path), output_dir=str(out_dir))
        result = embedder.process_directory(use_exiftool=False)

        assert result["processed"] == 0
        assert not final_output.exists()
        assert not temp_output.exists()

    def test_overwrite_mode_writes_in_place(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With overwrite=True, embedded video replaces the original file (issue #163)."""
        video = tmp_path / "clip.mp4"
        srt = tmp_path / "clip.srt"
        video.write_bytes(b"original video content here")
        srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nGPS(1,2,3)")

        def fake_run(cmd: list, *args, **kwargs):
            ok = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if cmd and "ffmpeg" in str(cmd[0]).lower():
                out_path = Path(cmd[-1])
                out_path.write_bytes(b"embedded in place")
                return ok
            if cmd and "ffprobe" in str(cmd[0]).lower():
                return type("R", (), {"returncode": 0, "stdout": "10.0\n", "stderr": ""})()
            return ok

        monkeypatch.setattr(subprocess, "run", fake_run)
        monkeypatch.setattr(
            "dji_metadata_embedder.embedder.Progress",
            self._fake_progress_class(),
        )

        embedder = DJIMetadataEmbedder(str(tmp_path), overwrite=True)
        result = embedder.process_directory(use_exiftool=False)

        assert result["processed"] == 1
        assert result["output_directory"] == str(tmp_path)
        assert video.exists()
        assert video.read_bytes() == b"embedded in place"
        assert not video.with_name(
            video.stem + _TEMP_SUFFIX + video.suffix
        ).exists()
