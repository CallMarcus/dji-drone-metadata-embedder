"""Geospatial track/photo models and exporters (GeoJSON, KML, HTML, CoT)."""

from .cot import convert_to_cot, track_to_cot
from .flightlog import (
    FlightLog,
    FlightLogError,
    MergeReport,
    merge_gimbal,
    merge_into_flights,
    parse_flight_log,
)
from .flightmap import (
    flights_to_geojson,
    flights_to_kml,
    scan_flights,
    write_flights_geojson,
    write_flights_kml,
)
from .flightmap3d_html import flights_to_3d_html, write_flights_3d_html
from .flightmap_html import flights_to_html, write_flights_html
from .footprint import FOV_TABLE, Footprint, build_footprints, lens_for
from .geojson import convert_to_geojson, track_to_geojson
from .html_viewer import convert_to_html, track_to_html
from .kml import convert_to_kml, track_to_kml
from .map_html import write_mixed_html
from .photomap import (
    PhotomapError,
    PhotoPoint,
    folder_has_photos,
    photos_to_geojson,
    photos_to_kml,
    redact_photo_points,
    scan_photos,
    write_photos_geojson,
    write_photos_kml,
)
from .photomap_html import parse_popup_fields, photos_to_html, write_photos_html
from .serve import serve_directory
from .solar import sun_position
from .tiles import DEFAULT_TILE_STYLE, TILE_STYLES, TileStyle
from .track import Track, TrackPoint, build_track
from .videogimbal import (
    VideoGimbalReport,
    VideoGimbalUnavailable,
    enrich_from_video,
)

__all__ = [
    "DEFAULT_TILE_STYLE",
    "FOV_TABLE",
    "TILE_STYLES",
    "FlightLog",
    "FlightLogError",
    "Footprint",
    "MergeReport",
    "PhotoPoint",
    "PhotomapError",
    "TileStyle",
    "Track",
    "TrackPoint",
    "VideoGimbalReport",
    "VideoGimbalUnavailable",
    "build_footprints",
    "build_track",
    "convert_to_cot",
    "convert_to_geojson",
    "convert_to_html",
    "convert_to_kml",
    "enrich_from_video",
    "flights_to_3d_html",
    "flights_to_geojson",
    "flights_to_html",
    "flights_to_kml",
    "folder_has_photos",
    "lens_for",
    "merge_gimbal",
    "merge_into_flights",
    "parse_flight_log",
    "parse_popup_fields",
    "photos_to_geojson",
    "photos_to_html",
    "photos_to_kml",
    "redact_photo_points",
    "scan_flights",
    "scan_photos",
    "serve_directory",
    "sun_position",
    "track_to_cot",
    "track_to_geojson",
    "track_to_html",
    "track_to_kml",
    "write_flights_3d_html",
    "write_flights_geojson",
    "write_flights_html",
    "write_flights_kml",
    "write_mixed_html",
    "write_photos_geojson",
    "write_photos_html",
    "write_photos_kml",
]
