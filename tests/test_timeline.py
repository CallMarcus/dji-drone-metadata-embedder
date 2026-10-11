import os
import re
import shutil
from datetime import datetime, timedelta
from fractions import Fraction
from pathlib import Path

import pytest

from dji_metadata_embedder.geo import timeline as tl
from dji_metadata_embedder.geo.clipprobe import ClipFacts, ClipProbeError
from dji_metadata_embedder.geo.fcpxml import build_fcpxml
from dji_metadata_embedder.mp4_telemetry import Mp4TelemetryError
from tests._series import series, write_srt

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
GOLDEN = Path(__file__).parent / "fixtures" / "timeline" / "session.fcpxml"
T0 = datetime(2026, 8, 15, 12, 19, 32)
AIR3S = "dvtm_Air3s.proto;model_name:FC9113"
MINI5 = "dvtm_Mini5Pro.proto;model_name:FC8671"


@pytest.fixture(autouse=True)
def _no_real_exiftool(monkeypatch):
    """ExifTool counts as present, but any unplanned call to the real
    extractor fails loudly; tests that need it patch extract_samples."""
    monkeypatch.setattr(tl, "exiftool_available", lambda: True)

    def unexpected(path):
        raise AssertionError(f"unexpected ExifTool extraction of {path.name}")

    monkeypatch.setattr(tl, "extract_samples", unexpected)


def _probe(created=None, schema=None, fail=()):
    created = created or {}

    def probe(path):
        if path.name in fail:
            raise ClipProbeError("unsupported frame rate 27.500 fps")
        return ClipFacts(
            path=path,
            rate=Fraction(30000, 1001),
            frames=600,
            width=3840,
            height=2160,
            has_audio=False,
            created_utc=created.get(path.name, T0),
            tc_start=None,
            schema=schema,
        )

    return probe


def _clip(folder, name, samples=None, srt_suffix=".SRT"):
    (folder / name).write_bytes(b"")
    if samples is not None:
        write_srt(folder / (Path(name).stem + srt_suffix), samples)


class Warnings(list):
    def __call__(self, message, item=None):
        self.append((item, message))

    def text(self):
        return "\n".join(m for _, m in self)


def _ramp(t, t0, t1, a, b):
    return a if t < t0 else (a + (b - a) * (t - t0) / (t1 - t0) if t < t1 else b)


def test_hover_clip_gets_a_steady_marker(tmp_path):
    _clip(tmp_path, "DJI_0001.MP4", series(20, with_dt=True))
    r = tl.build_timeline(tmp_path, probe=_probe())
    assert r.marker_counts()["steady"] == 1
    assert r.gimbal == {"srt": 0, "video": 0, "none": 1}
    assert r.clips[0].facts.path.is_absolute()


def test_srt_without_gimbal_reads_it_from_the_video(tmp_path, monkeypatch):
    _clip(tmp_path, "DJI_0001.MP4", series(20, with_dt=True))
    video = series(20, yaw=lambda t: 0.0, pitch=lambda t: _ramp(t, 5, 9, -80, -5))
    monkeypatch.setattr(tl, "extract_samples", lambda p: video)
    r = tl.build_timeline(tmp_path, probe=_probe(schema=AIR3S))
    assert r.gimbal["video"] == 1 and r.marker_counts()["reveal"] == 1


def test_no_video_gimbal_skips_the_walk(tmp_path, monkeypatch):
    _clip(tmp_path, "DJI_0001.MP4", series(20, with_dt=True))

    def boom(path):
        raise AssertionError("the video must not be read")

    monkeypatch.setattr(tl, "extract_samples", boom)
    warn = Warnings()
    tl.build_timeline(
        tmp_path, video_gimbal=False, warn=warn, probe=_probe(schema=AIR3S)
    )
    assert "no gimbal data" in warn.text()


def test_gimbal_less_schema_never_walks_the_video(tmp_path, monkeypatch):
    _clip(tmp_path, "DJI_0001.MP4", series(20, with_dt=True))

    def boom(path):
        raise AssertionError("the video must not be read")

    monkeypatch.setattr(tl, "extract_samples", boom)
    assert tl.build_timeline(tmp_path, probe=_probe(schema=MINI5)).gimbal["none"] == 1


