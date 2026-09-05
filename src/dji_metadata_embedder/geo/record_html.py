"""Print-ready flight-record HTML (#413). Self-contained, no JS, no
external assets — the record must open and print anywhere, forever."""

from __future__ import annotations

from datetime import datetime, timedelta
from html import escape
from pathlib import Path

from .airspace import M_PER_FT
from .provenance import stamp
from .airspace.evaluate import ZoneFinding
from .record import FlightRecordData

_STYLE = """
  * { box-sizing: border-box; }
  body { font: 14px/1.5 -apple-system, "Segoe UI", Roboto, sans-serif;
         color: #1a1a1a; margin: 2em auto; max-width: 900px; padding: 0 1em; }
  h1 { font-size: 1.6em; margin-bottom: 0.2em; }
  h2 { font-size: 1.2em; border-bottom: 1px solid #ccc; padding-bottom: 0.2em;
       margin-top: 2em; }
  h3 { font-size: 1em; margin-bottom: 0.3em; }
  table { border-collapse: collapse; width: 100%; margin: 0.5em 0 1em; }
  th, td { border: 1px solid #ccc; padding: 4px 8px; text-align: left;
           vertical-align: top; font-size: 0.95em; }
  th { background: #f2f2f2; }
  table.facts td:first-child, table.heights td:first-child { width: 30%; }
  small { color: #555; }
  .outline { display: block; margin: 0.5em 0; border: 1px solid #ddd;
             background: #fafafa; }
  dl { display: grid; grid-template-columns: max-content 1fr; gap: 0.2em 1em; }
  dt { font-weight: bold; }
  dd { margin: 0; }
  .footer { font-size: 0.85em; color: #555; margin-top: 0.5em; }
  .time-note { background: #fff3cd; padding: 0.5em 0.8em; border-left: 3px solid
               #cc9900; }
  .gap-note { background: #f4f4f4; padding: 0.5em 0.8em; border-left: 3px solid
              #888; }
  section.flight { margin-top: 3em; }
  @media print {
    body { margin: 0; max-width: none; }
    section.flight { page-break-after: always; }
  }
"""


def _esc(v: object) -> str:
    return escape(str(v), quote=True)


