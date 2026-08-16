"""Render a photo list as a standalone, self-contained HTML map.

Same contract as :mod:`.html_viewer`: the photo GeoJSON (with base64 EXIF
thumbnails) is embedded in a ``<script type="application/json">`` block and a
small vanilla Leaflet app renders it. Markers are clustered with
Leaflet.markercluster so archive-scale folders (many shots per church, many
churches) stay readable. Leaflet, the cluster plugin, and the OpenStreetMap
basemap load from the network; the photo data itself is embedded.
Linked GPano panoramas additionally pull in Pannellum (same pinned+SRI
pattern) for an in-page 360° viewer.
"""

from __future__ import annotations

import json
import logging
from html import escape
from pathlib import Path

from .photomap import PhotoPoint, photos_to_geojson
from .photomap_js import (
    CLUSTER_CSS_SRI,
    CLUSTER_DEFAULT_CSS_SRI,
    CLUSTER_JS_SRI,
    CLUSTER_VERSION,
    PANO_HEAD,
    PANO_JS,
    PANO_OVERLAY,
    PANO_SCRIPT,
    PHOTO_CSS,
    PHOTO_LAYER_JS,
)
from .provenance import stamp
from .tiles import DEFAULT_TILE_STYLE, tile_layer_js

logger = logging.getLogger(__name__)

# Pinned releases + Subresource Integrity hashes. Leaflet pins match
# html_viewer.py; the markercluster hashes were computed from the unpkg 1.5.3
# assets (sha256, base64) when this module was written.
_LEAFLET_VERSION = "1.9.4"
_LEAFLET_CSS_SRI = "sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
_LEAFLET_JS_SRI = "sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="

# Popup content control (issue #296): the user-facing field names and the
# GeoJSON properties they govern. Excluded fields are stripped from the
# embedded data itself, not merely hidden by the popup JS — a shared map must
# not leak in its source what it hides in its UI. thumb/link/pano always
# survive (the thumbnail is the photo itself, the link powers the 360°
# viewer, and pano is marker-type metadata), as do the pano initial-view
# props (yaw/pitch/hfov, #309 — view configuration, not personal data) and
# vthumb (#441 — marks the thumb as an opening-view crop, same category).
POPUP_FIELDS = ("name", "timestamp", "camera", "altitude", "credit")
_FIELD_TO_PROP = {
    "name": "name",
    "timestamp": "timestamp",
    "camera": "camera",
    "altitude": "alt",
    "credit": "credit",
}


def parse_popup_fields(spec: str) -> frozenset[str]:
    """Parse a ``--popup-fields`` value into a field set.

    ``"none"`` selects no fields; anything else must be a comma-separated,
    case-insensitive subset of :data:`POPUP_FIELDS`. Raises ``ValueError``
    naming the valid fields otherwise.
    """
    value = spec.strip().lower()
    if value == "none":
        return frozenset()
    fields = frozenset(part.strip() for part in value.split(",") if part.strip())
    unknown = fields - frozenset(POPUP_FIELDS)
    if unknown or not fields:
        raise ValueError(
            "invalid --popup-fields value"
            + (f" ({', '.join(sorted(unknown))})" if unknown else "")
            + f"; use 'none' or a comma list of: {', '.join(POPUP_FIELDS)}"
        )
    return fields


def _apply_popup_fields(geojson: dict, fields: frozenset[str]) -> None:
    """Strip excluded popup fields from *geojson* in place.

    "altitude" also covers the coordinate's third element, so an excluded
    altitude is absent from the HTML file entirely.
    """
    drop = [prop for field, prop in _FIELD_TO_PROP.items() if field not in fields]
    for feature in geojson["features"]:
        props = feature["properties"]
        for prop in drop:
            props.pop(prop, None)
        if "altitude" not in fields:
            coords = feature["geometry"]["coordinates"]
            if len(coords) == 3:
                feature["geometry"]["coordinates"] = coords[:2]


_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Photo map — {title}</title>
<!-- Leaflet + markercluster + OpenStreetMap tiles load from the network;
     the photo data (incl. thumbnails) is embedded below. -->
<link rel="stylesheet"
      href="https://unpkg.com/leaflet@{leaflet}/dist/leaflet.css"
      integrity="{leaflet_css_sri}" crossorigin="" />
<link rel="stylesheet"
      href="https://unpkg.com/leaflet.markercluster@{cluster}/dist/MarkerCluster.css"
      integrity="{cluster_css_sri}" crossorigin="" />
<link rel="stylesheet"
      href="https://unpkg.com/leaflet.markercluster@{cluster}/dist/MarkerCluster.Default.css"
      integrity="{cluster_default_css_sri}" crossorigin="" />
{pano_head}
<style>
  html, body {{ height: 100%; margin: 0; }}
  #map {{ height: 100%; }}
{photo_css}
</style>
</head>
<body>
<div id="map"></div>
{pano_overlay}
<script type="application/json" id="photo-data">
{data}
</script>
<script src="https://unpkg.com/leaflet@{leaflet}/dist/leaflet.js"
        integrity="{leaflet_js_sri}" crossorigin=""></script>
