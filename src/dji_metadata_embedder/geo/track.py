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

from ..utilities import parse_telemetry_samples, redact_coords, resolve_utc_offset


@dataclass
class TrackPoint:
    """One GPS-fixed sample: WGS84 lat/lon, absolute altitude (m), raw cue time,
    and best-effort UTC datetime."""

    lat: float
    lon: float
    alt: float
    timestamp: str
    utc: datetime | None = None


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
    """Build a :class:`Track` from a DJI SRT file.

    ``redact`` mirrors the embed pipeline: ``"drop"`` yields an empty track,
    ``"fuzz"`` coarsens coordinates to ~100 m (3 decimals), ``"none"`` keeps
    them. Each point's ``utc`` is the block's absolute datetime minus the
    resolved local->UTC offset (``tz_offset`` if given, else auto-detected from
    the file mtime); when the format carries no absolute datetime, ``utc`` is
    synthesized as ``mtime + (cue - first_cue)`` so consumers that need a
    timestamp (e.g. CoT) always have a monotonic one. Pre-GPS-lock ``(0, 0)``
    frames are already excluded by :func:`parse_telemetry_samples`.
    """
    srt_path = Path(srt_file)
    samples = parse_telemetry_samples(srt_path)

    abs_times = [s.dt for s in samples if s.dt is not None]
    mtime_utc = datetime.fromtimestamp(
        srt_path.stat().st_mtime, tz=timezone.utc
    ).replace(tzinfo=None)
    offset = resolve_utc_offset(abs_times, tz_offset, mtime_utc)
    base_cue = _cue_seconds(samples[0].cue) if samples else 0.0

    coords = redact_coords([(s.lat, s.lon) for s in samples], redact)
    if redact == "drop":
        points: list[TrackPoint] = []
    else:
        # ``redact_coords`` returns coordinates 1:1 for "none"/"fuzz". Guard the
        # invariant so a future mode that filters points cannot silently
        # truncate the track at the zip below.
        if len(coords) != len(samples):
            raise ValueError(
                f"redact_coords returned {len(coords)} coords for {len(samples)} "
                f"points (mode={redact!r}); cannot preserve alt/timestamp alignment"
            )
        points = []
        for c, s in zip(coords, samples):
            if s.dt is not None and offset is not None:
                utc = s.dt - offset
            else:
                utc = mtime_utc + timedelta(seconds=_cue_seconds(s.cue) - base_cue)
            points.append(
                TrackPoint(lat=c[0], lon=c[1], alt=s.alt, timestamp=s.cue, utc=utc)
            )

    return Track(name=srt_path.stem, points=points)
