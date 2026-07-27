# Camera's Gaze — design

**Date:** 2026-07-27
**Issue:** [#378](https://github.com/CallMarcus/dji-drone-metadata-embedder/issues/378)
**Status:** Approved

## Problem

The 3D flight map can now put you at the drone's altitude (Ghost Camera, #372)
and show the shape of the flight in the air (flight sculpture, #375). It still
cannot answer the question people actually ask of their own footage: **what was
the camera looking at, and when did it film this spot?**

Camera's Gaze answers both. A time cursor sweeps the flight; the camera's
ground footprint is drawn on the terrain as it goes, with the four frustum
corner rays connecting camera to ground; and clicking any spot returns every
second of recording that had it in frame. The second half is the provenance
payoff — "which frames show this place" is the question a verifier asks — and
it falls out for free once footprints exist for every sample.

The 3D map also has no playback at all today; the flat map has had it since
#267 (`docs/geospatial.md` says so in as many words). The time cursor closes
that gap, and pressing play inside the ghost view rides the recorded flight in
real time instead of arrow-keying sample by sample.

This is stage 3 of the 3D arc agreed 2026-07-26. Stage 4 (separate spec)
crossfades a ghost pose to the real photo or video frame.

## Scope

- Playback, gaze patch, beam and click-a-spot lookup in the **3D template
  only** (`geo/flightmap3d_html.py`), built in JS.
- **One new GeoJSON property**: `hfov_deg`, beside the existing `vfov_deg`.
- No new CLI flags, no new dependencies, no new pinned assets (the SRI-count
  test stays unchanged). Ships inside the existing `--3d` output; the GUI gets
  it through the 3D toggle and WebView preview.
- `footprint.py`, the `--footprint` export path, and the flat map are
  untouched.

Out of scope (deferred): the flat map's "All flights (compare)" playback mode
(a patch and beam per flight at once is visual noise, and the cockpit can only
ride one flight); a persistent "everything this flight saw" coverage union
layer; interpolating footprints between samples; media crossfade (stage 4);
true gimbal attitude for Mini-series drones (#374).

## Design

### 1. Data — one new GeoJSON property

`_add_ghost_props` (`geo/flightmap.py:324`) already emits per-point
`gyaw_deg` / `gpitch_deg` / `agl_m` and per-flight `vfov_deg` from the median
focal length. It gains `hfov_deg` from the same `fov_degrees(DEFAULT_LENS,
median(focals))` call, under the same honesty rule — emitted only when the
telemetry carries focal lengths:

```python
focals = [p.focal_len for p in points if p.focal_len is not None]
if focals:
    hfov, vfov = fov_degrees(DEFAULT_LENS, median(focals))
    properties["hfov_deg"] = round(hfov, 1)
    properties["vfov_deg"] = round(vfov, 1)
```

The property therefore also appears in `-f geojson` exports and in the flat
map's embedded data, where it is unused. That is acceptable and documented:
it is one number per flight, and splitting the emitter into 2D and 3D variants
to hide it would cost more than it saves. Any existing test that asserts an
exact property set on a flight feature needs updating with it.

The template picks it up beside the existing pose arrays:
`entry.hfov = p.hfov_deg || null;`.

Nothing else moves to Python. In particular the footprint rings are **not**
embedded: at ~115 bytes per second per flight a 20-clip folder map would gain
roughly 700 KB of derivable data, several times the size of the track
coordinates themselves, and the browser can recompute them in under 5 ms.

### 2. Footprint projection in the browser — `gazeRing(fl, i)`

A port of `frustum_ground_ring` (`geo/geometry.py:21`), frustum path only.
Python's nadir-rectangle branch is not needed: a pitch is always available,
real or estimated, so there is one code path instead of two.

Parameter resolution, in order, each fallback marking the ring estimated:

| Input | Source | Fallback |
| --- | --- | --- |
| AGL | `fl.agl[i]` | none — no ring |
| gimbal pitch | `fl.gpitch[i]` | `GHOST_EST_PITCH` (−30°) |
| bearing | `fl.gyaw[i] % 360` | `courseBearing(fl.pts, i)` |
| HFOV / VFOV | `fl.hfov` / `fl.vfov` | `GAZE_FALLBACK_HFOV` / `_VFOV` |

Return shape:

```js
{ ring: null | [[lon, lat] × 5],   // closed, far-left..near-left as in Python
  reason: null | 'no altitude' | 'camera above horizon',
  estimated: boolean,
  estNotes: [] }                   // e.g. ['no gimbal pitch', 'assumed lens']
```

No ring is produced for a sample `build_footprints` would also skip: AGL
null or ≤ 0 (`reason: 'no altitude'`), or pitch at/above the horizon
(`reason: 'camera above horizon'` — reachable only from real telemetry, since
the −30° estimate never is). Ground range clamps at
`GAZE_MAX_RANGE_FACTOR * agl`, mirroring `MAX_RANGE_AGL_FACTOR = 8.0`, so a
near-horizon frame degrades to a capped trapezoid instead of an unbounded one.

The projection itself mirrors the Python line for line — camera-frame corner
rays `(sh, sv) ∈ {(-1,1), (1,1), (1,-1), (-1,-1)}`, each ray's ground distance
`min(agl / -dz * horiz, maxRange)` when it descends and `maxRange` when it does
not, then yaw-rotated and converted to degrees through `111320` m per degree of
latitude and `111320 · cos(lat)` per degree of longitude.

Fallback FOV constants mirror the generic 20 mm-equivalent 4:3 `DEFAULT_LENS`:

```js
const GAZE_FALLBACK_HFOV = 84.0;   // fov_degrees(DEFAULT_LENS, None)[0]
const GAZE_FALLBACK_VFOV = 68.0;   // fov_degrees(DEFAULT_LENS, None)[1]
```

Rings are computed once per flight at load — `fl.rings[i]` for every sample —
because the click-a-spot lookup needs all of them and the maths is pure trig
with no terrain queries.

**Honest limitation, inherited from Python:** corner rays are projected onto a
flat ground plane at the drone's AGL reference and then draped by the fill
layer. On steep terrain the drawn patch differs from the true footprint. The
same approximation is already shipping in `--footprint` KML/GeoJSON.

### 3. Playback — `pb`

Ported from the flat map's animator (`geo/flightmap_html.py:123-235`) with its
semantics kept deliberately identical, so a user who learns one map's playback
knows the other's:

- Eligibility (`runs`): a LineString flight with `times` of the same length as
  its points and a positive last time.
- `PB_SPEEDS = [1, 5, 20, 60]`, cycled by one button.
- A `requestAnimationFrame` clock advancing `pb.t` by wall time × speed,
  pausing when it reaches the end, restarting from 0 when play is pressed at
  the end.
- `positionAt(run, t)` with a monotonic `run.cursor` hint, seek-backwards
  reset included.
- Element ids `pb-play`, `pb-speed`, `pb-slider`, `pb-time`, `pb-flight`, plus
  `pb-note` for the estimated/skip badge.

Differences from the flat map, both forced by the medium:

- The control is a plain `.playback` div positioned bottom-left (there is no
  `L.control`). The ghost HUD is bottom-centre, so they do not collide.
- The picker has no "All flights (compare)" option (see Scope).

The cursor dot is layer `gaze-cursor-dot` (`circle`) over a one-point
`gaze-cursor` source, styled like the flat map's marker (radius 7, white 2 px
stroke, flight-colour fill), updated every frame.

**The patch and beam update on sample change, not per frame.** Each ring *is*
one second of recording, so interpolating rings would invent geometry; and it
bounds the work at 60× speed to ~60 small `setData` calls a second instead of
3600. `renderCursor()` runs every frame; `renderGaze()` runs when
`sampleIndexAt(run, pb.t)` — the index of the sample at or before the cursor —
changes.

### 4. Riding the cockpit

While playback is running with `ghost.active` and `ghost.flight === run`, each
frame builds an interpolated pose and applies it with **`jumpTo`, never
`easeTo`**: an ease would fight the clock and churn `moveend`, which is where
this file's existing scars are (`ghostExit`'s aborted-ease guard,
`geo/flightmap3d_html.py:463`).

```js
function posePlayback(fl, t) {
  const i = sampleIndexAt(fl, t);
  if (i >= fl.pts.length - 1) return samplePose(fl, fl.pts.length - 1);
  const t0 = fl.times[i], t1 = fl.times[i + 1];
  const f = t1 > t0 ? (t - t0) / (t1 - t0) : 1;   // as in positionAt()
  const p0 = samplePose(fl, i), p1 = samplePose(fl, i + 1);
  const d = ((p1.bearing - p0.bearing + 540) % 360) - 180;   // shortest arc
  return Object.assign({}, p0, {
    lngLat: [lerp(p0.lngLat[0], p1.lngLat[0], f),
             lerp(p0.lngLat[1], p1.lngLat[1], f)],
    altitude: lerp(p0.altitude, p1.altitude, f),
    bearing: p0.bearing + d * f,
    pitch: lerp(p0.pitch, p1.pitch, f) });
}
```

`lerp` is a two-line local helper; `Object.assign` rather than object spread
matches `applyPose`'s existing style. The final sample returns its own pose
directly, since there is no following sample to interpolate toward.

Building the pose from two `samplePose` calls reuses every existing fallback
(takeoff-elevation conversion, estimated pitch, pitch clamping) rather than
duplicating them. `ghost.idx` is kept in step with the integer sample so the
HUD and arrow keys stay coherent, and `updateHud()` fires only when that index
changes.

Three interaction rules, each chosen to stay clear of the ease hazards
`ghostEnter`/`ghostExit` already document:

- Entering the cockpit **while playing** jumps in (`applyPose(pose, 0)`)
  instead of easing over `GHOST_ENTER_MS`. You are riding; the cinematic ease
  would be overridden by the next frame anyway.
- An arrow-key step **pauses** playback. Manual control wins.
- Exiting while playing keeps the clock running third-person. `ghostExit`
  needs no change: the per-frame drive stops the moment `ghost.active` goes
  false, and the existing `once('moveend')` restore guard still applies.

### 5. The gaze patch and the beam

**One shared source pair, not one per flight.** Playback runs a single flight
at a time, so there is only ever one cursor: a `gaze` source (the ring) and a
`beam` source, recoloured through `setPaintProperty` when the selected run
changes. The patch is rendered at `pb.t = 0` at load, before play is ever
pressed, so the feature is discoverable.

Patch layers:

- `gaze-fill` — `fill`, `fill-color` = run colour, `fill-opacity`
  `GAZE_PATCH_OPACITY = 0.25`. `fill` is in MapLibre's render-to-texture
  whitelist, so it drapes onto the terrain correctly and needs no elevation
  query at all.
- `gaze-edge` — `line`, 1.5 px, run colour. Estimated rings get a dashed
  edge: `setPaintProperty('gaze-edge', 'line-dasharray', estimated ? [2, 2]
  : null)`, where `null` restores the style-spec default (solid). It is flipped
  only when that state changes, so there is no per-frame churn, and the test
  asserts the round trip in **both** directions — a reset that silently fails
  would leave every later ring looking estimated.

Both are inserted with `beforeId = flights[0].id` (when that layer exists) so
the tracks stay readable through the patch.

**The beam.** `fill-extrusion` can only make vertical prisms measured from the
terrain surface, so each of the four corner rays is staircased into
`GAZE_BEAM_STEPS = 16` short prisms from the camera down to that ring corner.

Heights reuse the sculpture's conversion exactly (`planksFor`,
`geo/flightmap3d_html.py:559`) — the drone's true altitude minus the local
surface, because the shader re-adds the centroid's elevation:

