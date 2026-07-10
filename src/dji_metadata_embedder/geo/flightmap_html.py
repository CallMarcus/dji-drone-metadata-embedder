"""Render a multi-flight track list as a standalone, self-contained HTML map.

Same contract as :mod:`.html_viewer` and :mod:`.photomap_html`: the combined
flight GeoJSON is embedded in a ``<script type="application/json">`` block and
a small vanilla Leaflet app renders it — one coloured polyline per flight with
a start marker, a summary popup, and a layer control to toggle flights. Leaflet
and the OpenStreetMap basemap load from the network; the flight data itself is
embedded.
"""

from __future__ import annotations

import json
import logging
from html import escape
from pathlib import Path

from .flightmap import flights_to_geojson
from .track import Track

logger = logging.getLogger(__name__)

# Pinned Leaflet release + Subresource Integrity hashes (same pins as
# html_viewer.py / photomap_html.py).
_LEAFLET_VERSION = "1.9.4"
_LEAFLET_CSS_SRI = "sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
_LEAFLET_JS_SRI = "sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="

_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Flight map — {title}</title>
<!-- Leaflet + OpenStreetMap tiles load from the network; the flight data is
     embedded below, so this file is portable but not fully offline. -->
<link rel="stylesheet"
      href="https://unpkg.com/leaflet@{leaflet}/dist/leaflet.css"
      integrity="{css_sri}" crossorigin="" />
<style>
  html, body {{ height: 100%; margin: 0; }}
  #map {{ height: 100%; }}
  .flight-popup {{ font: 13px/1.5 sans-serif; }}
</style>
</head>
<body>
<div id="map"></div>
<script type="application/json" id="flight-data">
{data}
</script>
<script src="https://unpkg.com/leaflet@{leaflet}/dist/leaflet.js"
        integrity="{js_sri}" crossorigin=""></script>
<script>
{app_js}
</script>
</body>
</html>
"""

_APP_JS = """
const data = JSON.parse(document.getElementById('flight-data').textContent);
const map = L.map('map');
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

const esc = s => String(s).replace(/[&<>"']/g,
  ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));

// 12 visually distinct track colours, cycled when a folder has more flights.
const PALETTE = ['#e6194b', '#3cb44b', '#4363d8', '#f58231', '#911eb4',
                 '#42d4f4', '#f032e6', '#bfef45', '#469990', '#9a6324',
                 '#800000', '#000075'];

function fmtDuration(total) {
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const mm = h ? String(m).padStart(2, '0') : String(m);
  return (h ? h + ':' + mm : mm) + ':' + String(s).padStart(2, '0');
}

function popupHtml(p) {
  let html = `<div class="flight-popup"><b>${esc(p.name || '')}</b>`;
  if (p.start) html += `<br>${esc(p.start)}`;
  if (p.duration_s != null) html += `<br>duration: ${fmtDuration(p.duration_s)}`;
  if (p.alt_min != null) html += `<br>altitude: ${p.alt_min}–${p.alt_max} m`;
  html += `<br>${p.points} GPS point${p.points === 1 ? '' : 's'}`;
  if (p.segments) {
    html += `<br>${p.segments.length} size-split files: ` +
            `${esc(p.segments[0])} → ${esc(p.segments[p.segments.length - 1])}`;
  }
  html += '</div>';
  return html;
}

const overlays = {};
const allLatLngs = [];
(data.features || []).forEach((f, i) => {
  if (!f.geometry) return;
  const color = PALETTE[i % PALETTE.length];
  const p = f.properties || {};
  const group = L.layerGroup();
  let latlngs;
  if (f.geometry.type === 'LineString') {
    latlngs = f.geometry.coordinates.map(c => [c[1], c[0]]);
    L.polyline(latlngs, { color, weight: 3 })
      .bindPopup(popupHtml(p)).addTo(group);
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

if (allLatLngs.length > 1) {
  map.fitBounds(L.latLngBounds(allLatLngs).pad(0.1), { maxZoom: 17 });
} else if (allLatLngs.length === 1) {
  map.setView(allLatLngs[0], 16);
} else {
  map.setView([0, 0], 2);
}
if (Object.keys(overlays).length > 1) {
  L.control.layers(null, overlays).addTo(map);
}
"""


def flights_to_html(tracks: list[Track], title: str) -> str:
    """Return a complete self-contained HTML flight map."""
    geojson = flights_to_geojson(tracks)
    # Escape "<" to "\\u003c" (a JSON Unicode escape) so JSON.parse round-trips
    # it while no literal "</script>" can break out of the data block.
    data = json.dumps(geojson).replace("<", "\\u003c")
    return _TEMPLATE.format(
        title=escape(title),
        leaflet=_LEAFLET_VERSION,
        css_sri=_LEAFLET_CSS_SRI,
        js_sri=_LEAFLET_JS_SRI,
        data=data,
        app_js=_APP_JS,
    )


def write_flights_html(tracks: list[Track], output_path: Path, title: str) -> Path:
    """Write *tracks* as an HTML map to *output_path* and return it."""
    output_path.write_text(flights_to_html(tracks, title), encoding="utf-8")
    logger.info("HTML flight map created: %s", output_path)
    return output_path
