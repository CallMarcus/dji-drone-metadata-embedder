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
  .flights-panel hr {{ border: none; border-top: 1px solid #ddd;
                      margin: 6px 0; }}
  .map-note {{ position: absolute; top: 10px; left: 50%;
              transform: translateX(-50%); z-index: 6; background: #fffbe6;
              border: 1px solid #e0d8a8; border-radius: 4px;
              padding: 6px 28px 6px 12px; font: 13px/1.4 sans-serif; }}
  .map-note button {{ position: absolute; right: 6px; top: 4px; border: none;
                     background: none; cursor: pointer; font-size: 14px; }}
  .ghost-open {{ display: block; margin-top: 6px; cursor: pointer; }}
  .ghost-hud {{ position: absolute; bottom: 14px; left: 50%;
               transform: translateX(-50%); z-index: 6;
               background: rgba(20,20,24,.85); color: #fff;
               border-radius: 6px; padding: 8px 14px;
               font: 13px/1.6 sans-serif; display: flex; gap: 12px;
               align-items: center; max-width: 92vw; flex-wrap: wrap; }}
  .ghost-hud button {{ border: none; background: #444; color: #fff;
                      border-radius: 4px; cursor: pointer; font-size: 14px;
                      padding: 2px 9px; }}
  .ghost-badge {{ background: #b58900; color: #fff; border-radius: 3px;
                 padding: 0 6px; font-size: 11px; }}
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
    shown: true,
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
      addSculpture(f, fi);
    });
    map.on('zoomend', rebuildSculpture);
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
      f.shown = box.checked;
      map.setLayoutProperty(f.id, 'visibility',
                            box.checked ? 'visible' : 'none');
      applySculptVisibility();
    });
    label.appendChild(box);
    const swatch = document.createElement('span');
    swatch.textContent = ' \\u25a0 ';
    swatch.style.color = f.color;
    label.appendChild(swatch);
    label.appendChild(document.createTextNode(f.name));
    panel.appendChild(label);
  });
  if (flights.some(f => f.sculptSrc)) {
    panel.appendChild(document.createElement('hr'));
    const label = document.createElement('label');
    const box = document.createElement('input');
    box.type = 'checkbox';
    box.id = 'sculpture-toggle';
    box.checked = sculpture.on;
    box.addEventListener('change', () => {
      sculpture.on = box.checked;
      applySculptVisibility();
    });
    label.appendChild(box);
    label.appendChild(document.createTextNode(' Sculpture'));
    panel.appendChild(label);
  }
  document.body.appendChild(panel);
}

// --- Ghost Camera (#372): fly the free camera to the recorded drone pose ---
const GHOST_MAX_PITCH = 100;  // spike: setMaxPitch(120) OK, pitch 100 honoured
const GHOST_EST_PITCH = -30;  // assumed down-tilt when gimbal data is absent
const GHOST_ENTER_MS = 1200, GHOST_STEP_MS = 150;
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
  applySculptVisibility();   // a ribbon at the camera's own altitude would
                            // sit across the cockpit view
  ghost.flight = fl;
  ghost.idx = Math.max(0, Math.min(sampleIdx, fl.pts.length - 1));
  // Attach Escape/arrows before any failure-prone work: if anything below
  // throws, the user can still exit instead of a frozen handlerless map.
  window.addEventListener('keydown', ghostKeys);
  if (!ghost.saved) {
    // Survives exit -> rapid re-enter while the exit ease still runs, so
    // a re-entry never captures a mid-transition camera as "the view to
    // restore". Cleared only when a restore actually completes.
    ghost.saved = { center: map.getCenter(), zoom: map.getZoom(),
                    pitch: map.getPitch(), bearing: map.getBearing(),
                    maxPitch: map.getMaxPitch() };
  }
  map.setMaxPitch(GHOST_MAX_PITCH);
  GHOST_HANDLERS.forEach(h => map[h] && map[h].disable());
  ghost.takeoffElev = ghostTakeoffElev(fl);
  if (ghost.takeoffElev != null && map.areTilesLoaded
      && !map.areTilesLoaded()) {
    // 'idle' can park under eased transitions before late DEM tiles land
    // (the render loop stops at moveend), so poll on a timer instead:
    // firm up the takeoff height once tiles deliver it, then ease to the
    // corrected pose. A genuine sea-level 0 just keeps the initial pose.
    let tries = 20;
    const retry = () => {
      if (!ghost.active || ghost.flight !== fl) return;
      const elev = ghostTakeoffElev(fl);
      if (typeof elev === 'number' && elev !== 0) {
        if (elev !== ghost.takeoffElev) {
          ghost.takeoffElev = elev;
          applyPose(samplePose(fl, ghost.idx), GHOST_STEP_MS);
        }
      } else if (--tries > 0) {
        setTimeout(retry, 250);
      }
    };
    setTimeout(retry, 250);
  }
  if (fl.vfov && typeof map.setVerticalFieldOfView === 'function') {
    ghost.savedFov = map.getVerticalFieldOfView();
    map.setVerticalFieldOfView(fl.vfov);
  }
  applyPose(samplePose(fl, ghost.idx), GHOST_ENTER_MS);
  mountHud();
}