def test_djmd_only_clip_treats_missing_gimbal_as_level(tmp_path, monkeypatch):
    _clip(tmp_path, "DJI_0001.MP4")
    monkeypatch.setattr(tl, "extract_samples", lambda p: series(20))
    warn = Warnings()
    r = tl.build_timeline(tmp_path, warn=warn, probe=_probe(schema=AIR3S))
    assert r.gimbal["video"] == 1 and "no gimbal data" not in warn.text()


def test_undecodable_model_is_named_not_blamed_on_the_version(tmp_path, monkeypatch):
    _clip(tmp_path, "NEO.2.DJI_0080_D.MP4")

    def fail(path):
        raise Mp4TelemetryError("needs ExifTool >= 13.05")

    monkeypatch.setattr(tl, "extract_samples", fail)
    monkeypatch.setattr(tl, "exiftool_version", lambda: "13.59")
    warn = Warnings()
    r = tl.build_timeline(
        tmp_path, warn=warn, probe=_probe(schema="dvtm_NEO2.proto;model_name:X")
    )
    assert len(r.clips) == 1 and r.clips[0].moments == []
    assert (
        "cannot decode this model's video telemetry yet (dvtm_NEO2.proto)"
        in warn.text()
    )


def test_unprobeable_clip_is_omitted_and_progress_reported(tmp_path):
    _clip(tmp_path, "DJI_0001.MP4", series(10, with_dt=True))
    _clip(tmp_path, "DJI_0002.MP4", series(10, with_dt=True))
    calls, warn = [], Warnings()
    r = tl.build_timeline(
        tmp_path,
        warn=warn,
        progress=lambda i, n, item: calls.append((i, n, item)),
        probe=_probe(fail={"DJI_0002.MP4"}),
    )
    assert (len(r.clips), r.omitted) == (1, 1)
    assert calls == [(1, 2, "DJI_0001.MP4"), (2, 2, "DJI_0002.MP4")]
    assert (
        "DJI_0002.MP4",
        "left off the timeline: unsupported frame rate 27.500 fps",
    ) in warn


def test_every_clip_omitted_is_an_error(tmp_path):
    _clip(tmp_path, "DJI_0001.MP4")
    with pytest.raises(tl.TimelineError, match="No clip could be placed"):
        tl.build_timeline(tmp_path, probe=_probe(fail={"DJI_0001.MP4"}))


def test_no_clips_names_lrf_and_osv(tmp_path):
    (tmp_path / "DJI_0001.LRF").write_bytes(b"")
    (tmp_path / "PANO.OSV").write_bytes(b"")
    with pytest.raises(tl.TimelineError, match=r"\.LRF"):
        tl.build_timeline(tmp_path, probe=_probe())


def test_missing_exiftool_is_an_error(tmp_path, monkeypatch):
    _clip(tmp_path, "DJI_0001.MP4")
    monkeypatch.setattr(tl, "exiftool_available", lambda: False)
    with pytest.raises(tl.TimelineError, match="doctor --install exiftool"):
        tl.build_timeline(tmp_path, probe=_probe())


def test_order_by_creation_time_not_name(tmp_path):
    for name in ("DJI_0001.MP4", "DJI_0002.MP4", "DJI_0003.MP4"):
        _clip(tmp_path, name)
    created = {
        "DJI_0001.MP4": T0 + timedelta(seconds=60),
        "DJI_0002.MP4": T0,
        "DJI_0003.MP4": None,
    }
    r = tl.build_timeline(tmp_path, probe=_probe(created=created))
    assert [c.facts.path.name for c in r.clips] == [
        "DJI_0002.MP4",
        "DJI_0001.MP4",
        "DJI_0003.MP4",
    ]


