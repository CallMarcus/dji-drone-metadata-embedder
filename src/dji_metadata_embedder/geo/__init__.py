"""Geospatial track/photo models and exporters (GeoJSON, KML, HTML, CoT)."""

from .cot import convert_to_cot, track_to_cot
from .footprint import FOV_TABLE, Footprint, build_footprints, lens_for
from .geojson import convert_to_geojson, track_to_geojson
from .html_viewer import convert_to_html, track_to_html
from .kml import convert_to_kml, track_to_kml
from .photomap import (
    PhotomapError,
    PhotoPoint,
    photos_to_geojson,
    photos_to_kml,
    scan_photos,
    write_photos_geojson,
    write_photos_kml,
)
from .photomap_html import photos_to_html, write_photos_html
from .solar import sun_position
from .track import Track, TrackPoint, build_track

__all__ = [
    "Track",
    "TrackPoint",
    "build_track",
    "sun_position",
    "track_to_cot",
    "convert_to_cot",
    "track_to_geojson",
    "convert_to_geojson",
    "track_to_kml",
    "convert_to_kml",
    "track_to_html",
    "convert_to_html",
    "Footprint",
    "build_footprints",
    "lens_for",
    "FOV_TABLE",
    "PhotomapError",
    "PhotoPoint",
    "scan_photos",
    "photos_to_geojson",
    "write_photos_geojson",
    "photos_to_kml",
    "write_photos_kml",
    "photos_to_html",
    "write_photos_html",
]