- `tElev = takeoffElev(fl)`; camera true altitude `tElev + agl`; camera local
  surface `terrainElevAt(camera)`; corner local surface
  `terrainElevAt(corner)`.
- Along a ray, altitude interpolates from the camera's true altitude to the
  corner's ground elevation, and the local surface interpolates between the
  two sampled elevations, so `h(s) = alt(s) − local(s)` is `agl`-equivalent
  clearance at the camera and exactly 0 at the corner.
- Elevation is sampled **twice per ray, not once per step** — 8
  `queryTerrainElevation` calls per sample instead of 64, which matters at 60×
  speed.
- Flat-mode fallback when terrain is off or any elevation is unknown:
  `h(s) = agl · (1 − s)`, which is exactly right when the extrusion measures
  from sea level.
- Each prism carries `base = max(0, min(h₀, h₁))` and `hgt = max(h₀, h₁)`, so
  consecutive prisms share altitude at their joint and the silhouette is
  continuous rather than a ladder with gaps. `fill-extrusion-base` has a
  style-spec minimum of 0, hence the clamp in JS. A step whose `hgt` computes
  ≤ 0 is dropped — the same honesty rule that breaks the curtain when the
  drone is below the rendered (canopy-inclusive) surface.
- Width reuses `sculptWidthM()`, so the rays hold a constant screen thickness
  across zooms, and the perpendicular offset maths matches `planksFor`.

