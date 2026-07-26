"""Render a multi-flight track list as a standalone 3D terrain HTML map.

Same embedding contract as :mod:`.flightmap_html` (issue #268): the combined
flight GeoJSON sits in a ``<script type="application/json">`` block and a
vanilla MapLibre GL JS app renders it — tracks draped over Mapterhorn
terrain under a tilted camera. MapLibre, the OSM basemap, and the terrain
tiles load from the network; the flight data itself is embedded.

Tracks are draped on the terrain surface: MapLibre cannot render line
layers at an elevation (upstream request maplibre/maplibre-gl-js#644), so
altitude appears in the popups, not the geometry. The ghost view (#372)
sidesteps that limit with ``calculateCameraOptionsFromCameraLngLatAltRotation``:
geometry stays draped, but the camera itself flies the recorded poses.

Terrain source: Mapterhorn (keyless, Copernicus GLO-30 base, global
coverage). Dormant fallback if Mapterhorn ever disappears: AWS Terrarium
tiles — ``https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png``
with ``"encoding": "terrarium"`` on the raster-dem sources.
"""

from __future__ import annotations

import json
import logging
from html import escape
from pathlib import Path

from .flightmap import flights_to_geojson
from .flightmap_js import FLIGHT_POPUP_JS
from .track import Track

logger = logging.getLogger(__name__)

# Pinned MapLibre GL JS release + Subresource Integrity hashes (UMD build;
# v6+ is ESM-only and cannot be pinned as a single script tag).
_MAPLIBRE_VERSION = "5.24.0"
_MAPLIBRE_CSS_SRI = "sha256-qx5w1Z7EBGW65+cDDaLzzPKBM/1QLmK9WY7vut/XpzI="
_MAPLIBRE_JS_SRI = "sha256-RamwepGJzlYFTGIKlHzPQeKR5YyV6bYVM7dAqqZe5cs="

_MAPTERHORN_TILEJSON = "https://tiles.mapterhorn.com/tilejson.json"
# Single host on purpose: OSM deprecated the a/b/c subdomain round-robin.
_OSM_TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"

_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>3D flight map — {title}</title>
<!-- MapLibre + OSM basemap + Mapterhorn terrain load from the network; the
     flight data is embedded below, so this file is portable but not fully
     offline. -->
<link rel="stylesheet"
      href="https://unpkg.com/maplibre-gl@{maplibre}/dist/maplibre-gl.css" integrity="{css_sri}"
      crossorigin="" />
<style>
  html, body {{ height: 100%; margin: 0; }}
  #map {{ height: 100%; }}
  .flight-popup {{ font: 13px/1.5 sans-serif; }}
  .fallback {{ font: 15px/1.6 sans-serif; margin: 2em auto; max-width: 34em; }}
  .flights-panel {{ position: absolute; top: 10px; left: 10px; z-index: 5;
                   background: #fff; border-radius: 4px; padding: 8px 12px;
                   box-shadow: 0 1px 5px rgba(0,0,0,.4);
                   font: 13px/1.8 sans-serif; max-height: 60%;
                   overflow-y: auto; }}
  .flights-panel label {{ display: block; cursor: pointer; }}
  .map-note {{ position: absolute; top: 10px; left: 50%;
              transform: translateX(-50%); z-index: 6; background: #fffbe6;
              border: 1px solid #e0d8a8; border-radius: 4px;
              padding: 6px 28px 6px 12px; font: 13px/1.4 sans-serif; }}
  .map-note button {{ position: absolute; right: 6px; top: 4px; border: none;
                     background: none; cursor: pointer; font-size: 14px; }}
  .ghost-open {{ display: block; margin-top: 6px; cursor: pointer; }}
</style>
</head>
<body>
<div id="map"></div>
<script type="application/json" id="flight-data">
{data}
</script>
<script src="https://unpkg.com/maplibre-gl@{maplibre}/dist/maplibre-gl.js" integrity="{js_sri}"
        crossorigin=""></script>
<script>
{app_js}
</script>
</body>
</html>
"""

_APP_JS = """
const data = JSON.parse(document.getElementById('flight-data').textContent);
const REDACTED = data.redacted || 'none';
__SHARED_JS__

