"""Render a photo list as a standalone, self-contained HTML map.

Same contract as :mod:`.html_viewer`: the photo GeoJSON (with base64 EXIF
thumbnails) is embedded in a ``<script type="application/json">`` block and a
small vanilla Leaflet app renders it. Markers are clustered with
Leaflet.markercluster so archive-scale folders (many shots per church, many
churches) stay readable. Leaflet, the cluster plugin, and the OpenStreetMap
basemap load from the network; the photo data itself is embedded.
"""

from __future__ import annotations

import json
import logging
from html import escape
from pathlib import Path

from .photomap import PhotoPoint, photos_to_geojson

logger = logging.getLogger(__name__)

# Pinned releases + Subresource Integrity hashes. Leaflet pins match
# html_viewer.py; the markercluster hashes were computed from the unpkg 1.5.3
# assets (sha256, base64) when this module was written.
_LEAFLET_VERSION = "1.9.4"
_LEAFLET_CSS_SRI = "sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
_LEAFLET_JS_SRI = "sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
_CLUSTER_VERSION = "1.5.3"
_CLUSTER_JS_SRI = "sha256-Hk4dIpcqOSb0hZjgyvFOP+cEmDXUKKNE/tT542ZbNQg="
_CLUSTER_CSS_SRI = "sha256-YU3qCpj/P06tdPBJGPax0bm6Q1wltfwjsho5TR4+TYc="
_CLUSTER_DEFAULT_CSS_SRI = "sha256-YSWCMtmNZNwqex4CEw1nQhvFub2lmU7vcCKP+XVwwXA="

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
<style>
  html, body {{ height: 100%; margin: 0; }}
  #map {{ height: 100%; }}
  .photo-popup img {{ max-width: 260px; display: block; margin-bottom: 4px; }}
</style>
</head>
<body>
<div id="map"></div>
<script type="application/json" id="photo-data">
{data}
</script>
<script src="https://unpkg.com/leaflet@{leaflet}/dist/leaflet.js"
        integrity="{leaflet_js_sri}" crossorigin=""></script>
<script src="https://unpkg.com/leaflet.markercluster@{cluster}/dist/leaflet.markercluster.js"
        integrity="{cluster_js_sri}" crossorigin=""></script>
<script>
{app_js}
</script>
</body>
</html>
"""

_APP_JS = """
const data = JSON.parse(document.getElementById('photo-data').textContent);
const map = L.map('map');
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

const esc = s => String(s).replace(/[&<>"']/g,
  ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));

const points = (data.features || []).filter(
  f => f.geometry && f.geometry.type === 'Point');
const cluster = L.markerClusterGroup();
const latlngs = [];
for (const f of points) {
  const c = f.geometry.coordinates;                  // [lon, lat, alt]
  const p = f.properties || {};
  latlngs.push([c[1], c[0]]);
  let html = '<div class="photo-popup">';
  if (p.thumb) {
    html += `<img src="data:image/jpeg;base64,${p.thumb}" alt="">`;
  }
  html += `<b>${esc(p.name || '')}</b>`;
  if (p.timestamp) html += `<br>${esc(p.timestamp)}`;
  if (p.camera) html += `<br>${esc(p.camera)}`;
  html += `<br>altitude: ${Number(p.alt || 0).toFixed(0)} m</div>`;
  cluster.addLayer(L.marker([c[1], c[0]]).bindPopup(html, { maxWidth: 300 }));
}
map.addLayer(cluster);
if (latlngs.length > 1) {
  map.fitBounds(L.latLngBounds(latlngs).pad(0.1));
} else if (latlngs.length === 1) {
  map.setView(latlngs[0], 16);
} else {
  map.setView([0, 0], 2);
}
"""


def photos_to_html(points: list[PhotoPoint], title: str) -> str:
    """Return a complete self-contained HTML photo map."""
    geojson = photos_to_geojson(points, include_thumbnails=True)
    # Escape "<" to "\\u003c" (a JSON Unicode escape) so JSON.parse round-trips
    # it while no literal "</script>" can break out of the data block.
    data = json.dumps(geojson).replace("<", "\\u003c")
    return _TEMPLATE.format(
        title=escape(title),
        leaflet=_LEAFLET_VERSION,
        leaflet_css_sri=_LEAFLET_CSS_SRI,
        leaflet_js_sri=_LEAFLET_JS_SRI,
        cluster=_CLUSTER_VERSION,
        cluster_css_sri=_CLUSTER_CSS_SRI,
        cluster_default_css_sri=_CLUSTER_DEFAULT_CSS_SRI,
        cluster_js_sri=_CLUSTER_JS_SRI,
        data=data,
        app_js=_APP_JS,
    )


def write_photos_html(points: list[PhotoPoint], output_path: Path, title: str) -> Path:
    """Write *points* as an HTML map to *output_path* and return it."""
    output_path.write_text(photos_to_html(points, title), encoding="utf-8")
    logger.info("HTML photo map created: %s", output_path)
    return output_path
