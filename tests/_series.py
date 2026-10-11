"""Synthetic telemetry for timeline tests. Coordinates are synthetic (an
open-ocean origin). Motion is given as functions of REAL time t in seconds;
sample i sits at cue i/hz (playback) and t = cue / factor."""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

from dji_metadata_embedder.utilities import TelemetrySample

LAT0, LON0 = 10.0, 20.0
M_PER_DEG = math.radians(1.0) * 6_371_000.0
BASE = datetime(2026, 8, 15, 14, 19, 32)
Fn = Callable[[float], float]


def cue(sec: float) -> str:
    ms = round(sec * 1000)
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def wrap180(deg: float) -> float:
    return (deg + 180.0) % 360.0 - 180.0


def series(
    duration_s: float,
    hz: float = 30.0,
    *,
    east: Fn | None = None,
    north: Fn | None = None,
    height: Fn | None = None,
    yaw: Fn | None = None,
    pitch: Fn | None = None,
    factor: float = 1.0,
    quantum_deg: float | None = 1e-6,
    h_quantum: float | None = 0.1,
    rel_alt: bool = True,
    drop: Callable[[float], bool] | None = None,
    with_dt: bool = False,
) -> list[TelemetrySample]:
    """Samples over ``duration_s`` playback seconds. Positions are rounded to
    ``quantum_deg`` (six decimals, like DJI SRTs) and heights to
    ``h_quantum``; yaw is wrapped to [-180, 180) like DJI writes it."""
    east = east or (lambda t: 0.0)
    north = north or (lambda t: 0.0)
    height = height or (lambda t: 45.0)
    coslat = math.cos(math.radians(LAT0))
    out: list[TelemetrySample] = []
    for i in range(int(duration_s * hz) + 1):
        c = i / hz
        t = c / factor
        if drop is not None and drop(t):
            continue
        lat = LAT0 + north(t) / M_PER_DEG
        lon = LON0 + east(t) / (M_PER_DEG * coslat)
        if quantum_deg:
            lat = round(lat / quantum_deg) * quantum_deg
            lon = round(lon / quantum_deg) * quantum_deg
        h = height(t)
        if h_quantum:
            h = round(h / h_quantum) * h_quantum
        out.append(
            TelemetrySample(
                lat,
                lon,
                100.0 + h,
                cue(c),
                BASE + timedelta(seconds=t) if with_dt else None,
                rel_alt=h if rel_alt else None,
                gimbal_yaw=wrap180(yaw(t)) if yaw else None,
                gimbal_pitch=pitch(t) if pitch else None,
            )
        )
    return out


def write_srt(path: Path, samples: list[TelemetrySample]) -> Path:
    """Write samples as a DJI Format-3b SRT (parses with parse_telemetry_samples)."""
    blocks = []
    for i, s in enumerate(samples):
        end = samples[i + 1].cue if i + 1 < len(samples) else s.cue
        dt = s.dt or BASE
        gimbal = (
            f" [gb_yaw: {s.gimbal_yaw:.1f} gb_pitch: {s.gimbal_pitch:.1f} gb_roll: 0.0]"
            if s.gimbal_yaw is not None and s.gimbal_pitch is not None
            else ""
        )
        blocks.append(
            f"{i + 1}\n{s.cue} --> {end}\n"
            f'<font size="28">FrameCnt: {i + 1}, DiffTime: 33ms\n'
            f"{dt:%Y-%m-%d %H:%M:%S}.{dt.microsecond // 1000:03d}\n"
            f"[iso: 100] [shutter: 1/1000.0] [fnum: 1.7] [ev: 0] [ct: 5500] "
            f"[color_md: default] [focal_len: 24.00] [latitude: {s.lat:.6f}] "
            f"[longitude: {s.lon:.6f}] [rel_alt: {(s.rel_alt or 0.0):.3f} "
            f"abs_alt: {s.alt:.3f}]{gimbal} </font>\n"
        )
    path.write_text("\n".join(blocks), encoding="utf-8")
    return path
