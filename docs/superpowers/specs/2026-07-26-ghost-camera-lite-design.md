# Flightmap 3D "Ghost Camera" cockpit view — design

**Date:** 2026-07-26
**Issue:** [#372](https://github.com/CallMarcus/dji-drone-metadata-embedder/issues/372)
**Status:** Approved

## Problem

The 3D flight map (#268, v2.1.0) drapes tracks on the terrain surface because
MapLibre cannot render line layers at altitude (upstream
maplibre/maplibre-gl-js#644). The altitude, gimbal yaw/pitch, and focal-length
telemetry we already parse into every `TrackPoint` is therefore invisible in
the 3D geometry — it only surfaces as popup numbers.

MapLibre's *free camera* API has no such limitation: it can place the map
camera at an arbitrary position and orientation. That is exactly a drone pose.

**Ghost Camera** flies the map camera to the drone's recorded pose so the user
sees what the camera saw, rendered from terrain, and can scrub through
neighbouring seconds from the drone's seat. Besides the delight, this is
verification made visual: if the rendered ridgelines match the footage's
skyline, the telemetry is truthful — provenance, not targeting, per the
project's use-for-good direction.

This is stage 1 of a 3D arc agreed 2026-07-26. Later stages (separate specs):
true-altitude ribbon/curtain via a hand-rolled custom WebGL layer, "Camera's
Gaze" footprint-sweep playback + search-footage-by-place, and crossfading from
the rendered pose to the real photo/video frame.

## Scope

- Per-point gimbal/AGL data added to the flight GeoJSON (shared by the HTML
  viewers and the `-f geojson` export, same precedent as `times_s`).
- Ghost mode in the **3D template only**: enter from the track popup, cockpit
  scrub with keyboard/buttons, HUD, exit back to the overview camera.
- No new dependencies, no new pinned assets (SRI-count test unchanged), no new
  CLI flags — ships inside the existing `--3d` output. The GUI gets it for
  free through the 3D toggle and WebView preview.

Out of scope (deferred, in arc order or later): free-look while parked,
playback/animation in the 3D map, the custom WebGL layer, media crossfade,
any 2D-map changes.

## Design

### 1. Data model — `geo/flightmap.py::flights_to_geojson`

Each LineString feature's properties gain, following the `times_s` pattern:

- `gyaw_deg`, `gpitch_deg`, `agl_m` — per-point parallel arrays aligned with
  `coordinates`. An array is emitted only when at least one point in the
  flight has the value; points without it hold `null`. Rounded to 0.1° /
  0.1 m to keep archive-scale files sane.
- `vfov_deg` — per-flight scalar: the camera's vertical field of view derived
  from the flight's median `focal_len` via the `footprint.py` lens model
  (35 mm-equivalent focal length + sensor aspect). Omitted when no point
  carries `focal_len`.
- The degenerate single-fix `Point` feature gets none of these (same as
  `times_s` today).

The FeatureCollection gains a top-level `redacted` property carrying the
redaction mode (`"none"` / `"fuzz"`; `"drop"` never reaches the writer with
points). The HUD uses it so a fuzzed pose is never presented as exact.

These properties flow into the standalone `-f geojson` export too — same
precedent as `times_s`; documented in the docstring. No other Python changes:
redaction already happens once, upstream, in `Track`.

### 2. Ghost mode — 3D template JS (`geo/flightmap3d_html.py`)

**Entry.** The 3D template's popup assembly appends a "View from here" button
after `popupHtml(p)` — the shared `flightmap_js.py` snippet is untouched, so
the 2D map is unaffected. On click, the nearest track point to the clicked
`lngLat` is the starting sample. The button renders for LineString flights
only (a single-fix Point has no arrays to scrub).

**Data access gotcha.** MapLibre JSON-stringifies nested arrays in feature
properties returned by `queryRenderedFeatures`. Ghost JS therefore reads its
arrays from the embedded `FeatureCollection` script block, never from queried
properties. To map a queried feature back to the embedded data, the template
gives each feature a stable id equal to its index in the collection (queried
features do not otherwise carry their collection index).

**Pose.** Position via `maplibregl.MercatorCoordinate.fromLngLat`, with
camera height = *terrain elevation at the flight's takeoff point* (one
`map.queryTerrainElevation` per flight, cached) + `agl_m[i]`. This is
self-consistent with the rendered terrain, so a disagreement between DJI's
altitude datum and Mapterhorn's cannot put the ghost underground. Fallbacks:
absolute altitude from `coordinates` when `agl_m` is absent; terrain-less
(flat) mode works too — `queryTerrainElevation` returns null → absolute
altitude. Orientation via `FreeCameraOptions.setPitchBearing`: bearing =
`gyaw_deg[i]`, camera pitch = `90 + gpitch_deg[i]` (gimbal −90° nadir → 0,
0° horizon → 90), clamped to the maximum the spike establishes. Vertical FOV
set from `vfov_deg` on entry (if the spike confirms
`setVerticalFieldOfView` exists) and restored on exit.

**Missing gimbal data** (some SRT variants carry none): the button stays
available — yaw falls back to the course bearing toward the next point,
pitch to a fixed −30° down-tilt (tunable constant), and the HUD badges the
view as estimated. Decided over hiding the button because whole formats would
otherwise lose the feature; the badge keeps it honest.

**Cockpit scrub.** ←/→ keys and on-screen ‹ › buttons step one sample, with
hold-to-repeat; each step is a ~150 ms micro-ease. Entering and exiting ghost
mode is a ~1.2 s hand-rolled position-lerp + orientation-slerp (the free
camera has no built-in easing). While ghost mode is active the normal map
interaction handlers are disabled so they cannot fight the free camera. Esc
or the HUD's ✕ eases back to the saved overview camera, re-enables handlers,
and restores the FOV.

### 3. HUD

One overlay element, mounted on entry and unmounted on exit, styled like the
existing flights panel (plain CSS, no assets):

- **Always:** flight name; sample position as elapsed time ("0:42 / 3:10",
  from `times_s` + the flight's start); height — AGL when `agl_m` is present,
  otherwise absolute altitude, labelled which; recorded gimbal yaw/pitch —
  always the *true recorded* numbers, never the clamped ones.
- **Badges, only when they apply:** "pitch clamped to N°"; "estimated view —
  no gimbal data"; "position fuzzed ~100 m" (from `redacted`).
- **Controls:** the ‹ › step buttons and ✕ exit live on the HUD, so touch
  users get buttons and keyboard users get arrows/Esc.

**Failure posture.** The existing terrain-failure banner already covers
Mapterhorn being unreachable; ghost mode still works in that flat state
(skylines just aren't meaningful, which the banner communicates).

### 4. Spike — task 1 of the implementation plan

A headless-browser probe against the pinned MapLibre 5.24.0 UMD build,
results recorded in the plan before any template work:

1. Free-camera pitch range — are orientations past the regular 85° limit
   honoured?
2. `queryTerrainElevation` behaviour with terrain enabled and disabled.
3. Does `setVerticalFieldOfView` exist on this build?

Documented fallback if probe 1 fails: the standard-camera approximation
(`easeTo` on a look-at target projected along the gimbal ray), accepting the
85° pitch cap and approximate position.

## Testing

- **Python unit tests:** array presence/alignment/null-padding/rounding,
  emitted-only-when-any-value, `vfov_deg` derivation, `redacted` property,
  single-fix Point exclusion; golden-file updates for exporters sharing
  `flights_to_geojson`.
- **Browser suite:** open the 3D fixture; click a track → button present;
  enter ghost mode → free-camera position matches the expected Mercator pose
  within tolerance; step → HUD advances; Esc → overview camera restored.
  SRI-count test unchanged.
- **E2E:** Marcus eyeballs real footage — the ridgeline match is the
  acceptance criterion. WebView2 ghost-mode behaviour piggybacks on the
  pending #366 real-hardware preview check.

## Docs

Flightmap docs section (what the ghost view is, the provenance framing, the
estimated-view and fuzzed badges) + changelog entry.
