"""Overlay content for the --airspace flightmap layer (#413 PR 2).

Pure: no I/O, no network. Dedupes each track's fetched zones, runs the
shipped evaluator, and emits one JSON-able dict the 2D map embeds.
Restriction classes and limits are published data for the popups — never
verdicts. All fetched zones are included (the map shows the area's
published picture); time-window relevance lives in each zone's
``applicability`` text, and entered-facts only ever come from the
evaluator's findings.
"""

from __future__ import annotations

from datetime import datetime

from ..track import Track
from .evaluate import evaluate
from .fetch import AirspaceData
from .model import Applicability, VerticalLimit

_MTIME_NOTE = (
    "times derived from file modification times, not telemetry datetimes"
)
_PARTIAL_NOTE = "point timestamps are incomplete"


def _fmt_utc(dt: datetime | None) -> str | None:
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC") if dt else None


def _fmt_limit(limit: VerticalLimit | None) -> str | None:
    return limit.label() if limit is not None else None


def _fmt_window(win: Applicability) -> str:
    if win.start and win.end:
        return f"{_fmt_utc(win.start)} – {_fmt_utc(win.end)}"
    if win.start:
        return f"from {_fmt_utc(win.start)}"
    if win.end:
        return f"until {_fmt_utc(win.end)}"
    return "open-ended"


def _time_note(track: Track) -> str | None:
    times = [p.utc for p in track.points if p.utc is not None]
    if len(times) != len(track.points) or not times:
        return _PARTIAL_NOTE
    return _MTIME_NOTE if track.utc_source == "mtime" else None


def zones_to_overlay_json(
    tracks: list[Track], airspace_per_track: list[AirspaceData]
) -> dict:
    """One embeddable dict: deduped zones + entered-facts + corner notes."""
    zone_dicts: dict[tuple[str, str], dict] = {}
    notes: list[str] = []
    covered = False
    for track, data in zip(tracks, airspace_per_track):
        if data.gap_reason is not None:
            line = f"Airspace, {track.name}: {data.gap_reason}"
            if line not in notes:
                notes.append(line)
            continue
        covered = True
        if data.source is not None:
            line = f"Airspace: {data.source.feed}, fetched {data.source.fetched}"
            if line not in notes:
                notes.append(line)
        report = evaluate(track, data.zones)
        for zone in data.zones:
            key = (zone.source.feed, zone.identifier)
            if key not in zone_dicts:
                zone_dicts[key] = {
                    "id": zone.identifier,
                    "name": zone.name,
                    "restriction": zone.restriction,
                    "lower": _fmt_limit(zone.lower),
                    "upper": _fmt_limit(zone.upper),
                    "applicability": [
                        _fmt_window(w) for w in zone.applicability
                    ],
                    "polygons": zone.polygons,
                    "holes": zone.holes,
                    "source": {
                        "feed": zone.source.feed,
                        "license": zone.source.license,
                        "fetched": zone.source.fetched,
                    },
                    "entered": [],
                }
        note = _time_note(track)
        for finding in report.findings:
            if not finding.entered:
                continue
            key = (finding.zone.source.feed, finding.zone.identifier)
            zone_dicts[key]["entered"].append({
                "flight": track.name,
                "entry_utc": _fmt_utc(finding.entry_utc),
                "exit_utc": _fmt_utc(finding.exit_utc),
                "max_rel_alt_m": finding.max_rel_alt_m,
                "max_amsl_m": finding.max_amsl_m,
                "time_note": note,
            })
    return {
        "zones": list(zone_dicts.values()),
        "notes": notes,
        "covered": covered,
    }
