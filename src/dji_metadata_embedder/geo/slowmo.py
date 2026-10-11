"""Per-clip slow-motion factor: playback seconds per real second.

SRT cues and djmd ``SampleTime`` run on playback time, which is where an
editor sees a frame; physics (speeds, turn rates, minimum durations) has to
run on real time. Per-sample clocks are unusable for that on real footage
(Air 3S 8x clip, verified 2026-10-11): SRT datetimes stall in a ~33 Hz
staircase under 240 Hz blocks, and djmd ``GPSDateTime`` is ExifTool's
``CreateDate + SampleTime`` approximation, i.e. playback time again. Only
whole-clip spans are trustworthy, so the factor is one scalar per clip: from
djmd ``TimeStamp`` when every sample has it, otherwise from the SRT
datetime span.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ..utilities import TelemetrySample
from .track import _cue_seconds

# DJI slow-motion ratios (120 fps and 240 fps into 30 fps playback, etc.).
DJI_RATIOS = (1.0, 2.0, 4.0, 8.0)
SNAP_TOLERANCE = 0.05  # relative: a measured 7.8 snaps to 8
MIN_REAL_SPAN_S = 2.0  # below this the ratio is mostly measurement error
FACTOR_MIN = 0.05  # outside [FACTOR_MIN, FACTOR_MAX]: time-lapse, hyperlapse
FACTOR_MAX = 16.0  # or a broken clock; detection is skipped for the clip
SLOWMO_THRESHOLD = 1.5


@dataclass(frozen=True)
class ClockReport:
    factor: float  # playback seconds per real second; 1.0 when unknown
    source: str  # "timestamp", "datetime" or "none"
    in_range: bool  # False: skip moment detection for this clip

    @property
    def is_slowmo(self) -> bool:
        return self.factor > SLOWMO_THRESHOLD


def slowmo_factor(
    samples: Sequence[TelemetrySample], *, use_datetimes: bool
) -> ClockReport:
    """Measure the clip's playback/real time ratio.

    ``use_datetimes`` must be False for djmd-sourced samples: their ``dt`` is
    ExifTool's playback-time approximation and would always read 1.0.
    """
    timed = [(c, s) for s in samples if (c := _cue_seconds(s.cue)) is not None]
    if len(timed) < 2:
        return ClockReport(1.0, "none", True)
    cues = [c for c, _ in timed]
    cue_span = max(cues) - min(cues)
    real_span: float | None = None
    source = "none"
    reals = [s.real_s for _, s in timed if s.real_s is not None]
    if len(reals) == len(timed):
        real_span = max(reals) - min(reals)
        source = "timestamp"
    elif use_datetimes:
        dts = [s.dt for _, s in timed if s.dt is not None]
        if len(dts) == len(timed):
            real_span = (max(dts) - min(dts)).total_seconds()
            source = "datetime"
    if real_span is None or real_span < MIN_REAL_SPAN_S or cue_span <= 0:
        return ClockReport(1.0, "none", True)
    factor = cue_span / real_span
    for ratio in DJI_RATIOS:
        if abs(factor - ratio) <= SNAP_TOLERANCE * ratio:
            factor = ratio
            break
    return ClockReport(factor, source, FACTOR_MIN <= factor <= FACTOR_MAX)
