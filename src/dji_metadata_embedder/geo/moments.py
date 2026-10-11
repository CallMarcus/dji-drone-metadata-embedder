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
# Within this of takeoff height a steady stretch is labelled "at takeoff
# height": usually the drone on the ground before takeoff or after landing,
# and "hover at 0 m" overclaims (calibration, Air 3S, 2026-10-11).
TAKEOFF_HEIGHT_M = 1.0
VERTICAL_MIN_CLIMB = 0.3  # m/s; vertical-dominant stretches are never steady
GLIDE_SPLIT_DEG = 30.0  # split a glide where travel heading drifts this far
MAX_QUANTUM_M = 0.5  # coarser position/height precision skips detection
SLOWMO_NOTE_MIN = 1.5
TILT_MIN_DEG = 25.0
TILT_REVERSAL_DEG = 2.0
PAN_MIN_DEG = 45.0
PAN_REVERSAL_DEG = 3.0
SWEEP_MIN_RATE = 3.0  # °/s real, mean over the sweep
# A sweep shorter than this is a gimbal recentre snap (0.5 s, 160-180 °/s on
# real Air 3S footage), not a shot.
SWEEP_MIN_S = 1.0  # real seconds
REVEAL_START_MAX_PITCH = -40.0
REVEAL_END_MIN_PITCH = -15.0
ANGLE_FLAT_EPS = 1.0  # degrees; trims the still ends off a sweep
RISE_MIN_M = 10.0
RISE_MIN_RATE = 1.0  # m/s real, mean over the climb
RISE_REVERSAL_M = 1.0  # dips smaller than this don't end a climb
# A climb is evaluated per sustained climbing run: below this climb rate the
# aircraft is holding height (hover wobble, a pause after auto-takeoff),
# which must neither join nor dilute the climb.
RISE_CLIMBING_RATE = 0.5  # m/s
RISE_BRIDGE_S = 0.5  # real seconds of slower climb bridged inside a run
RISE_MIN_PITCH = -20.0  # camera level or unknown; looking down is no reveal
HEIGHT_FLAT_EPS = 0.2  # metres; trims the still ends off a climb


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
            mean_h = sum(heights) / len(heights)
            if abs(mean_h) < TAKEOFF_HEIGHT_M:
                label = f"Steady {play:.1f} s · at takeoff height"
            else:
                label += f" at {mean_h:.0f} m"
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


def _legs(values: list[float], tol: float) -> list[tuple[int, int]]:
    """Monotone legs of ``values`` between turning points, ignoring
    reversals smaller than ``tol``. Returns (start, end) index pairs."""
    legs: list[tuple[int, int]] = []
    if len(values) < 2:
        return legs
    start, ext, direction = 0, 0, 0
    for i in range(1, len(values)):
        v = values[i]
        if direction == 0:
            if v - values[start] > tol:
                direction, ext = 1, i
            elif values[start] - v > tol:
                direction, ext = -1, i
        elif direction == 1:
            if v > values[ext]:
                ext = i
            elif values[ext] - v > tol:
                legs.append((start, ext))
                start, ext, direction = ext, i, -1
        else:
            if v < values[ext]:
                ext = i
            elif v - values[ext] > tol:
                legs.append((start, ext))
                start, ext, direction = ext, i, 1
    if direction != 0:
        legs.append((start, ext))
    return legs


def _refine(values: list[float], s: int, e: int, eps: float) -> tuple[int, int]:
    """Trim the still stretches off both ends of a leg."""
    s0, e0 = s, e
    while s < e and abs(values[s + 1] - values[s0]) <= eps:
        s += 1
    while e > s and abs(values[e - 1] - values[e0]) <= eps:
        e -= 1
    return s, e


def _defined_runs(
    series: MotionSeries, values: list[float | None]
) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for i, v in enumerate(values):
        ok = series.valid[i] and v is not None
        if ok and start is None:
            start = i
        elif not ok and start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(values) - 1))
    return runs


def _trim_slow(
    rates: list[float | None], s: int, e: int, min_rate: float
) -> tuple[int, int] | None:
    """Trim a sweep's ends where the camera turns slower than ``min_rate``:
    a slow creep after a pan is stillness to an editor (calibration, Air 3S,
    2026-10-11), and must not hold the marker open."""

    def slow(i: int) -> bool:
        r = rates[i]
        return r is None or abs(r) < min_rate

    while s < e and slow(s):
        s += 1
    while e > s and slow(e):
        e -= 1
    return (s, e) if s < e else None


