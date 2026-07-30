"""Flight-record content model (#413): everything the HTML renders.

Assembles per-flight facts (times, distances, the three-label heights),
the flight-relevant regulatory measure, and the airspace evaluation into
plain data. Heights follow the #413 principle: every figure carries
quantity + source + the measure it approximates, and a missing datum is a
stated note, never a substituted number.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen

from .airspace import AirspaceReport, evaluate, fetch_zones
from .airspace.jurisdiction import resolve_jurisdiction
from .geometry import haversine_m
from .terrain import TerrainUnavailable, surface_elevations
from .track import Track

_MTIME_NOTE = (
    "Times were derived from file modification times, not from telemetry "
    "datetimes — verify them before relying on this record."
)


@dataclass
class FlightRecordData:
    name: str
    start_utc: datetime | None
    end_utc: datetime | None
    duration_s: float
    takeoff: tuple[float, float]
    distance_m: float
    max_home_m: float
    max_rel_alt_m: float | None
    max_surface_m: float | None
    surface_note: str | None
    max_amsl_m: float | None
    time_note: str | None
    measure_note: str | None
    airspace: AirspaceReport
    points: list[tuple[float, float]] = field(default_factory=list)


def _heights_above_surface(
    track: Track, cache_dir: Path, transport
) -> tuple[list[float] | None, str | None]:
    """Per-point est. height above surface, or (None, why-not)."""
    if any(p.rel_alt is None for p in track.points):
        return None, (
            "the telemetry carries no height-above-takeoff for every "
            "point, so no surface-referenced estimate can be built"
        )
    try:
        coords = [(p.lat, p.lon) for p in track.points]
        surface = surface_elevations(coords, cache_dir, transport=transport)
    except TerrainUnavailable as exc:
        return None, str(exc)
    takeoff_elev = surface[0]
    heights = [
        takeoff_elev + (p.rel_alt or 0.0) - s
        for p, s in zip(track.points, surface)
    ]
    return heights, None


def build_records(
    tracks: list[Track],
    *,
    cache_dir: Path,
    refresh: bool = False,
    transport=None,
    announce=lambda msg: None,
) -> list[FlightRecordData]:
    # Resolved at call time (not a default arg) so tests can monkeypatch
    # record.urlopen — a default binds at def time and dodges the patch.
    if transport is None:
        transport = urlopen
    records: list[FlightRecordData] = []
    for track in tracks:
        pts = track.points
        times = [p.utc for p in pts if p.utc is not None]
        start = min(times) if times else None
        end = max(times) if times else None
        duration = (end - start).total_seconds() if start and end else 0.0
        home = (pts[0].lat, pts[0].lon)
        distance = sum(
            haversine_m(a.lat, a.lon, b.lat, b.lon)
            for a, b in zip(pts, pts[1:])
        )
        max_home = max(
            (haversine_m(home[0], home[1], p.lat, p.lon) for p in pts),
            default=0.0,
        )
        rel_alts = [p.rel_alt for p in pts if p.rel_alt is not None]
        resolution = resolve_jurisdiction(track)

        # A gap jurisdiction still gets terrain estimates: the logbook half
        # never depends on the airspace half. fetch_zones never raises —
        # a missing jurisdiction comes back as data.gap_reason.
        data = fetch_zones(
            track, cache_dir, refresh=refresh,
            transport=transport, announce=announce,
        )
        heights, surface_note = _heights_above_surface(
            track, cache_dir, transport
        )
        if data.gap_reason is not None:
            report = AirspaceReport(gap_reason=data.gap_reason)
        else:
            report = evaluate(track, data.zones, surface_heights_m=heights)
            report.source = data.source
        alts = [p.alt for p in pts]
        max_amsl = max(alts) if alts else None
        records.append(
            FlightRecordData(
                name=track.name,
                start_utc=start,
                end_utc=end,
                duration_s=duration,
                takeoff=home,
                distance_m=distance,
                max_home_m=max_home,
                max_rel_alt_m=max(rel_alts) if rel_alts else None,
                max_surface_m=max(heights) if heights else None,
                surface_note=surface_note,
                max_amsl_m=max_amsl,
                time_note=_MTIME_NOTE if track.utc_source == "mtime" else None,
                measure_note=(
                    resolution.jurisdiction.measure_note
                    if resolution.jurisdiction
                    else None
                ),
                airspace=report,
                points=[(p.lat, p.lon) for p in pts],
            )
        )
    return records
