"""Render a :class:`Track` as KML — a LineString placemark for Google Earth."""

from __future__ import annotations

import logging
from pathlib import Path
from xml.sax.saxutils import escape

from .track import Track, build_track

logger = logging.getLogger(__name__)

_KML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>{name}</name>
    <Placemark>
      <name>DJI Flight Path</name>
      <LineString>
        <altitudeMode>absolute</altitudeMode>
        <coordinates>{coordinates}</coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>
"""


def track_to_kml(track: Track) -> str:
    """Return a KML document string for *track* (coordinates as lon,lat,alt)."""
    coordinates = " ".join(f"{p.lon},{p.lat},{p.alt}" for p in track.points)
    return _KML_TEMPLATE.format(name=escape(track.name), coordinates=coordinates)


def write_kml(track: Track, output_path: Path) -> Path:
    """Write *track* as KML to *output_path* and return it."""
    output_path.write_text(track_to_kml(track), encoding="utf-8")
    logger.info("KML file created: %s", output_path)
    return output_path


def convert_to_kml(
    srt_file: Path | str, output_file: Path | str | None = None, redact: str = "none"
) -> Path:
    """Convert a DJI SRT file to KML. Defaults output to ``<srt>.kml``."""
    srt_path = Path(srt_file)
    output_path = Path(output_file) if output_file else srt_path.with_suffix(".kml")
    return write_kml(build_track(srt_path, redact=redact), output_path)
