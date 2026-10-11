"""Motion series for moment detection: samples resampled onto a 10 Hz
playback grid, projected to metres, smoothed and differentiated over 1 s
real-time baselines.

Each step answers a measured failure (spec review, 2026-10-11): gimbal yaw
is unwrapped on the raw samples before resampling, because interpolating
across the ±180 seam invents a ~360° swing; interpolation never crosses a
source gap, because a GPS dropout would otherwise become a perfect straight
glide; derivatives use 1 s baselines, because adjacent differences turn one
0.11 m position quantum into 0.52 m/s² of "acceleration".
"""

from __future__ import annotations

import math
from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

from ..utilities import TelemetrySample
from .track import _cue_seconds

GRID_HZ = 10.0  # resampling rate on the playback (cue) clock
SMOOTH_REAL_S = 1.0  # centred moving-average window
BASELINE_REAL_S = 1.0  # central-difference baseline for derivatives
GAP_MIN_S = 0.5  # never interpolate across a source gap longer than
GAP_SPACING_FACTOR = 3.0  # max(GAP_MIN_S, this x the median sample spacing)
MOVING_MIN_SPEED = 0.5  # m/s; below this travel course is undefined
EARTH_R = 6_371_000.0
_NAN = float("nan")


@dataclass
class MotionSeries:
    factor: float
    cue: list[float]
    real: list[float]
    valid: list[bool]
    east: list[float]
    north: list[float]
    height: list[float]
    height_is_relative: bool
    yaw: list[float | None]
    pitch: list[float | None]
    speed: list[float | None]
    climb: list[float | None]
    accel: list[float | None]
    course: list[float | None]
    yaw_rate: list[float | None]
    pitch_rate: list[float | None]
    h_quantum: float
    v_quantum: float

    @property
    def gimbal_known(self) -> bool:
        return any(
            y is not None and p is not None for y, p in zip(self.yaw, self.pitch)
        )

    def runs(self) -> list[tuple[int, int]]:
        """Inclusive index ranges of consecutive valid grid points."""
        out: list[tuple[int, int]] = []
        start: int | None = None
        for i, ok in enumerate(self.valid):
            if ok and start is None:
                start = i
            elif not ok and start is not None:
                out.append((start, i - 1))
                start = None
        if start is not None:
            out.append((start, len(self.valid) - 1))
        return out


def unwrap_degrees(values: Sequence[float | None]) -> list[float | None]:
    """Remove ±360 jumps so consecutive known angles differ by <= 180."""
    out: list[float | None] = []
    prev: float | None = None
    offset = 0.0
    for v in values:
        if v is None:
            out.append(None)
            continue
        cur = v + offset
        if prev is not None:
            while cur - prev > 180.0:
                offset -= 360.0
                cur -= 360.0
            while cur - prev < -180.0:
                offset += 360.0
                cur += 360.0
        out.append(cur)
        prev = cur
    return out


def decimal_quantum(values: Sequence[float], max_decimals: int = 7) -> float:
    """The power-of-ten step the values are written to (1e-6 for six
    decimals), or 0.0 when fewer than two distinct values say nothing."""
    distinct = set(values)
    if len(distinct) < 2:
        return 0.0
    for k in range(max_decimals + 1):
        scale = 10.0**k
        # 1e-6, not looser: finer decimals leave residues of ~1e-5 at coarse
        # scales (10.000001 x 10), while true integers leave float noise ~1e-8.
        if all(abs(v * scale - round(v * scale)) < 1e-6 for v in distinct):
            return 10.0**-k
    return 10.0**-max_decimals


def _lerp(a: float | None, b: float | None, w: float) -> float | None:
    if a is None or b is None:
        return None
    return a + w * (b - a)


def _moving_average(values: list[float], half: int) -> list[float]:
    if half <= 0:
        return list(values)
    prefix = [0.0]
    for v in values:
        prefix.append(prefix[-1] + v)
    n = len(values)
    out = []
    for i in range(n):
        lo, hi = max(0, i - half), min(n, i + half + 1)
        out.append((prefix[hi] - prefix[lo]) / (hi - lo))
    return out


def _central(
    real: list[float], values: Sequence[float | None], k: int, s: int, e: int, i: int
) -> float | None:
    lo, hi = i - k, i + k
    if lo < s or hi > e:
        return None
    a, b = values[lo], values[hi]
    if a is None or b is None:
        return None
    dt = real[hi] - real[lo]
    return (b - a) / dt if dt > 0 else None


def _empty(factor: float) -> MotionSeries:
    return MotionSeries(
        factor, [], [], [], [], [], [], False, [], [], [], [], [], [], [], [], 0.0, 0.0
    )


