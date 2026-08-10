"""Embed warns when a source carries DJI djmd/dbgi streams (issue #478).

The MP4 muxer cannot tag DJI's proprietary data streams, so the default
embed drops them — previously in silence, leaving the "with metadata"
output as the one variant *missing* the manufacturer's own embedded
telemetry. The embed run now says so per affected file (and points at
--container mkv), and ``check`` reports the streams' presence.
"""

import json
import subprocess
from pathlib import Path

from dji_metadata_embedder import metadata_check
from dji_metadata_embedder.embedder import (
    DJIMetadataEmbedder,
    _dji_data_stream_tags,
)


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


def _fake_run(data_streams: list[dict]):
    """subprocess.run replacement: ffmpeg writes its output, the data-stream
    ffprobe query answers with *data_streams*, other ffprobe calls answer a
    duration (so output validation passes)."""
    streams_json = json.dumps({"streams": data_streams})

    def run(cmd, *args, **kwargs):
        ok = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        prog = str(cmd[0]).lower()
        if "ffmpeg" in prog:
            Path(cmd[-1]).write_bytes(b"embedded content")
            return ok
        if "ffprobe" in prog:
            if "-select_streams" in cmd:
                return type(
                    "R", (), {"returncode": 0, "stdout": streams_json, "stderr": ""}
                )()
            return type("R", (), {"returncode": 0, "stdout": "10.0\n", "stderr": ""})()
        return ok

    return run


DJI_STREAMS = [{"codec_tag_string": "djmd"}, {"codec_tag_string": "dbgi"}]


class TestDjiDataStreamTags:
    def test_returns_tags_from_ffprobe_json(self, monkeypatch):
        monkeypatch.setattr(subprocess, "run", _fake_run(DJI_STREAMS))
        assert _dji_data_stream_tags(Path("clip.mp4")) == ["djmd", "dbgi"]

    def test_ignores_other_data_streams(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run", _fake_run([{"codec_tag_string": "tmcd"}])
        )
        assert _dji_data_stream_tags(Path("clip.mp4")) == []

    def test_missing_ffprobe_is_empty_not_fatal(self, monkeypatch):
        def raise_missing(cmd, *args, **kwargs):
            raise FileNotFoundError("ffprobe")

        monkeypatch.setattr(subprocess, "run", raise_missing)
        assert _dji_data_stream_tags(Path("clip.mp4")) == []

    def test_unparseable_output_is_empty(self, monkeypatch):
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **k: type(
                "R", (), {"returncode": 0, "stdout": "10.0\n", "stderr": ""}
            )(),
        )
        assert _dji_data_stream_tags(Path("clip.mp4")) == []


class TestProcessDirectoryNotice:
    def _prep(self, tmp_path: Path) -> Path:
        video = tmp_path / "DJI_20240101_123456.mp4"
        srt = tmp_path / "DJI_20240101_123456.srt"
        video.write_bytes(b"fake mp4 content here")
        srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nGPS(1,2,3)")
        out_dir = tmp_path / "processed"
        out_dir.mkdir()
        return out_dir

    def _run(self, tmp_path, monkeypatch, *, streams, **embedder_kwargs):
        out_dir = self._prep(tmp_path)
        monkeypatch.setattr(subprocess, "run", _fake_run(streams))
        monkeypatch.setattr(
            "dji_metadata_embedder.embedder.Progress", _fake_progress_class()
        )
        embedder = DJIMetadataEmbedder(
            str(tmp_path), output_dir=str(out_dir), **embedder_kwargs
        )
        return embedder.process_directory(use_exiftool=False)

    def test_mp4_default_warns_and_still_processes(self, tmp_path, monkeypatch):
        result = self._run(tmp_path, monkeypatch, streams=DJI_STREAMS)
        assert result["processed"] == 1
        notices = [w for w in result["warnings"] if "djmd" in w]
        assert len(notices) == 1
        assert "--container mkv" in notices[0]
        assert "authoritative" in notices[0]
        assert "LOST" not in notices[0]

    def test_overwrite_mode_says_lost(self, tmp_path, monkeypatch):
        result = self._run(
            tmp_path, monkeypatch, streams=DJI_STREAMS, overwrite=True
        )
        notices = [w for w in result["warnings"] if "djmd" in w]
        assert len(notices) == 1
        assert "LOST" in notices[0]

    def test_mkv_container_does_not_warn(self, tmp_path, monkeypatch):
        result = self._run(
            tmp_path, monkeypatch, streams=DJI_STREAMS, container="mkv"
        )
        assert result["processed"] == 1
        assert not [w for w in result["warnings"] if "djmd" in w]

    def test_no_data_streams_no_warning(self, tmp_path, monkeypatch):
        result = self._run(tmp_path, monkeypatch, streams=[])
        assert result["processed"] == 1
        assert not [w for w in result["warnings"] if "djmd" in w]


class TestCheckReportsEmbeddedTelemetry:
    def _check(self, monkeypatch, ffprobe_data):
        monkeypatch.setattr(metadata_check, "run_ffprobe", lambda p: ffprobe_data)
        monkeypatch.setattr(metadata_check, "run_exiftool", lambda p: {})
        return metadata_check.check_file(Path("clip.mp4"))

    def test_djmd_stream_sets_flag(self, monkeypatch):
        result = self._check(
            monkeypatch,
            {
                "format": {"tags": {}},
                "streams": [{"codec_type": "data", "codec_tag_string": "djmd"}],
            },
        )
        assert result["embedded_telemetry"] is True

    def test_plain_file_reports_false(self, monkeypatch):
        result = self._check(
            monkeypatch,
            {
                "format": {"tags": {}},
                "streams": [{"codec_type": "video", "codec_tag_string": "hvc1"}],
            },
        )
        assert result["embedded_telemetry"] is False

    def test_non_dji_data_stream_reports_false(self, monkeypatch):
        result = self._check(
            monkeypatch,
            {
                "format": {"tags": {}},
                "streams": [{"codec_type": "data", "codec_tag_string": "tmcd"}],
            },
        )
        assert result["embedded_telemetry"] is False
