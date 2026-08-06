"""The 3D map's gaze + playback JS, spliced into the map's _APP_JS.

Moved out verbatim in #383. The block is self-contained: it touches only
script-scope globals (``map``, ``flights``, ``ghost``, ``GHOST_EST_PITCH``,
``courseBearing``, ``samplePose``, ``applyPose``, ``takeoffElev``,
``terrainElevAt``, ``sculptWidthM``, ``fmtDuration``, ``REDACTED``) and is
called from a handful of pre-existing lines. It replaces the
``__GAZE_JS__`` placeholder exactly where it used to live, so load-time
execution order is unchanged; ``app_js`` reaches the template as a
``.format()`` VALUE, so braces here need no doubling (mirrors
``__SHARED_JS__``/``flightmap_js.py``).
"""

GAZE_JS = """\
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
const gaze = { dashed: false, beamAt: 0 };
const BEAM_MIN_MS = 85;   // ~12 beam rebuilds/s while the clock free-runs
                          // (#382: measured, not guessed -- see the issue)

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
  const g = gazeRingAt(pb.run, pb.sample);
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
    // Wall-clock throttle while the clock free-runs (#382): each staircase
    // rebuild costs ~(GAZE_BEAM_STEPS + 1) * 4 terrain queries, measured at
    // roughly a third of the frame budget at 60x on real hardware -- and
    // nobody can track individual rays at that speed. Presentation only:
    // the patch above stays per-sample (it costs no terrain queries), the
    // click lookup is untouched, and every PAUSED render -- step, scrub,
    // pbPause itself -- rebuilds exactly, so any resting state shows the
    // true beam for the current sample.
    const now = performance.now();
    if (!pb.playing || now - gaze.beamAt >= BEAM_MIN_MS) {
      gaze.beamAt = now;
      bsrc.setData({ type: 'FeatureCollection',
                     features: beamFor(pb.run, pb.sample, g.ring) });
    }
  }
  if (g.estimated !== gaze.dashed) {
    gaze.dashed = g.estimated;
    // null restores the style-spec default (solid). The reset direction is
    // tested: a failure there would mark every later ring estimated.
    map.setPaintProperty('gaze-edge', 'line-dasharray',
                         g.estimated ? [2, 2] : null);
  }
}

function beamFillLocals(locals, tElev, farElev) {
  // Estimate cold DEM boundaries from their known neighbours (linear
  // between the nearest known samples; constant extension at the ends).
  // With NOTHING known, assume the flat plane gazeRing itself projects
  // onto -- which reproduces the pre-#384 clearance exactly, so a wholly
  // cold ray degrades no further than it always did.
  const n = locals.length;
  if (!locals.some(v => v != null)) {
    for (let k = 0; k < n; k++) {
      locals[k] = tElev + (farElev - tElev) * (k / (n - 1));
    }
    return;
  }
  for (let k = 0; k < n; k++) {
    if (locals[k] != null) continue;
    let p = k - 1;                        // already filled, so never null
    let q = k + 1;
    while (q < n && locals[q] == null) q++;
    const a = p >= 0 ? locals[p] : null;
    const b = q < n ? locals[q] : null;
    locals[k] = a == null ? b
      : (b == null ? a : a + (b - a) * ((k - p) / (q - p)));
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
    if (camTrue == null || cornerElev == null) {
      for (let k = 0; k <= GAZE_BEAM_STEPS; k++) {
        // Terrain off: the extrusion measures from sea level, so raw AGL is
        // already the right clearance.
        hs.push(agl * (1 - k / GAZE_BEAM_STEPS));
      }
    } else {
      // Sample the surface first, then fill cold boundaries from their known
      // neighbours: a null mid-ray sample must not switch height datums --
      // the old agl*(1-s) fallback among terrain-relative neighbours kinked
      // the ray upward at exactly that boundary (#384).
      const locals = [];
      for (let k = 0; k <= GAZE_BEAM_STEPS; k++) {
        locals.push(terrainElevAt(at(k / GAZE_BEAM_STEPS)));
      }
      beamFillLocals(locals, tElev, farElev);
      for (let k = 0; k <= GAZE_BEAM_STEPS; k++) {
        const s = k / GAZE_BEAM_STEPS;
        hs.push(camTrue + (farElev - camTrue) * s - locals[k]);
      }
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
  // same reason the sculpture does; the patch is what you came to see. But
  // only when the cockpit rides the SAME flight the clock is playing --
  // another flight's beam is nowhere near your eye (#384).
  const beam = (v === 'visible' && !(ghost.active && ghost.flight === pb.run))
    ? 'visible' : 'none';
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
  // The free-running throttle above may have skipped the last rebuild;
  // a resting map must show the true beam for the current sample (#382).
  renderGaze();
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

function gazeRingAt(fl, i) {
  // ONE computation per sample, shared by the render path and the click
  // lookup -- renderGaze calling gazeRing directly beside this memo was two
  // sources for the same rings, a duplication invitation (#383). Lazy per
  // index: playback warms only what it draws (no O(n) bill on first render),
  // while gazePasses' full scan fills the rest on the first click. The
  // estimated flag is kept PER SAMPLE, not discarded: gimbal yaw and pitch
  // are per-sample optional fields, so a clip that drops attitude for part
  // of a flight has some rings drawn from real data and others from the
  // assumed GHOST_EST_PITCH tilt. Reading one sample's flag would let the
  // popup omit the warning for extrapolated frames, which is exactly the
  // claim this feature must not make.
  if (!fl.rings) fl.rings = new Array(fl.pts.length);
  if (!fl.rings[i]) {
    const g = gazeRing(fl, i);
    fl.rings[i] = { ring: g.ring, estimated: g.estimated,
                    estNotes: g.estNotes, reason: g.reason };
  }
  return fl.rings[i];
}

function gazeRingsFor(fl) {
  for (let i = 0; i < fl.pts.length; i++) gazeRingAt(fl, i);
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
  // t1e is where COVERAGE ends -- one interval past the last sample's
  // timestamp -- so a label built from it reconciles with secs on screen: a
  // single-sample pass reads t0-(t0+1s) next to "1 s", not t0-t0 (#389).
  const close = () => passes.push({
    i0: start, i1: prev, t0: times[start], t1e: times[prev] + dt(prev),
    secs: secs, est: est, estNotes: notes });
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
  // #424: airspace zone volumes/footprints are also click targets with their
  // own published-facts popup -- same "owns this click" deferral the flight
  // line already gets, so clicking a zone never doubles up with an unrelated
  // gaze/no-footprint popup underneath it.
  const ownedIds = lineIds.concat(
    ['airspace-volume', 'airspace-volume-entered', 'airspace-footprint']
      .filter(id => map.getLayer(id)));
  if (ownedIds.length
      && map.queryRenderedFeatures(ev.point, { layers: ownedIds }).length) {
    return;                    // another layer's click handler owns this click
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
                    + fmtDuration(Math.round(p.t1e));
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

"""