Layer `beam-ray` — `fill-extrusion`, base and height data-driven,
`fill-extrusion-opacity` `GAZE_BEAM_OPACITY = 0.5`,
`fill-extrusion-vertical-gradient: false`.

Up to 64 small polygons per sample, rebuilt only on sample change.

### 6. Click a spot → the seconds that filmed it

A general `map.on('click')` handler, which bails when
`map.queryRenderedFeatures(ev.point)` hits a flight-line layer (those already
own a popup with **View from here**) and when positions are fuzzed.

For every flight with rings, ray-cast point-in-polygon against each ring;
consecutive hit samples merge into passes. In-frame seconds are counted per
sample interval (`times[i+1] − times[i]`, the previous interval for the last
sample) so a single-sample hit reads as about a second rather than zero.

Popup, built with DOM nodes and `textContent` rather than interpolated HTML
(flight names come from filenames):

> **DJI_0001** — in frame 14 s over 3 passes
> `0:12–0:18`  `1:04–1:09`  `2:31–2:33`

Each pass is a button: select that flight in the picker, seek the clock to the
pass start, and start playing. If you are already in the cockpit on that
flight, that *is* riding it — no separate control needed. The list caps at
`GAZE_MAX_PASSES = 12` with a "+N more" note, so a hover over one spot cannot
produce a thousand buttons. When the matched flight's rings were estimated,
the popup says so. A miss gets an explicit answer — "No recorded frame covered
this spot" — rather than silence.

