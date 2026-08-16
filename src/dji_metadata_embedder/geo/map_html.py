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

import json
import logging
from html import escape
from pathlib import Path

from .flightmap import flights_to_geojson
from .flightmap_js import FLIGHT_POPUP_JS, PLAYBACK_JS
from .photomap import PhotoPoint, photos_to_geojson
from .photomap_js import (
    CLUSTER_CSS_SRI,
    CLUSTER_DEFAULT_CSS_SRI,
    CLUSTER_JS_SRI,
    CLUSTER_VERSION,
    HOVER_CONTROL_JS,
    PANO_HEAD,
    PANO_JS,
    PANO_OVERLAY,
    PANO_SCRIPT,
    PHOTO_CSS,
    PHOTO_LAYER_JS,
)
from .provenance import stamp
from .tiles import DEFAULT_TILE_STYLE, tile_layer_js
from .track import Track

logger = logging.getLogger(__name__)

# Pinned Leaflet release + Subresource Integrity hashes (same pins as the
# sibling templates).
_LEAFLET_VERSION = "1.9.4"
_LEAFLET_CSS_SRI = "sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
_LEAFLET_JS_SRI = "sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="


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


_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Map — {title}</title>
<!-- Leaflet + markercluster + the basemap tiles load from the network; the
     photo and flight data (incl. thumbnails) is embedded below. -->
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
  .flight-popup {{ font: 13px/1.5 sans-serif; }}
  /* Playback control (issue #267) */
  .playback {{ background: #fff; border-radius: 4px; padding: 6px 10px;
              box-shadow: 0 1px 5px rgba(0,0,0,.4); display: flex;
              gap: 8px; align-items: center; flex-wrap: wrap;
              font: 13px/1 sans-serif; }}
  .playback button {{ border: none; background: none; cursor: pointer;
                     font-size: 15px; padding: 0; }}
  .playback input[type=range] {{ width: 140px; }}
  .playback span {{ font-variant-numeric: tabular-nums; }}
  .playback label {{ opacity: .7; }}
  .playback select {{ font: inherit; max-width: 160px; }}
</style>
</head>
<body>
<div id="map"></div>
{pano_overlay}
<script type="application/json" id="map-data">
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
const data = JSON.parse(document.getElementById('map-data').textContent);
const map = L.map('map');
__TILE_LAYER__

__SHARED_JS__

// Every feature carries properties.type (#322): photo pins and 360°
// panoramas from the photomap scanner, one track per flight from the
// flightmap scanner. The tag, not the geometry, decides the renderer — a
// single-fix flight arrives as a Point but is still a track.
const feats = data.features || [];
const byType = t => feats.filter(
  f => f.geometry && (f.properties || {}).type === t);
const photoFeatures = byType('photo').concat(byType('pano'));

__PHOTO_LAYER__

// Flight tracks: one coloured polyline per flight with the flightmap
// summary popup and a start dot; a single-fix clip degrades to the dot.
const overlays = {};
const allLatLngs = [];
const runs = [];   // playback (#267): flights with usable per-point times
byType('track').forEach((f, i) => {
  const color = PALETTE[i % PALETTE.length];
  const p = f.properties || {};
  const group = L.layerGroup();
  let latlngs;
  if (f.geometry.type === 'LineString') {
    latlngs = f.geometry.coordinates.map(c => [c[1], c[0]]);
    L.polyline(latlngs, { color, weight: 3 })
      .bindPopup(popupHtml(p)).addTo(group);
    const times = p.times_s;
    if (Array.isArray(times) && times.length === latlngs.length &&
        times[times.length - 1] > 0) {
      const name = p.name || `flight ${i + 1}`;
      runs.push({ latlngs, times, color, group, name, cursor: 0, marker: null });
    }
  } else {                                             // single-fix clip
    const c = f.geometry.coordinates;
    latlngs = [[c[1], c[0]]];
  }
  L.circleMarker(latlngs[0], { color, radius: 6, fillOpacity: 0.9 })
    .bindPopup(popupHtml(p)).addTo(group);
  group.addTo(map);
  const label = `<span style="color:${color}">&#9632;</span> ` +
                esc(p.name || `flight ${i + 1}`);
  overlays[label] = group;
  allLatLngs.push(...latlngs);
});

// One expanded layer control covers everything: the photo/pano rows reuse
// the pin CSS as legend swatches (photomap's rule), then one row per flight.
const allOverlays = {};
if (photoMarkers.length) {
  allOverlays['<span class="photo-pin pin-photo pin-swatch"></span>Photos'] =
    photoCluster;
}
if (panoMarkers.length) {
  allOverlays['<span class="photo-pin pin-pano pin-swatch"></span>360° panoramas'] =
    panoCluster;
}
Object.assign(allOverlays, overlays);
if (Object.keys(allOverlays).length > 1) {
  L.control.layers(null, allOverlays, { collapsed: false }).addTo(map);
}
__HOVER_CONTROL__

const bounds = photoLatLngs.concat(allLatLngs);
if (bounds.length > 1) {
  map.fitBounds(L.latLngBounds(bounds).pad(0.1), { maxZoom: 17 });
} else if (bounds.length === 1) {
  map.setView(bounds[0], 16);
} else {
  map.setView([0, 0], 2);
}
__PLAYBACK_JS__
"""


def mixed_to_html(
    points: list[PhotoPoint],
    tracks: list[Track],
    title: str,
    *,
    link_base: str | None = None,
    redact: str = "none",
    tile_style: str = DEFAULT_TILE_STYLE,
) -> str:
    """Return the complete self-contained combined HTML map.

    Same knobs as the parent templates, deliberately fewer of them: this is
    the simple mode. ``link_base`` gates the 360° viewer and original-photo
    links exactly as in :func:`.photomap_html.photos_to_html`; ``redact`` is
    the badge for coordinates the *scanners* already coarsened.
    """
    geojson = mixed_to_geojson(points, tracks, link_base=link_base, redact=redact)
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
            .replace("__HOVER_CONTROL__", HOVER_CONTROL_JS)
            .replace("__SHARED_JS__", FLIGHT_POPUP_JS)
            .replace("__PLAYBACK_JS__", PLAYBACK_JS)
            + (PANO_JS if pano_enabled else "")
        ).replace("__TILE_LAYER__", tile_layer_js(tile_style)),
    ))


def write_mixed_html(
    points: list[PhotoPoint],
    tracks: list[Track],
    output_path: Path,
    title: str,
    *,
    link_base: str | None = None,
    redact: str = "none",
    tile_style: str = DEFAULT_TILE_STYLE,
) -> Path:
    """Write the combined map to *output_path* and return it."""
    output_path.write_text(
        mixed_to_html(
            points, tracks, title,
            link_base=link_base, redact=redact, tile_style=tile_style,
        ),
        encoding="utf-8",
    )
    logger.info("HTML combined map created: %s", output_path)
    return output_path
