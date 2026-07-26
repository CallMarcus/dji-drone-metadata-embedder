# Flightmap 3D "flight sculpture" — design

**Date:** 2026-07-26
**Issue:** [#375](https://github.com/CallMarcus/dji-drone-metadata-embedder/issues/375)
**Status:** Approved

## Problem

The 3D flight map (#268, v2.1.0) drapes tracks on the terrain surface because
MapLibre cannot render line layers at altitude (upstream
maplibre/maplibre-gl-js#644). Ghost Camera (#372) put the viewer *at* the
drone's altitude, but the flight's shape in the air is still invisible from
the outside: from the overview camera a 30 m hover and a 300 m transit look
identical.

The **flight sculpture** makes altitude a thing you can see: a translucent
light curtain rising from the ground to the drone, capped by a solid ribbon at
true flight altitude. It reads as an object over the landscape — the shape of
the flight, standing up out of the terrain — while remaining a literal plot of
recorded `rel_alt`. Verification made visual again, per the project's
use-for-good direction: a curtain that stands on the ground where the drone
was tells you the altitude telemetry agrees with the terrain.

This is stage 2 of the 3D arc agreed 2026-07-26. Later stages (separate
specs): "Camera's Gaze" footprint-sweep playback and search-footage-by-place,
then crossfading a ghost pose to the real photo/video frame.

## Scope

- Sculpture geometry in the **3D template only**, built in JS at load time.
- No new GeoJSON properties, no new CLI flags, no new dependencies, no new
  pinned assets (SRI-count test unchanged). Ships inside the existing `--3d`
  output; the GUI gets it through the 3D toggle and WebView preview.
- One new global toggle in the existing flights panel.

Out of scope (deferred): colour ramps encoding speed/altitude/time, animation
or playback of the sculpture, any 2D-map changes, altitude geometry in the
`-f geojson` export, media crossfade.

## Design

### 1. Vehicle — `fill-extrusion`, not a custom WebGL layer

The arc notes assumed a small hand-rolled custom WebGL layer (anti-bloat: no
deck.gl). A spike against the pinned MapLibre 5.24.0 UMD build, run through
the `terrain_stub` browser fixture Ghost Camera added, ruled that out.

**Custom `'3d'` layers are unusable with terrain enabled.** MapLibre calls the
layer's `render()` and the matrix is correct, but with the default depth state
every fragment is depth-rejected: nothing draws, at any altitude. Confirmed by
reading the centre pixel back immediately after `drawArrays` — it still holds
the already-composited terrain scene, so the rejection is against terrain's
depth, not a projection error. The escape hatches each cost something:

| mode (terrain on) | near quad | far quad | verdict |
| --- | --- | --- | --- |
| MapLibre default | 0 px | 0 px | invisible |
| `disable(DEPTH_TEST)` | 1506 px | 8346 px | draws, far paints over near |
| `clear(DEPTH_BUFFER_BIT)` | 8142 px | 1710 px | self-sorts, no terrain occlusion |

(The `clear` row matches the terrain-off baseline of 8088/1730, i.e. correct
self-sorting.) A custom layer can be visible, self-sorted, or terrain-occluded
— never all three.

**`fill-extrusion` renders correctly under terrain** and carries data-driven
`-base` and `-height`, verified in the same spike. Its vertex shader applies
`get_elevation(a_centroid)`, so base and height are measured **from the
terrain surface, not sea level**, with elevation sampled at each polygon's
centroid. That is exactly the semantics the sculpture wants: the `agl_m` array
Ghost Camera already emits drops straight in, with no `queryTerrainElevation`
calls and none of the cold-DEM race that cost Ghost Camera a review round.

Both custom layers and `fill-extrusion` are absent from MapLibre's
render-to-texture whitelist (`background`, `fill`, `line`, `raster`,
`hillshade`, `color-relief`), so both draw in the main pass after the terrain
mesh; only `fill-extrusion` survives it.

### 2. Geometry — 3D template JS (`geo/flightmap3d_html.py`)

Built in JS at load time from the flight entry's existing `pts` (full
`[lon, lat, alt]` triples) and `agl` arrays. Nothing is added to the embedded
GeoJSON, so archive-scale files do not grow and the `flights_to_geojson`
contract is untouched.

For each consecutive point pair where **both** ends have a non-null AGL, one
rectangular "plank" polygon centred on the segment, of width *W* (below),
carrying its height as a property. Both layers read that one feature through
different expressions, so the geometry is built and stored once:

| layer | `fill-extrusion-base` | `fill-extrusion-height` | opacity | vertical-gradient |
| --- | --- | --- | --- | --- |
| curtain | `0` | `['get', 'hgt']` | 0.35 | on |
| ribbon | `['get', 'rbase']` | `['get', 'hgt']` | 1.0 | off |

(`hgt` is height above the local surface — see the amendment below, which
replaced the original raw `agl` with a true-altitude conversion. `rbase` is
the ribbon's clamped base, computed in JS rather than as a `max` expression
so no expression-language support needs assuming.)

The ribbon's base is clamped at 0 because `fill-extrusion-base` has a
style-spec minimum of 0 — without the clamp a hover below the 6 m ribbon
thickness would compute a negative base. Clamped, such a segment renders as a
ground-standing block, which is what a 4 m hover should look like.

Mean AGL per segment matches the centroid-sampling the shader already does.

**Amendment 2026-07-26 (post-Task-6 review): heights are converted to true
altitude.** As first written this design put `agl_m` straight into
`fill-extrusion-height`, which was wrong. `agl_m` is height above the
*takeoff point*, but `fill-extrusion` anchors to the *local terrain under
each segment*, so the curtain top landed at `local_ground + rel_alt` instead
of the drone's real altitude of `takeoff_elevation + rel_alt`. The two agree
only where the ground sits at takeoff level.

That is not merely a labelling error. DJI drones hold altitude, not ground
clearance, so a level flight toward a rising ridge keeps a constant `rel_alt`
while its real clearance shrinks. The original geometry would have drawn a
constant-height curtain riding up the hillside — showing steady clearance
exactly where the truth is a closing gap, which inverts the safety-relevant
reading in a feature framed around verification.

Each segment's extrusion height is therefore
`(takeoff_elevation + mean_AGL) - local_terrain_elevation`, both elevations
read with `map.queryTerrainElevation` (gated on `map.getTerrain()`, since it
returns 0 rather than null when terrain is off or tiles are cold). The
shader then re-adds the local elevation, so the top lands at true altitude
and the curtain's length is genuine ground clearance. With terrain
unavailable both elevations are absent and the height falls back to plain
`mean_AGL`, which is correct there because `get_elevation` returns 0. A
segment computing a non-positive height — below the rendered surface, from a
datum artefact or a rooftop launch — is skipped rather than drawn flat.

Cold DEM tiles make the first build a flat-mode approximation, so the
sculpture re-samples on a bounded timer and rebuilds once tiles land. `idle`
is not usable for this: it parks under the load-time `fitBounds` ease, a
gotcha established in #372.
Tracks are decimated to one point per second upstream (`_decimate_points`), so
a 20-minute flight yields ~1200 segments — well inside `fill-extrusion`'s
building-scale budget.

**Colour and the fade.** Each flight keeps the identity colour it already has
in the panel and the 2D map, applied per feature via `['get', ...]`. The
ground-ward fade comes from MapLibre's built-in
`fill-extrusion-vertical-gradient`, which darkens an extrusion's sides toward
its base. A true alpha fade is not available: the fill-extrusion fragment
shader hardcodes `v_color`'s alpha to `1.0` (so `fill-extrusion-color` alpha
is ignored) and `fill-extrusion-opacity` is `data-constant`, i.e. layer-level
only. Stacking banded layers at different opacities would buy a real alpha
ramp at 3× the geometry plus z-fighting at the seams; the built-in gradient is
taken instead. Note the gradient term saturates for tall extrusions
(`pow(height/150, 0.5)`), so on high flights the fade concentrates in the
lower part of the curtain — acceptable, and honest about where the ground is.

**Width is zoom-adaptive.** *W* is recomputed on `zoomend` to hold roughly 3
screen pixels, clamped to [4 m, 60 m], and pushed with `setData`. A fixed
metre width fails at both ends: too thin and the sculpture vanishes exactly
when you zoom out to see the whole flight, too wide and it is a slab up close.

### 3. Layers and controls

Two layers per flight, `sculpt-<i>-curtain` and `sculpt-<i>-ribbon`,
added after the flight's track layer. Per-flight layers (rather than two
shared layers filtered by a property) keep the existing panel checkbox logic —
which today flips one `visibility` — a straight extension.

