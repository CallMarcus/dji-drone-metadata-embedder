"""Render a :class:`Track` as Cursor-on-Target (CoT) XML for ATAK/TAK.

Emits one well-formed XML document with an ``<events>`` root holding timed PLI
position events (the primary, schema-clean representation) plus a best-effort
``b-m-r`` route polyline. Course/speed are derived from consecutive sampled
points. See docs/fmv-interop.md for ingestion notes and caveats.

Security note: this module only *writes* XML using stdlib ``xml.etree.ElementTree``
(ET.Element / ET.SubElement / ET.tostring). It never parses untrusted external XML,
so the XXE / billion-laughs parser-side vulnerabilities that ``defusedxml`` guards
against are not applicable here.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

from .geometry import (
    downsample_by_time,
    haversine_m,
    initial_bearing_deg,
    point_utc,
)
from .track import Track, TrackPoint, build_track

logger = logging.getLogger(__name__)

# CoT sentinel for unknown circular/linear error (90% containment, metres).
_CE_LE_UNKNOWN = "9999999.0"
_COT_TIME_FMT = "%Y-%m-%dT%H:%M:%SZ"


def _add_point(ev: ET.Element, p: TrackPoint) -> None:
    ET.SubElement(
        ev,
        "point",
        {
            "lat": f"{p.lat}",
            "lon": f"{p.lon}",
            "hae": f"{p.alt}",
            "ce": _CE_LE_UNKNOWN,
            "le": _CE_LE_UNKNOWN,
        },
    )


def _append_pli_event(
    root: ET.Element,
    name: str,
    index: int,
    p: TrackPoint,
    nxt: TrackPoint | None,
    cot_type: str,
    stale_seconds: float,
) -> None:
    p_utc = point_utc(p)
    t = p_utc.strftime(_COT_TIME_FMT)
    stale = (p_utc + timedelta(seconds=stale_seconds)).strftime(_COT_TIME_FMT)
    ev = ET.SubElement(
        root,
        "event",
        {
            "version": "2.0",
            "uid": f"DJI-{name}-{index}",
            "type": cot_type,
            "how": "m-g",
            "time": t,
            "start": t,
            "stale": stale,
        },
    )
    _add_point(ev, p)
    detail = ET.SubElement(ev, "detail")
    ET.SubElement(detail, "contact", {"callsign": name})
    ET.SubElement(detail, "precisionlocation", {"altsrc": "GPS"})
    if nxt is not None:
        dt = (point_utc(nxt) - p_utc).total_seconds()
        if dt > 0:
            dist = haversine_m(p.lat, p.lon, nxt.lat, nxt.lon)
            ET.SubElement(
                detail,
                "track",
                {
                    "course": f"{initial_bearing_deg(p.lat, p.lon, nxt.lat, nxt.lon):.1f}",
                    "speed": f"{dist / dt:.2f}",
                },
            )
    ET.SubElement(detail, "remarks").text = f"frame {index}, abs_alt {p.alt} m"


def _append_route_event(root: ET.Element, name: str, sampled: list[TrackPoint]) -> None:
    first, last = sampled[0], sampled[-1]
    t = point_utc(first).strftime(_COT_TIME_FMT)
    stale = (point_utc(last) + timedelta(hours=1)).strftime(_COT_TIME_FMT)
    ev = ET.SubElement(
        root,
        "event",
        {
            "version": "2.0",
            "uid": f"DJI-{name}-route",
            "type": "b-m-r",
            "how": "m-g",
            "time": t,
            "start": t,
            "stale": stale,
        },
    )
    _add_point(ev, first)
    detail = ET.SubElement(ev, "detail")
    for j, p in enumerate(sampled):
        ET.SubElement(
            detail,
            "link",
            {
                "uid": f"DJI-{name}-route-{j}",
                "type": "b-m-p",
                "point": f"{p.lat},{p.lon},{p.alt}",
            },
        )
    ET.SubElement(detail, "contact", {"callsign": f"{name} route"})
    ET.SubElement(detail, "remarks").text = f"DJI flight path, {len(sampled)} points"


def track_to_cot(
    track: Track,
    *,
    cot_type: str = "a-n-A",
    interval: float = 1.0,
    stale_seconds: float = 300.0,
) -> str:
    """Return a CoT XML document string for *track*.

    ``interval`` downsamples the per-frame telemetry (seconds between sampled
    points). ``cot_type`` is the CoT type/affiliation code for the PLI events
    (default neutral air). Requires each kept point to carry ``utc`` (always set
    by :func:`build_track`).
    """
    sampled = downsample_by_time(track.points, interval)
    root = ET.Element("events")
    for i, p in enumerate(sampled):
        nxt = sampled[i + 1] if i + 1 < len(sampled) else None
        _append_pli_event(root, track.name, i, p, nxt, cot_type, stale_seconds)
    if len(sampled) >= 2:
        _append_route_event(root, track.name, sampled)
    ET.indent(root)
    return ET.tostring(root, encoding="unicode", xml_declaration=True) + "\n"


def write_cot(track: Track, output_path: Path, **kwargs) -> Path:
    """Write *track* as CoT XML to *output_path* and return it."""
    output_path.write_text(track_to_cot(track, **kwargs), encoding="utf-8")
    logger.info("CoT file created: %s", output_path)
    return output_path


def convert_to_cot(
    srt_file: Path | str,
    output_file: Path | str | None = None,
    *,
    redact: str = "none",
    tz_offset: timedelta | None = None,
    interval: float = 1.0,
    cot_type: str = "a-n-A",
) -> Path:
    """Convert a DJI SRT file to CoT XML. Defaults output to ``<srt>.cot.xml``."""
    srt_path = Path(srt_file)
    output_path = (
        Path(output_file)
        if output_file
        else srt_path.with_name(f"{srt_path.stem}.cot.xml")
    )
    track = build_track(srt_path, redact=redact, tz_offset=tz_offset)
    return write_cot(track, output_path, interval=interval, cot_type=cot_type)
