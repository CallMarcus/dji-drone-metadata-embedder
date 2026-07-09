"""Multi-flight folder scan and exporters (GeoJSON, KML) for ``flightmap``.

A directory of DJI ``.SRT`` sidecars is parsed straight into :class:`Track`
objects — the videos are never opened and no external tool is needed — so
scanning an archive of clips is fast. The resulting track list is the single
model every flightmap writer consumes: GeoJSON and KML here, the combined
HTML map in :mod:`.flightmap_html`.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from xml.sax.saxutils import escape

from .track import Track, build_track

logger = logging.getLogger(__name__)

# Both cases so case-sensitive filesystems match DJI's .SRT and renamed .srt;
# identical paths matched twice (case-insensitive filesystems) dedupe via set.
_SRT_PATTERNS = ("*.SRT", "*.srt")


def _display_name(path: Path, root: Path, recursive: bool) -> str:
    """Flight label: the SRT stem, path-qualified on recursive scans.

    DJI restarts numbering per card/session, so recursive scans keep the
    subdirectory (``session1/DJI_0001``) to stop distinct flights collapsing
    onto one label — same rule as the photomap scanner.
    """
    if not recursive:
        return path.stem
    return path.relative_to(root).with_suffix("").as_posix()


def scan_flights(
    directory: Path | str, recursive: bool = False, redact: str = "none"
) -> tuple[list[Track], list[str]]:
    """Scan *directory* for ``.SRT`` files and return ``(tracks, skipped)``.

    ``tracks`` holds one :class:`Track` per SRT that yielded at least one GPS
    fix; SRTs with no usable telemetry (non-DJI subtitles, clips that never
    acquired a fix, unreadable files) go to ``skipped``. Both lists are sorted
    by name so output is deterministic regardless of filesystem order.
    ``redact`` is applied per track by :func:`build_track` (``fuzz`` coarsens
    to ~100 m).
    """
    root = Path(directory)
    files: set[Path] = set()
    for pattern in _SRT_PATTERNS:
        files.update(root.rglob(pattern) if recursive else root.glob(pattern))
    tracks: list[Track] = []
    skipped: list[str] = []
    for path in sorted(files):
        name = _display_name(path, root, recursive)
        try:
            track = build_track(path, redact=redact)
        except (OSError, ValueError) as exc:
            logger.warning("Skipping %s: %s", path, exc)
            skipped.append(name)
            continue
        if not track.points:
            skipped.append(name)
            continue
        track.name = name
        tracks.append(track)
    tracks.sort(key=lambda t: t.name)
    skipped.sort()
    return tracks, skipped


def format_duration(seconds: int) -> str:
    """Format whole seconds for display: ``243`` -> ``4:03``, ``3723`` -> ``1:02:03``."""
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _flight_properties(track: Track) -> dict:
    """Per-flight summary properties shared by every writer's popups/tables."""
    first, last = track.points[0], track.points[-1]
    props: dict = {"name": track.name, "points": len(track.points)}
    if first.utc is not None:
        props["start"] = first.utc.strftime("%Y-%m-%d %H:%M:%S UTC")
        if last.utc is not None:
            props["duration_s"] = round((last.utc - first.utc).total_seconds())
    alts = [p.alt for p in track.points]
    props["alt_min"] = round(min(alts), 1)
    props["alt_max"] = round(max(alts), 1)
    return props


def flights_to_geojson(tracks: list[Track]) -> dict:
    """Return a GeoJSON ``FeatureCollection`` with one feature per flight.

    Each flight is a ``LineString`` carrying name/start/duration/altitude
    summary properties; a single-fix clip degrades to a ``Point`` because
    RFC 7946 §3.1.4 requires two or more positions in a LineString. Unlike
    the single-track exporter no per-sample Point features are emitted — at
    archive scale they would swamp the map and the file.
    """
    features: list[dict] = []
    for track in tracks:
        coords = [[p.lon, p.lat, p.alt] for p in track.points]
        if len(coords) >= 2:
            geometry: dict = {"type": "LineString", "coordinates": coords}
        else:
            geometry = {"type": "Point", "coordinates": coords[0]}
        features.append(
            {
                "type": "Feature",
                "geometry": geometry,
                "properties": _flight_properties(track),
            }
        )
    return {"type": "FeatureCollection", "features": features}


def write_flights_geojson(tracks: list[Track], output_path: Path) -> Path:
    """Write *tracks* as GeoJSON to *output_path* and return it."""
    output_path.write_text(
        json.dumps(flights_to_geojson(tracks), indent=2), encoding="utf-8"
    )
    logger.info("GeoJSON flight map created: %s", output_path)
    return output_path


_KML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>{name}</name>{placemarks}
  </Document>
</kml>
"""


def flights_to_kml(tracks: list[Track], title: str) -> str:
    """Return a KML document with one path placemark per flight.

    Google Earth and Google My Maps both render each placemark as a separate
    line, so a whole folder of flights imports as one layered document.
    """
    placemarks = []
    for track in tracks:
        props = _flight_properties(track)
        desc = [props.get("start")]
        if "duration_s" in props:
            desc.append(f"duration: {format_duration(props['duration_s'])}")
        desc.append(f"altitude: {props['alt_min']:g} - {props['alt_max']:g} m")
        desc.append(f"{props['points']} GPS points")
        if len(track.points) >= 2:
            coords = " ".join(f"{p.lon},{p.lat},{p.alt}" for p in track.points)
            geometry = (
                "<LineString><altitudeMode>absolute</altitudeMode>"
                f"<coordinates>{coords}</coordinates></LineString>"
            )
        else:
            p = track.points[0]
            geometry = (
                "<Point><altitudeMode>absolute</altitudeMode>"
                f"<coordinates>{p.lon},{p.lat},{p.alt}</coordinates></Point>"
            )
        placemarks.append(
            "\n    <Placemark>"
            f"<name>{escape(track.name)}</name>"
            f"<description>{escape(' · '.join(d for d in desc if d))}</description>"
            f"{geometry}"
            "</Placemark>"
        )
    return _KML_TEMPLATE.format(name=escape(title), placemarks="".join(placemarks))


def write_flights_kml(tracks: list[Track], output_path: Path, title: str) -> Path:
    """Write *tracks* as KML to *output_path* and return it."""
    output_path.write_text(flights_to_kml(tracks, title), encoding="utf-8")
    logger.info("KML flight map created: %s", output_path)
    return output_path
