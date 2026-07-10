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
import posixpath
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from .. import utilities
from ..utilities import load_samples, redact_coords
from .geometry import haversine_m
from .track import Track, build_track_from_samples

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


# Spatial-continuity bounds for size-split joining: allow this much GPS wobble
# even across a zero-second gap, plus travel at a generous top speed (DJI sport
# mode peaks around 27 m/s).
_JITTER_FLOOR_M = 50.0
_MAX_SPEED_MS = 30.0


@dataclass
class _ScanEntry:
    """A scanned track plus its raw SRT wall-clock boundaries.

    ``first_dt``/``last_dt`` are the *unresolved local* datetimes straight from
    the SRT blocks (``None`` for formats without a datetime line). Split-file
    gaps are measured on these rather than on the resolved UTC in the track:
    both segments share the same unknown offset, so the gap is exact even when
    timezone auto-detection fails, and it never falls back to file mtimes,
    which zip/cloud copies rewrite.
    """

    track: Track
    first_dt: datetime | None
    last_dt: datetime | None


def _joinable(prev: _ScanEntry, nxt: _ScanEntry, max_gap_s: float) -> bool:
    """True when *nxt* looks like the size-split continuation of *prev*."""
    if posixpath.dirname(prev.track.name) != posixpath.dirname(nxt.track.name):
        return False
    if prev.last_dt is None or nxt.first_dt is None:
        return False
    gap = (nxt.first_dt - prev.last_dt).total_seconds()
    # Sub-second overlap tolerated: the new file's first block can be stamped
    # marginally before the old file's last one is flushed.
    if not -1.0 <= gap <= max_gap_s:
        return False
    a, b = prev.track.points[-1], nxt.track.points[0]
    limit = _JITTER_FLOOR_M + max(gap, 0.0) * _MAX_SPEED_MS
    return haversine_m(a.lat, a.lon, b.lat, b.lon) <= limit


def join_split_flights(
    entries: list[_ScanEntry], max_gap_s: float = 15.0
) -> list[Track]:
    """Chain size-split recordings into single flights.

    DJI closes the MP4/SRT pair when it hits the 4 GB container limit and
    keeps recording into the next numbered file, so one flight can arrive as
    several consecutive tracks. Segments are joined when they sit in the same
    directory, the next file's telemetry starts within ``max_gap_s`` seconds
    of the previous one ending, and the track resumes within the distance the
    drone could plausibly have covered in that gap. Consecutive file numbers
    are deliberately not required — photos share DJI's numbering counter, so
    segment numbers can skip. A joined track keeps the first segment's name
    and lists all sources in :attr:`Track.segments`.
    """
    ordered = sorted(
        entries,
        key=lambda e: (e.first_dt is None, e.first_dt or datetime.min, e.track.name),
    )
    flights: list[_ScanEntry] = []
    for entry in ordered:
        if flights and _joinable(flights[-1], entry, max_gap_s):
            prev = flights[-1]
            if prev.track.segments is None:
                prev.track.segments = [prev.track.name]
            prev.track.segments.append(entry.track.name)
            # Rebase the appended segment's clock onto the previous one using
            # the raw SRT gap. When each file's UTC was synthesized from its
            # own mtime (timezone auto-detection failed), the segments'
            # timelines don't line up and the joined duration would collapse
            # to one file's length; with properly resolved offsets the shift
            # is zero.
            prev_end_utc = prev.track.points[-1].utc
            first_utc = entry.track.points[0].utc
            if prev_end_utc is not None and first_utc is not None:
                # _joinable guaranteed both boundary datetimes exist.
                assert prev.last_dt is not None and entry.first_dt is not None
                shift = prev_end_utc + (entry.first_dt - prev.last_dt) - first_utc
                if shift:
                    for p in entry.track.points:
                        if p.utc is not None:
                            p.utc += shift
            prev.track.points.extend(entry.track.points)
            prev.last_dt = entry.last_dt
        else:
            flights.append(entry)
    return [e.track for e in flights]


