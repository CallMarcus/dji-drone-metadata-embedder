"""JS helpers shared by the 2D and 3D flightmap HTML writers.

One source of truth for the popup renderer and track palette so the two
templates cannot drift apart. :data:`FLIGHT_POPUP_JS` is plain browser JS
embedded by string concatenation — it must stay dependency-free and must
not reference Leaflet or MapLibre.

:data:`PLAYBACK_JS`, by contrast, IS Leaflet-specific (``L.control``,
``L.DomUtil``, ``L.circleMarker``) and is shared only by the two Leaflet
templates — :mod:`.flightmap_html` and :mod:`.map_html` — never the 3D one.
It is self-contained: it reads only ``runs``, ``map``, ``esc``,
``fmtDuration``, and the DOM ids it creates itself.
"""

from __future__ import annotations

FLIGHT_POPUP_JS = """const esc = s => String(s).replace(/[&<>"']/g,
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
}"""

# Flight playback control (issues #267, #327) — extracted verbatim from the
# 2D flightmap template so map_html.py's combined template cannot drift from
# it. See the module docstring: this constant, unlike FLIGHT_POPUP_JS above,
# is Leaflet-specific.
PLAYBACK_JS = """// Flight playback (issues #267, #327): a hand-rolled requestAnimationFrame
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
}"""
