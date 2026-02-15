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
    """Tests for _validate_embedded_output."""

    def test_returns_false_when_temp_missing(self, tmp_path: Path) -> None:
        original = tmp_path / "original.mp4"
        original.write_bytes(b"x" * 1000)
        temp_path = tmp_path / "out.mp4.tmp"
        assert not _validate_embedded_output(original, temp_path)

    def test_returns_false_when_temp_smaller_than_original(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        original = tmp_path / "original.mp4"
        original.write_bytes(b"x" * 2000)
        temp_path = tmp_path / "out.mp4.tmp"
        temp_path.write_bytes(b"x" * 500)
        monkeypatch.setattr(
            subprocess, "run", lambda *a, **k: type("R", (), {"returncode": 0})()
        )
        assert not _validate_embedded_output(original, temp_path)

    def test_returns_true_when_size_ok_and_ffprobe_succeeds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        original = tmp_path / "original.mp4"
        original.write_bytes(b"x" * 1000)
        temp_path = tmp_path / "out.mp4.tmp"
        temp_path.write_bytes(b"x" * 1500)
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **k: type("R", (), {"returncode": 0})(),
        )
        assert _validate_embedded_output(original, temp_path) is True

    def test_returns_false_when_ffprobe_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        original = tmp_path / "original.mp4"
        original.write_bytes(b"x" * 1000)
        temp_path = tmp_path / "out.mp4.tmp"
        temp_path.write_bytes(b"x" * 1500)
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **k: type("R", (), {"returncode": 1})(),
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
        temp_output = Path(str(final_output) + _TEMP_SUFFIX)

        ffmpeg_called: list = []

        def fake_run(cmd: list, *args, **kwargs):
            res = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if cmd and "ffmpeg" in str(cmd[0]).lower():
                ffmpeg_called.append(cmd)
                out_path = Path(cmd[-1])
                # Write at least as many bytes as original so validation (size >= original) passes
                out_path.write_bytes(b"embedded content (padded for size check)")
                return res
            if cmd and "ffprobe" in str(cmd[0]).lower():
                return res
            return res

        monkeypatch.setattr(subprocess, "run", fake_run)
        monkeypatch.setattr(
            "dji_metadata_embedder.embedder.Progress",
            self._fake_progress_class(),
        )

        embedder = DJIMetadataEmbedder(str(tmp_path), output_dir=str(out_dir))
        result = embedder.process_directory(use_exiftool=False)

        assert result["processed"] == 1
        assert final_output.exists()
        assert final_output.read_bytes() == b"embedded content (padded for size check)"
        assert not temp_output.exists()
        assert len(ffmpeg_called) >= 1
        assert ffmpeg_called[0][-1].endswith(_TEMP_SUFFIX)

    def test_final_not_created_when_validation_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When validation fails, final output is not created and temp is removed."""
        video = tmp_path / "DJI_20240101_123456.mp4"
        srt = tmp_path / "DJI_20240101_123456.srt"
        video.write_bytes(b"x" * 2000)
        srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nGPS(1,2,3)")

        out_dir = tmp_path / "processed"
        out_dir.mkdir()
        final_output = out_dir / "DJI_20240101_123456_metadata.mp4"
        temp_output = Path(str(final_output) + _TEMP_SUFFIX)

        def fake_run(cmd: list, *args, **kwargs):
            res = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if cmd and "ffmpeg" in str(cmd[0]).lower():
                Path(cmd[-1]).write_bytes(b"x" * 100)
                return res
            if cmd and "ffprobe" in str(cmd[0]).lower():
                return res
            return res

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
            res = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if cmd and "ffmpeg" in str(cmd[0]).lower():
                out_path = Path(cmd[-1])
                out_path.write_bytes(b"embedded in place (padded for validation)")
                return res
            if cmd and "ffprobe" in str(cmd[0]).lower():
                return res
            return res

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
        assert video.read_bytes() == b"embedded in place (padded for validation)"
        assert not Path(str(video) + _TEMP_SUFFIX).exists()
