"""Keyless basemap styles shared by the HTML map writers (#311).

Each style pins a Leaflet tile URL template, the provider's required
attribution, and its maximum zoom. Keyless community providers only — no
API-key plumbing. All are OpenStreetMap-data styles, so the map reads the
same, just drawn differently.
"""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class TileStyle:
    """One basemap: Leaflet URL template + provider attribution + max zoom."""

    url: str
    max_zoom: int
    attribution: str


TILE_STYLES: dict[str, TileStyle] = {
    "osm": TileStyle(
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        max_zoom=19,
        attribution="&copy; OpenStreetMap contributors",
    ),
    "osm-hot": TileStyle(
        url="https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
        max_zoom=19,
        attribution=(
            "&copy; OpenStreetMap contributors, style &copy; Humanitarian "
            "OpenStreetMap Team, hosted by OpenStreetMap France"
        ),
    ),
    "opentopomap": TileStyle(
        url="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
        max_zoom=17,
        attribution=(
            "map data &copy; OpenStreetMap contributors, SRTM | style "
            "&copy; OpenTopoMap (CC-BY-SA)"
        ),
    ),
    "cyclosm": TileStyle(
        url="https://{s}.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png",
        max_zoom=20,
        attribution=(
            "&copy; OpenStreetMap contributors, style CyclOSM, hosted by "
            "OpenStreetMap France"
        ),
    ),
}

DEFAULT_TILE_STYLE = "osm"


def tile_layer_js(style: str) -> str:
    """Return the Leaflet ``L.tileLayer(...).addTo(map)`` call for *style*.

    The values are trusted module constants (URL template and attribution
    HTML), embedded verbatim into the page's app script; ``json.dumps``
    provides the JS string quoting. Unknown *style* raises ``KeyError`` —
    the CLI restricts choices to :data:`TILE_STYLES` before this runs.
    """
    ts = TILE_STYLES[style]
    return (
        f"L.tileLayer({json.dumps(ts.url)}, {{\n"
        f"  maxZoom: {ts.max_zoom},\n"
        f"  attribution: {json.dumps(ts.attribution)}\n"
        "}).addTo(map);"
    )
