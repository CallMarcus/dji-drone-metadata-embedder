"""Canonical flight-track model built from parsed SRT telemetry.

A :class:`Track` is the single source of truth every exporter and viewer
consumes. Redaction is applied here, once, so no downstream renderer can leak
exact coordinates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..utilities import TelemetrySample, load_samples, redact_coords, resolve_utc_offset
from ..mp4_telemetry import is_video


@dataclass
class TrackPoint:
    """One GPS-fixed sample: WGS84 lat/lon, absolute altitude (m), raw cue time,
    best-effort UTC datetime, and optional footprint inputs (AGL via rel_alt,
    35mm-equivalent focal length, gimbal yaw/pitch) when the format carries them."""

    lat: float
    lon: float
    alt: float
    timestamp: str
    utc: datetime | None = None
    rel_alt: float | None = None
    focal_len: float | None = None
    gimbal_yaw: float | None = None
    gimbal_pitch: float | None = None


@dataclass
class Track:
    """A named ordered sequence of :class:`TrackPoint`."""

    name: str
    points: list[TrackPoint]


def _cue_seconds(cue: str) -> float:
    """Convert an SRT cue ``HH:MM:SS,mmm`` into total seconds (0.0 if unparseable)."""
    m = re.match(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", cue)
    if not m:
        return 0.0
    h, mnt, s, ms = (int(g) for g in m.groups())
    return h * 3600 + mnt * 60 + s + ms / 1000.0


def build_track(
    srt_file: Path | str,
    redact: str = "none",
    tz_offset: timedelta | None = None,
) -> Track:
    """Build a :class:`Track` from a DJI ``.SRT`` or a video (MP4/MOV).

    SRT ``dt`` is local wall-clock, so its UTC is resolved from ``tz_offset`` or
    the file mtime (unchanged behaviour). A video's ``dt`` is already absolute
    UTC (ExifTool ``GPSDateTime``), so it is used directly with a zero offset.
    ``redact`` mirrors the embed pipeline: ``"drop"`` empties the track,
    ``"fuzz"`` coarsens to ~100 m, ``"none"`` keeps coordinates.
    """
    path = Path(srt_file)
    samples = load_samples(path)
    if is_video(path):
        return build_track_from_samples(path.stem, samples, redact, assume_utc=True)
    mtime_utc = datetime.fromtimestamp(
        path.stat().st_mtime, tz=timezone.utc
    ).replace(tzinfo=None)
    return build_track_from_samples(
        path.stem, samples, redact, tz_offset=tz_offset, mtime_utc=mtime_utc
    )


def build_track_from_samples(
    name: str,
    samples: list[TelemetrySample],
    redact: str = "none",
    *,
    assume_utc: bool = False,
    tz_offset: timedelta | None = None,
    mtime_utc: datetime | None = None,
) -> Track:
    """Assemble a :class:`Track` from samples, resolving each point's UTC.

    ``assume_utc`` (video): each ``sample.dt`` is already UTC -> zero offset.
    Otherwise (SRT): resolve the local->UTC offset from ``tz_offset``/``mtime_utc``
    and synthesise a monotonic UTC from the cue when a sample has no datetime.
    """
    if assume_utc:
        offset: timedelta | None = timedelta(0)
    else:
        abs_times = [s.dt for s in samples if s.dt is not None]
        _mtime = mtime_utc if mtime_utc is not None else datetime.min
        offset = resolve_utc_offset(abs_times, tz_offset, _mtime)
    base_cue = _cue_seconds(samples[0].cue) if samples else 0.0

    coords = redact_coords([(s.lat, s.lon) for s in samples], redact)
    if redact == "drop":
        return Track(name=name, points=[])
    if len(coords) != len(samples):
        raise ValueError(
            f"redact_coords returned {len(coords)} coords for {len(samples)} "
            f"points (mode={redact!r}); cannot preserve alt/timestamp alignment"
        )
    points: list[TrackPoint] = []
    for c, s in zip(coords, samples):
        if s.dt is not None and offset is not None:
            utc = s.dt - offset
        elif mtime_utc is not None:
            utc = mtime_utc + timedelta(seconds=_cue_seconds(s.cue) - base_cue)
        else:
            utc = None
        points.append(
            TrackPoint(
                lat=c[0],
                lon=c[1],
                alt=s.alt,
                timestamp=s.cue,
                utc=utc,
                rel_alt=s.rel_alt,
                focal_len=s.focal_len,
                gimbal_yaw=s.gimbal_yaw,
                gimbal_pitch=s.gimbal_pitch,
            )
        )
    return Track(name=name, points=points)