def build_motion(
    samples: Sequence[TelemetrySample], factor: float = 1.0
) -> MotionSeries:
    """Resample, project, smooth and differentiate one clip's samples.

    ``factor`` is playback seconds per real second (see ``geo.slowmo``)."""
    timed = sorted(
        ((c, s) for s in samples if (c := _cue_seconds(s.cue)) is not None),
        key=lambda cs: cs[0],
    )
    pts: list[tuple[float, TelemetrySample]] = []
    for c, s in timed:
        if pts and c <= pts[-1][0]:
            continue  # duplicate cue (concatenated SRTs): keep the first
        pts.append((c, s))
    if len(pts) < 2:
        return _empty(factor)

    relative = all(s.rel_alt is not None for _, s in pts)
    lat0, lon0 = pts[0][1].lat, pts[0][1].lon
    coslat = math.cos(math.radians(lat0))
    t = [c for c, _ in pts]
    e_raw = [math.radians(s.lon - lon0) * EARTH_R * coslat for _, s in pts]
    n_raw = [math.radians(s.lat - lat0) * EARTH_R for _, s in pts]
    h_raw = [s.rel_alt if relative and s.rel_alt is not None else s.alt for _, s in pts]
    yaw_raw = unwrap_degrees([s.gimbal_yaw for _, s in pts])
    pitch_raw = [s.gimbal_pitch for _, s in pts]
    lat_q = decimal_quantum([s.lat for _, s in pts])
    lon_q = decimal_quantum([s.lon for _, s in pts])
    h_quantum = max(
        math.radians(lat_q) * EARTH_R, math.radians(lon_q) * EARTH_R * coslat
    )
    v_quantum = decimal_quantum(h_raw)

    spacing = sorted(b - a for a, b in pairwise(t))
    max_gap = max(GAP_MIN_S, GAP_SPACING_FACTOR * spacing[len(spacing) // 2])
    step = 1.0 / GRID_HZ
    count = int((t[-1] - t[0]) / step + 1e-9) + 1
    cue = [t[0] + i * step for i in range(count)]
    valid = [False] * count
    east = [_NAN] * count
    north = [_NAN] * count
    height = [_NAN] * count
    yaw: list[float | None] = [None] * count
    pitch: list[float | None] = [None] * count
    for i, g in enumerate(cue):
        a = min(max(bisect_right(t, g) - 1, 0), len(t) - 2)
        b = a + 1
        gap = t[b] - t[a]
        if gap <= 0 or gap > max_gap:
            continue
        w = (g - t[a]) / gap
        valid[i] = True
        east[i] = e_raw[a] + w * (e_raw[b] - e_raw[a])
        north[i] = n_raw[a] + w * (n_raw[b] - n_raw[a])
        height[i] = h_raw[a] + w * (h_raw[b] - h_raw[a])
        yaw[i] = _lerp(yaw_raw[a], yaw_raw[b], w)
        pitch[i] = _lerp(pitch_raw[a], pitch_raw[b], w)

    real = [c / factor for c in cue]
    none: list[float | None] = [None] * count
    series = MotionSeries(
        factor,
        cue,
        real,
        valid,
        east,
        north,
        height,
        relative,
        yaw,
        pitch,
        list(none),
        list(none),
        list(none),
        list(none),
        list(none),
        list(none),
        h_quantum,
        v_quantum,
    )
    half = round(SMOOTH_REAL_S * factor * GRID_HZ) // 2
    for lo, hi in series.runs():
        for arr in (series.east, series.north, series.height):
            arr[lo : hi + 1] = _moving_average(arr[lo : hi + 1], half)
    _derivatives(series)
    return series


def _derivatives(series: MotionSeries) -> None:
    n = len(series.cue)
    k = max(1, round(BASELINE_REAL_S / 2 * series.factor * GRID_HZ))
    real = series.real
    ve: list[float | None] = [None] * n
    vn: list[float | None] = [None] * n
    vh: list[float | None] = [None] * n
    runs = series.runs()
    for s, e in runs:
        for i in range(s, e + 1):
            ve[i] = _central(real, series.east, k, s, e, i)
            vn[i] = _central(real, series.north, k, s, e, i)
            vh[i] = _central(real, series.height, k, s, e, i)
            series.yaw_rate[i] = _central(real, series.yaw, k, s, e, i)
            series.pitch_rate[i] = _central(real, series.pitch, k, s, e, i)
    for s, e in runs:
        for i in range(s, e + 1):
            x, y, z = ve[i], vn[i], vh[i]
            if x is not None and y is not None and z is not None:
                speed = math.hypot(x, y)
                series.speed[i] = speed
                series.climb[i] = z
                if speed >= MOVING_MIN_SPEED:
                    series.course[i] = math.degrees(math.atan2(x, y)) % 360.0
            ax = _central(real, ve, k, s, e, i)
            ay = _central(real, vn, k, s, e, i)
            az = _central(real, vh, k, s, e, i)
            if ax is not None and ay is not None and az is not None:
                series.accel[i] = math.sqrt(ax * ax + ay * ay + az * az)
