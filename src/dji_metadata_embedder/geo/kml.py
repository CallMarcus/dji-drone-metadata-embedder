"""Render a :class:`Track` as KML — a LineString placemark for Google Earth."""

from __future__ import annotations

import logging
from pathlib import Path
from xml.sax.saxutils import escape

from .footprint import Footprint
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
    </Placemark>{footprints}
  </Document>
</kml>
"""


def _footprints_folder(footprints: list[Footprint]) -> str:
    if not footprints:
        return ""
    placemarks = []
    for fp in footprints:
        coords = " ".join(f"{lon},{lat},0" for lon, lat in fp.ring)
        placemarks.append(
            "\n      <Placemark><name>footprint {idx}</name>"
            "<Polygon><altitudeMode>clampToGround</altitudeMode>"
            "<outerBoundaryIs><LinearRing>"
            "<coordinates>{coords}</coordinates>"
            "</LinearRing></outerBoundaryIs></Polygon></Placemark>".format(
                idx=fp.index, coords=coords
            )
        )
    return (
        "\n    <Folder><name>Camera footprints</name>" + "".join(placemarks) + "\n    </Folder>"
    )


def track_to_kml(track: Track, footprints: list[Footprint] | None = None) -> str:
    """Return a KML document string for *track* (coordinates as lon,lat,alt)."""
    coordinates = " ".join(f"{p.lon},{p.lat},{p.alt}" for p in track.points)
    return _KML_TEMPLATE.format(
        name=escape(track.name),
        coordinates=coordinates,
        footprints=_footprints_folder(footprints or []),
    )


def write_kml(track: Track, output_path: Path, footprints: list[Footprint] | None = None) -> Path:
    """Write *track* as KML to *output_path* and return it."""
    output_path.write_text(track_to_kml(track, footprints), encoding="utf-8")
    logger.info("KML file created: %s", output_path)
    return output_path


def convert_to_kml(
    srt_file: Path | str,
    output_file: Path | str | None = None,
    redact: str = "none",
    *,
    footprint: bool = False,
    footprint_interval: float = 2.0,
    model: str | None = None,
) -> Path:
    """Convert a DJI SRT file to KML. Defaults output to ``<srt>.kml``.

    With ``footprint`` and ``redact == "none"``, a folder of per-interval camera
    footprint polygons is added."""
    from .footprint import build_footprints, lens_for

    srt_path = Path(srt_file)
    output_path = Path(output_file) if output_file else srt_path.with_suffix(".kml")
    track = build_track(srt_path, redact=redact)
    footprints = None
    if footprint and redact == "none":
        footprints = build_footprints(track, lens=lens_for(model), interval=footprint_interval)
    return write_kml(track, output_path, footprints)