Simultaneously a `gaze-hits` source highlights the matching stretches of
flight line: one LineString per pass, extended one sample either side so a
single-sample hit is still visible, `line-color` data-driven from the flight's
colour, 6 px at 0.55 opacity, inserted with the same
`beforeId = flights[0].id` so the track still reads on top of its halo.
Cleared on popup close and replaced on the next lookup.

### 7. Visibility and rebuild triggers

`applyGazeVisibility()`, called from the same places `applySculptVisibility()`
is:

- `gaze-fill` / `gaze-edge`: visible when a run is selected, that flight is
  shown in the panel, and positions are not fuzzed. A sample with no ring is
  handled by emptying the source (§8), not by toggling visibility — one
  mechanism per concern.
- `beam-ray`: the same conditions **plus `!ghost.active`** — a beam
  originating at your own eye would fill the cockpit view, the same reason the
  sculpture steps aside.

Rebuild triggers for `renderGaze()`:

- the integer sample index changes during playback or a seek;
- the selected run changes;
- `zoomend`, sharing `rebuildSculpture`'s 0.5 m width threshold, so the beam's
  screen thickness tracks the sculpture's;
- the terminal branch of `sculptSettle()`, so the **load-time** beam corrects
  once the DEM firms up. It rides that existing bounded retry rather than
  starting a second timer. During playback no settle is needed at all — every
  sample change rebuilds the beam, so it self-corrects as tiles warm.

