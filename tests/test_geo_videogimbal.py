"""#546: gimbal attitude from the sibling video's djmd stream."""

from datetime import datetime

import pytest

from dji_metadata_embedder.geo.media import find_video_path
from dji_metadata_embedder.geo.videogimbal import (
    VideoGimbalUnavailable,
    enrich_from_video,
    merge_video_gimbal,
    needs_gimbal,
)
from dji_metadata_embedder.mp4_telemetry import Mp4TelemetryError
from dji_metadata_embedder.utilities import TelemetrySample


def _srt(cue: str, yaw=None, pitch=None) -> TelemetrySample:
    return TelemetrySample(
        lat=10.0, lon=20.0, alt=5.0, cue=cue,
        dt=datetime(2026, 8, 15, 14, 23, 33),
        gimbal_yaw=yaw, gimbal_pitch=pitch,
    )


def _djmd(cue: str, yaw: float, pitch: float) -> TelemetrySample:
    return TelemetrySample(
        lat=10.0, lon=20.0, alt=5.0, cue=cue,
        dt=datetime(2026, 8, 15, 12, 23, 33),
        gimbal_yaw=yaw, gimbal_pitch=pitch,
    )


# --- merge_video_gimbal: pure cue join ---


def test_merge_fills_missing_attitude_from_nearest_cue():
    srt = [_srt("00:00:00,000"), _srt("00:00:01,000")]
    video = [
        _djmd("00:00:00,017", 90.0, -30.0),
        _djmd("00:00:00,983", 95.0, -35.0),
        _djmd("00:00:01,017", 100.0, -40.0),
    ]
    assert merge_video_gimbal(srt, video) == 2
    assert (srt[0].gimbal_yaw, srt[0].gimbal_pitch) == (90.0, -30.0)
    # 1.000 is 17 ms from both neighbours; the earlier one wins ties.
    assert srt[1].gimbal_yaw in (95.0, 100.0)


def test_merge_never_overwrites_srt_values():
    srt = [_srt("00:00:00,000", yaw=12.0, pitch=None)]
    video = [_djmd("00:00:00,000", 90.0, -30.0)]
    assert merge_video_gimbal(srt, video) == 1
    assert srt[0].gimbal_yaw == 12.0
    assert srt[0].gimbal_pitch == -30.0


def test_merge_skips_cues_beyond_tolerance_and_unparseable():
    srt = [_srt("00:00:05,000"), _srt("garbage")]
    video = [_djmd("00:00:00,000", 90.0, -30.0)]
    assert merge_video_gimbal(srt, video) == 0
    assert srt[0].gimbal_yaw is None and srt[1].gimbal_yaw is None


def test_merge_counts_only_samples_that_gained_something():
    srt = [_srt("00:00:00,000", yaw=1.0, pitch=2.0), _srt("00:00:01,000")]
    video = [_djmd("00:00:00,000", 90.0, -30.0), _djmd("00:00:01,000", 91.0, -31.0)]
    assert merge_video_gimbal(srt, video) == 1


def test_needs_gimbal_is_false_only_when_every_sample_is_complete():
    assert needs_gimbal([_srt("00:00:00,000")])
    assert needs_gimbal([_srt("00:00:00,000", yaw=1.0)])
    assert not needs_gimbal([_srt("00:00:00,000", yaw=1.0, pitch=2.0)])
    assert not needs_gimbal([])


# --- find_video_path ---


def test_find_video_path_prefers_mp4_over_mov_and_is_none_when_absent(tmp_path):
    (tmp_path / "DJI_0001.SRT").write_text("", encoding="utf-8")
    assert find_video_path(tmp_path, "DJI_0001") is None
    (tmp_path / "DJI_0001.mov").write_bytes(b"")
    assert find_video_path(tmp_path, "DJI_0001") == tmp_path / "DJI_0001.mov"
    (tmp_path / "DJI_0001.MP4").write_bytes(b"")
    assert find_video_path(tmp_path, "DJI_0001") == tmp_path / "DJI_0001.MP4"


# --- enrich_from_video ---


def test_enrich_without_sibling_video_reports_reason(tmp_path):
    srt = tmp_path / "DJI_0001.SRT"
    srt.write_text("", encoding="utf-8")
    calls = []
    report = enrich_from_video(srt, [_srt("00:00:00,000")], extract=calls.append)
    assert report.matched == 0 and calls == []
    assert report.video is None
    assert "no video" in (report.reason or "")


def test_enrich_skips_when_srt_already_carries_attitude(tmp_path):
    srt = tmp_path / "DJI_0001.SRT"
    srt.write_text("", encoding="utf-8")
    (tmp_path / "DJI_0001.MP4").write_bytes(b"")
    calls = []
    report = enrich_from_video(
        srt, [_srt("00:00:00,000", yaw=1.0, pitch=2.0)], extract=calls.append
    )
    assert calls == []
    assert "already" in (report.reason or "")


def test_enrich_reports_extractor_errors_as_reason(tmp_path, monkeypatch):
    srt = tmp_path / "DJI_0001.SRT"
    srt.write_text("", encoding="utf-8")
    (tmp_path / "DJI_0001.MP4").write_bytes(b"")
    monkeypatch.setattr(
        "dji_metadata_embedder.geo.videogimbal.exiftool_available", lambda: True
    )

    def boom(path):
        raise Mp4TelemetryError("No embedded telemetry found in DJI_0001.MP4")

    report = enrich_from_video(srt, [_srt("00:00:00,000")], extract=boom)
    assert report.matched == 0
    assert report.video == "DJI_0001.MP4"
    assert "No embedded telemetry" in (report.reason or "")


def test_enrich_raises_when_exiftool_is_missing(tmp_path, monkeypatch):
    srt = tmp_path / "DJI_0001.SRT"
    srt.write_text("", encoding="utf-8")
    (tmp_path / "DJI_0001.MP4").write_bytes(b"")
    monkeypatch.setattr(
        "dji_metadata_embedder.geo.videogimbal.exiftool_available", lambda: False
    )
    with pytest.raises(VideoGimbalUnavailable, match="doctor --install exiftool"):
        enrich_from_video(srt, [_srt("00:00:00,000")], extract=lambda p: [])


def test_enrich_merges_and_reports(tmp_path, monkeypatch):
    srt = tmp_path / "DJI_0001.SRT"
    srt.write_text("", encoding="utf-8")
    (tmp_path / "DJI_0001.MP4").write_bytes(b"")
    monkeypatch.setattr(
        "dji_metadata_embedder.geo.videogimbal.exiftool_available", lambda: True
    )
    samples = [_srt("00:00:00,000"), _srt("00:00:01,000"), _srt("00:00:09,000")]
    seen = []

    def fake(path):
        seen.append(path)
        return [_djmd("00:00:00,000", 90.0, -30.0), _djmd("00:00:01,000", 91.0, -31.0)]

    report = enrich_from_video(srt, samples, name="DJI_0001", extract=fake)
    assert seen == [tmp_path / "DJI_0001.MP4"]
    assert (report.name, report.video) == ("DJI_0001", "DJI_0001.MP4")
    assert (report.matched, report.total) == (2, 3)
    assert report.reason is None
    assert report.seconds >= 0.0
    assert samples[2].gimbal_yaw is None
