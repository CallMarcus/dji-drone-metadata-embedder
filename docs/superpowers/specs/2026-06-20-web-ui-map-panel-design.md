# Design: Web-UI flight-path map panel (#222)

_Date: 2026-06-20_

## Context

The local web UI (#170, shipped) is a no-build, vanilla-JS hash-routed SPA served
by Flask (`src/dji_metadata_embedder/ui/`). Tabs (Doctor / Embed / Validate /
Convert / Check) each render into `#app` via a `routes` map in `static/app.js`;
an `api()` helper attaches the session token and parses JSON. The server
(`ui/server.py`) gates every non-public route by token and sets a strict
Content-Security-Policy (`default-src 'self'; script-src 'self'; style-src
'self'; img-src 'self' data:; connect-src 'self'; …`).

Two pieces already exist that this builds on:

- `geo/track.py` + `geo/geojson.py` — the canonical `Track` and
  `track_to_geojson` (redaction applied once at the Track layer).
- `geo/html_viewer.py` (#221, shipped) — a standalone Leaflet+OSM viewer whose
  embedded app JS (altitude-colored polyline, start/end markers, clickable
  points, `fitBounds`) is directly portable into the panel.

This spec adds an **in-app interactive map panel** (the headline of mapping
Phase 3): a new "Map" tab that fetches the same GeoJSON the CLI produces and
renders the flight path, an altitude profile, and a "play the flight" marker.

## Goals

- A **"Map" tab** that takes an SRT path, fetches GeoJSON from a new endpoint,
  and renders the flight path on a Leaflet/OSM basemap.
- An **altitude profile** chart and a **playback marker / scrubber** over the
  track.
- **One source of truth**: the front-end consumes the same `track_to_geojson`
  output the CLI emits — no re-parsing in the browser.
- **Redaction-aware**: redaction is applied server-side, so no exact coordinates
  reach the browser when `--redact`-equivalent is selected.
- Keep the UI's strict CSP almost intact: the only relaxation is allowing OSM
  raster tiles as images.

## Non-goals

- **Video-synced scrubbing** (scrub the path in lock-step with the embedded
  video). Deferred: the UI serves no video today; needs a video route + frame
  sync. The scrubber here scrubs the *track*, not a video.
- **Footprint-polygon overlay** (#215). Not in v1; the endpoint returns track
  GeoJSON only. A future toggle can add `Polygon` features.
- **Offline/vendored map tiles.** Basemap tiles load from the network; only the
  app shell and Leaflet are local. (Consistent with the standalone viewer.)
- **A JS build step / framework.** The UI stays no-build vanilla JS.

## Architecture: one Track, rendered in the browser

```
SRT path + redact ─► POST /api/geojson ─► build_track() ─► track_to_geojson()
                                                              │ (JSON)
                                                              ▼
                       static/map.js (Leaflet + SVG chart + playback)
```

The server owns parsing and redaction; the browser only renders. The map logic
lives in its own `static/map.js` module (not bloating the 383-line `app.js`),
loaded alongside a self-hosted Leaflet.

## Backend (`ui/server.py`)

- **New route `POST /api/geojson`** — body `{srt: str, redact?: "none"|"drop"|"fuzz"}`.
  - Validates `srt` is an existing file (else `400`, mirroring `/api/convert`).
  - `track = build_track(Path(srt), redact=redact or "none")`.
  - Returns `jsonify(track_to_geojson(track))`.
  - Token-gated by the existing `before_request` (it is not a public path).
  - Errors return `{"error": ...}` with `400`/`500`, matching the other
    `/api/*` handlers.
- **CSP change** in `_security_headers`: `img-src 'self' data:` becomes
  `img-src 'self' data: https://*.tile.openstreetmap.org`. This is the only
  relaxation; `script-src`/`style-src`/`connect-src` stay `'self'`. Leaflet
  raster tiles are `<img>` elements, so `img-src` is sufficient (no
  `connect-src` change needed).

## Vendored Leaflet (`ui/static/vendor/leaflet/`)

Leaflet **1.9.4** (matching `geo/html_viewer.py`) committed locally:
`leaflet.js`, `leaflet.css`, and the `images/` referenced by the CSS
(`marker-icon.png`, `marker-shadow.png`, etc.). Fetched from the pinned unpkg
release and verified against the SRI hashes already in `html_viewer.py`
(`_LEAFLET_CSS_SRI`, `_LEAFLET_JS_SRI`) before committing.

Self-hosting keeps `script-src`/`style-src` at `'self'`. **No `'unsafe-inline'`
is required**: Leaflet positions panes and tiles through the CSSOM
(`element.style.transform = …`), which CSP `style-src` does not govern — only
markup `style=""` attributes and `<style>` blocks are, and Leaflet uses neither.
Leaflet's CSS references its marker images by relative `url(images/…)`, resolved
under `'self'`.

## Front-end

### `templates/index.html`
- Add a **"Map" tab**: `<a href="#/map" class="tab" data-tab="map">Map</a>`.
- In `<head>`, add the vendored Leaflet stylesheet; before `app.js`, add the
  vendored `leaflet.js` and the new `map.js` (both via `url_for('static', …)`).

### `static/app.js`
- Add one route: `map: (root) => window.djiMap.render(root)`. No other changes;
  the existing `api()` helper and token flow are reused by `map.js`.

### `static/map.js` (`window.djiMap`)
A self-contained IIFE exposing `render(root)`:
- **Form**: SRT path text input, a redact `<select>` (none/drop/fuzz, default
  none), and a "Load" button.
- **On load**: `POST /api/geojson` via the shared token-aware fetch (reuse
  `window.djiEmbed.api`), then:
  - **Map**: init Leaflet, OSM tile layer, draw the altitude-colored polyline,
    start/end markers, and clickable per-point markers; `fitBounds` to the
    track. Ported from `html_viewer.py`'s `_APP_JS`.
  - **Altitude profile**: an inline **SVG** path of `abs_alt` across the track
    (no charting dependency), with a vertical cursor line.
  - **Playback**: a play/pause button and a range **scrubber** `[0, N-1]`. A
    Leaflet marker advances along the track on a timer; scrubbing moves the
    marker and the chart cursor; the three stay in sync.
- **Empty/edge states**: no GPS fix (empty features) or `redact=drop` (empty
  track) → an inline "No GPS track in this clip" message instead of a map.

### `static/app.css`
Add styles for the map container height, the SVG chart, and the playback
controls. Stays `'self'`.

## Data flow & redaction

SRT path + redact → `/api/geojson` → server `build_track(redact=…)` →
`track_to_geojson` → JSON → `map.js`. Because redaction is enforced at the Track
layer server-side, `drop` yields an empty track and `fuzz` yields ~100 m
coarsened coordinates *before* anything leaves the server — the browser never
sees exact coordinates under redaction.

## Error handling

- Invalid/missing SRT path → `400` → inline error in the panel.
- Server/parse error → `500` → inline error.
- Track with no GPS fix or fully redacted → empty-state message, no map crash.
- Tile fetch failures are Leaflet's own concern (network); the path still
  renders over a blank basemap.

## Verification

- **Backend** (`tests/test_ui_server.py`, Flask test client; the module is
  skipped when Flask is not installed, matching the existing UI tests):
  - `/api/geojson` for a sample SRT → `200` and a `FeatureCollection`.
  - Missing/invalid `srt` → `400`.
  - `redact=fuzz` → coordinates coarsened (3 dp); `redact=drop` → the LineString
    feature has null geometry and no Point features.
  - A response/CSP assertion that `img-src` includes
    `https://*.tile.openstreetmap.org`.
- **Front-end**: this project has no JS unit-test harness, so `map.js` is
  covered by the endpoint tests plus a manual smoke (open the Map tab against a
  sample SRT and confirm the path, chart, and playback render). A lightweight
  test asserting `index.html` references `map.js` and the Map tab pins the
  wiring.
- **Docs**: a "Map" subsection in `docs/user_guide.md`.

## Issue / roadmap mapping

- Implements **#222** (mapping Phase 3, gated on #170 which has shipped).
- Consumes the existing `track_to_geojson` (#215 Phase 1) — the same data the
  standalone viewer (#221) renders.
- **Deferred to future issues**: video-synced scrubbing; a footprint-polygon
  overlay reusing the #215 `Polygon` features.