### 8. Failure posture and edge cases

| Condition | Behaviour |
| --- | --- |
| `--redact fuzz` | No patch, no beam, no lookup. Playback still works. A dimmed line in the flights panel says why. A footprint projected from a coordinate moved ~100 m is a confident claim about ground that was not filmed; `--footprint` already refuses redacted exports. |
| No `times_s` | Not playable and not gazeable — there is no "which second" to answer. |
| Times but no `agl_m` | Playable, no gaze. |
| Single-fix clip (Point) | Excluded from both, as it already is from the ghost view. |
| Sample with null/≤ 0 AGL, or camera at/above horizon | That second's sources are cleared rather than frozen on the last good ring, and `#pb-note` names the reason, so a vanishing patch reads as information. |
| Terrain off, or DEM cold | Patch unaffected (draped `fill`, no elevation query). Beam falls back to flat mode and corrects on the next rebuild. |
| No flight has times | No playback control, no gaze; the map is exactly what it is today. |
| No WebGL | Existing plain-HTML fallback covers everything. |

## Testing

Two new files on the `browser` marker, using the `serve_map` / `terrain_stub` /
`terrain_steps` fixtures already in `tests/browser/conftest.py`:
`tests/browser/test_flightmap_3d_playback.py` and
`tests/browser/test_flightmap_gaze.py`.

**Cross-language parity is the load-bearing test.** Browser tests run in the
same Python process as the package, so the test imports `frustum_ground_ring`
directly, calls `page.evaluate("gazeRing(...)")` on the same inputs, and
compares corner by corner to 1e-9°. Cases: a nadir frame, an oblique frame, and
a near-horizon frame that exercises the 8 × AGL clamp. A second probe reads
`GAZE_FALLBACK_HFOV` / `GAZE_FALLBACK_VFOV` off the page and asserts them
against `fov_degrees(DEFAULT_LENS, None)`. Without these two the JS port is
free to drift from the Python it mirrors.

Playback: the clock advances and pauses at the end; the slider seeks; the speed
button cycles `[1, 5, 20, 60]`; the picker switches flights and resets the
clock; a flight without times is absent from the picker; a map with no
playable flight has no control at all.

Cockpit riding: the applied pose tracks the samples as the clock runs; an
arrow-key step pauses; entering while playing jumps rather than eases (assert
no ease is in flight); exiting while playing leaves the clock running and
restores the saved view.

Gaze: the patch polygon matches the parity test's ring for a known sample; an
above-horizon sample clears the source and sets `#pb-note`; a null-AGL sample
clears it; the edge's dash state flips with estimated-ness; the patch is
present at load before play is pressed.

Beam: prisms exist for a known sample; `base`/`hgt` are continuous along a ray
(each step's base equals the neighbour's height at the joint); the beam is
hidden while `ghost.active` and visible again after exit; flat mode with
terrain off puts `hgt` at `agl` at the camera end; a below-surface step is
dropped over the `terrain_steps` cliff.

Lookup: a click inside a known ring returns the expected pass list; a click
outside every ring returns the miss message; a pass button seeks the clock and
starts playback; the highlight appears and clears on popup close; a click on a
flight line still opens the flight popup, not the lookup; `--redact fuzz`
yields no gaze layers while playback still works.

Python: one unit test in `tests/test_geo_flightmap.py` for `hfov_deg` emission
(present with focal lengths, absent without), beside the existing `vfov_deg`
assertions.

## Docs

`docs/geospatial.md`: the 3D section's closing claim that "there's no playback
in the 3D view" (line 269) stops being true and must be rewritten. A new
**Camera's gaze** subsection follows the ghost-camera and sculpture ones,
covering the time cursor, riding the flight from the cockpit, the patch and
beam, clicking a spot to find footage, and the two honesty gates (fuzzed
positions turn it off; missing gimbal attitude makes it an estimate). README's
feature list gains one line. The changelog is generated at release time and
needs no manual edit.
