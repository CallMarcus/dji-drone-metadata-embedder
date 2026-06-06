"""Render a :class:`Track` as a standalone, self-contained HTML map.

The document embeds the same GeoJSON that :func:`track_to_geojson` produces
inside a ``<script type="application/json">`` block and ships a small vanilla
Leaflet app that draws the path colored by altitude. Leaflet and the
OpenStreetMap basemap tiles load from the network; the flight data itself is
embedded, so the file is portable but not fully offline.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .geojson import track_to_geojson
from .track import Track, build_track

logger = logging.getLogger(__name__)

# Pinned Leaflet release + Subresource Integrity hashes (see Task 1 Step 0).
_LEAFLET_VERSION = "1.9.4"
_LEAFLET_CSS_SRI = "sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
_LEAFLET_JS_SRI = "sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="

_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Flight path — {title}</title>
<!-- Leaflet + OpenStreetMap tiles load from the network; flight data is
     embedded below, so this file is portable but not fully offline. -->
<link rel="stylesheet"
      href="https://unpkg.com/leaflet@{leaflet}/dist/leaflet.css"
      integrity="{css_sri}" crossorigin="" />
<style>
  html, body {{ height: 100%; margin: 0; }}
  #map {{ height: 100%; }}
  .legend {{ background: #fff; padding: 6px 8px; font: 12px/1.4 sans-serif;
             box-shadow: 0 0 6px rgba(0,0,0,0.3); border-radius: 4px; }}
  .legend i {{ display: inline-block; width: 12px; height: 12px;
               margin-right: 4px; vertical-align: middle; }}
  .notice {{ position: absolute; top: 10px; left: 50%;
             transform: translateX(-50%); z-index: 1000; background: #fff;
             padding: 6px 10px; border-radius: 4px; font: 13px sans-serif;
             box-shadow: 0 0 6px rgba(0,0,0,0.3); }}
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

const features = data.features || [];
const line = features.find(f => f.geometry && f.geometry.type === 'LineString');
const points = features.filter(f => f.geometry && f.geometry.type === 'Point');

function altColor(alt, lo, hi) {
  const t = hi > lo ? (alt - lo) / (hi - lo) : 0;   // 0 (low) .. 1 (high)
  const hue = 240 * (1 - t);                        // 240=blue -> 0=red
  return `hsl(${hue}, 90%, 45%)`;
}

if (line) {
  const coords = line.geometry.coordinates;          // [lon, lat, alt]
  const alts = coords.map(c => c[2]);
  const lo = Math.min(...alts), hi = Math.max(...alts);
  const latlngs = coords.map(c => [c[1], c[0]]);
  for (let i = 0; i < coords.length - 1; i++) {
    const mid = (coords[i][2] + coords[i + 1][2]) / 2;
    L.polyline([latlngs[i], latlngs[i + 1]],
               { color: altColor(mid, lo, hi), weight: 4 }).addTo(map);
  }
  map.fitBounds(L.latLngBounds(latlngs).pad(0.1));
  L.circleMarker(latlngs[0], { color: '#2e7d32', radius: 7 })
    .bindPopup('Start').addTo(map);
  L.circleMarker(latlngs[latlngs.length - 1], { color: '#c62828', radius: 7 })
    .bindPopup('End').addTo(map);

  const legend = L.control({ position: 'bottomright' });
  legend.onAdd = function () {
    const div = L.DomUtil.create('div', 'legend');
    div.innerHTML =
      '<b>Altitude</b><br>' +
      `<i style="background:${altColor(hi, lo, hi)}"></i>${hi.toFixed(0)} m<br>` +
      `<i style="background:${altColor(lo, lo, hi)}"></i>${lo.toFixed(0)} m`;
    return div;
  };
  legend.addTo(map);
} else if (points.length) {
  const c = points[0].geometry.coordinates;
  map.setView([c[1], c[0]], 16);
} else {
  map.setView([0, 0], 2);
  const note = L.DomUtil.create('div', 'notice', document.body);
  note.textContent = 'No GPS track in this clip.';
}

for (const f of points) {
  const c = f.geometry.coordinates;                  // [lon, lat, alt]
  const p = f.properties || {};
  L.circleMarker([c[1], c[0]], { radius: 3, color: '#1565c0' })
    .bindPopup(
      `#${p.index}<br>alt: ${p.abs_alt} m<br>${p.timestamp}`
    ).addTo(map);
}
"""


def track_to_html(track: Track) -> str:
    """Return a complete self-contained HTML document for *track*."""
    geojson = track_to_geojson(track)
    # Escape "<" so a value containing "</script>" cannot break out of the
    # embedded data block. json.dumps already escapes nothing HTML-specific.
    data = json.dumps(geojson, indent=2).replace("<", "\\u003c")
    return _TEMPLATE.format(
        title=track.name,
        leaflet=_LEAFLET_VERSION,
        css_sri=_LEAFLET_CSS_SRI,
        js_sri=_LEAFLET_JS_SRI,
        data=data,
        app_js=_APP_JS,
    )


def write_html(track: Track, output_path: Path) -> Path:
    """Write *track* as an HTML map to *output_path* and return it."""
    output_path.write_text(track_to_html(track), encoding="utf-8")
    logger.info("HTML viewer created: %s", output_path)
    return output_path


def convert_to_html(
    srt_file: Path | str, output_file: Path | str | None = None, redact: str = "none"
) -> Path:
    """Convert a DJI SRT file to a standalone HTML map. Defaults to ``<srt>.html``."""
    srt_path = Path(srt_file)
    output_path = Path(output_file) if output_file else srt_path.with_suffix(".html")
    return write_html(build_track(srt_path, redact=redact), output_path)
