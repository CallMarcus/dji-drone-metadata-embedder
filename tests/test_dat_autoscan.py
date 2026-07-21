"""Tests for --dat-auto discovery (issue #339: a missing DAT log warns).

--dat-auto pairs each video with a DAT flight log named after it. The miss
case must warn — mirroring the --audio-sidecar branch — because a user who
copied ``FLY042.DAT`` (the aircraft's own name) next to ``DJI_0001.MP4``
otherwise gets a completely silent no-op. Also pins the two adjacent nits
from the same issue: lowercase ``.dat`` must pair on every platform, and a
multi-match pick must be deterministic and say which log it chose.
"""

import subprocess
from pathlib import Path

import pytest

from dji_metadata_embedder.embedder import DJIMetadataEmbedder


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


def _make_run_capture(captured: list):
    """subprocess.run replacement: captures ffmpeg cmds (writing their output)
    and answers ffprobe duration queries so output validation passes."""

    def fake_run(cmd, *args, **kwargs):
        ok = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        if cmd and "ffmpeg" in str(cmd[0]).lower():
            captured.append(cmd)
            Path(cmd[-1]).write_bytes(b"embedded content")
            return ok
        if cmd and "ffprobe" in str(cmd[0]).lower():
            return type(
                "R", (), {"returncode": 0, "stdout": "10.0\n", "stderr": ""}
            )()
        return ok

    return fake_run


class TestDatAutoscan:
    """process_directory pairing behaviour for --dat-auto."""

    STEM = "DJI_20240101_123456"

    def _prep(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, list]:
        """A one-video folder with ffmpeg + Progress stubbed and DAT parsing
        captured. Returns (out_dir, list of paths parse_dat_v13 was fed)."""
        video = tmp_path / f"{self.STEM}.mp4"
        srt = tmp_path / f"{self.STEM}.srt"
        video.write_bytes(b"fake mp4 content here")
        srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nGPS(1,2,3)")
        out_dir = tmp_path / "processed"
        out_dir.mkdir()

        monkeypatch.setattr(subprocess, "run", _make_run_capture([]))
        monkeypatch.setattr(
            "dji_metadata_embedder.embedder.Progress", _fake_progress_class()
        )
        parsed: list = []

        def fake_parse(path):
            parsed.append(path)
            return {"records": [{"altitude": 1.0}]}

        monkeypatch.setattr(
            "dji_metadata_embedder.embedder.parse_dat_v13", fake_parse
        )
        return out_dir, parsed

    def _run(self, tmp_path: Path, out_dir: Path) -> dict:
        embedder = DJIMetadataEmbedder(
            str(tmp_path), output_dir=str(out_dir), dat_autoscan=True
        )
        return embedder.process_directory(use_exiftool=False)

    def test_missing_dat_warns_and_continues(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No name-matching DAT → the video still processes and a warning
        names it, exactly like the missing-audio-sidecar case (issue #339)."""
        out_dir, parsed = self._prep(tmp_path, monkeypatch)
        # The realistic failure: an aircraft-named log that matches no video.
        (tmp_path / "FLY042.DAT").write_bytes(b"dat")

        result = self._run(tmp_path, out_dir)

        assert result["processed"] == 1
        assert parsed == [], f"unmatched DAT was parsed: {parsed}"
        assert any(
            "dat" in w.lower() and f"{self.STEM}.mp4" in w
            for w in result["warnings"]
        ), f"expected a missing-DAT warning, got {result['warnings']}"

    def test_exact_match_produces_no_warning(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The happy path stays quiet: <video>.DAT is parsed, nothing warns."""
        out_dir, parsed = self._prep(tmp_path, monkeypatch)
        dat = tmp_path / f"{self.STEM}.DAT"
        dat.write_bytes(b"dat")

        result = self._run(tmp_path, out_dir)

        assert parsed == [dat]
        assert not any("dat" in w.lower() for w in result["warnings"]), (
            f"unexpected DAT warning: {result['warnings']}"
        )

    def test_lowercase_dat_extension_pairs_on_every_platform(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """dji_0001.dat pairs on Linux/macOS too, not only on Windows's
        case-insensitive filesystem (issue #339 nit)."""
        out_dir, parsed = self._prep(tmp_path, monkeypatch)
        dat = tmp_path / f"{self.STEM}.dat"
        dat.write_bytes(b"dat")

        result = self._run(tmp_path, out_dir)

        assert parsed == [dat], (
            f"lowercase .dat was not paired, parse saw {parsed}"
        )
        assert not any("dat" in w.lower() for w in result["warnings"])

    def test_multiple_matches_pick_deterministically_and_say_so(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Several prefix matches → the first by name is used and a warning
        names the choice, instead of a silent filesystem-order pick."""
        out_dir, parsed = self._prep(tmp_path, monkeypatch)
        first = tmp_path / f"{self.STEM}_a.DAT"
        first.write_bytes(b"dat")
        (tmp_path / f"{self.STEM}_b.DAT").write_bytes(b"dat")

        result = self._run(tmp_path, out_dir)

        assert parsed == [first]
        assert any(
            "multiple" in w.lower() and first.name in w
            for w in result["warnings"]
        ), f"expected a multiple-match note, got {result['warnings']}"
