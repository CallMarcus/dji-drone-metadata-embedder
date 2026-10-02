"""Track-vs-zones evaluation (#413). Pure: no I/O, no network.

Facts only: which zones the track entered, when, and the height maxima
during the dwell — one per datum, so the renderer can compare each limit
against the matching datum and never across datums.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime

from ..track import Track, TrackPoint
from .model import SourceInfo, Zone


def point_in_ring(lon: float, lat: float, ring: list[tuple[float, float]]) -> bool:
    """Ray-casting point-in-polygon on plain WGS84 coordinates."""
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


@dataclass
class ZoneFinding:
    """One zone's result against the track.

    ``entry_utc``/``exit_utc`` span first entry to last exit across the
    *whole* track; a zone left and re-entered reports one spanning window,
    not per-visit windows."""

    zone: Zone
    entered: bool
    entry_utc: datetime | None = None
    exit_utc: datetime | None = None
    max_rel_alt_m: float | None = None  # above takeoff, aircraft-reported
    max_surface_m: float | None = None  # est. above surface (DEM), if given
    max_amsl_m: float | None = None  # aircraft absolute altitude


@dataclass
class AirspaceReport:
    findings: list[ZoneFinding] = field(default_factory=list)
    not_applicable: list[Zone] = field(default_factory=list)
    source: SourceInfo | None = None
    gap_reason: str | None = None


def track_window(track: Track) -> tuple[datetime, datetime] | None:
    """The flight's UTC span, or None unless every point is timed —
    the rule the fetch layer shares when a feed is asked for a window."""
    times = [p.utc for p in track.points if p.utc is not None]
    if len(times) != len(track.points) or not times:
        return None  # uncertain time -> treat every zone as applicable
    return min(times), max(times)


def _applies(zone: Zone, window: tuple[datetime, datetime] | None) -> bool:
    if not zone.applicability or window is None:
        return True
    start_f, end_f = window
    for win in zone.applicability:
        if (win.start is None or win.start <= end_f) and (
            win.end is None or win.end >= start_f
        ):
            return True
    return False


Ring = list[tuple[float, float]]
BBox = tuple[float, float, float, float]  # min lon, min lat, max lon, max lat


def _bbox(ring: Ring) -> BBox:
    if not ring:  # an empty ring contains nothing; this box matches nothing
        return (math.inf, math.inf, -math.inf, -math.inf)
    lons = [c[0] for c in ring]
    lats = [c[1] for c in ring]
    return min(lons), min(lats), max(lons), max(lats)


def _in_ring(lon: float, lat: float, ring: Ring, box: BBox) -> bool:
    # The box test is exact, not a heuristic: a point outside a ring's
    # bounding box cannot be inside the ring, so skipping the ray cast
    # never changes an answer. It keeps a 2,463-part dipul zone cheap for
    # every track point that is nowhere near most of its parts (#593).
    if not (box[0] <= lon <= box[2] and box[1] <= lat <= box[3]):
        return False
    return point_in_ring(lon, lat, ring)


@dataclass
class _Prepared:
    """One zone's rings paired with their bounding boxes, built once per
    ``evaluate`` call. ``parts`` is (exterior, its holes) per polygon when
    the zone groups holes per part, else every polygon with every hole."""

    parts: list[tuple[Ring, BBox, list[tuple[Ring, BBox]]]]
    per_part: bool
    zone_holes: list[tuple[Ring, BBox]]


def _prepare(zone: Zone) -> _Prepared:
    if zone.part_holes is not None:
        return _Prepared(
            parts=[
                (ring, _bbox(ring), [(h, _bbox(h)) for h in holes])
                for ring, holes in zip(zone.polygons, zone.part_holes, strict=True)
            ],
            per_part=True,
            zone_holes=[],
        )
    return _Prepared(
        parts=[(ring, _bbox(ring), []) for ring in zone.polygons],
        per_part=False,
        zone_holes=[(h, _bbox(h)) for h in zone.holes],
    )


def _inside(p: TrackPoint, zone: Zone, prepared: _Prepared | None = None) -> bool:
    """Inside an exterior ring and outside the interior rings (holes) that
    belong to it (#422). With ``zone.part_holes`` a part's holes cut only
    that part (#593): a point counts if, for some part, it is inside the
    exterior and in none of that part's holes, so an island part lying in
    another part's hole is still entered. Without it, the zone-level
    convention: inside any exterior, minus every hole. Plain even-odd
    parity over one flat list was rejected in review: it under-reports for
    overlapping same-limit volumes — and an under-reporting record misleads
    in the one direction it must not."""
    prep = prepared if prepared is not None else _prepare(zone)
    lon, lat = p.lon, p.lat
    if prep.per_part:
        return any(
            _in_ring(lon, lat, ring, box)
            and not any(_in_ring(lon, lat, h, hb) for h, hb in holes)
            for ring, box, holes in prep.parts
        )
    if not any(_in_ring(lon, lat, ring, box) for ring, box, _ in prep.parts):
        return False
    return not any(_in_ring(lon, lat, h, hb) for h, hb in prep.zone_holes)


def evaluate(
    track: Track,
    zones: list[Zone],
    *,
    surface_heights_m: list[float] | None = None,
) -> AirspaceReport:
    """Evaluate *track* against *zones*; heights are reported per datum."""
    if surface_heights_m is not None and len(surface_heights_m) != len(track.points):
        raise ValueError(
            f"surface_heights_m has {len(surface_heights_m)} entries but "
            f"track has {len(track.points)} points"
        )
    window = track_window(track)
    report = AirspaceReport()
    for zone in zones:
        prep = _prepare(zone)
        if zone.not_active_reason or not _applies(zone, window):
            # "Not applicable" is a statement about this flight: only a zone
            # the track was actually inside is listed (#562 — a country-wide
            # activity-flagged feed would otherwise list hundreds of zones
            # the flight never went near).
            if any(_inside(p, zone, prep) for p in track.points):
                report.not_applicable.append(zone)
            continue
        finding = ZoneFinding(zone=zone, entered=False)
        for i, p in enumerate(track.points):
            if not _inside(p, zone, prep):
                continue
            finding.entered = True
            if p.utc is not None:
                if finding.entry_utc is None:
                    finding.entry_utc = p.utc
                finding.exit_utc = p.utc
            if p.rel_alt is not None:
                finding.max_rel_alt_m = (
                    p.rel_alt
                    if finding.max_rel_alt_m is None
                    else max(finding.max_rel_alt_m, p.rel_alt)
                )
            if surface_heights_m is not None:
                finding.max_surface_m = (
                    surface_heights_m[i]
                    if finding.max_surface_m is None
                    else max(finding.max_surface_m, surface_heights_m[i])
                )
            finding.max_amsl_m = (
                p.alt if finding.max_amsl_m is None else max(finding.max_amsl_m, p.alt)
            )
        report.findings.append(finding)
    return report
