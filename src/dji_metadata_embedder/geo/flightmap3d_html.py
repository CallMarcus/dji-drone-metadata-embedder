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
  .panel-note {{ opacity: .7; font-size: 11px; }}
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
  .ghost-video {{ position: absolute; top: 0; left: 50%; height: 100%;
                 width: auto; transform: translateX(-50%);
                 pointer-events: none; z-index: 1;
                 transition: opacity .18s linear; }}
  #ghost-hud #ghost-blend {{ width: 110px; }}
  .playback {{ position: absolute; bottom: 14px; left: 10px; z-index: 6;
              background: #fff; border-radius: 4px; padding: 6px 10px;
              box-shadow: 0 1px 5px rgba(0,0,0,.4); display: flex;
              gap: 6px; align-items: center; flex-wrap: wrap;
              font: 13px/1.4 sans-serif; max-width: 92vw; }}
  .playback button {{ border: none; background: none; cursor: pointer;
                     font-size: 15px; padding: 0 4px; }}
  .playback input[type=range] {{ width: 140px; }}
  .playback span {{ font-variant-numeric: tabular-nums; }}
  .playback select {{ font: inherit; max-width: 160px; }}
  .gaze-pass {{ font: inherit; margin: 3px 4px 0 0; cursor: pointer;
               border: 1px solid #bbb; border-radius: 3px;
               background: #f6f6f6; padding: 1px 6px; }}
  .gaze-est {{ margin-top: 4px; opacity: .7; font-size: 11px; }}
  .gaze-skip {{ margin-top: 4px; opacity: .7; font-size: 11px; }}
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
    entry.hfov = p.hfov_deg || null;
    entry.media = p.media || null;
    entry.cue = p.cue_s || null;
    entry.segi = p.seg_i || null;
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
    sculptSettle();
    buildPanel();
    mountPlayback();
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
      applyGazeVisibility();
      // A lookup highlight can span several flights, so there is no cheap
      // way to tell here which of its passes still belong to a shown flight
      // -- clearing it is the simple, honest choice: it can always be
      // reopened by clicking the spot again (#378 whole-branch review, M1).
      gazeHighlight([]);
    });
    label.appendChild(box);
    const swatch = document.createElement('span');
    swatch.textContent = ' \\u25a0 ';
    swatch.style.color = f.color;
    label.appendChild(swatch);
    label.appendChild(document.createTextNode(f.name));
    panel.appendChild(label);
  });
  if (REDACTED !== 'none' && runs.length) {
    const note = document.createElement('div');
    note.className = 'panel-note';
    // The crossfade gate (mountCrossfade) withholds the same way the gaze
    // gate does, but has no HUD of its own to say so while the cockpit is
    // closed -- state it here too, same shape as the gaze note (#380
    // whole-branch review I1).
    note.textContent = flights.some(f => f.media)
      ? 'Camera gaze and video crossfade off \\u2014 positions fuzzed'
      : 'Camera gaze off \\u2014 positions fuzzed';
    panel.appendChild(note);
  }
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
  else if (ev.key === 'v' || ev.key === 'V') {
    setBlend(cross.blend > 0.5 ? 0 : 1);
    ev.preventDefault();
  }
}

function terrainElevAt(lngLat) {
  // Gate on getTerrain(): queryTerrainElevation returns null when terrain is
  // off, but 0 (not null) when terrain is on and its tiles are still cold
  // (#372 spike round 3).
  if (!(map.getTerrain && map.getTerrain())) return null;
  const e = map.queryTerrainElevation(lngLat);
  return typeof e === 'number' ? e : null;
}