// Collect flights: draped 2D geometry only — the third GeoJSON coordinate
// (altitude) is deliberately unused here (maplibre-gl-js#644).
const flights = [];
const allCoords = [];
(data.features || []).forEach((f, i) => {
  if (!f.geometry) return;
  const p = f.properties || {};
  const entry = {
    id: 'flight-' + i,
    name: p.name || `flight ${i + 1}`,
    color: PALETTE[i % PALETTE.length],
    props: p,
  };
  if (f.geometry.type === 'LineString') {
    entry.geometry = { type: 'LineString',
                       coordinates: f.geometry.coordinates.map(c => [c[0], c[1]]) };
    entry.pts = f.geometry.coordinates;      // full [lon, lat, alt] triples
    entry.times = p.times_s || null;
    entry.gyaw = p.gyaw_deg || null;
    entry.gpitch = p.gpitch_deg || null;
    entry.agl = p.agl_m || null;
    entry.vfov = p.vfov_deg || null;
  } else {                                             // single-fix clip
    const c = f.geometry.coordinates;
    entry.geometry = { type: 'Point', coordinates: [c[0], c[1]] };
  }
  flights.push(entry);
  const cs = entry.geometry.type === 'LineString'
    ? entry.geometry.coordinates : [entry.geometry.coordinates];
  allCoords.push(...cs);
});

function showNote(text, dismissible) {
  const note = document.createElement('div');
  note.className = 'map-note';
  note.appendChild(document.createTextNode(text));
  if (dismissible) {
    const x = document.createElement('button');
    x.textContent = '×';
    x.setAttribute('aria-label', 'Dismiss');
    x.addEventListener('click', () => note.remove());
    note.appendChild(x);
  }
  document.body.appendChild(note);
}

let map = null;
try {
  const options = {
    container: 'map',
    style: {
      version: 8,
      sources: {
        osm: { type: 'raster', tiles: ['__OSM_TILES__'], tileSize: 256,
               maxzoom: 19,
               attribution: '&copy; OpenStreetMap contributors' },
        terrain: { type: 'raster-dem', url: '__MAPTERHORN__',
                   attribution: 'Terrain &copy; Mapterhorn (Copernicus DEM)' },
        hillshade: { type: 'raster-dem', url: '__MAPTERHORN__' },
      },
      layers: [
        { id: 'osm', type: 'raster', source: 'osm' },
        { id: 'hillshade', type: 'hillshade', source: 'hillshade',
          paint: { 'hillshade-exaggeration': 0.35 } },
      ],
    },
    pitch: 60,
    maxPitch: 75,
  };
  if (allCoords.length) {
    const bounds = allCoords.reduce(
      (b, c) => b.extend(c),
      new maplibregl.LngLatBounds(allCoords[0], allCoords[0]));
    options.bounds = bounds;
    options.fitBoundsOptions = { padding: 60, pitch: 60, maxZoom: 15 };
  } else {
    options.center = [0, 20];
    options.zoom = 1.5;
  }
  map = new maplibregl.Map(options);
} catch (e) {
  // No WebGL (or MapLibre failed to start): plain-HTML fallback.
  document.getElementById('map').innerHTML =
    '<p class="fallback">This 3D view needs WebGL, which this browser ' +
    'does not provide. The flat map (flightmap.html) shows the same ' +
    'flights without it.</p>';
}

if (map) {
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }));

  let terrainFailed = false;
  map.on('error', ev => {
    // Mapterhorn unreachable → drop to a flat (still tilted) view once.
    const src = ev.sourceId || (ev.source && ev.source.id);
    if ((src === 'terrain' || src === 'hillshade') && !terrainFailed) {
      terrainFailed = true;
      map.setTerrain(null);
      if (map.getLayer('hillshade')) map.removeLayer('hillshade');
      showNote('Terrain tiles unavailable — showing flat view.', true);
    }
  });

  map.on('load', () => {
    map.setTerrain({ source: 'terrain', exaggeration: 1 });
    flights.forEach((f, fi) => {
      map.addSource(f.id, { type: 'geojson', data: {
        type: 'Feature', geometry: f.geometry, properties: {} } });
      if (f.geometry.type === 'LineString') {
        map.addLayer({ id: f.id, type: 'line', source: f.id,
          layout: { 'line-cap': 'round', 'line-join': 'round' },
          paint: { 'line-color': f.color, 'line-width': 3 } });
      } else {
        map.addLayer({ id: f.id, type: 'circle', source: f.id,
          paint: { 'circle-color': f.color, 'circle-radius': 6 } });
      }
      map.on('click', f.id, ev => {
        const el = document.createElement('div');
        el.innerHTML = popupHtml(f.props);
        const popup = new maplibregl.Popup({ maxWidth: '320px' })
          .setLngLat(ev.lngLat).setDOMContent(el).addTo(map);
        if (f.pts) {
          const btn = document.createElement('button');
          btn.className = 'ghost-open';
          btn.textContent = 'View from here';
          const ll = ev.lngLat;
          btn.addEventListener('click', () => {
            popup.remove();
            ghostEnter(fi, nearestSample(f, ll));
          });
          el.appendChild(btn);
        }
      });
      map.on('mouseenter', f.id, () => {
        map.getCanvas().style.cursor = 'pointer';
      });
      map.on('mouseleave', f.id, () => {
        map.getCanvas().style.cursor = '';
      });
    });
    buildPanel();
  });
}

