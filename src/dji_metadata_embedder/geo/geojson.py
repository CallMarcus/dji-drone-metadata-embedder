"""Render a :class:`Track` as GeoJSON (RFC 7946).

GeoJSON is the canonical interchange the map viewers (#221, #222) consume: a
``FeatureCollection`` holding one ``LineString`` for the path plus one ``Point``
per sample carrying altitude and timestamp.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .footprint import Footprint, build_footprints, lens_for
from .track import Track, build_track
from ..utilities import Home, parse_home, redact_home
from ..mp4_telemetry import is_video

logger = logging.getLogger(__name__)


def _footprint_feature(fp: Footprint) -> dict:
    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[lon, lat] for lon, lat in fp.ring]],
        },
        "properties": {
            "kind": "footprint",
            "index": fp.index,
            "timestamp": fp.timestamp,
            "agl": round(fp.agl, 3),
            "hfov": round(fp.hfov, 1),
            "vfov": round(fp.vfov, 1),
        },
    }


def track_to_geojson(
    track: Track,
    footprints: list[Footprint] | None = None,
    home: Home | None = None,
) -> dict:
    """Return a GeoJSON ``FeatureCollection`` dict for *track*."""
    # RFC 7946 §3.1.4 requires a LineString to have two or more positions, so a
    # track with fewer points (e.g. --redact drop, or a clip that never got a
    # GPS fix) is represented with a null geometry rather than an invalid empty
    # LineString that strict consumers reject.
    if len(track.points) >= 2:
        line_geometry: dict | None = {
            "type": "LineString",
            "coordinates": [[p.lon, p.lat, p.alt] for p in track.points],
        }
    else:
        line_geometry = None
    features: list[dict] = [
        {
            "type": "Feature",
            "geometry": line_geometry,
            "properties": {"name": track.name},
        }
    ]
    for index, p in enumerate(track.points):
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [p.lon, p.lat, p.alt]},
                "properties": {
                    "index": index,
                    "abs_alt": p.alt,
                    "timestamp": p.timestamp,
                },
            }
        )
    for fp in footprints or []:
        features.append(_footprint_feature(fp))
    if home is not None:
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [home.lon, home.lat]},
                "properties": {"type": "home"},
            }
        )
    return {"type": "FeatureCollection", "features": features}


def write_geojson(
    track: Track,
    output_path: Path,
    footprints: list[Footprint] | None = None,
    home: Home | None = None,
) -> Path:
    """Write *track* as GeoJSON to *output_path* and return it."""
    output_path.write_text(
        json.dumps(track_to_geojson(track, footprints, home), indent=2), encoding="utf-8"
    )
    logger.info("GeoJSON file created: %s", output_path)
    return output_path


def convert_to_geojson(
    srt_file: Path | str,
    output_file: Path | str | None = None,
    redact: str = "none",
    *,
    footprint: bool = False,
    footprint_interval: float = 2.0,
    model: str | None = None,
    extract_home: bool = False,
) -> Path:
    """Convert a DJI SRT file to GeoJSON. Defaults output to ``<srt>.geojson``.

    When ``footprint`` is set and ``redact == "none"``, per-interval camera
    ground-footprint polygons are added. Footprints are suppressed under any
    redaction (a precise polygon would re-sharpen a fuzzed centre)."""
    srt_path = Path(srt_file)
    output_path = Path(output_file) if output_file else srt_path.with_suffix(".geojson")
    track = build_track(srt_path, redact=redact)
    footprints = None
    if footprint and redact == "none":
        footprints = build_footprints(track, lens=lens_for(model), interval=footprint_interval)
    home = None
    if extract_home and not is_video(srt_path):
        home = redact_home(parse_home(srt_path.read_text(encoding="utf-8")), redact)
    return write_geojson(track, output_path, footprints, home=home)