class _TzWarningAggregator(logging.Filter):
    """Collapse per-file timezone auto-detection warnings into one summary.

    A folder whose mtimes were rewritten by a zip/cloud transfer would
    otherwise repeat :func:`..utilities.estimate_utc_offset`'s warning once
    per file — on an archive scan that is pure noise. The per-file warnings
    are swallowed here and :func:`scan_flights` emits a single count-carrying
    summary instead.
    """

    _PREFIX = "Timezone auto-detection failed"

    def __init__(self) -> None:
        super().__init__()
        self.count = 0

    def filter(self, record: logging.LogRecord) -> bool:
        if record.getMessage().startswith(self._PREFIX):
            self.count += 1
            return False
        return True


def scan_flights(
    directory: Path | str,
    recursive: bool = False,
    redact: str = "none",
    join_gap: float = 15.0,
    tz_offset: timedelta | None = None,
) -> tuple[list[Track], list[str]]:
    """Scan *directory* for ``.SRT`` files and return ``(tracks, skipped)``.

    ``tracks`` holds one :class:`Track` per flight: SRTs that yielded at least
    one GPS fix, with size-split recordings chained into single flights when
    ``join_gap`` (seconds, 0 disables) allows — see :func:`join_split_flights`.
    SRTs with no usable telemetry (non-DJI subtitles, clips that never
    acquired a fix, unreadable files) go to ``skipped``. Both lists are sorted
    by name so output is deterministic regardless of filesystem order.
    ``redact`` (``fuzz`` coarsens to ~100 m) is applied *after* joining so the
    coarsened coordinates cannot break the continuity check. ``tz_offset``
    fixes the SRT-local -> UTC offset for every file; ``None`` auto-detects it
    per file from the mtime, falling back to mtime-based start times (with one
    aggregated warning) when the mtimes were rewritten by a transfer.
    """
    root = Path(directory)
    files: set[Path] = set()
    for pattern in _SRT_PATTERNS:
        files.update(root.rglob(pattern) if recursive else root.glob(pattern))
    entries: list[_ScanEntry] = []
    skipped: list[str] = []
    tz_warnings = _TzWarningAggregator()
    util_logger = logging.getLogger(utilities.__name__)
    util_logger.addFilter(tz_warnings)
    try:
        for path in sorted(files):
            name = _display_name(path, root, recursive)
            try:
                samples = load_samples(path)
                if not samples:
                    skipped.append(name)
                    continue
                mtime_utc = datetime.fromtimestamp(
                    path.stat().st_mtime, tz=timezone.utc
                ).replace(tzinfo=None)
                track = build_track_from_samples(
                    name, samples, tz_offset=tz_offset, mtime_utc=mtime_utc
                )
            except (OSError, ValueError) as exc:
                logger.warning("Skipping %s: %s", path, exc)
                skipped.append(name)
                continue
            entries.append(_ScanEntry(track, samples[0].dt, samples[-1].dt))
    finally:
        util_logger.removeFilter(tz_warnings)
    if tz_warnings.count:
        logger.warning(
            "Timezone auto-detection failed for %d of %d SRT files: their "
            "mtimes do not match the recording window (common after zip/cloud "
            "transfers), so those start times fall back to the file mtime and "
            "may be wrong. Pass --tz-offset to set the recording timezone "
            "explicitly.",
            tz_warnings.count,
            len(files),
        )
    if join_gap > 0:
        tracks = join_split_flights(entries, max_gap_s=join_gap)
    else:
        tracks = [e.track for e in entries]
    if redact == "fuzz":
        for track in tracks:
            coords = redact_coords([(p.lat, p.lon) for p in track.points], "fuzz")
            for p, (lat, lon) in zip(track.points, coords):
                p.lat, p.lon = lat, lon
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
    if track.segments:
        props["segments"] = track.segments
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
        if track.segments:
            desc.append(
                f"{len(track.segments)} size-split files "
                f"({track.segments[0]} → {track.segments[-1]})"
            )
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
