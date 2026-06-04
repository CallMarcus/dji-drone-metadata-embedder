"""Canonical flight-track model built from parsed SRT telemetry.

A :class:`Track` is the single source of truth every exporter and viewer
consumes. Redaction is applied here, once, so no downstream renderer can leak
exact coordinates.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..utilities import parse_telemetry_points, redact_coords


@dataclass
class TrackPoint:
    """One GPS-fixed sample: WGS84 lat/lon, absolute altitude (m), raw cue time."""

    lat: float
    lon: float
    alt: float
    timestamp: str


@dataclass
class Track:
    """A named ordered sequence of :class:`TrackPoint`."""

    name: str
    points: list[TrackPoint]


def build_track(srt_file: Path | str, redact: str = "none") -> Track:
    """Build a :class:`Track` from a DJI SRT file.

    ``redact`` mirrors the embed pipeline: ``"drop"`` yields an empty track,
    ``"fuzz"`` coarsens coordinates to ~100 m (3 decimals), ``"none"`` keeps
    them. Pre-GPS-lock ``(0, 0)`` frames are already excluded by
    :func:`parse_telemetry_points`.
    """
    srt_path = Path(srt_file)
    raw = parse_telemetry_points(srt_path)

    coords = redact_coords([(lat, lon) for lat, lon, _, _ in raw], redact)
    if redact == "drop":
        points: list[TrackPoint] = []
    else:
        points = [
            TrackPoint(lat=c[0], lon=c[1], alt=alt, timestamp=ts)
            for c, (_, _, alt, ts) in zip(coords, raw)
        ]

    return Track(name=srt_path.stem, points=points)