function ghostStep(d) {
  if (!ghost.active) return;
  const n = ghost.flight.pts.length;
  const next = Math.max(0, Math.min(ghost.idx + d, n - 1));
  if (next === ghost.idx) return;
  ghost.idx = next;
  applyPose(samplePose(ghost.flight, next), GHOST_STEP_MS);
  updateHud();
}

function ghostExit() {
  if (!ghost.active) return;
  ghost.active = false;
  applySculptVisibility();
  window.removeEventListener('keydown', ghostKeys);
  // Keep this FOV restore ABOVE the easeTo and once('moveend') below:
  // setVerticalFieldOfView fires moveend synchronously, and a listener
  // registered first would consume it and self-restore mid-ease.
  if (ghost.savedFov != null
      && typeof map.setVerticalFieldOfView === 'function') {
    map.setVerticalFieldOfView(ghost.savedFov);
    ghost.savedFov = null;
  }
  const saved = ghost.saved;
  map.easeTo({ center: saved.center, zoom: saved.zoom, pitch: saved.pitch,
               bearing: saved.bearing, duration: GHOST_ENTER_MS });
  map.once('moveend', () => {
    // Interrupting this ease (MapLibre fires moveend for aborted eases
    // too, e.g. a rapid ghost re-entry) must not restore mid-session:
    // that would unlock the camera inside the new ghost session.
    if (ghost.active) return;
    map.setMaxPitch(saved.maxPitch);
    GHOST_HANDLERS.forEach(h => map[h] && map[h].enable());
    ghost.saved = null;
  });
  unmountHud();
  ghost.flight = null;
  ghost.takeoffElev = null;
}

function mountHud() {
  const hud = document.createElement('div');
  hud.id = 'ghost-hud';
  hud.className = 'ghost-hud';
  const mk = (id, text, fn) => {
    const b = document.createElement('button');
    b.id = id; b.textContent = text;
    b.addEventListener('click', fn);
    return b;
  };
  const info = document.createElement('span');
  info.id = 'ghost-info';
  const badges = document.createElement('span');
  badges.id = 'ghost-badges';
  const exit = mk('ghost-exit', '\\u00d7', ghostExit);
  exit.setAttribute('aria-label', 'Exit ghost view');
  hud.append(mk('ghost-prev', '\\u2039', () => ghostStep(-1)),
             info, badges,
             mk('ghost-next', '\\u203a', () => ghostStep(1)),
             exit);
  document.body.appendChild(hud);
  ghost.hud = hud;
  updateHud();
}

function unmountHud() {
  if (ghost.hud) { ghost.hud.remove(); ghost.hud = null; }
}

function updateHud() {
  if (!ghost.hud) return;
  const fl = ghost.flight, i = ghost.idx;
  const pose = samplePose(fl, i);
  let txt = fl.name;
  if (fl.times) {
    txt += ' \\u00b7 ' + fmtDuration(Math.round(fl.times[i])) + ' / '
         + fmtDuration(Math.round(fl.times[fl.times.length - 1]));
  }
  txt += ' \\u00b7 ' + (pose.aglHere != null
    ? pose.aglHere.toFixed(0) + ' m above takeoff'
    : fl.pts[i][2].toFixed(0) + ' m (as logged)');
  if (pose.gimbalYaw != null || pose.gimbalPitch != null) {
    const deg = v => v != null ? v.toFixed(0) + '\\u00b0' : '\\u2014';
    txt += ' \\u00b7 gimbal ' + deg(pose.gimbalYaw) + ' / '
         + deg(pose.gimbalPitch);
  }
  ghost.hud.querySelector('#ghost-info').textContent = txt;
  const badges = ghost.hud.querySelector('#ghost-badges');
  badges.textContent = '';
  const badge = t => {
    const s = document.createElement('span');
    s.className = 'ghost-badge';
    s.textContent = t;
    badges.appendChild(s);
  };
  if (pose.clamped) badge('pitch clamped to ' + GHOST_MAX_PITCH + '\\u00b0');
  if (pose.estimated) badge('estimated view \\u2014 no gimbal data');
  if (REDACTED === 'fuzz') badge('position fuzzed ~100 m');
}

// --- Flight sculpture (#375): AGL curtain + true-altitude ribbon ---
// fill-extrusion base/height are measured from the terrain surface (the
// shader applies get_elevation(a_centroid)), so agl_m drops straight in --
// no queryTerrainElevation, no cold-DEM race. A custom WebGL layer cannot
// be used here at all: with terrain on, MapLibre depth-rejects every
// fragment of a custom '3d' layer (spike, #375).
const SCULPT_RIBBON_M = 6;    // solid slab thickness at flight altitude
const SCULPT_PX = 3;          // target plank width, screen pixels
const SCULPT_MIN_M = 4, SCULPT_MAX_M = 60;
const sculpture = { on: true, widthM: null };