<script src="https://unpkg.com/leaflet.markercluster@{cluster}/dist/leaflet.markercluster.js"
        integrity="{cluster_js_sri}" crossorigin=""></script>
{pano_scripts}
<script>
{app_js}
</script>
</body>
</html>
"""

_APP_JS = """
const data = JSON.parse(document.getElementById('photo-data').textContent);
const map = L.map('map');
__TILE_LAYER__

const esc = s => String(s).replace(/[&<>"']/g,
  ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));

const photoFeatures = (data.features || []).filter(
  f => f.geometry && f.geometry.type === 'Point');

__PHOTO_LAYER__

if (photoMarkers.length && panoMarkers.length) {
  // Expanded control doubles as the legend: the labels reuse the pin CSS as
  // colored swatches. Only shown when the folder actually mixes types.
  L.control.layers(null, {
    '<span class="photo-pin pin-photo pin-swatch"></span>Photos': photoCluster,
    '<span class="photo-pin pin-pano pin-swatch"></span>360° panoramas':
      panoCluster
  }, { collapsed: false }).addTo(map);
}
if (photoLatLngs.length > 1) {
  map.fitBounds(L.latLngBounds(photoLatLngs).pad(0.1), { maxZoom: 17 });
} else if (photoLatLngs.length === 1) {
  map.setView(photoLatLngs[0], 16);
} else {
  map.setView([0, 0], 2);
}
"""


def photos_to_html(
    points: list[PhotoPoint],
    title: str,
    *,
    link_base: str | None = None,
    popup_fields: frozenset[str] | None = None,
    tile_style: str = DEFAULT_TILE_STYLE,
) -> str:
    """Return a complete self-contained HTML photo map.

    ``link_base`` (issue #253): when not ``None``, popups link the thumbnail
    and filename to the original photo file — ``""`` means the originals sit
    beside the HTML, otherwise a folder/URL prefix. Such links only resolve
    while the originals stay reachable; the default (``None``) keeps the map
    fully self-contained. GPano panoramas always render as distinct,
    toggleable orange markers (issue #283); the embedded Pannellum 360°
    viewer additionally activates when links are enabled.

    ``popup_fields`` (issue #296): a set from :func:`parse_popup_fields`
    limiting which EXIF-derived details the map carries; ``None`` (default)
    keeps everything. Excluded fields never reach the HTML file.

    ``tile_style`` (issue #311): a :data:`~.tiles.TILE_STYLES` key selecting
    the basemap drawn under the markers.
    """
    geojson = photos_to_geojson(
        points, include_thumbnails=True, link_base=link_base
    )
    if popup_fields is not None:
        _apply_popup_fields(geojson, popup_fields)
    # Escape "<" to "\\u003c" (a JSON Unicode escape) so JSON.parse round-trips
    # it while no literal "</script>" can break out of the data block.
    data = json.dumps(geojson).replace("<", "\\u003c")
    pano_enabled = link_base is not None and any(p.is_pano for p in points)
    return stamp(_TEMPLATE.format(
        title=escape(title),
        leaflet=_LEAFLET_VERSION,
        leaflet_css_sri=_LEAFLET_CSS_SRI,
        leaflet_js_sri=_LEAFLET_JS_SRI,
        cluster=CLUSTER_VERSION,
        cluster_css_sri=CLUSTER_CSS_SRI,
        cluster_default_css_sri=CLUSTER_DEFAULT_CSS_SRI,
        cluster_js_sri=CLUSTER_JS_SRI,
        photo_css=PHOTO_CSS,
        data=data,
        pano_head=PANO_HEAD if pano_enabled else "",
        pano_overlay=PANO_OVERLAY if pano_enabled else "",
        pano_scripts=PANO_SCRIPT if pano_enabled else "",
        app_js=(
            _APP_JS.replace("__PHOTO_LAYER__", PHOTO_LAYER_JS)
            + (PANO_JS if pano_enabled else "")
        ).replace("__TILE_LAYER__", tile_layer_js(tile_style)),
    ))


def write_photos_html(
    points: list[PhotoPoint],
    output_path: Path,
    title: str,
    *,
    link_base: str | None = None,
    popup_fields: frozenset[str] | None = None,
    tile_style: str = DEFAULT_TILE_STYLE,
) -> Path:
    """Write *points* as an HTML map to *output_path* and return it."""
    output_path.write_text(
        photos_to_html(
            points, title, link_base=link_base, popup_fields=popup_fields,
            tile_style=tile_style,
        ),
        encoding="utf-8",
    )
    logger.info("HTML photo map created: %s", output_path)
    return output_path