function buildPanel() {
  if (!flights.length) return;
  const panel = document.createElement('div');
  panel.id = 'flights-panel';
  panel.className = 'flights-panel';
  flights.forEach(f => {
    const label = document.createElement('label');
    const box = document.createElement('input');
    box.type = 'checkbox';
    box.checked = true;
    box.addEventListener('change', () => {
      map.setLayoutProperty(f.id, 'visibility',
                            box.checked ? 'visible' : 'none');
    });
    label.appendChild(box);
    const swatch = document.createElement('span');
    swatch.textContent = ' \\u25a0 ';
    swatch.style.color = f.color;
    label.appendChild(swatch);
    label.appendChild(document.createTextNode(f.name));
    panel.appendChild(label);
  });
  document.body.appendChild(panel);
}

// --- Ghost Camera (#372): fly the free camera to the recorded drone pose ---
const GHOST_MAX_PITCH = 100;  // spike: setMaxPitch(120) OK, pitch 100 honoured
const GHOST_EST_PITCH = -30;  // assumed down-tilt when gimbal data is absent
const GHOST_HANDLERS = ['dragPan', 'dragRotate', 'scrollZoom', 'keyboard',
                        'doubleClickZoom', 'touchZoomRotate'];
const ghost = { active: false, flight: null, idx: 0, saved: null,
                savedFov: null, takeoffElev: null, hud: null,
                applied: null };

function nearestSample(fl, ll) {
  const cosLat = Math.cos(ll.lat * Math.PI / 180);
  let best = 0, bestD = Infinity;
  fl.pts.forEach((c, i) => {
    const dx = (c[0] - ll.lng) * cosLat, dy = c[1] - ll.lat;
    const d = dx * dx + dy * dy;
    if (d < bestD) { bestD = d; best = i; }
  });
  return best;
}

function courseBearing(pts, i) {
  const a = pts[Math.min(i, pts.length - 2)];
  const b = pts[Math.min(i + 1, pts.length - 1)];
  const toRad = Math.PI / 180;
  const dLon = (b[0] - a[0]) * toRad;
  const la1 = a[1] * toRad, la2 = b[1] * toRad;
  const y = Math.sin(dLon) * Math.cos(la2);
  const x = Math.cos(la1) * Math.sin(la2)
          - Math.sin(la1) * Math.cos(la2) * Math.cos(dLon);
  return ((Math.atan2(y, x) * 180 / Math.PI) + 360) % 360;
}

function samplePose(fl, i) {
  const c = fl.pts[i];
  let altitude;
  const aglHere = fl.agl && fl.agl[i] != null ? fl.agl[i] : null;
  if (ghost.takeoffElev != null && aglHere != null) {
    altitude = ghost.takeoffElev + aglHere;   // terrain-consistent height
  } else {
    altitude = c[2];                          // logged absolute altitude
  }
  let bearing, gp, estimated = false;
  if (fl.gyaw && fl.gyaw[i] != null) bearing = fl.gyaw[i];
  else { bearing = courseBearing(fl.pts, i); estimated = true; }
  if (fl.gpitch && fl.gpitch[i] != null) gp = fl.gpitch[i];
  else { gp = GHOST_EST_PITCH; estimated = true; }
  const wantPitch = 90 + gp;    // gimbal -90 (nadir) -> 0, 0 (horizon) -> 90
  return {
    lngLat: [c[0], c[1]], altitude,
    bearing, pitch: Math.max(0, Math.min(wantPitch, GHOST_MAX_PITCH)),
    clamped: wantPitch > GHOST_MAX_PITCH, estimated, aglHere,
    gimbalYaw: fl.gyaw ? fl.gyaw[i] : null,
    gimbalPitch: fl.gpitch ? fl.gpitch[i] : null,
  };
}

function applyPose(pose, ms) {
  // roll=0 explicitly: MapLibre 5.24.0 emits a 'roll' key even when the arg
  // is omitted, and jumpTo/easeTo crash on setRoll(NaN).
  const opts = map.calculateCameraOptionsFromCameraLngLatAltRotation(
    pose.lngLat, pose.altitude, pose.bearing, pose.pitch, 0);
  ghost.applied = { lng: pose.lngLat[0], lat: pose.lngLat[1],
                    altitude: pose.altitude, bearing: pose.bearing,
                    pitch: pose.pitch };
  if (ms) map.easeTo(Object.assign({}, opts, { duration: ms }));
  else map.jumpTo(opts);
}

function ghostKeys(ev) {
  if (ev.key === 'Escape') { ghostExit(); ev.preventDefault(); }
  else if (ev.key === 'ArrowLeft') { ghostStep(-1); ev.preventDefault(); }
  else if (ev.key === 'ArrowRight') { ghostStep(1); ev.preventDefault(); }
}

