"""Render a mixed folder — photos, panoramas, flight tracks — as one map.

The ``dji-embed map`` simple mode (#322): both existing scanners' output is
merged into a single GeoJSON FeatureCollection in which every feature
carries a ``type`` tag (``photo``/``pano``/``track``), rendered by one
Leaflet template that combines the photomap's clustered pins/popups/360°
viewer with the flightmap's per-flight polylines and playback. The type
tags are the load-bearing contract: a future 3D variant is a template swap
over this same collection, never a data-model migration.
"""

from __future__ import annotations

import logging

from .flightmap import flights_to_geojson
from .photomap import PhotoPoint, photos_to_geojson
from .track import Track

logger = logging.getLogger(__name__)


def mixed_to_geojson(
    points: list[PhotoPoint],
    tracks: list[Track],
    *,
    link_base: str | None = None,
    redact: str = "none",
) -> dict:
    """Merge photos and flights into one type-tagged ``FeatureCollection``.

    Every feature gains ``properties.type`` — ``photo``, ``pano``, or
    ``track`` — so one template (2D today, 3D later) can render and toggle
    the types without inspecting geometry. Photo features keep their
    embedded thumbnails (this collection only ever feeds the HTML writer);
    ``link_base`` and the top-level ``redacted`` member behave exactly as
    in the source exporters.
    """
    photo_fc = photos_to_geojson(points, include_thumbnails=True, link_base=link_base)
    for feature in photo_fc["features"]:
        props = feature["properties"]
        props["type"] = "pano" if props.get("pano") else "photo"
    flight_fc = flights_to_geojson(tracks, redact=redact)
    for feature in flight_fc["features"]:
        feature["properties"]["type"] = "track"
    return {
        "type": "FeatureCollection",
        "redacted": redact,
        "features": photo_fc["features"] + flight_fc["features"],
    }
