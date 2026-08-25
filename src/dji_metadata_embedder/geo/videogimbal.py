"""Gimbal attitude from the sibling video's timed metadata (#546).

Air 3S and later write no gimbal fields to the SRT, yet the MP4's ``djmd``
stream carries ``GimbalYaw``/``GimbalPitch`` on every frame. This module
fills the SRT samples' missing attitude from that stream so the 3D map's
camera footprints become measurements instead of the estimated 30-degree
down-tilt. It is opt-in (``flightmap --gimbal-from-video``): ExifTool must
walk every sample of the video, which costs roughly 15 seconds per gigabyte.

The join is on elapsed cue, not UTC: the SRT and the djmd stream are the
same recording, so both clocks start at zero, whereas their wall-clock
stamps disagree by a few hundred milliseconds on real Air 3S footage.
"""

from __future__ import annotations

import time
from bisect import bisect_left
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..mp4_telemetry import (
    _EXIFTOOL_INSTALL_HINT,
    Mp4TelemetryError,
    extract_samples,
)
from ..utilities import TelemetrySample
from ..utils.exiftool import exiftool_available
from .media import find_video_path
from .track import _cue_seconds

__all__ = [
    "VideoGimbalReport",
    "VideoGimbalUnavailable",
    "enrich_from_video",
    "merge_video_gimbal",
    "needs_gimbal",
]

# SRT and djmd samples are frame-aligned on every model seen so far; the
# slack only has to survive a djmd stream that is a few frames shorter than
# the SRT. Half a second never reaches the neighbouring second of a 1 Hz SRT.
_CUE_TOLERANCE_S = 0.5


class VideoGimbalUnavailable(Mp4TelemetryError):
    """ExifTool is missing, so no video can be read: stop, don't report per file."""


@dataclass
class VideoGimbalReport:
    """What :func:`enrich_from_video` did for one SRT, for the CLI to say."""

    name: str
    video: str | None = None
    matched: int = 0
    total: int = 0
    seconds: float = 0.0
    reason: str | None = None


def needs_gimbal(samples: list[TelemetrySample]) -> bool:
    """True when any sample lacks gimbal yaw or pitch."""
    return any(s.gimbal_yaw is None or s.gimbal_pitch is None for s in samples)


def merge_video_gimbal(
    samples: list[TelemetrySample], video_samples: list[TelemetrySample]
) -> int:
    """Fill missing gimbal yaw/pitch in *samples* from the nearest-cue video
    sample within :data:`_CUE_TOLERANCE_S`. SRT-borne values always win.

    Returns the number of samples that received at least one value.
    """
    stamped = sorted(
        (t, v) for v in video_samples if (t := _cue_seconds(v.cue)) is not None
    )
    if not stamped:
        return 0
    times = [t for t, _ in stamped]
    matched = 0
    for s in samples:
        if s.gimbal_yaw is not None and s.gimbal_pitch is not None:
            continue
        cue = _cue_seconds(s.cue)
        if cue is None:
            continue
        k = bisect_left(times, cue)
        best: tuple[float, TelemetrySample] | None = None
        for j in (k - 1, k):
            if 0 <= j < len(times):
                dt = abs(times[j] - cue)
                if best is None or dt < best[0]:
                    best = (dt, stamped[j][1])
        if best is None or best[0] > _CUE_TOLERANCE_S:
            continue
        v = best[1]
        gained = False
        if s.gimbal_yaw is None and v.gimbal_yaw is not None:
            s.gimbal_yaw = v.gimbal_yaw
            gained = True
        if s.gimbal_pitch is None and v.gimbal_pitch is not None:
            s.gimbal_pitch = v.gimbal_pitch
            gained = True
        matched += gained
    return matched


def enrich_from_video(
    srt_path: Path,
    samples: list[TelemetrySample],
    *,
    name: str | None = None,
    extract: Callable[[Path], list[TelemetrySample]] = extract_samples,
) -> VideoGimbalReport:
    """Fill *samples*' missing gimbal attitude from the video beside *srt_path*.

    Skips (with a reason) when every sample is already complete, when no
    sibling video exists, or when the video yields no usable telemetry
    (:class:`Mp4TelemetryError`: no djmd track, decoder too old, ...).
    Raises :class:`VideoGimbalUnavailable` when ExifTool itself is missing,
    since that affects every file and deserves one loud message.
    """
    srt_path = Path(srt_path)
    report = VideoGimbalReport(name=name or srt_path.stem, total=len(samples))
    if not needs_gimbal(samples):
        report.reason = "the SRT already carries gimbal attitude"
        return report
    video = find_video_path(srt_path.parent, srt_path.stem)
    if video is None:
        report.reason = "no video with the same name beside the SRT"
        return report
    report.video = video.name
    if not exiftool_available():
        raise VideoGimbalUnavailable(_EXIFTOOL_INSTALL_HINT)
    started = time.perf_counter()
    try:
        video_samples = extract(video)
    except Mp4TelemetryError as exc:
        report.reason = str(exc)
        report.seconds = time.perf_counter() - started
        return report
    report.matched = merge_video_gimbal(samples, video_samples)
    report.seconds = time.perf_counter() - started
    if report.matched == 0:
        report.reason = "the video's telemetry carries no gimbal attitude"
    return report
