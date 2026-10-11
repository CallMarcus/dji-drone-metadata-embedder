"""Editor moments from a motion series. Pure: no I/O.

Kinds: steady stretches (aircraft and gimbal holding smooth), the gimbal
reveal family (reveal, tilt, pan) and altitude rises. No coordinates ever
reach a label or note. Thresholds are starting values calibrated on real
footage before release; docs/user_guide.md ("How moments are detected")
carries the final values.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .motion import MotionSeries

KINDS = frozenset({"steady", "reveal", "rise"})

STEADY_MAX_ACCEL = 0.5  # m/s², over 1 s baselines
STEADY_MAX_GIMBAL_RATE = 3.0  # °/s, yaw and pitch each
STEADY_MIN_S = 4.0  # real seconds, after trimming
STEADY_BRIDGE_S = 0.5  # real seconds of non-steady bridged inside a run
STEADY_TRIM_S = 0.5  # real seconds off each end
STEADY_LONGEST_ONLY = False  # calibration fallback: longest piece per class
HOVER_MAX_SPEED = 0.5  # m/s
HOVER_MAX_CLIMB = 0.3  # m/s
VERTICAL_MIN_CLIMB = 0.3  # m/s; vertical-dominant stretches are never steady
GLIDE_SPLIT_DEG = 30.0  # split a glide where travel heading drifts this far
MAX_QUANTUM_M = 0.5  # coarser position/height precision skips detection
SLOWMO_NOTE_MIN = 1.5


@dataclass(frozen=True)
class Moment:
    kind: str  # steady, reveal, tilt, pan, rise
    start_s: float  # playback seconds within the clip
    end_s: float
    label: str
    note: str


@dataclass
class MomentReport:
    moments: list[Moment] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    coverage: dict[str, float] = field(default_factory=dict)


def _note(
    series: MotionSeries,
    body: str,
    *,
    gimbal_caveat: bool = False,
    camera_unknown: bool = False,
) -> str:
    parts = [body]
    if gimbal_caveat:
        parts.append("gimbal not recorded, steadiness from aircraft motion only")
    if camera_unknown:
        parts.append("camera angle not recorded")
    if series.factor > SLOWMO_NOTE_MIN:
        parts.append(f"slow motion ≈×{series.factor:g}")
    return "; ".join(parts)


def _angle_diff(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def _steady_class(series: MotionSeries, i: int, gimbal: bool) -> str | None:
    if not series.valid[i]:
        return None
    a, v, c = series.accel[i], series.speed[i], series.climb[i]
    if a is None or v is None or c is None or a >= STEADY_MAX_ACCEL:
        return None
    if gimbal:
        yr, pr = series.yaw_rate[i], series.pitch_rate[i]
        if yr is None or pr is None:
            return None
        if abs(yr) >= STEADY_MAX_GIMBAL_RATE or abs(pr) >= STEADY_MAX_GIMBAL_RATE:
            return None
    if abs(c) >= VERTICAL_MIN_CLIMB and abs(c) >= v:
        return None  # vertical: a rise or nothing, never steady
    if v < HOVER_MAX_SPEED and abs(c) < HOVER_MAX_CLIMB:
        return "hover"
    return "glide"


def _bridge(labels: list[str | None], series: MotionSeries) -> None:
    n, i = len(labels), 0
    while i < n:
        if labels[i] is not None:
            i += 1
            continue
        j = i
        while j < n and labels[j] is None:
            j += 1
        if (
            i > 0
            and j < n
            and labels[i - 1] == labels[j]
            and all(series.valid[i:j])
            and series.real[j] - series.real[i - 1] < STEADY_BRIDGE_S
        ):
            for k in range(i, j):
                labels[k] = labels[i - 1]
        i = j


def _label_runs(labels: list[str | None]) -> list[tuple[str, int, int]]:
    runs: list[tuple[str, int, int]] = []
    i, n = 0, len(labels)
    while i < n:
        cls = labels[i]
        if cls is None:
            i += 1
            continue
        j = i
        while j + 1 < n and labels[j + 1] == cls:
            j += 1
        runs.append((cls, i, j))
        i = j + 1
    return runs


def _split_glides(
    runs: list[tuple[str, int, int]], series: MotionSeries
) -> list[tuple[str, int, int]]:
    out: list[tuple[str, int, int]] = []
    for cls, s, e in runs:
        if cls != "glide":
            out.append((cls, s, e))
            continue
        start, ref = s, None
        for i in range(s, e + 1):
            course = series.course[i]
            if course is None:
                continue
            if ref is None:
                ref = course
            elif _angle_diff(course, ref) > GLIDE_SPLIT_DEG:
                out.append((cls, start, i - 1))
                start, ref = i, course
        out.append((cls, start, e))
    return out


def _trim(series: MotionSeries, s: int, e: int, trim: float) -> tuple[int, int] | None:
    t0, t1 = series.real[s] + trim, series.real[e] - trim
    while s <= e and series.real[s] < t0:
        s += 1
    while e >= s and series.real[e] > t1:
        e -= 1
    return (s, e) if s < e else None


def _steady_moment(series: MotionSeries, cls: str, s: int, e: int) -> Moment:
    play = series.cue[e] - series.cue[s]
    real = series.real[e] - series.real[s]
    speeds = [v for v in series.speed[s : e + 1] if v is not None]
    mean_v = sum(speeds) / len(speeds) if speeds else 0.0
    if cls == "hover":
        label = f"Steady {play:.1f} s · hover"
        if series.height_is_relative:
            heights = series.height[s : e + 1]
            label += f" at {sum(heights) / len(heights):.0f} m"
    else:
        label = f"Steady {play:.1f} s · glide ≈{mean_v:.0f} m/s"
    note = _note(
        series,
        f"real {real:.1f} s, mean speed ≈{mean_v:.1f} m/s",
        gimbal_caveat=not series.gimbal_known,
    )
    return Moment("steady", series.cue[s], series.cue[e], label, note)


def _longest_per_class(moments: list[Moment]) -> list[Moment]:
    best: dict[str, Moment] = {}
    for m in moments:
        cls = "hover" if "· hover" in m.label else "glide"
        if cls not in best or m.end_s - m.start_s > best[cls].end_s - best[cls].start_s:
            best[cls] = m
    return sorted(best.values(), key=lambda m: m.start_s)


def _steady(series: MotionSeries) -> list[Moment]:
    gimbal = series.gimbal_known
    labels = [_steady_class(series, i, gimbal) for i in range(len(series.cue))]
    _bridge(labels, series)
    out: list[Moment] = []
    for cls, s, e in _split_glides(_label_runs(labels), series):
        trimmed = _trim(series, s, e, STEADY_TRIM_S)
        if trimmed is None:
            continue
        s, e = trimmed
        if series.real[e] - series.real[s] < STEADY_MIN_S:
            continue
        out.append(_steady_moment(series, cls, s, e))
    return _longest_per_class(out) if STEADY_LONGEST_ONLY else out


def detect_moments(series: MotionSeries, kinds: frozenset[str] = KINDS) -> MomentReport:
    """Detect the requested moment kinds in one clip's motion series."""
    report = MomentReport()
    if len(series.cue) < 2:
        report.notes.append("too little telemetry to detect moments")
        return report
    coarse_h = series.h_quantum > MAX_QUANTUM_M
    coarse_v = series.v_quantum > MAX_QUANTUM_M
    if "steady" in kinds:
        if coarse_h or coarse_v:
            worst = max(series.h_quantum, series.v_quantum)
            report.notes.append(
                f"position precision {worst:.1f} m is too coarse for steady stretches"
            )
        else:
            report.moments.extend(_steady(series))
    report.moments.sort(key=lambda m: (m.start_s, m.kind))
    span = series.cue[-1] - series.cue[0]
    for kind in sorted({m.kind for m in report.moments}):
        total = sum(m.end_s - m.start_s for m in report.moments if m.kind == kind)
        report.coverage[kind] = total / span if span > 0 else 0.0
    return report
