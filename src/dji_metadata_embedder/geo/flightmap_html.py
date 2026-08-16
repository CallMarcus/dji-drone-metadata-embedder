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
from .flightmap_airspace_js import AIRSPACE_OVERLAY_JS
from .flightmap_js import FLIGHT_POPUP_JS, PLAYBACK_JS
from .provenance import stamp
from .tiles import DEFAULT_TILE_STYLE, tile_layer_js
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
{airspace_css}</style>
</head>
<body>
<div id="map"></div>
<script type="application/json" id="flight-data">
{data}
</script>{airspace_block}
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
__TILE_LAYER__

__SHARED_JS__

const overlays = {};
const allLatLngs = [];
const runs = [];   // playback (#267): flights with usable per-point times
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
__AIRSPACE_JS__
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
__PLAYBACK_JS__
"""


_AIRSPACE_CSS = """  .airspace-note { background: rgba(255,255,255,.85);
                   border-radius: 4px; padding: 4px 8px;
                   font: 12px/1.5 sans-serif; max-width: 320px; }
  .airspace-label { background: rgba(255,255,255,.75); border: none;
                    box-shadow: none; color: #2b3a4a; padding: 1px 4px;
                    font: 11px/1.2 sans-serif; }
  .airspace-label::before { display: none; }
"""


def flights_to_html(
    tracks: list[Track], title: str, *, tile_style: str = DEFAULT_TILE_STYLE,
    redact: str = "none", airspace_json: dict | None = None
) -> str:
    """Return a complete self-contained HTML flight map.

    ``tile_style`` (issue #311): a :data:`~.tiles.TILE_STYLES` key selecting
    the basemap drawn under the tracks.

    ``airspace_json`` (#413): the overlay dict from
    :func:`~.airspace.overlay.zones_to_overlay_json`; None renders the map
    exactly as before.
    """
    geojson = flights_to_geojson(tracks, redact=redact)
    # Escape "<" to "\\u003c" (a JSON Unicode escape) so JSON.parse round-trips
    # it while no literal "</script>" can break out of the data block.
    data = json.dumps(geojson).replace("<", "\\u003c")
    airspace_block = airspace_css = airspace_js = ""
    if airspace_json is not None:
        adata = json.dumps(airspace_json).replace("<", "\\u003c")
        airspace_block = (
            '\n<script type="application/json" id="airspace-data">\n'
            f"{adata}\n</script>"
        )
        airspace_css = _AIRSPACE_CSS
        airspace_js = AIRSPACE_OVERLAY_JS
    return stamp(_TEMPLATE.format(
        title=escape(title),
        leaflet=_LEAFLET_VERSION,
        css_sri=_LEAFLET_CSS_SRI,
        js_sri=_LEAFLET_JS_SRI,
        data=data,
        airspace_block=airspace_block,
        airspace_css=airspace_css,
        app_js=_APP_JS.replace("__TILE_LAYER__", tile_layer_js(tile_style))
        .replace("__SHARED_JS__", FLIGHT_POPUP_JS)
        .replace("__AIRSPACE_JS__", airspace_js)
        .replace("__PLAYBACK_JS__", PLAYBACK_JS),
    ))


def write_flights_html(
    tracks: list[Track],
    output_path: Path,
    title: str,
    *,
    tile_style: str = DEFAULT_TILE_STYLE,
    redact: str = "none",
    airspace_json: dict | None = None,
) -> Path:
    """Write *tracks* as an HTML map to *output_path* and return it."""
    output_path.write_text(
        flights_to_html(
            tracks, title, tile_style=tile_style, redact=redact, airspace_json=airspace_json
        ),
        encoding="utf-8",
    )
    logger.info("HTML flight map created: %s", output_path)
    return output_path
