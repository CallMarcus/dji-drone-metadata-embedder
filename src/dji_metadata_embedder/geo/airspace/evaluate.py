"""Track-vs-zones evaluation (#413). Pure: no I/O, no network.

Facts only: which zones the track entered, when, and the height maxima
during the dwell — one per datum, so the renderer can compare each limit
against the matching datum and never across datums.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..track import Track
from .model import SourceInfo, Zone


def point_in_ring(
    lon: float, lat: float, ring: list[tuple[float, float]]
) -> bool:
    """Ray-casting point-in-polygon on plain WGS84 coordinates."""
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (
            yj - yi
        ) + xi:
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
    max_rel_alt_m: float | None = None   # above takeoff, aircraft-reported
    max_surface_m: float | None = None   # est. above surface (DEM), if given
    max_amsl_m: float | None = None      # aircraft absolute altitude


@dataclass
class AirspaceReport:
    findings: list[ZoneFinding] = field(default_factory=list)
    not_applicable: list[Zone] = field(default_factory=list)
    source: SourceInfo | None = None
    gap_reason: str | None = None


def _window(track: Track) -> tuple[datetime, datetime] | None:
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
    window = _window(track)
    report = AirspaceReport()
    for zone in zones:
        if not _applies(zone, window):
            report.not_applicable.append(zone)
            continue
        finding = ZoneFinding(zone=zone, entered=False)
        for i, p in enumerate(track.points):
            if not any(point_in_ring(p.lon, p.lat, ring) for ring in zone.polygons):
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
