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
__TILE_LAYER__

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
  if (p.height_min != null) {
    html += `<br>height: ${p.height_min} to ${p.height_max} m above takeoff`;
  } else if (p.alt_min != null) {
    html += `<br>altitude: ${p.alt_min} to ${p.alt_max} m (as logged)`;
  }
  html += `<br>${p.points} GPS point${p.points === 1 ? '' : 's'}`;
  if (p.segments) {
    html += `<br>recorded across ${p.segments.length} files: ` +
            `${esc(p.segments[0])} → ${esc(p.segments[p.segments.length - 1])}`;
  }
  html += '</div>';
  return html;
}

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

// Flight playback (issues #267, #327): a hand-rolled requestAnimationFrame
// animator — no plugin, no new pinned assets. By default one flight plays at a
// time (#327: playing a folder no longer animates every track at once); a
// selector switches the active flight, and an "All flights" option restores the
// #267 shared-clock compare mode (every flight from its own takeoff). The
// control is inert until Play is pressed; the default map costs nothing extra.
// Each flight's dot lives in that flight's layer group, so the layer control
// hides it together with the track.
const maxT = Math.max(0, ...runs.map(r => r.times[r.times.length - 1]));
if (runs.length && maxT > 0) {
  let sel = 0;   // index into runs, or 'all' for the #267 compare mode
  const selRuns = () => sel === 'all' ? runs : [runs[sel]];
  const selMax = () => sel === 'all'
    ? maxT : runs[sel].times[runs[sel].times.length - 1];

  const ctl = L.control({ position: 'bottomleft' });
  ctl.onAdd = () => {
    const div = L.DomUtil.create('div', 'playback');
    let picker = '';
    if (runs.length > 1) {
      picker = '<label for="pb-flight">flight</label>' +
        '<select id="pb-flight" title="Flight to play">' +
        runs.map((r, i) => `<option value="${i}">${esc(r.name)}</option>`).join('') +
        '<option value="all">All flights (compare)</option></select>';
    }
    div.innerHTML =
      '<button id="pb-play" type="button" title="Play flight">&#9654;</button>' +
      '<button id="pb-speed" type="button" title="Playback speed">1&times;</button>' +
      `<input id="pb-slider" type="range" min="0" max="${selMax()}" step="0.1" value="0">` +
      `<span id="pb-time">0:00 / ${fmtDuration(Math.round(selMax()))}</span>` +
      picker;
    L.DomEvent.disableClickPropagation(div);
    return div;
  };
  ctl.addTo(map);
  const playBtn = document.getElementById('pb-play');
  const speedBtn = document.getElementById('pb-speed');
  const slider = document.getElementById('pb-slider');
  const timeEl = document.getElementById('pb-time');
  const flightSel = document.getElementById('pb-flight');
  const SPEEDS = [1, 5, 20, 60];
  const pb = { t: 0, playing: false, speed: 1, raf: null, last: 0 };

  function positionAt(run, t) {
    const times = run.times, lls = run.latlngs;
    if (t <= times[0]) return lls[0];
    if (t >= times[times.length - 1]) return lls[lls.length - 1];
    let i = run.cursor;
    if (times[i] > t) i = 0;                       // seeked backwards
    while (times[i + 1] < t) i++;
    run.cursor = i;
    const t0 = times[i], t1 = times[i + 1];
    const f = t1 > t0 ? (t - t0) / (t1 - t0) : 1;
    const a = lls[i], b = lls[i + 1];
    return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f];
  }
  function render() {
    const active = selRuns();
    for (const run of runs) {
      if (active.includes(run)) {
        const pos = positionAt(run, pb.t);
        if (!run.marker) {
          run.marker = L.circleMarker(pos, { radius: 7, color: '#fff', weight: 2,
            fillColor: run.color, fillOpacity: 1 }).addTo(run.group);
        } else run.marker.setLatLng(pos);
      } else if (run.marker) {                     // deselected: drop its dot
        run.group.removeLayer(run.marker);
        run.marker = null;
      }
    }
    slider.value = pb.t;
    timeEl.textContent =
      `${fmtDuration(Math.round(pb.t))} / ${fmtDuration(Math.round(selMax()))}`;
  }
  function pause() {
    pb.playing = false;
    playBtn.innerHTML = '&#9654;';
    if (pb.raf) cancelAnimationFrame(pb.raf);
  }
  function tick(now) {
    if (!pb.playing) return;
    pb.t = Math.min(selMax(), pb.t + (now - pb.last) / 1000 * pb.speed);
    pb.last = now;
    render();
    if (pb.t >= selMax()) { pause(); return; }
    pb.raf = requestAnimationFrame(tick);
  }
  function play() {
    if (pb.t >= selMax()) pb.t = 0;
    pb.playing = true;
    playBtn.innerHTML = '&#10074;&#10074;';
    pb.last = performance.now();
    pb.raf = requestAnimationFrame(tick);
  }
  playBtn.addEventListener('click', () => pb.playing ? pause() : play());
  speedBtn.addEventListener('click', () => {
    pb.speed = SPEEDS[(SPEEDS.indexOf(pb.speed) + 1) % SPEEDS.length];
    speedBtn.innerHTML = `${pb.speed}&times;`;
  });
  slider.addEventListener('input', () => {
    pb.t = Number(slider.value);
    render();
  });
  if (flightSel) {
    flightSel.addEventListener('change', () => {
      pause();                                      // switching resets the clock
      sel = flightSel.value === 'all' ? 'all' : Number(flightSel.value);
      pb.t = 0;
      slider.max = selMax();
      render();
    });
  }
}
"""


def flights_to_html(
    tracks: list[Track], title: str, *, tile_style: str = DEFAULT_TILE_STYLE
) -> str:
    """Return a complete self-contained HTML flight map.

    ``tile_style`` (issue #311): a :data:`~.tiles.TILE_STYLES` key selecting
    the basemap drawn under the tracks.
    """
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
        app_js=_APP_JS.replace("__TILE_LAYER__", tile_layer_js(tile_style)),
    )


def write_flights_html(
    tracks: list[Track],
    output_path: Path,
    title: str,
    *,
    tile_style: str = DEFAULT_TILE_STYLE,
) -> Path:
    """Write *tracks* as an HTML map to *output_path* and return it."""
    output_path.write_text(
        flights_to_html(tracks, title, tile_style=tile_style), encoding="utf-8"
    )
    logger.info("HTML flight map created: %s", output_path)
    return output_path
