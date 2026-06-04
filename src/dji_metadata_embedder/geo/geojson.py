"""Render a :class:`Track` as GeoJSON (RFC 7946).

GeoJSON is the canonical interchange the map viewers (#221, #222) consume: a
``FeatureCollection`` holding one ``LineString`` for the path plus one ``Point``
per sample carrying altitude and timestamp.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .track import Track, build_track

logger = logging.getLogger(__name__)


def track_to_geojson(track: Track) -> dict:
    """Return a GeoJSON ``FeatureCollection`` dict for *track*."""
    line_coords = [[p.lon, p.lat, p.alt] for p in track.points]
    features: list[dict] = [
        {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": line_coords},
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
    return {"type": "FeatureCollection", "features": features}


def write_geojson(track: Track, output_path: Path) -> Path:
    """Write *track* as GeoJSON to *output_path* and return it."""
    output_path.write_text(
        json.dumps(track_to_geojson(track), indent=2), encoding="utf-8"
    )
    logger.info("GeoJSON file created: %s", output_path)
    return output_path


def convert_to_geojson(
    srt_file: Path | str, output_file: Path | str | None = None, redact: str = "none"
) -> Path:
    """Convert a DJI SRT file to GeoJSON. Defaults output to ``<srt>.geojson``."""
    srt_path = Path(srt_file)
    output_path = Path(output_file) if output_file else srt_path.with_suffix(".geojson")
    return write_geojson(build_track(srt_path, redact=redact), output_path)