function takeoffElev(fl) {
  const p0 = fl.pts[0];
  return terrainElevAt([p0[0], p0[1]]);
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
  applySculptVisibility();   // a ribbon at the camera's own altitude would
                            // sit across the cockpit view
  applyGazeVisibility();
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
  ghost.takeoffElev = takeoffElev(fl);
  if (ghost.takeoffElev != null && map.areTilesLoaded
      && !map.areTilesLoaded()) {
    // 'idle' can park under eased transitions before late DEM tiles land
    // (the render loop stops at moveend), so poll on a timer instead:
    // firm up the takeoff height once tiles deliver it, then ease to the
    // corrected pose. A genuine sea-level 0 just keeps the initial pose.
    let tries = 20;
    const retry = () => {
      if (!ghost.active || ghost.flight !== fl) return;
      const elev = takeoffElev(fl);
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
  // Riding: jump in. The cinematic ease would be overridden by the next
  // playback frame, and eases here are the moveend hazard. Only true when
  // the clock is actually driving THIS flight -- a different flight's clock
  // running must not skip the cinematic entry for nothing.
  const riding = pb.playing && pb.run === fl;
  if (riding) {
    // The click wins: seek playback to the clicked sample instead of
    // snapping the camera back to pb.t on the very next driven frame.
    pb.t = fl.times[ghost.idx];
  }
  applyPose(samplePose(fl, ghost.idx), riding ? 0 : GHOST_ENTER_MS);
  mountHud();
  mountCrossfade();
}

function ghostStep(d) {
  if (!ghost.active) return;
  // Manual control wins over the clock -- but only the clock driving THIS
  // flight; stepping in one flight's cockpit must not stop another
  // flight's playback.
  if (pb.playing && pb.run === ghost.flight) pbPause();
  const n = ghost.flight.pts.length;
  const next = Math.max(0, Math.min(ghost.idx + d, n - 1));
  if (next === ghost.idx) return;
  ghost.idx = next;
  if (pb.run === ghost.flight) {
    // Keep the clock in step with the cockpit, so the gaze patch on the
    // ground matches the second the camera is now looking from.
    // pbRender(true) SKIPS the per-frame ghost drive on purpose: that drive
    // jumpTo's to this same pose, and being instant it would beat the eased
    // step below, turning every arrow key into a hard cut. The patch is data
    // and updates now; the camera is motion and glides.
    pb.t = ghost.flight.times[next];
    pbRender(true);
  }
  applyPose(samplePose(ghost.flight, next), GHOST_STEP_MS);
  updateHud();
  renderCrossfade();
}

function ghostExit() {
  if (!ghost.active) return;
  ghost.active = false;
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
    applySculptVisibility();
    applyGazeVisibility();
  });
  unmountHud();
  unmountCrossfade();
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
             mk('ghost-next', '\\u203a', () => ghostStep(1)));
  if (hasMedia(ghost.flight)) {
    const blend = document.createElement('input');
    blend.type = 'range';
    blend.id = 'ghost-blend';
    blend.min = '0';
    blend.max = '100';
    blend.value = '0';
    blend.title = 'Blend the map into the footage';
    blend.addEventListener('input',
                           () => setBlend(Number(blend.value) / 100));
    hud.appendChild(blend);
  }
  hud.appendChild(exit);
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
// fill-extrusion base/height are measured from the LOCAL terrain surface
// under each segment (the shader applies get_elevation(a_centroid)), but
// agl_m is height above the single TAKEOFF point -- planksFor() converts
// through terrainElevAt() so the rendered height is true ground clearance.
// A custom WebGL layer cannot be used here at all: with terrain on,
// MapLibre depth-rejects every fragment of a custom '3d' layer (spike, #375).
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
  const tElev = takeoffElev(fl);
  for (let i = 0; i < fl.pts.length - 1; i++) {
    const a = fl.pts[i], b = fl.pts[i + 1];
    const aglA = fl.agl[i], aglB = fl.agl[i + 1];
    // A null AGL breaks the curtain: the gap length is unknown, so
    // interpolating across it would invent altitude.
    if (aglA == null || aglB == null) continue;
    const agl = (aglA + aglB) / 2;
    const lElev = tElev == null
      ? null : terrainElevAt([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]);
    // agl is height above TAKEOFF, but fill-extrusion measures from the
    // LOCAL surface under this segment. Converting through both elevations
    // puts the ribbon at the drone's true altitude, so the curtain's length
    // is real ground clearance: fly level at a rising ridge and it shortens.
    // With terrain off both are null and agl is already right, because
    // get_elevation returns 0 and the extrusion measures from sea level.
    const hgt = (tElev != null && lElev != null)
      ? (tElev + agl) - lElev : agl;
    // Non-positive: the drone is at or below the rendered surface (rooftop
    // launch, or a DEM/datum artefact near a cliff). fill-extrusion cannot
    // render below the terrain at all, so break the curtain rather than
    // invent a flat slab.
    if (hgt <= 0) continue;
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
      properties: { hgt: hgt, rbase: Math.max(0, hgt - SCULPT_RIBBON_M) },
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
  // Gate on the DATA, not on this build's output: with terrain in play a
  // build can legitimately come back empty (canopy-height flight, cold
  // tiles) and a later settle must still be able to populate it. Bailing
  // here would strand the flight without a source, and with it the panel's
  // Sculpture toggle.
  if (!(fl.pts && fl.agl && fl.agl.some(v => v != null))) return;
  if (sculpture.widthM == null) sculpture.widthM = sculptWidthM();
  const feats = planksFor(fl, sculpture.widthM);
  const src = 'sculpt-' + fi;
  map.addSource(src, { type: 'geojson',
    data: { type: 'FeatureCollection', features: feats } });
  map.addLayer({ id: src + '-curtain', type: 'fill-extrusion', source: src,
    paint: { 'fill-extrusion-color': fl.color,
             'fill-extrusion-base': 0,
             'fill-extrusion-height': ['get', 'hgt'],
             'fill-extrusion-opacity': 0.35,
             // Built-in gradient darkens the sides toward the ground: the
             // fade cannot be alpha (the shader hardcodes colour alpha to
             // 1.0 and fill-extrusion-opacity is layer-level only).
             'fill-extrusion-vertical-gradient': true } });
  map.addLayer({ id: src + '-ribbon', type: 'fill-extrusion', source: src,
    paint: { 'fill-extrusion-color': fl.color,
             'fill-extrusion-base': ['get', 'rbase'],
             'fill-extrusion-height': ['get', 'hgt'],
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

function setSculptData() {
  flights.forEach(fl => {
    if (!fl.sculptSrc) return;
    const src = map.getSource(fl.sculptSrc);
    if (src) src.setData({ type: 'FeatureCollection',
                           features: planksFor(fl, sculpture.widthM) });
  });
}

function rebuildSculpture() {
  const w = sculptWidthM();
  // Ignore trivial changes: setData on every zoom frame would churn.
  if (sculpture.widthM != null && Math.abs(w - sculpture.widthM) < 0.5) return;
  sculpture.widthM = w;
  setSculptData();
  renderGaze();
}

function sculptSettle() {
  // Cold DEM tiles make queryTerrainElevation answer 0, so the first build
  // is a flat-mode approximation. Re-sample on a bounded timer and rebuild
  // when the terrain firms up. 'idle' cannot be used: it parks under the
  // load-time fitBounds ease (#372). areTilesLoaded() alone is not enough
  // either -- it counts errored tiles as loaded and can flicker true before
  // the DEM is usable -- so require a non-zero sample. A genuine sea-level
  // takeoff is indistinguishable from "not loaded yet" and simply settles
  // on the final pass. A partially warm DEM can also give mixed readings
  // (inflated heights, or segments briefly dropped); the rebuild fixes it.
  if (!(map.getTerrain && map.getTerrain())) return;
  const probe = flights.find(fl => fl.pts && fl.agl);
  if (!probe) return;
  let tries = 20;
  const retry = () => {
    const e = takeoffElev(probe);
    if ((typeof e === 'number' && e !== 0) || --tries <= 0) {
      setSculptData();
      // The load-time beam was built against cold tiles; it rides this same
      // bounded retry rather than starting a second timer. During playback
      // every sample change rebuilds it anyway.
      renderGaze();
      return;
    }
    setTimeout(retry, 250);
  };
  setTimeout(retry, 250);
}

// --- Camera's Gaze (#378): the ground the camera actually saw ---
// gazeRing() is a port of geometry.frustum_ground_ring -- the four frustum
// corner rays projected onto flat ground at the drone's AGL reference, then
// draped by the fill layer. A cross-language parity test compares it to the
// Python corner by corner, because the same projection ships in --footprint
// exports and the two must not drift. Rings are NOT embedded in the HTML:
// they are derivable, and at ~115 bytes per second per flight a folder map
// would grow by hundreds of KB.
// Missing attitude falls back to GHOST_EST_PITCH, not to footprint.py's nadir
// assumption: the cockpit already assumes -30, and a patch under the drone
// while the cockpit looks at the horizon is two claims in one frame.
const GAZE_FALLBACK_HFOV = 84.0;    // fov_degrees(DEFAULT_LENS, None): the
const GAZE_FALLBACK_VFOV = 68.0;    // generic 20 mm-equivalent 4:3 lens
const GAZE_MAX_RANGE_FACTOR = 8.0;  // mirrors MAX_RANGE_AGL_FACTOR
const GAZE_M_PER_DEG_LAT = 111320;

function emptyFC() { return { type: 'FeatureCollection', features: [] }; }

function gazeRing(fl, i) {
  const notes = [];
  const agl = (fl.agl && fl.agl[i] != null) ? fl.agl[i] : null;
  if (agl == null || agl <= 0) {
    return { ring: null, reason: 'no altitude', estimated: false,
             estNotes: notes };
  }
  let pitch;
  if (fl.gpitch && fl.gpitch[i] != null) pitch = fl.gpitch[i];
  else { pitch = GHOST_EST_PITCH; notes.push('no gimbal pitch'); }
  if (pitch >= 0) {
    // At or above the horizon there is no ground intersection to speak of;
    // build_footprints() skips these frames and so do we.
    return { ring: null, reason: 'camera above horizon',
             estimated: notes.length > 0, estNotes: notes };
  }
  let bearing;
  if (fl.gyaw && fl.gyaw[i] != null) bearing = fl.gyaw[i] % 360;
  else { bearing = courseBearing(fl.pts, i); notes.push('no gimbal yaw'); }
  let hfov = fl.hfov, vfov = fl.vfov;
  if (!hfov || !vfov) {
    hfov = GAZE_FALLBACK_HFOV;
    vfov = GAZE_FALLBACK_VFOV;
    notes.push('assumed lens');
  }
  const c = fl.pts[i];
  const maxRange = GAZE_MAX_RANGE_FACTOR * agl;
  const toRad = Math.PI / 180;
  const th = pitch * toRad;
  const tanH = Math.tan(hfov * toRad / 2), tanV = Math.tan(vfov * toRad / 2);
  const fwdN = Math.cos(th), fwdZ = Math.sin(th);   // optical axis, pre-yaw
  const upN = -Math.sin(th), upZ = Math.cos(th);    // camera-up, pre-yaw
  const psi = bearing * toRad;
  const cosP = Math.cos(psi), sinP = Math.sin(psi);
  const mLon = GAZE_M_PER_DEG_LAT * Math.max(Math.cos(c[1] * toRad), 1e-6);
  const ring = [];
  [[-1, 1], [1, 1], [1, -1], [-1, -1]].forEach(sc => {
    const de = sc[0] * tanH;
    const dn = fwdN + sc[1] * tanV * upN;
    const dz = fwdZ + sc[1] * tanV * upZ;
    const horiz = Math.hypot(de, dn);
    // A ray that climbs never meets the ground: clamp it along its azimuth
    // so a near-horizon frame degrades to a capped trapezoid, not an
    // unbounded one.
    const dist = dz < 0 ? Math.min(agl / -dz * horiz, maxRange) : maxRange;
    const e0 = horiz > 1e-12 ? de / horiz * dist : 0;
    const n0 = horiz > 1e-12 ? dn / horiz * dist : 0;
    const east = e0 * cosP + n0 * sinP;
    const north = -e0 * sinP + n0 * cosP;
    ring.push([c[0] + east / mLon, c[1] + north / GAZE_M_PER_DEG_LAT]);
  });
  ring.push(ring[0]);
  return { ring: ring, reason: null, estimated: notes.length > 0,
           estNotes: notes };
}

const GAZE_PATCH_OPACITY = 0.25;
// fill-extrusion can only make VERTICAL prisms measured from the terrain
// surface, so a slanted ray has to be staircased. Each of the four frustum
// corner rays becomes GAZE_BEAM_STEPS short prisms; neighbours share their
// boundary height, so the spans touch or overlap and the silhouette is
// continuous rather than a ladder.
const GAZE_BEAM_STEPS = 16;
const GAZE_BEAM_OPACITY = 0.5;
const gaze = { dashed: false };

function addGazeLayers() {
  // Below the flight lines: a track must stay readable through its own patch.
  const before = map.getLayer(flights[0].id) ? flights[0].id : undefined;
  map.addSource('gaze-hits', { type: 'geojson', data: emptyFC() });
  map.addLayer({ id: 'gaze-hits-line', type: 'line', source: 'gaze-hits',
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': ['get', 'color'], 'line-width': 6,
             'line-opacity': 0.55 } }, before);
  map.addSource('gaze', { type: 'geojson', data: emptyFC() });
  map.addLayer({ id: 'gaze-fill', type: 'fill', source: 'gaze',
    paint: { 'fill-color': pb.run.color,
             'fill-opacity': GAZE_PATCH_OPACITY } }, before);
  map.addLayer({ id: 'gaze-edge', type: 'line', source: 'gaze',
    paint: { 'line-color': pb.run.color, 'line-width': 1.5 } }, before);
  // Beam is fill-extrusion and draws in the main pass, so it needs no
  // beforeId.
  map.addSource('beam', { type: 'geojson', data: emptyFC() });
  map.addLayer({ id: 'beam-ray', type: 'fill-extrusion', source: 'beam',
    paint: { 'fill-extrusion-color': pb.run.color,
             'fill-extrusion-base': ['get', 'base'],
             'fill-extrusion-height': ['get', 'hgt'],
             'fill-extrusion-opacity': GAZE_BEAM_OPACITY,
             'fill-extrusion-vertical-gradient': false } });
}

function setGazeNote(text) {
  const note = document.getElementById('pb-note');
  if (!note) return;
  note.textContent = text || '';
  note.style.display = text ? '' : 'none';
}

function renderGaze() {
  if (!pb.run || pb.sample < 0 || !map.getLayer('gaze-fill')) return;
  const g = gazeRing(pb.run, pb.sample);
  const src = map.getSource('gaze');
  if (g.ring) {
    if (src) {
      src.setData({ type: 'Feature', properties: {},
        geometry: { type: 'Polygon', coordinates: [g.ring] } });
    }
    setGazeNote(g.estimated
      ? 'estimated footprint \\u2014 ' + g.estNotes.join(', ') : '');
  } else {
    // Empty the source rather than leave the last good ring standing: a
    // frozen patch would claim the camera was still filming that ground.
    if (src) src.setData(emptyFC());
    setGazeNote(g.reason);
  }
  const bsrc = map.getSource('beam');
  if (bsrc) {
    bsrc.setData({ type: 'FeatureCollection',
                   features: beamFor(pb.run, pb.sample, g.ring) });
  }
  if (g.estimated !== gaze.dashed) {
    gaze.dashed = g.estimated;
    // null restores the style-spec default (solid). The reset direction is
    // tested: a failure there would mark every later ring estimated.
    map.setPaintProperty('gaze-edge', 'line-dasharray',
                         g.estimated ? [2, 2] : null);
  }
}

function beamFor(fl, i, ring) {
  const feats = [];
  if (!ring) return feats;
  const agl = fl.agl[i], c = fl.pts[i];
  const tElev = takeoffElev(fl);
  const camTrue = tElev == null ? null : tElev + agl;
  const half = sculptWidthM() / 2;
  const mLat = GAZE_M_PER_DEG_LAT;
  for (let r = 0; r < 4; r++) {
    const corner = ring[r];
    const at = s => [c[0] + (corner[0] - c[0]) * s,
                     c[1] + (corner[1] - c[1]) * s];
    const cornerElev = camTrue == null ? null : terrainElevAt(corner);
    // gazeRing projected onto the flat plane at tElev; where the DEM at that
    // corner is above the camera the corner cannot be a ground hit at all
    // (pitch is always negative here), so fall back to gazeRing's own datum
    // rather than aiming the ray upward.
    const farElev = (cornerElev != null && cornerElev > camTrue) ? tElev
                                                                  : cornerElev;
    // Height at each step BOUNDARY, shared by the two prisms that meet there
    // so joints match by construction. The local surface is sampled per
    // boundary and never interpolated end to end: interpolating cancels the
    // corner elevation algebraically -- h(s) collapses to (A - E_cam)(1 - s)
    // -- and the ray would follow the ground contour instead of flying
    // straight over the ridges and valleys it crosses.
    const hs = [];
    for (let k = 0; k <= GAZE_BEAM_STEPS; k++) {
      const s = k / GAZE_BEAM_STEPS;
      if (camTrue == null || cornerElev == null) {
        // Terrain off: the extrusion measures from sea level, so raw AGL is
        // already the right clearance.
        hs.push(agl * (1 - s));
        continue;
      }
      const local = terrainElevAt(at(s));
      const alt = camTrue + (farElev - camTrue) * s;
      hs.push(local == null ? agl * (1 - s) : alt - local);
    }
    for (let k = 0; k < GAZE_BEAM_STEPS; k++) {
      const hgt = Math.max(hs[k], hs[k + 1]);
      // At or below the rendered surface: fill-extrusion cannot draw there,
      // so the ray honestly stops instead of tunnelling through the ground.
      if (hgt <= 0) continue;
      const a = at(k / GAZE_BEAM_STEPS), b = at((k + 1) / GAZE_BEAM_STEPS);
      const mLon = mLat * Math.cos((a[1] + b[1]) / 2 * Math.PI / 180);
      const dx = (b[0] - a[0]) * mLon, dy = (b[1] - a[1]) * mLat;
      const len = Math.sqrt(dx * dx + dy * dy);
      if (!len) continue;
      const ox = -dy / len * half / mLon, oy = dx / len * half / mLat;
      feats.push({ type: 'Feature',
        // base is clamped in JS: the style spec forbids a negative
        // fill-extrusion-base.
        properties: { base: Math.max(0, Math.min(hs[k], hs[k + 1])),
                      hgt: hgt },
        geometry: { type: 'Polygon', coordinates: [[
          [a[0] + ox, a[1] + oy], [b[0] + ox, b[1] + oy],
          [b[0] - ox, b[1] - oy], [a[0] - ox, a[1] - oy],
          [a[0] + ox, a[1] + oy],
        ]] } });
    }
  }
  return feats;
}

// --- Playback (#378): the flat map's animator (#267/#327), MapLibre-side ---
// Semantics are deliberately identical to geo/flightmap_html.py so a user who
// learns one map's playback knows the other's: same eligibility rule, same
// speeds, same rAF clock, same pause-at-end. No "All flights (compare)" mode
// here -- a gaze patch and beam per flight at once is noise, and the cockpit
// can only ride one flight.
const PB_SPEEDS = [1, 5, 20, 60];
const runs = flights.filter(f => f.pts && Array.isArray(f.times)
  && f.times.length === f.pts.length
  && f.times[f.times.length - 1] > 0);
const pb = { t: 0, playing: false, speed: 1, raf: null, last: 0,
             run: null, cursor: 0, sample: -1 };

function pbMax() {
  return pb.run ? pb.run.times[pb.run.times.length - 1] : 0;
}

function sampleIndexAt(fl, t) {
  // Index of the sample at or before t, with a monotonic cursor hint so a
  // playing clock does not rescan the array every frame.
  const times = fl.times;
  if (t <= times[0]) { pb.cursor = 0; return 0; }
  if (t >= times[times.length - 1]) return times.length - 1;
  let i = pb.cursor;
  if (times[i] > t) i = 0;                    // seeked backwards
  while (times[i + 1] <= t) i++;
  pb.cursor = i;
  return i;
}

function positionAt(fl, t) {
  const i = sampleIndexAt(fl, t), pts = fl.pts;
  if (i >= pts.length - 1) return [pts[i][0], pts[i][1]];
  const t0 = fl.times[i], t1 = fl.times[i + 1];
  const f = t1 > t0 ? (t - t0) / (t1 - t0) : 1;
  const a = pts[i], b = pts[i + 1];
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f];
}

function pbRecolour() {
  if (map.getLayer('gaze-cursor-dot')) {
    map.setPaintProperty('gaze-cursor-dot', 'circle-color', pb.run.color);
  }
  if (map.getLayer('gaze-fill')) {
    map.setPaintProperty('gaze-fill', 'fill-color', pb.run.color);
    map.setPaintProperty('gaze-edge', 'line-color', pb.run.color);
  }
  if (map.getLayer('beam-ray')) {
    map.setPaintProperty('beam-ray', 'fill-extrusion-color', pb.run.color);
  }
  // Not a paint concern: this is the run-change hook. pbRecolour() is called
  // from exactly the two places pb.run is reassigned (the picker and
  // gazeSeek), so re-deriving gaze visibility from the NEW run here is what
  // keeps a hidden flight's gaze off, and a shown flight's gaze on, across a
  // switch (#378 whole-branch review, I2).
  applyGazeVisibility();
}

function pbRender(skipGhost) {
  // skipGhost lets a caller refresh the cursor, patch and readout WITHOUT
  // driving the cockpit camera -- see ghostStep, whose own eased move would
  // otherwise be beaten to the same target by the instant drive below.
  if (!pb.run) return;
  const src = map.getSource('gaze-cursor');
  if (src) src.setData({ type: 'Feature', properties: {},
    geometry: { type: 'Point', coordinates: positionAt(pb.run, pb.t) } });
  const slider = document.getElementById('pb-slider');
  if (slider) slider.value = String(pb.t);
  const time = document.getElementById('pb-time');
  if (time) {
    time.textContent = fmtDuration(Math.round(pb.t)) + ' / '
                     + fmtDuration(Math.round(pbMax()));
  }
  const s = sampleIndexAt(pb.run, pb.t);
  if (s !== pb.sample) {
    // Each ring IS one second of recording; interpolating between them would
    // invent geometry, and rebuilding per frame would churn at 60x speed.
    pb.sample = s;
    renderGaze();
  }
  if (!skipGhost) pbDriveGhost();
}

function lerp(a, b, f) { return a + (b - a) * f; }

function posePlayback(fl, t) {
  // Built from two samplePose() calls so every existing fallback -- takeoff
  // elevation, the -30 pitch estimate, the pitch clamp -- applies unchanged.
  const i = sampleIndexAt(fl, t);
  if (i >= fl.pts.length - 1) return samplePose(fl, fl.pts.length - 1);
  const t0 = fl.times[i], t1 = fl.times[i + 1];
  const f = t1 > t0 ? (t - t0) / (t1 - t0) : 1;
  const p0 = samplePose(fl, i), p1 = samplePose(fl, i + 1);
  const d = ((p1.bearing - p0.bearing + 540) % 360) - 180;   // shortest arc
  return Object.assign({}, p0, {
    lngLat: [lerp(p0.lngLat[0], p1.lngLat[0], f),
             lerp(p0.lngLat[1], p1.lngLat[1], f)],
    altitude: lerp(p0.altitude, p1.altitude, f),
    bearing: p0.bearing + d * f,
    pitch: lerp(p0.pitch, p1.pitch, f),
  });
}

function pbDriveGhost() {
  if (!ghost.active || ghost.flight !== pb.run) return;
  // jumpTo, never easeTo: an ease would fight the clock and churn moveend,
  // which is where this file's ghost-exit guard already earned its scars.
  applyPose(posePlayback(pb.run, pb.t), 0);
  if (pb.sample !== ghost.idx) {
    ghost.idx = pb.sample;
    updateHud();
    renderCrossfade();
  }
}

function applyGazeVisibility() {
  const v = (pb.run && pb.run.shown) ? 'visible' : 'none';
  // The beam originates at the camera, so it hides in the cockpit for the
  // same reason the sculpture does; the patch is what you came to see.
  const beam = (v === 'visible' && !ghost.active) ? 'visible' : 'none';
  // gaze-hits-line is NOT here: a lookup highlight can span several flights
  // at once, so it has no single pb.run to follow. It stays laid out
  // 'visible' always; its own source data (emptied by gazeHighlight([]) on
  // panel toggle -- see buildPanel -- and on popup close) is what controls
  // whether anything is actually drawn (#378 whole-branch review, M1).
  [['gaze-fill', v], ['gaze-edge', v], ['gaze-cursor-dot', v],
   ['beam-ray', beam]].forEach(pair => {
    if (map.getLayer(pair[0])) {
      map.setLayoutProperty(pair[0], 'visibility', pair[1]);
    }
  });
}

function pbPause() {
  pb.playing = false;
  syncCrossfadePlayback();
  const b = document.getElementById('pb-play');
  if (b) b.textContent = '\\u25b6';
  if (pb.raf) cancelAnimationFrame(pb.raf);
  pb.raf = null;
}

function pbTick(now) {
  if (!pb.playing) return;
  pb.t = Math.min(pbMax(), pb.t + (now - pb.last) / 1000 * pb.speed);
  pb.last = now;
  pbRender();
  if (pb.t >= pbMax()) { pbPause(); return; }
  pb.raf = requestAnimationFrame(pbTick);
}

function pbPlay() {
  if (!pb.run) return;
  if (pb.t >= pbMax()) { pb.t = 0; pb.cursor = 0; }
  pb.playing = true;
  syncCrossfadePlayback();
  const b = document.getElementById('pb-play');
  if (b) b.textContent = '\\u275a\\u275a';
  pb.last = performance.now();
  pb.raf = requestAnimationFrame(pbTick);
}

function mountPlayback() {
  if (!runs.length) return;
  pb.run = runs[0];
  const div = document.createElement('div');
  div.id = 'playback';
  div.className = 'playback';
  const mk = (tag, id) => {
    const e = document.createElement(tag);
    e.id = id;
    return e;
  };
  const play = mk('button', 'pb-play');
  play.type = 'button';
  play.title = 'Play flight';
  play.textContent = '\\u25b6';
  const speed = mk('button', 'pb-speed');
  speed.type = 'button';
  speed.title = 'Playback speed';
  speed.textContent = '1\\u00d7';
  const slider = mk('input', 'pb-slider');
  slider.type = 'range';
  slider.min = '0';
  slider.step = '0.1';
  slider.value = '0';
  slider.max = String(pbMax());
  slider.title = 'Seek';
  const time = mk('span', 'pb-time');
  const note = mk('span', 'pb-note');
  note.className = 'ghost-badge';
  note.style.display = 'none';
  div.append(play, speed, slider, time, note);
  if (runs.length > 1) {
    const sel = mk('select', 'pb-flight');
    sel.title = 'Flight to play';
    runs.forEach((r, i) => {
      const o = document.createElement('option');
      o.value = String(i);
      o.textContent = r.name;
      sel.appendChild(o);
    });
    sel.addEventListener('change', () => {
      pbPause();                          // switching resets the clock
      pb.run = runs[Number(sel.value)];
      pb.t = 0;
      pb.cursor = 0;
      pb.sample = -1;
      slider.max = String(pbMax());
      pbRecolour();
      pbRender();
    });
    div.appendChild(sel);
  }
  play.addEventListener('click', () => pb.playing ? pbPause() : pbPlay());
  speed.addEventListener('click', () => {
    pb.speed = PB_SPEEDS[(PB_SPEEDS.indexOf(pb.speed) + 1) % PB_SPEEDS.length];
    speed.textContent = pb.speed + '\\u00d7';
    // The riding/stepping boundary is speed-dependent, not just
    // playing-dependent -- without this a speed change across
    // CROSSFADE_MAX_RATE would not take effect until the next sample.
    syncCrossfadePlayback();
  });
  slider.addEventListener('input', () => {
    pb.t = Number(slider.value);
    pbRender();
  });
  document.body.appendChild(div);
  map.addSource('gaze-cursor', { type: 'geojson', data: emptyFC() });
  map.addLayer({ id: 'gaze-cursor-dot', type: 'circle', source: 'gaze-cursor',
    paint: { 'circle-radius': 7, 'circle-color': pb.run.color,
             'circle-stroke-color': '#fff', 'circle-stroke-width': 2 } });
  if (REDACTED === 'none') {
    // Fuzzed coordinates would make every footprint a confident claim about
    // ground the camera never saw. The clock still works.
    addGazeLayers();
    map.on('click', gazeLookup);
  }
  pbRender();
}

// --- Click a spot, get the seconds that filmed it (#378) ---
const GAZE_MAX_PASSES = 12;
// The popup from the PREVIOUS lookup, if one is still open. MapLibre's own
// closeOnClick binds a plain (not one-time) 'click' listener when a popup
// opens, so on a second click that listener is still registered ALONGSIDE
// gazeLookup's -- and because gazeLookup was registered first (once, at
// mount), it runs first, then the stale popup's close listener runs after
// it in the SAME dispatch and unconditionally empties gaze-hits, wiping the
// highlight this click just set. Closing the previous popup ourselves,
// synchronously, before computing anything for the new click sidesteps that
// listener-order dependency entirely instead of relying on it.
let gazePopup = null;

function pointInRing(ring, lng, lat) {
  // Ray casting over the four edges of a closed ring. Footprints are tens to
  // hundreds of metres across, so planar lon/lat is exact enough.
  let inside = false;
  const n = ring.length - 1;
  for (let i = 0, j = n - 1; i < n; j = i++) {
    const xi = ring[i][0], yi = ring[i][1];
    const xj = ring[j][0], yj = ring[j][1];
    if (((yi > lat) !== (yj > lat))
        && lng < (xj - xi) * (lat - yi) / (yj - yi) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

function gazeRingsFor(fl) {
  // Memoised on first lookup: a map nobody clicks pays nothing, and a map
  // clicked twice pays once. The estimated flag is kept PER SAMPLE, not
  // discarded: gimbal yaw and pitch are per-sample optional fields, so a clip
  // that drops attitude for part of a flight has some rings drawn from real
  // data and others from the assumed GHOST_EST_PITCH tilt. Reading one
  // sample's flag would let the popup omit the warning for extrapolated
  // frames, which is exactly the claim this feature must not make.
  if (!fl.rings) {
    fl.rings = fl.pts.map((p, i) => {
      const g = gazeRing(fl, i);
      return { ring: g.ring, estimated: g.estimated, estNotes: g.estNotes };
    });
  }
  return fl.rings;
}

function gazePasses(fl, lngLat) {
  const rings = gazeRingsFor(fl), times = fl.times;
  const hits = [];
  rings.forEach((r, i) => {
    if (r.ring && pointInRing(r.ring, lngLat.lng, lngLat.lat)) hits.push(i);
  });
  if (!hits.length) return [];
  // Seconds are counted per sample interval, so a single-sample hit reads as
  // about a second rather than zero.
  const dt = i => (i + 1 < times.length) ? times[i + 1] - times[i]
    : (i > 0 ? times[i] - times[i - 1] : 1);
  const passes = [];
  let start = hits[0], prev = hits[0], secs = 0, est = false, notes = [];
  // A pass counts as estimated if ANY of its matched samples was, and its
  // estNotes is the UNION of every matched sample's reasons: the warning has
  // to name the weakest frame it is offering, not just the first one (the
  // same reasoning gazeRingsFor's own comment gives for keeping the flag per
  // sample -- see #378 whole-branch review, I1).
  const close = () => passes.push({
    i0: start, i1: prev, t0: times[start], t1: times[prev], secs: secs,
    est: est, estNotes: notes });
  hits.forEach(i => {
    if (i > prev + 1) {
      close();
      start = i;
      secs = 0;
      est = false;
      notes = [];
    }
    secs += dt(i);
    est = est || rings[i].estimated;
    rings[i].estNotes.forEach(n => { if (!notes.includes(n)) notes.push(n); });
    prev = i;
  });
  close();
  return passes;
}

function gazeSkipCounts() {
  // Everything gazeLookup's search loop below does NOT look at, bucketed by
  // why: hidden playable flights, playable flights with no agl_m at all
  // (spec: "Times but no agl_m -> Playable, no gaze" -- gazeRing can never
  // produce a ring for one), and flights that never made it into `runs` in
  // the first place -- a single-fix clip, or a track whose times do not line
  // up with its points -- which cannot appear in that loop at all. The miss
  // message below must not claim more than this function actually counts
  // (#378 whole-branch review, C1).
  const runSet = new Set(runs);
  let hidden = 0, noHeight = 0;
  runs.forEach(fl => {
    if (!fl.shown) hidden++;
    else if (!fl.agl) noHeight++;
  });
  flights.forEach(fl => { if (!runSet.has(fl)) noHeight++; });
  return { hidden: hidden, noHeight: noHeight, total: hidden + noHeight };
}

function gazeSeek(fl, t) {
  if (pb.run !== fl) {
    pb.run = fl;
    const sel = document.getElementById('pb-flight');
    if (sel) sel.value = String(runs.indexOf(fl));
    const slider = document.getElementById('pb-slider');
    if (slider) slider.max = String(pbMax());
    pbRecolour();
  }
  pb.t = t;
  pb.cursor = 0;
  pb.sample = -1;
  pbRender();
  // In the cockpit on this flight, playing IS riding it -- no second control.
  if (!pb.playing) pbPlay();
}

function gazeHighlight(entries) {
  const src = map.getSource('gaze-hits');
  if (!src) return;
  const feats = [];
  entries.forEach(e => e.passes.forEach(p => {
    // One sample either side, so a single-sample hit is still a visible line.
    const a = Math.max(0, p.i0 - 1);
    const b = Math.min(e.fl.pts.length - 1, p.i1 + 1);
    feats.push({ type: 'Feature', properties: { color: e.fl.color },
      geometry: { type: 'LineString',
        coordinates: e.fl.pts.slice(a, b + 1).map(c => [c[0], c[1]]) } });
  }));
  src.setData({ type: 'FeatureCollection', features: feats });
}

function gazeLookup(ev) {
  const lineIds = flights.map(f => f.id).filter(id => map.getLayer(id));
  if (lineIds.length
      && map.queryRenderedFeatures(ev.point, { layers: lineIds }).length) {
    return;                    // the flight line owns this click
  }
  if (gazePopup) gazePopup.remove();   // see gazePopup's own comment above
  const el = document.createElement('div');
  el.className = 'flight-popup';
  const entries = [];
  runs.forEach(fl => {
    if (!fl.shown) return;
    const passes = gazePasses(fl, ev.lngLat);
    if (!passes.length) return;
    entries.push({ fl: fl, passes: passes });
    const head = document.createElement('div');
    const name = document.createElement('strong');
    name.textContent = fl.name;
    head.appendChild(name);
    const total = passes.reduce((a, p) => a + p.secs, 0);
    head.appendChild(document.createTextNode(
      ' \\u2014 in frame ' + Math.round(total) + ' s over ' + passes.length
      + (passes.length === 1 ? ' pass' : ' passes')));
    el.appendChild(head);
    const row = document.createElement('div');
    passes.slice(0, GAZE_MAX_PASSES).forEach(p => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'gaze-pass';
      b.textContent = fmtDuration(Math.round(p.t0)) + '\\u2013'
                    + fmtDuration(Math.round(p.t1));
      b.addEventListener('click', () => gazeSeek(fl, p.t0));
      row.appendChild(b);
    });
    if (passes.length > GAZE_MAX_PASSES) {
      row.appendChild(document.createTextNode(
        ' +' + (passes.length - GAZE_MAX_PASSES) + ' more'));
    }
    el.appendChild(row);
    // Warn on ANY estimated pass, and say whether it is all of them: a clip
    // can lose gimbal attitude partway through, so "some" is often the honest
    // word. Checking a single sample would silently drop the warning for
    // extrapolated frames the user is about to go looking for.
    const estCount = passes.filter(p => p.est).length;
    if (estCount) {
      // The reason is the union of every LISTED pass's notes -- not a
      // hardcoded "no gimbal data", which is false whenever the estimate
      // actually came from an assumed lens (mp4_telemetry.py logs real
      // gimbal attitude but no focal length on every sidecar-less MP4 clip;
      // #378 whole-branch review, I1). Only the listed passes, because those
      // are the only ones with a visible button.
      const notes = [];
      passes.slice(0, GAZE_MAX_PASSES).forEach(p => {
        if (!p.est) return;
        p.estNotes.forEach(n => { if (!notes.includes(n)) notes.push(n); });
      });
      const est = document.createElement('div');
      est.className = 'gaze-est';
      let text = estCount === passes.length ? 'estimated'
                                            : 'some passes estimated';
      if (notes.length) text += ' \\u2014 ' + notes.join(', ');
      est.textContent = text;
      el.appendChild(est);
    }
  });
  if (!entries.length) {
    el.appendChild(document.createTextNode(
      'No footprint on this map covers this spot.'));
    // Say what was actually searched, not just what was not found: a false
    // "no" is the worst answer this feature can give (#378 whole-branch
    // review, C1).
    const skip = gazeSkipCounts();
    if (skip.total) {
      const parts = [];
      if (skip.hidden) {
        parts.push(skip.hidden
          + (skip.hidden === 1 ? ' hidden flight' : ' hidden flights'));
      }
      if (skip.noHeight) {
        parts.push(skip.noHeight + (skip.noHeight === 1
          ? ' flight with no height data' : ' flights with no height data'));
      }
      const note = document.createElement('div');
      note.className = 'gaze-skip';
      note.textContent = skip.total
        + (skip.total === 1 ? ' flight was' : ' flights were')
        + ' not searched \\u2014 ' + parts.join(', ') + '.';
      el.appendChild(note);
    }
  }
  gazeHighlight(entries);
  gazePopup = new maplibregl.Popup({ maxWidth: '320px' })
    .setLngLat(ev.lngLat).setDOMContent(el).addTo(map);
  gazePopup.on('close', () => { gazeHighlight([]); gazePopup = null; });
}

// --- Media crossfade (#380): blend the reconstruction into the footage ---
// The video is composited by CSS opacity only -- never drawn into a canvas,
// which would taint it and buy nothing.
const CROSSFADE_MAX_RATE = 4;     // browsers cannot decode reliably above
                                   // this; PB_SPEEDS has no value in (1, 4],
                                   // so in the shipped UI this is effectively
                                   // "riding only at 1x"
const CROSSFADE_DRIFT_S = 0.25;   // re-seek only when playback slips this far
const cross = { el: null, blend: 0, seg: -1, pending: null, href: null,
                 broken: null };

function mediaFor(fl, i) {
  // Which file, and how far into it. The offset is the point's own SRT cue:
  // cues are video-relative and the split-join never rewrites them.
  if (!fl || !fl.media || !fl.cue) return null;
  const seg = fl.segi ? fl.segi[i] : 0;
  const href = fl.media[seg];
  if (!href) return { href: null, seg: seg, t: null };
  return { href: href, seg: seg, t: fl.cue[i] };
}

// Answers "may we offer the crossfade?", not "does this flight have
// footage?" -- both call sites want the redaction answer, not the raw one.
function hasMedia(fl) {
  return REDACTED === 'none'
    && !!(fl && fl.media && fl.cue && fl.media.some(h => h));
}

function setBlend(x) {
  cross.blend = Math.max(0, Math.min(1, x));
  if (cross.el) cross.el.style.opacity = String(cross.blend);
  const s = document.getElementById('ghost-blend');
  if (s && Number(s.value) / 100 !== cross.blend) {
    s.value = String(Math.round(cross.blend * 100));
  }
}

function crossBadge(text) {
  const badges = ghost.hud && ghost.hud.querySelector('#ghost-badges');
  if (!badges) return;
  const s = document.createElement('span');
  s.className = 'ghost-badge';
  s.textContent = text;
  badges.appendChild(s);
}

function mountCrossfade() {
  // Fuzzed positions are deliberately ~100 m out, so overlaying real footage
  // would invite a comparison against geometry we know is wrong. Linking is
  // still permitted (photomap allows the same pair) -- it is the blend that
  // is withheld.
  if (REDACTED !== 'none') return;
  // Cockpit-only: the slider lives in the ghost HUD, and outside the cockpit
  // there is no pose for the footage to be compared against.
  if (cross.el || !hasMedia(ghost.flight)) return;
  const v = document.createElement('video');
  v.id = 'ghost-video';
  v.className = 'ghost-video';
  v.muted = true;
  v.playsInline = true;
  v.preload = 'auto';
  v.style.opacity = '0';
  v.addEventListener('loadedmetadata', () => {
    if (cross.pending != null) {
      const t = cross.pending;
      cross.pending = null;
      seekCrossfade(t);
    }
  });
  v.addEventListener('error', () => {
    // A blank overlay reads as "the camera saw nothing here". Name the file
    // instead and take the control away -- and record it in cross.broken, so
    // the next renderCrossfade (one arrow key or one sample tick away) does
    // not straight-line undo all three the way this used to. Worded as what
    // the <video> error event actually tells us: it fires the same way for
    // a moved file, a wrong href base, a transport failure and a codec the
    // browser cannot decode -- DJI's own 4K default, H.265/HEVC, is exactly
    // that case in Firefox and on Chrome without a platform decoder -- so
    // "unavailable" would assert a cause the code cannot know (#380
    // whole-branch review I3).
    cross.broken = cross.href;
    const slider = document.getElementById('ghost-blend');
    if (slider) slider.disabled = true;
    v.style.display = 'none';
    crossBadge('could not load: ' + (cross.broken || ''));
  });
  document.getElementById('map').appendChild(v);
  cross.el = v;
  cross.seg = -1;
  cross.pending = null;
  setBlend(0);
  renderCrossfade();
}

function unmountCrossfade() {
  cross.blend = 0;
  if (!cross.el) return;
  cross.el.pause();
  // Clear the source and let the element re-check itself before removal --
  // otherwise a multi-GB MP4 the browser was mid-fetch on keeps downloading
  // after the cockpit closes (#380 whole-branch review M3).
  cross.el.removeAttribute('src');
  cross.el.load();
  cross.el.remove();
  cross.el = null;
  cross.seg = -1;
  cross.pending = null;
  cross.broken = null;
  cross.href = null;
}

function seekCrossfade(t) {
  const v = cross.el;
  if (!v || t == null) return;
  // currentTime does not stick before metadata arrives; hold it and apply
  // once the browser knows the duration.
  if (v.readyState < 1) { cross.pending = t; return; }
  if (Math.abs(v.currentTime - t) > 0.05) v.currentTime = t;
}

function renderCrossfade() {
  if (!cross.el || !ghost.active) return;
  if (!ghost.flight.vfov) {
    // Without a focal length the map's own field of view is a guess, so a
    // mismatch is not evidence the telemetry is wrong. updateHud() clears
    // #ghost-badges on every call, so this is re-added here (rather than
    // once at mount) to survive every step, not just the first frame.
    crossBadge('alignment approximate \\u2014 no focal length');
  }
  const slider = document.getElementById('ghost-blend');
  const m = mediaFor(ghost.flight, ghost.idx);
  if (!m || !m.href) {
    // A segment whose file was never resolved: hide rather than leave the
    // previous file's frame standing over a different part of the flight,
    // and say so. media[seg] is null here, so there is no filename left to
    // name -- this is the honest version of what spec #380 section 8 asks
    // for (#380 whole-branch review I2).
    cross.el.style.display = 'none';
    if (slider) slider.disabled = true;
    crossBadge('no video for this part of the flight');
    syncCrossfadePlayback();
    return;
  }
  if (m.seg !== cross.seg) {
    cross.seg = m.seg;
    cross.pending = m.t;
    cross.broken = null;      // a different file may load fine
    cross.href = m.href;
    // A src swap resets playback state, so the seek is re-applied from the
    // loadedmetadata handler below rather than now.
    cross.el.src = m.href;
    cross.el.load();
  } else {
    const v = cross.el;
    const drifted = v.paused
      || Math.abs(v.currentTime - m.t) > CROSSFADE_DRIFT_S;
    if (drifted) seekCrossfade(m.t);
  }
  if (cross.broken) {
    // The error handler already hid the element, disabled the slider and
    // posted the badge once. Without this the next render (one arrow key or
    // one sample tick away) would straight-line undo all three, leaving a
    // LIVE blend slider over a video that will never show a frame -- the
    // "camera saw nothing here" reading this posture exists to prevent.
    cross.el.style.display = 'none';
    if (slider) slider.disabled = true;
    crossBadge('could not load: ' + cross.broken);
    syncCrossfadePlayback();
    return;
  }
  cross.el.style.display = '';
  if (slider) slider.disabled = false;
  syncCrossfadePlayback();
}

function syncCrossfadePlayback() {
  const v = cross.el;
  if (!v || !ghost.active) return;
  const riding = pb.playing && pb.run === ghost.flight;
  if (riding && pb.speed <= CROSSFADE_MAX_RATE) {
    v.playbackRate = pb.speed;
    if (v.paused) v.play().catch(() => {});    // autoplay policy: muted, so
    return;                                    // this should not reject
  }
  // Paused, scrubbing, or faster than the decoder can follow: step instead.
  // A slideshow is honest; a decoder falling silently behind is not.
  if (!v.paused) v.pause();
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