def _utc(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC") if dt else "unknown"


def _duration(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m} min {s} s"


def _both_units(metres: float, limit_unit: str) -> str:
    if limit_unit == "ft":
        return f"{metres:.0f} m ({metres / M_PER_FT:.0f} ft)"
    return f"{metres:.0f} m"


def _height_block(rec: FlightRecordData) -> str:
    rows = []
    if rec.max_rel_alt_m is not None:
        rows.append(
            "<tr><td>Max height above takeoff point</td>"
            f"<td>{rec.max_rel_alt_m:.0f} m</td>"
            "<td>aircraft-reported, exact — height above the takeoff "
            "point is not the measure the regulations use</td></tr>"
        )
    if rec.max_surface_m is not None:
        rows.append(
            "<tr><td>Estimated max height above surface</td>"
            f"<td>{rec.max_surface_m:.0f} m</td>"
            "<td>estimated from a digital surface model (includes "
            "vegetation and buildings) — approximates the "
            "surface-referenced measure the regulations use</td></tr>"
        )
    else:
        rows.append(
            "<tr><td>Estimated max height above surface</td>"
            "<td>unavailable</td>"
            f"<td>{_esc(rec.surface_note or 'no surface data')}</td></tr>"
        )
    if rec.max_amsl_m is not None:
        rows.append(
            "<tr><td>Max altitude (AMSL)</td>"
            f"<td>{rec.max_amsl_m:.0f} m</td>"
            "<td>aircraft-reported absolute altitude</td></tr>"
        )
    return "<table class='heights'>" + "".join(rows) + "</table>"


def _zone_row(f: ZoneFinding) -> str:
    z = f.zone
    # ED-269 publishes floors: 27 live FI zones state a lowerLimit with no
    # upper, and 28 live FI/LU zones are banded (e.g. 50–120 m AGL). The
    # ceiling alone would read as "0 up to X" — the opposite of the
    # published shape — so bands show both ends and a bare floor shows
    # "from X"; the FAA's universal 0-ft floor stays out of the way (#422).
    if z.upper is not None and z.lower is not None and z.lower.value > 0:
        if (z.lower.unit, z.lower.reference) == (z.upper.unit, z.upper.reference):
            if z.upper.unit == "FL":
                limit = f"FL {z.lower.value:g}–{z.upper.value:g}"
            else:
                limit = (
                    f"{z.lower.value:g}–{z.upper.value:g} "
                    f"{z.upper.unit} {z.upper.reference}"
                )
        else:
            limit = f"{z.lower.label()} – {z.upper.label()}"
    elif z.upper is not None:
        limit = z.upper.label()
    elif z.lower is not None:
        limit = f"from {z.lower.label()}"
    else:
        limit = "not stated"
    stated = z.upper if z.upper is not None else z.lower
    if not f.entered:
        status, compare = "outside", "—"
    else:
        status = f"entered {_utc(f.entry_utc)} – {_utc(f.exit_utc)}"
        if stated is None:
            compare = "no stated limit to compare against"
        elif stated.reference == "AGL":
            if f.max_surface_m is not None:
                compare = (
                    "est. max height above surface during dwell: "
                    + _both_units(f.max_surface_m, stated.unit)
                )
            else:
                compare = (
                    "limit stated in AGL; the surface-referenced "
                    "estimate is unavailable — not directly comparable "
                    "with the aircraft's takeoff-referenced height"
                )
        elif stated.reference == "AMSL":
            if f.max_amsl_m is not None:
                compare = (
                    "max altitude (AMSL) during dwell: "
                    + _both_units(f.max_amsl_m, stated.unit)
                )
            else:
                compare = "limit stated in AMSL; no absolute altitude recorded"
        elif stated.reference == "STD":
            compare = (
                "limit stated as a flight level (pressure datum); not "
                "comparable with telemetry altitudes"
            )
        else:
            compare = "limit datum not recognized"
    name_cell = f"{_esc(z.name)}<br><small>{_esc(z.identifier)}</small>"
    if z.activation:
        # #503: the feed's own activation status/schedule text, verbatim
        # and labelled — the record never evaluated it.
        name_cell += (
            "<br><small>activation (published, not evaluated): "
            f"{_esc('; '.join(z.activation))}</small>"
        )
    if z.notes:
        # #565: the publisher's free text (exceptions, contacts, reasons),
        # verbatim and labelled; the record never evaluated it.
        name_cell += (
            "<br><small>published, not evaluated: "
            f"{_esc('; '.join(z.notes))}</small>"
        )
    return (
        f"<tr><td>{name_cell}</td>"
        f"<td>{_esc(z.restriction)}</td><td>{_esc(limit)}</td>"
        f"<td>{_esc(status)}</td><td>{_esc(compare)}</td></tr>"
    )


def _svg(rec: FlightRecordData) -> str:
    import math

    pts = rec.points
    rings = [
        ring
        for f in rec.airspace.findings
        if f.entered
        for ring in f.zone.polygons + f.zone.holes
    ]
    all_lon = [p[1] for p in pts] + [c[0] for r in rings for c in r]
    all_lat = [p[0] for p in pts] + [c[1] for r in rings for c in r]
    if not all_lon:
        return ""
    w, h, pad = 420, 300, 12
    lon1, lon2 = min(all_lon), max(all_lon)
    lat1, lat2 = min(all_lat), max(all_lat)
    kx = math.cos(math.radians((lat1 + lat2) / 2))
    span = max((lon2 - lon1) * kx, lat2 - lat1, 1e-6)

    def xy(lat: float, lon: float) -> str:
        x = pad + ((lon - lon1) * kx / span) * (w - 2 * pad)
        y = pad + ((lat2 - lat) / span) * (h - 2 * pad)
        return f"{x:.1f},{y:.1f}"

    track = " ".join(xy(la, lo) for la, lo in pts)
    zone_polys = "".join(
        "<polygon points='" + " ".join(xy(la, lo) for lo, la in ring)
        + "' fill='none' stroke='#888' stroke-dasharray='4 3'/>"
        for ring in rings
    )
    return (
        f"<svg viewBox='0 0 {w} {h}' class='outline' role='img' "
        "aria-label='track outline'>"
        + zone_polys
        + f"<polyline points='{track}' fill='none' stroke='#1a56a0' "
        "stroke-width='2'/></svg>"
    )


def _offset_label(offset: timedelta) -> str:
    total = int(offset.total_seconds())
    sign = "+" if total >= 0 else "-"
    h, m = divmod(abs(total) // 60, 60)
    return f"{sign}{h:02d}:{m:02d}"


def _cover_time(dt: datetime | None, offset: timedelta | None) -> str:
    """Local + UTC when the track resolved an offset, UTC alone otherwise
    (a zero offset falls through — the same clock twice is noise). The UTC
    line self-dates so a midnight crossing stays visible in the cover.
    Generated digits only — safe to embed unescaped."""
    if dt is None:
        return "unknown"
    if offset is None or not offset:
        return dt.strftime("%H:%M:%S UTC")
    local = dt + offset
    return (
        f"{local:%H:%M:%S} {_offset_label(offset)}"
        f"<br><small>{dt:%Y-%m-%d %H:%M:%S} UTC</small>"
    )


def _cover_row(rec: FlightRecordData) -> str:
    # The logbook date is the pilot's local date when the offset is known
    # (a 23:30 UTC flight at +02:00 happened on the next local day). The
    # cell labels its datum: auto-detection can fail per file, so rows of
    # one table can mix local and UTC dates. When the offset was
    # auto-detected the local clock is exact regardless — it is the
    # telemetry's own wall clock; only the offset label and the UTC line
    # inherit the guess.
    if rec.start_utc is None:
        date = "unknown"
    elif rec.local_offset:
        local_date = (rec.start_utc + rec.local_offset).strftime("%Y-%m-%d")
        date = f"{local_date} <small>local</small>"
    else:
        date = f"{rec.start_utc:%Y-%m-%d} <small>UTC</small>"
    # Both spec'd height columns, each labelled with its datum in the
    # header; a missing estimate is stated, never substituted (#422).
    if rec.max_rel_alt_m is not None:
        takeoff_height = f"{rec.max_rel_alt_m:.0f} m"
    else:
        takeoff_height = "unavailable"
    if rec.max_surface_m is not None:
        surface_height = f"{rec.max_surface_m:.0f} m"
    else:
        surface_height = "unavailable"
    n_entered = sum(1 for f in rec.airspace.findings if f.entered)
    if rec.airspace.gap_reason:
        airspace_summary = rec.airspace.gap_reason
    elif n_entered:
        airspace_summary = (
            f"entered {n_entered} zone{'s' if n_entered != 1 else ''}"
        )
    else:
        airspace_summary = "no zones intersected"
    return (
        "<tr>"
        f"<td>{_esc(rec.name)}</td>"
        f"<td>{date}</td>"
        f"<td>{_cover_time(rec.start_utc, rec.local_offset)}</td>"
        f"<td>{_cover_time(rec.end_utc, rec.local_offset)}</td>"
        f"<td>{_esc(_duration(rec.duration_s))}</td>"
        f"<td>{rec.takeoff[0]:.5f}, {rec.takeoff[1]:.5f}</td>"
        f"<td>{_esc(takeoff_height)}</td>"
        f"<td>{_esc(surface_height)}</td>"
        f"<td>{_esc(airspace_summary)}</td>"
        "</tr>"
    )


def _footer(version: str) -> str:
    return (
        "<p class='footer'>Generated from aircraft telemetry by "
        f"dji-embed {_esc(version)} — factual record, not a determination "
        "of regulatory compliance.</p>"
    )


def _not_applicable_table(rec: FlightRecordData) -> str:
    if not rec.airspace.not_applicable:
        return ""
    rows = "".join(
        f"<tr><td>{_esc(z.name)}</td><td>{_esc(z.identifier)}</td>"
        "<td>not applicable during this flight window</td></tr>"
        for z in rec.airspace.not_applicable
    )
    return (
        "<h3>Zones not applicable</h3>"
        "<table class='not-applicable'>"
        "<tr><th>Zone</th><th>Identifier</th><th>Reason</th></tr>"
        + rows + "</table>"
    )


def _source_dl(source, terrain_source: str | None, version: str) -> str:
    items = []
    if source is not None:
        items += [
            ("Feed", source.feed),
            ("URL", source.url),
            ("Fetched", source.fetched),
        ]
        if source.effective:
            # The dataset's own edition date (#502) — "Fetched" is only
            # when this copy was downloaded.
            items.append(("Effective", source.effective))
        items += [
            ("License", source.license),
            ("Caveat", source.caveat),
        ]
        if source.note:
            items.append(("Note", source.note))
    if terrain_source is not None:
        items.append(("Terrain source", terrain_source))
    items.append((
        "Terrain data",
        "Surface-referenced heights are estimated from a digital surface "
        "model (includes vegetation and buildings), not surveyed AGL.",
    ))
    items.append(("Generated by", f"dji-embed {version}"))
    parts = "".join(
        f"<dt>{_esc(k)}</dt><dd>{_esc(v)}</dd>" for k, v in items
    )
    return f"<dl>{parts}</dl>"


def _flight_section(rec: FlightRecordData, version: str) -> str:
    facts = (
        "<table class='facts'>"
        f"<tr><td>Start</td><td>{_esc(_utc(rec.start_utc))}</td></tr>"
        f"<tr><td>End</td><td>{_esc(_utc(rec.end_utc))}</td></tr>"
        f"<tr><td>Duration</td><td>{_esc(_duration(rec.duration_s))}</td></tr>"
        f"<tr><td>Distance flown</td><td>{rec.distance_m:.0f} m</td></tr>"
        f"<tr><td>Max distance from home</td>"
        f"<td>{rec.max_home_m:.0f} m</td></tr>"
        "<tr><td>Takeoff point</td>"
        f"<td>{rec.takeoff[0]:.5f}, {rec.takeoff[1]:.5f}</td></tr>"
        "</table>"
    )

    time_note_html = ""
    if rec.time_note:
        time_note_html = (
            f"<p class='time-note'><strong>{_esc(rec.time_note)}</strong></p>"
        )

    measure_html = ""
    if rec.measure_note:
        measure_html = f"<p>{_esc(rec.measure_note)}</p>"

    gap_html = ""
    if rec.airspace.gap_reason:
        gap_html = (
            f"<p class='gap-note'>{_esc(rec.airspace.gap_reason)}</p>"
        )

    airspace_html = ""
    if rec.airspace.findings:
        entered = [f for f in rec.airspace.findings if f.entered]
        not_entered = len(rec.airspace.findings) - len(entered)
        rows = "".join(_zone_row(f) for f in entered)
        summary_html = ""
        if not_entered:
            is_plural = not_entered != 1
            summary_html = (
                f"<p>{not_entered} further zone{'s' if is_plural else ''} "
                f"in the evaluated area {'were' if is_plural else 'was'} "
                "not entered.</p>"
            )
        # "Entered" is a horizontal fact; with floor zones now surfaced, a
        # reader could take it vertically — say what it means (#422 review).
        entry_note = ""
        if entered:
            entry_note = (
                "<p><small>Entry is horizontal: the track's ground "
                "position was inside the zone's published outline. The "
                "vertical facts are stated separately; this record makes "
                "no determination about either.</small></p>"
            )
        airspace_html = (
            "<h3>Airspace zones</h3>"
            "<table class='airspace'>"
            "<tr><th>Zone</th><th>Restriction</th><th>Limit</th>"
            "<th>Status</th><th>Comparison</th></tr>"
            + rows + "</table>"
            + entry_note
            + summary_html
            + _not_applicable_table(rec)
        )
    elif not rec.airspace.gap_reason:
        airspace_html = _not_applicable_table(rec)

    source_html = ""
    if rec.airspace.source is not None or rec.terrain_source is not None:
        source_html = (
            "<h3>Data &amp; caveats</h3>"
            + _source_dl(rec.airspace.source, rec.terrain_source, version)
        )

    return (
        f"<section class='flight'><h2>{_esc(rec.name)}</h2>"
        + facts
        + time_note_html
        + _height_block(rec)
        + measure_html
        + airspace_html
        + gap_html
        + _svg(rec)
        + source_html
        + _footer(version)
        + "</section>"
    )


def record_to_html(
    records: list[FlightRecordData], title: str, version: str
) -> str:
    cover_rows = "".join(_cover_row(r) for r in records)
    cover = (
        "<table class='cover'><tr><th>Flight</th><th>Date</th>"
        "<th>Start</th><th>End</th><th>Duration</th><th>Takeoff</th>"
        "<th>Max height<br><small>above takeoff</small></th>"
        "<th>Max height<br><small>est. above surface</small></th>"
        "<th>Airspace</th></tr>"
        + cover_rows + "</table>"
    )
    sections = "".join(_flight_section(r, version) for r in records)
    return stamp(
        "<!DOCTYPE html>\n"
        "<html lang='en'><head><meta charset='utf-8'>"
        f"<title>{_esc(title)}</title>"
        f"<style>{_STYLE}</style></head><body>"
        f"<h1>{_esc(title)}</h1>"
        + cover
        + sections
        + "</body></html>"
    )


def write_flight_record(
    records: list[FlightRecordData], out: Path, title: str
) -> Path:
    from dji_metadata_embedder import __version__

    out.write_text(
        record_to_html(records, title, __version__), encoding="utf-8"
    )
    return out