function sculptWidthM() {
  // Hold a roughly constant screen width: a fixed metre width vanishes
  // when you zoom out to see the whole flight, and becomes a slab up close.
  const mPerPx = 40075016.686 * Math.cos(map.getCenter().lat * Math.PI / 180)
               / (512 * Math.pow(2, map.getZoom()));
  return Math.max(SCULPT_MIN_M,
                  Math.min(mPerPx * SCULPT_PX, SCULPT_MAX_M));
}

function planksFor(fl, widthM) {
  // One rectangle per consecutive pair that has AGL at both ends.
  const feats = [];
  if (!fl.pts || !fl.agl) return feats;
  const half = widthM / 2;
  for (let i = 0; i < fl.pts.length - 1; i++) {
    const a = fl.pts[i], b = fl.pts[i + 1];
    const aglA = fl.agl[i], aglB = fl.agl[i + 1];
    // A null AGL breaks the curtain: the gap length is unknown, so
    // interpolating across it would invent altitude.
    if (aglA == null || aglB == null) continue;
    const agl = (aglA + aglB) / 2;
    // A negative mean AGL (rooftop/cliff-top launch: rel_alt is signed and
    // not clamped upstream) breaks the curtain too: fill-extrusion cannot
    // render below the terrain surface at all (the style spec floors base
    // at 0), so a below-takeoff segment has no honest representation.
    // Breaking the curtain is truthful; inventing a zero-height slab is not.
    if (agl < 0) continue;
    const mLat = 111320;
    const mLon = 111320 * Math.cos((a[1] + b[1]) / 2 * Math.PI / 180);
    const dx = (b[0] - a[0]) * mLon, dy = (b[1] - a[1]) * mLat;
    const len = Math.sqrt(dx * dx + dy * dy);
    if (!len) continue;                 // duplicate fix: no direction
    const ox = -dy / len * half / mLon, oy = dx / len * half / mLat;
    feats.push({
      type: 'Feature',
      // rbase is clamped here rather than in a paint expression: the
      // style spec forbids a negative fill-extrusion-base, and a hover
      // lower than the ribbon thickness would compute one.
      properties: { agl: agl, rbase: Math.max(0, agl - SCULPT_RIBBON_M) },
      geometry: { type: 'Polygon', coordinates: [[
        [a[0] + ox, a[1] + oy], [b[0] + ox, b[1] + oy],
        [b[0] - ox, b[1] - oy], [a[0] - ox, a[1] - oy],
        [a[0] + ox, a[1] + oy],
      ]] },
    });
  }
  return feats;
}

function addSculpture(fl, fi) {
  if (sculpture.widthM == null) sculpture.widthM = sculptWidthM();
  const feats = planksFor(fl, sculpture.widthM);
  if (!feats.length) return;
  const src = 'sculpt-' + fi;
  map.addSource(src, { type: 'geojson',
    data: { type: 'FeatureCollection', features: feats } });
  map.addLayer({ id: src + '-curtain', type: 'fill-extrusion', source: src,
    paint: { 'fill-extrusion-color': fl.color,
             'fill-extrusion-base': 0,
             'fill-extrusion-height': ['get', 'agl'],
             'fill-extrusion-opacity': 0.35,
             // Built-in gradient darkens the sides toward the ground: the
             // fade cannot be alpha (the shader hardcodes colour alpha to
             // 1.0 and fill-extrusion-opacity is layer-level only).
             'fill-extrusion-vertical-gradient': true } });
  map.addLayer({ id: src + '-ribbon', type: 'fill-extrusion', source: src,
    paint: { 'fill-extrusion-color': fl.color,
             'fill-extrusion-base': ['get', 'rbase'],
             'fill-extrusion-height': ['get', 'agl'],
             'fill-extrusion-opacity': 1,
             'fill-extrusion-vertical-gradient': false } });
  fl.sculptSrc = src;
}

function applySculptVisibility() {
  flights.forEach(fl => {
    if (!fl.sculptSrc) return;
    // Ghost mode hides it: a solid ribbon at the camera's own altitude
    // would sit across the cockpit view.
    const v = (sculpture.on && fl.shown && !ghost.active) ? 'visible' : 'none';
    ['-curtain', '-ribbon'].forEach(sfx => {
      const id = fl.sculptSrc + sfx;
      if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', v);
    });
  });
}

function rebuildSculpture() {
  const w = sculptWidthM();
  // Ignore trivial changes: setData on every zoom frame would churn.
  if (sculpture.widthM != null && Math.abs(w - sculpture.widthM) < 0.5) return;
  sculpture.widthM = w;
  flights.forEach(fl => {
    if (!fl.sculptSrc) return;
    const src = map.getSource(fl.sculptSrc);
    if (src) src.setData({ type: 'FeatureCollection',
                           features: planksFor(fl, w) });
  });
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