def test_session_gap_warning(tmp_path):
    _clip(tmp_path, "DJI_0001.MP4")
    _clip(tmp_path, "DJI_0002.MP4")
    warn = Warnings()
    tl.build_timeline(
        tmp_path,
        warn=warn,
        probe=_probe(created={"DJI_0002.MP4": T0 + timedelta(hours=5)}),
    )
    assert any(
        item == "DJI_0002.MP4" and "more than one session" in m for item, m in warn
    )


def test_non_clip_files_are_ignored(tmp_path):  # Review Focus 1
    _clip(tmp_path, "DJI_0001.MP4", series(10, with_dt=True))
    for name in (
        "DJI_0001.JPG",
        "DJI_0001.LRF",
        "PANO.OSV",
        "DJI_0001.m4a",
        "Old.fcpxml",
    ):
        (tmp_path / name).write_bytes(b"")
    assert [
        c.facts.path.name for c in tl.build_timeline(tmp_path, probe=_probe()).clips
    ] == ["DJI_0001.MP4"]


def test_mixed_case_suffixes_are_found_and_paired(tmp_path):  # Review Focus 2
    _clip(tmp_path, "DJI_0001.Mp4", series(20, with_dt=True), srt_suffix=".srt")
    _clip(tmp_path, "DJI_0002.mov")
    r = tl.build_timeline(tmp_path, probe=_probe())
    by_name = {c.facts.path.name: c for c in r.clips}
    assert set(by_name) == {"DJI_0001.Mp4", "DJI_0002.mov"}
    assert by_name["DJI_0001.Mp4"].moments


def test_out_of_range_clock_places_the_clip_unmarked(tmp_path):
    _clip(tmp_path, "DJI_0001.MP4", series(90, factor=30, with_dt=True))
    warn = Warnings()
    r = tl.build_timeline(tmp_path, warn=warn, probe=_probe())
    assert r.clips[0].moments == [] and "outside the supported range" in warn.text()


def test_slow_motion_clips_are_counted(tmp_path):
    _clip(tmp_path, "DJI_0001.MP4", series(80, factor=8, with_dt=True))
    assert tl.build_timeline(tmp_path, probe=_probe()).slowmo_clips == 1


def _normalise(text, folder):
    text = text.replace(folder.resolve().as_uri(), "file:///SESSION")
    return re.sub(
        r"<!-- Generated by DJI Metadata Embedder v\S+",
        "<!-- Generated by DJI Metadata Embedder vX",
        text,
    )


def test_golden_session(tmp_path):
    """Snapshot of a whole session: synthetic reveal and rise clips plus the
    tracked real-format SRT fixtures (no coordinates reach the FCPXML).
    After a deliberate threshold change, regenerate with UPDATE_GOLDEN=1
    and review the diff before committing it."""
    _clip(
        tmp_path,
        "DJI_0001.MP4",
        series(
            20, with_dt=True, yaw=lambda t: 0.0, pitch=lambda t: _ramp(t, 5, 9, -80, -5)
        ),
    )
    _clip(
        tmp_path,
        "DJI_0002.MP4",
        series(
            30,
            with_dt=True,
            yaw=lambda t: 0.0,
            pitch=lambda t: -5.0,
            height=lambda t: 20.0 if t < 5 else 20.0 + min(30.0, 2.0 * (t - 5)),
        ),
    )
    for model in ("air3S", "neo2"):
        shutil.copy(SAMPLES / model / "clip.SRT", tmp_path / f"{model}_clip.SRT")
        (tmp_path / f"{model}_clip.MP4").write_bytes(b"")
    created = {
        "DJI_0001.MP4": T0,
        "DJI_0002.MP4": T0 + timedelta(seconds=30),
        "air3S_clip.MP4": T0 + timedelta(seconds=90),
        "neo2_clip.MP4": T0 + timedelta(seconds=120),
    }
    result = tl.build_timeline(tmp_path, probe=_probe(created=created))
    text = _normalise(build_fcpxml(result.clips, "session"), tmp_path)
    if os.environ.get("UPDATE_GOLDEN"):
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(text, encoding="utf-8", newline="\n")
    assert text == GOLDEN.read_text(encoding="utf-8")
