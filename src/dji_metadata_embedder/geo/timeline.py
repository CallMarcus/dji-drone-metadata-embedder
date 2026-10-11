"""Assemble a flight timeline from a folder of clips.

Scan, probe, load telemetry (SRT first, else the video's djmd stream), fill
gimbal from the video only when its schema carries it, measure slow motion,
detect moments and order clips by creation time. CLI concerns (output
naming, the overwrite guard, JSONL) live in cli.py; this module reports
through the ``progress`` and ``warn`` callbacks.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from itertools import pairwise
from pathlib import Path

from ..mp4_telemetry import _EXIFTOOL_INSTALL_HINT, Mp4TelemetryError, extract_samples
from ..utilities import TelemetrySample, parse_telemetry_samples
from ..utils.exiftool import (
    decode_floor,
    exiftool_available,
    exiftool_version,
    version_key,
)
from .clipprobe import ClipFacts, ClipProbeError, probe_clip
from .fcpxml import TimelineClip
from .moments import KINDS, detect_moments
from .motion import build_motion
from .slowmo import slowmo_factor
from .videogimbal import merge_video_gimbal, needs_gimbal, schema_carries_gimbal

CLIP_SUFFIXES = frozenset({".mp4", ".mov"})
SESSION_GAP = timedelta(hours=3)
MARKER_KINDS = ("steady", "reveal", "tilt", "pan", "rise")

Progress = Callable[[int, int, str], None]
Warn = Callable[[str, "str | None"], None]


class TimelineError(RuntimeError):
    """Nothing can be placed: no clips, no ExifTool, or every clip omitted."""


@dataclass
class TimelineResult:
    clips: list[TimelineClip]
    omitted: int
    gimbal: dict[str, int]
    slowmo_clips: int

    def marker_counts(self) -> dict[str, int]:
        counts = Counter(m.kind for c in self.clips for m in c.moments)
        return {kind: counts.get(kind, 0) for kind in MARKER_KINDS}


def _no_progress(current: int, total: int, item: str) -> None:
    return None


def _no_warn(message: str, item: str | None = None) -> None:
    return None


def scan_clips(folder: Path) -> list[Path]:
    """Top-level MP4/MOV files, any suffix case. Photos, .LRF proxies, .OSV
    files, audio and earlier timelines are not clips."""
    return sorted(
        (
            p
            for p in folder.iterdir()
            if p.is_file() and p.suffix.lower() in CLIP_SUFFIXES
        ),
        key=lambda p: p.name,
    )


def _srt_index(folder: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for p in sorted(folder.iterdir(), key=lambda p: p.name):
        if p.is_file() and p.suffix.lower() == ".srt":
            index.setdefault(p.stem, p)
    return index


def _decode_failure(schema: str | None, exc: Exception) -> str:
    """Name the model when ExifTool is new enough but still can't decode it
    (Neo 2 at 13.59: "Unknown protocol"), instead of advising an upgrade."""
    ver = exiftool_version()
    if schema and ver and version_key(ver) >= version_key(decode_floor(schema)):
        model = schema.split(";")[0]
        return (
            f"ExifTool {ver} cannot decode this model's video telemetry yet ({model})"
        )
    return str(exc)


def _level_defaults(samples: list[TelemetrySample]) -> None:
    """A gimbal-carrying djmd schema omits zero values: missing means level
    (pitch 0) and north (yaw 0), not unknown."""
    for s in samples:
        if s.gimbal_yaw is None:
            s.gimbal_yaw = 0.0
        if s.gimbal_pitch is None:
            s.gimbal_pitch = 0.0


def _fill_gimbal(
    path: Path,
    facts: ClipFacts,
    samples: list[TelemetrySample],
    source: str,
    video_gimbal: bool,
    warn: Warn,
) -> str:
    """Return the gimbal source: "srt", "video" or "none"."""
    carries = schema_carries_gimbal(facts.schema)
    if not needs_gimbal(samples):
        return "srt" if source == "srt" else "video"
    if source == "djmd":
        if carries:
            _level_defaults(samples)
            return "video"
        return "none"
    if not carries or not video_gimbal:
        return "none"
    try:
        video_samples = extract_samples(path)
    except Mp4TelemetryError as exc:
        warn(
            f"gimbal not read from the video: {_decode_failure(facts.schema, exc)}",
            path.name,
        )
        return "none"
    _level_defaults(video_samples)
    return "video" if merge_video_gimbal(samples, video_samples) else "none"


def _process(
    path: Path,
    facts: ClipFacts,
    srt: Path | None,
    kinds: frozenset[str],
    video_gimbal: bool,
    warn: Warn,
) -> tuple[TimelineClip, str, bool]:
    samples: list[TelemetrySample] = []
    source = "none"
    if srt is not None:
        samples, source = parse_telemetry_samples(srt), "srt"
    elif facts.schema is not None:
        try:
            samples, source = extract_samples(path), "djmd"
        except Mp4TelemetryError as exc:
            warn(
                f"{_decode_failure(facts.schema, exc)}; placed without markers",
                path.name,
            )
            return TimelineClip(facts), "none", False
    if not samples:
        warn("no GPS telemetry; placed without markers", path.name)
        return TimelineClip(facts), "none", False
    gimbal = (
        _fill_gimbal(path, facts, samples, source, video_gimbal, warn)
        if "reveal" in kinds
        else "none"
    )
    clock = slowmo_factor(samples, use_datetimes=source == "srt")
    if not clock.in_range:
        warn(
            f"playback runs {clock.factor:.2f}x real time, outside the supported "
            "range; placed without markers",
            path.name,
        )
        return TimelineClip(facts), gimbal, False
    if clock.source == "none":
        warn(
            "no usable recording clock: slow motion cannot be detected, speeds "
            "assume real time",
            path.name,
        )
    report = detect_moments(build_motion(samples, clock.factor), kinds)
    for note in report.notes:
        warn(note, path.name)
    return TimelineClip(facts, report.moments), gimbal, clock.is_slowmo


def _in_recording_order(clips: list[TimelineClip]) -> list[TimelineClip]:
    """By creation time (UTC), ties and undated clips by name; undated last."""
    dated = [c for c in clips if c.facts.created_utc is not None]
    undated = [c for c in clips if c.facts.created_utc is None]
    dated.sort(key=lambda c: (c.facts.created_utc, c.facts.path.name))
    undated.sort(key=lambda c: c.facts.path.name)
    return dated + undated


def _warn_session_gaps(clips: list[TimelineClip], warn: Warn) -> None:
    for prev, cur in pairwise(clips):
        a, b = prev.facts.created_utc, cur.facts.created_utc
        if a is None or b is None:
            continue
        gap = b - (a + timedelta(seconds=float(prev.facts.duration)))
        if gap > SESSION_GAP:
            warn(
                f"{gap.total_seconds() / 3600:.0f} h after the previous clip: this "
                "folder may hold more than one session",
                cur.facts.path.name,
            )


def build_timeline(
    folder: Path,
    *,
    kinds: frozenset[str] = KINDS,
    video_gimbal: bool = True,
    progress: Progress = _no_progress,
    warn: Warn = _no_warn,
    probe: Callable[[Path], ClipFacts] | None = None,
) -> TimelineResult:
    folder = Path(folder).resolve()
    clips = scan_clips(folder)
    if not clips:
        raise TimelineError(
            f"No MP4/MOV clips in {folder}. .LRF proxies and .OSV 360° files "
            "are not used for timelines."
        )
    if not exiftool_available():
        raise TimelineError(_EXIFTOOL_INSTALL_HINT)
    probe_fn = probe or probe_clip
    srts = _srt_index(folder)
    placed: list[TimelineClip] = []
    omitted = 0
    gimbal = {"srt": 0, "video": 0, "none": 0}
    slowmo = 0
    for i, path in enumerate(clips, start=1):
        progress(i, len(clips), path.name)
        try:
            facts = probe_fn(path)
        except ClipProbeError as exc:
            omitted += 1
            warn(f"left off the timeline: {exc}", path.name)
            continue
        if facts.tc_note:
            warn(facts.tc_note, path.name)
        clip, source, is_slow = _process(
            path, facts, srts.get(path.stem), kinds, video_gimbal, warn
        )
        placed.append(clip)
        gimbal[source] += 1
        slowmo += int(is_slow)
    if not placed:
        raise TimelineError(
            "No clip could be placed on the timeline; see the warnings above."
        )
    placed = _in_recording_order(placed)
    _warn_session_gaps(placed, warn)
    return TimelineResult(placed, omitted, gimbal, slowmo)