def _sweeps(
    series: MotionSeries,
    values: list[float | None],
    rates: list[float | None],
    tol: float,
    min_deg: float,
) -> list[tuple[int, int, float, float]]:
    """(start index, end index, start angle, end angle) of qualifying sweeps."""
    out: list[tuple[int, int, float, float]] = []
    for rs, re_ in _defined_runs(series, values):
        seg = [v for v in values[rs : re_ + 1] if v is not None]
        for a, b in _legs(seg, tol):
            # Magnitude between the turning points; the refined indices only
            # place the marker. A slow sweep moves less than ANGLE_FLAT_EPS
            # per grid step, so refining eats into the move itself.
            s, e = _refine(seg, a, b, ANGLE_FLAT_EPS)
            trimmed = _trim_slow(rates, rs + s, rs + e, SWEEP_MIN_RATE)
            if trimmed is None:
                continue
            ts, te = trimmed
            # Gate on the window the marker covers; the label keeps the
            # leg's full turn (a slow creep is part of the camera's turn).
            window = seg[te - rs] - seg[ts - rs]
            real = series.real[te] - series.real[ts]
            if (
                abs(window) < min_deg
                or real < SWEEP_MIN_S
                or abs(window) / real < SWEEP_MIN_RATE
            ):
                continue
            out.append((ts, te, seg[a], seg[b]))
    return out


def _tilts(series: MotionSeries) -> list[Moment]:
    out: list[Moment] = []
    for s, e, start, end in _sweeps(
        series, series.pitch, series.pitch_rate, TILT_REVERSAL_DEG, TILT_MIN_DEG
    ):
        delta = end - start
        real = series.real[e] - series.real[s]
        if (
            delta > 0
            and start <= REVEAL_START_MAX_PITCH
            and end >= REVEAL_END_MIN_PITCH
        ):
            kind, label = "reveal", f"Reveal · tilt up {delta:.0f}°"
        else:
            kind = "tilt"
            label = f"Tilt {'up' if delta > 0 else 'down'} {abs(delta):.0f}°"
        note = _note(series, f"real {real:.1f} s, {abs(delta) / real:.0f}°/s")
        out.append(Moment(kind, series.cue[s], series.cue[e], label, note))
    return out


def _pans(series: MotionSeries) -> list[Moment]:
    out: list[Moment] = []
    for s, e, start, end in _sweeps(
        series, series.yaw, series.yaw_rate, PAN_REVERSAL_DEG, PAN_MIN_DEG
    ):
        delta = end - start
        real = series.real[e] - series.real[s]
        side = "right" if delta > 0 else "left"
        note = _note(series, f"real {real:.1f} s, {abs(delta) / real:.0f}°/s")
        out.append(
            Moment(
                "pan",
                series.cue[s],
                series.cue[e],
                f"Pan {side} {abs(delta):.0f}°",
                note,
            )
        )
    return out


def _climbing_runs(series: MotionSeries, s: int, e: int) -> list[tuple[int, int]]:
    """Sub-runs of [s, e] climbing at RISE_CLIMBING_RATE or more, bridging
    slower stretches shorter than RISE_BRIDGE_S."""
    runs: list[tuple[int, int]] = []
    start: int | None = None
    last_fast: int | None = None
    for i in range(s, e + 1):
        c = series.climb[i]
        if c is not None and c >= RISE_CLIMBING_RATE:
            if start is None:
                start = i
            elif last_fast is not None and (
                series.real[i] - series.real[last_fast] >= RISE_BRIDGE_S
            ):
                runs.append((start, last_fast))
                start = i
            last_fast = i
    if start is not None and last_fast is not None:
        runs.append((start, last_fast))
    return [(a, b) for a, b in runs if b > a]


def _rises(series: MotionSeries) -> list[Moment]:
    out: list[Moment] = []
    for rs, re_ in series.runs():
        seg = series.height[rs : re_ + 1]
        for a, b in _legs(seg, RISE_REVERSAL_M):
            ra, rb = _refine(seg, a, b, HEIGHT_FLAT_EPS)
            for s, e in _climbing_runs(series, rs + ra, rs + rb):
                moment = _rise_moment(series, s, e)
                if moment is not None:
                    out.append(moment)
    return out


def _rise_moment(series: MotionSeries, s: int, e: int) -> Moment | None:
    """The rise over grid indices [s, e], or None if it doesn't qualify."""
    gain = series.height[e] - series.height[s]
    real = series.real[e] - series.real[s]
    if gain < RISE_MIN_M or real <= 0 or gain / real < RISE_MIN_RATE:
        return None
    pitches = [p for p in series.pitch[s : e + 1] if p is not None]
    if any(p < RISE_MIN_PITCH for p in pitches):
        return None
    note = _note(
        series,
        f"real {real:.1f} s, ≈{gain / real:.1f} m/s",
        camera_unknown=not pitches,
    )
    return Moment("rise", series.cue[s], series.cue[e], f"Rise {gain:.0f} m", note)


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
    if "reveal" in kinds:
        if series.gimbal_known:
            report.moments.extend(_tilts(series))
            report.moments.extend(_pans(series))
        else:
            report.notes.append("no gimbal data: reveals, tilts and pans skipped")
    if "rise" in kinds:
        if coarse_v:
            report.notes.append(
                f"height precision {series.v_quantum:.1f} m is too coarse for rises"
            )
        else:
            report.moments.extend(_rises(series))
    report.moments.sort(key=lambda m: (m.start_s, m.kind))
    span = series.cue[-1] - series.cue[0]
    for kind in sorted({m.kind for m in report.moments}):
        total = sum(m.end_s - m.start_s for m in report.moments if m.kind == kind)
        report.coverage[kind] = total / span if span > 0 else 0.0
    return report