function ghostTakeoffElev(fl) {
  const p0 = fl.pts[0];
  // Gate on getTerrain(): with terrain failed/off, queryTerrainElevation
  // returns 0 (spike round 3) and would fake a sea-level takeoff.
  const elev = map.getTerrain && map.getTerrain()
    ? map.queryTerrainElevation([p0[0], p0[1]]) : null;
  return typeof elev === 'number' ? elev : null;
}

function ghostEnter(flightIdx, sampleIdx) {
  const fl = flights[flightIdx];
  if (ghost.active || !fl || !fl.pts) return;
  ghost.active = true;
  ghost.flight = fl;
  ghost.idx = Math.max(0, Math.min(sampleIdx, fl.pts.length - 1));
  // Attach Escape/arrows before any failure-prone work: if anything below
  // throws, the user can still exit instead of a frozen handlerless map.
  window.addEventListener('keydown', ghostKeys);
  ghost.saved = { center: map.getCenter(), zoom: map.getZoom(),
                  pitch: map.getPitch(), bearing: map.getBearing(),
                  maxPitch: map.getMaxPitch() };
  map.setMaxPitch(GHOST_MAX_PITCH);
  GHOST_HANDLERS.forEach(h => map[h] && map[h].disable());
  ghost.takeoffElev = ghostTakeoffElev(fl);
  if (ghost.takeoffElev != null && map.areTilesLoaded
      && !map.areTilesLoaded()) {
    // The takeoff DEM tile may not be in yet, and qte returns 0 until it
    // is (cold cache -> camera underground). Re-sample once the map
    // settles and re-apply the current pose.
    map.once('idle', () => {
      if (!ghost.active || ghost.flight !== fl) return;
      ghost.takeoffElev = ghostTakeoffElev(fl);
      applyPose(samplePose(fl, ghost.idx));
    });
  }
  if (fl.vfov && typeof map.setVerticalFieldOfView === 'function') {
    ghost.savedFov = map.getVerticalFieldOfView();
    map.setVerticalFieldOfView(fl.vfov);
  }
  applyPose(samplePose(fl, ghost.idx));
}

function ghostStep(d) {
  if (!ghost.active) return;
  const n = ghost.flight.pts.length;
  const next = Math.max(0, Math.min(ghost.idx + d, n - 1));
  if (next === ghost.idx) return;
  ghost.idx = next;
  applyPose(samplePose(ghost.flight, next));
}

function ghostExit() {
  if (!ghost.active) return;
  ghost.active = false;
  window.removeEventListener('keydown', ghostKeys);
  if (ghost.savedFov != null
      && typeof map.setVerticalFieldOfView === 'function') {
    map.setVerticalFieldOfView(ghost.savedFov);
    ghost.savedFov = null;
  }
  map.jumpTo({ center: ghost.saved.center, zoom: ghost.saved.zoom,
               pitch: ghost.saved.pitch, bearing: ghost.saved.bearing });
  map.setMaxPitch(ghost.saved.maxPitch);   // after jumpTo: pitch is legal again
  GHOST_HANDLERS.forEach(h => map[h] && map[h].enable());
  ghost.flight = null;
  ghost.takeoffElev = null;
}
"""


def flights_to_3d_html(
    tracks: list[Track], title: str, redact: str = "none"
) -> str:
    """Return a complete 3D-terrain HTML flight map (draped tracks)."""
    geojson = flights_to_geojson(tracks, redact=redact)
    # Escape "<" to "\\u003c" (a JSON Unicode escape) so JSON.parse round-trips
    # it while no literal "</script>" can break out of the data block.
    data = json.dumps(geojson).replace("<", "\\u003c")
    app_js = (
        _APP_JS.replace("__SHARED_JS__", FLIGHT_POPUP_JS)
        .replace("__OSM_TILES__", _OSM_TILES)
        .replace("__MAPTERHORN__", _MAPTERHORN_TILEJSON)
    )
    return _TEMPLATE.format(
        title=escape(title),
        maplibre=_MAPLIBRE_VERSION,
        css_sri=_MAPLIBRE_CSS_SRI,
        js_sri=_MAPLIBRE_JS_SRI,
        data=data,
        app_js=app_js,
    )


def write_flights_3d_html(
    tracks: list[Track], output_path: Path, title: str, redact: str = "none"
) -> Path:
    """Write *tracks* as a 3D HTML map to *output_path* and return it."""
    output_path.write_text(
        flights_to_3d_html(tracks, title, redact=redact), encoding="utf-8"
    )
    logger.info("3D HTML flight map created: %s", output_path)
    return output_path