- **Per-flight checkbox** (existing): hides that flight's track *and* both of
  its sculpture layers together.
- **Global "Sculpture" checkbox** (new, appended to the panel below a
  separator): hides every sculpture layer, respecting per-flight state — a
  flight already unchecked stays hidden when the sculpture is switched back
  on. On by default: showing the flight's relationship to the terrain is what
  `--3d` is for.
- **Ghost mode**: entering hides all sculpture layers (a solid ribbon at the
  camera's exact altitude would sit across the cockpit view), exiting restores
  them subject to both toggles.

### 4. Failure posture and edge cases

- **No AGL for a flight** (SRT variants without `rel_alt`): that flight gets no
  sculpture layers. If *no* flight has AGL, the global toggle is not added at
  all rather than offering a control that does nothing.
- **Null AGL at a point:** the segment is skipped, breaking the curtain there
  rather than interpolating across a gap of unknown length.
- **Single-fix `Point` flights:** no sculpture (no segments), same exclusion as
  `times_s` and the ghost arrays.
- **Terrain unavailable:** the existing flat-view banner already covers it, and
  the sculpture degrades correctly — `get_elevation` returns 0, so extrusions
  sit on the flat plane at the same AGL.
- **`redact="fuzz"`:** coordinates are already fuzzed upstream in `Track`, so
  the sculpture inherits the fuzzing with no special handling.

## Testing

- **Browser suite:** sculpture layers exist with type `fill-extrusion`;
  per-segment `height` tracks the converted `hgt`; the global toggle hides
  and restores;
  a per-flight checkbox hides that flight's sculpture; per-flight state
  survives a global off/on cycle; ghost enter hides the sculpture and exit
  restores it; a flight without AGL produces no sculpture layers and no
  toggle; zoom change updates the plank width. SRI-count test unchanged.
- **New fixture — stepped DEM.** The existing `terrain_stub` serves a constant
  elevation, which cannot test occlusion at all. A stepped variant (two
  elevations across a tile boundary, tilejson `maxzoom` raised so a step falls
  inside the viewport) settles the one open risk: whether terrain occludes the
  extrusions, i.e. whether a ridge hides the ribbon behind it. The fixture is
  reusable for the rest of the arc. If occlusion turns out not to work, the
  sculpture still ships — it would read as an X-ray view through hills, which
  is a visual regret, not a correctness bug — and the finding is recorded.
- **E2E:** Marcus eyeballs the real hilly-terrain footage staged for #372; the
  curtain standing on the ground under the track is the acceptance criterion.
  WebView2 behaviour piggybacks on the pending #366 hardware check.

## Docs

Flightmap docs section covering what the sculpture shows, that curtain height
is AGL (not absolute altitude) and why, the toggle, and the no-`rel_alt`
limitation. `docs/geospatial.md`, beside the Ghost camera section.
