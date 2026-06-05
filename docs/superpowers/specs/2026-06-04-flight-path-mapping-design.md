# Design: Flight-path mapping (track export + map viewer)

_Date: 2026-06-04_

## Context

DJI footage carries a per-frame GPS track that the project already parses
(`parse_dji_srt`, `parse_telemetry_points`) and exports as GPX/CSV. Several
drone apps render that track as an overlay on a map (Google Maps, Google
Earth). This is squarely in the project's stated
[use-for-good direction](https://github.com/CallMarcus/dji-drone-metadata-embedder#intended-use--scope): georeferencing
for mapping, journalism/OSINT verification, SAR, and damage assessment.

Two existing issues already cover the *export-to-external-tools* half:

- **#215** — `feat(geo): camera footprint + KML/GeoJSON export`. Bundles the
  hard camera-footprint-polygon projection math with a KML/GeoJSON export.
- **#217** — MISB 0601 KLV + Cursor-on-Target export (pro FMV/GIS interop).

What no issue covers yet is an **in-app viewer** — the app *rendering* the path
on a map itself, not just producing files for other tools. That is the headline
new work here.

## Goals

- Ship a small **track export foundation** (GeoJSON + KML) that external map
  tools render *and* that our own viewers consume.
- Ship a **standalone HTML viewer** that draws the flight path on a map with no
  external tool, no server, and no API key.
- Lay the path for a **richer interactive map** inside the existing local web
  UI (`feat/issue-170-web-ui`).
- Reuse the existing parser and redaction; add no required runtime
  dependencies for the CLI.

## Non-goals

- **Camera-footprint polygons** (gimbal + lens FOV → ground coverage). Stays as
  the harder follow-up tracked by #215.
- **MISB KLV / CoT interop** (#217) — separate effort.
- **Burning a map overlay into the video** (picture-in-picture). Out of scope.
- **Google Maps JS API** — rejected (API key + billing + ToS limits on storing/
  displaying data). OpenStreetMap/Leaflet is the basemap.
- Offline/vendored map tiles. Basemap tiles load from the network; only the
  flight data is embedded. A vendored-offline mode can come later if requested.

## Architecture: one Track, many renderers

A single canonical `Track` is built once from the existing parser and passed
through redaction. Every renderer consumes that Track (or the GeoJSON derived
from it). Redaction is enforced once, at the Track layer, so no renderer can
bypass `--redact`.

```
parse_dji_srt() ─► Track (points: lat, lon, abs_alt, rel_alt, speed?, time)
                     │  (redaction applied here)
        ┌────────────┼─────────────────┐
        ▼            ▼                  ▼
   GeoJSON        KML          (viewers render the GeoJSON)
     │
     ├─► Phase 2: standalone HTML (Leaflet template, GeoJSON embedded inline)
     └─► Phase 3: web-UI map panel (Leaflet front-end fetches GeoJSON)
```

New `geo/` package (alongside `telemetry_converter.py`, not inside it):

- `geo/track.py` — build the normalized `Track` from existing parse output.
- `geo/geojson.py` — `Track` → GeoJSON `FeatureCollection`.
- `geo/kml.py` — `Track` → KML.
- `geo/html_viewer.py` — `Track`/GeoJSON → self-contained HTML.

## Phase 1 — track export foundation

- **CLI:** `dji-embed convert geojson <SRT>` and `dji-embed convert kml <SRT>`,
  with batch support mirroring the existing `gpx`/`csv` subcommands.
- **GeoJSON:** `FeatureCollection` with a `LineString` for the track plus
  per-point `Point` features carrying `abs_alt`, `rel_alt`, `speed` (if
  available), and `timestamp` properties.
- **KML:** a `LineString` placemark (with altitude) that opens directly in
  Google Earth.
- **Dependencies:** none — pure stdlib JSON/string serialization.
- **Privacy:** routed through existing redaction (`--redact drop/fuzz`).
- **Tests:** golden fixture → expected GeoJSON/KML structure; CLI smoke tests.

This is a thin serializer over data we already parse, and it unblocks Phases
2–3. It replaces the *track* portion of #215; footprint polygons remain #215's
follow-up.

## Phase 2 — standalone HTML viewer

- **CLI:** `dji-embed convert html <SRT>` → a single `flight.html`.
- **Render:** Leaflet + OpenStreetMap tiles. Polyline auto-zoomed to fit,
  start/end markers, clickable points popping up `abs_alt`/`speed`/`timestamp`,
  and the path **colored by altitude**.
- **Dependencies:** none in Python — an HTML template with the GeoJSON embedded
  inline; Leaflet pulled from CDN.
- **Tradeoff:** basemap tiles and the Leaflet library load from the network; the
  flight data itself is embedded, so the file is portable but not fully offline.
  Documented in `--help` and `docs/`.
- **Tests:** assert the embedded GeoJSON is present and well-formed; smoke test
  that the file is produced for a fixture.

## Phase 3 — web-UI interactive map

- Extends `feat/issue-170-web-ui`: a map panel whose front-end fetches the same
  GeoJSON the CLI produces. Richer extras live here — altitude profile chart,
  "play the flight" animation, video-synced scrubbing.
- **Depends on** the web-UI branch landing first; kept roadmap-level / lighter
  spec until then.

## Rejected alternatives

- **Google Maps JS API** — API key + billing + ToS restrictions on storing/
  displaying the data. OSM/Leaflet avoids all of it.
- **folium** (Python) — adds folium+branca runtime deps for what a template
  string does. Not worth it for a lean CLI.

## Verification

- Unit tests per serializer: known fixture → expected GeoJSON/KML structure.
- HTML viewer: embedded-GeoJSON presence + file-produced smoke test.
- CLI smoke tests for the new `convert` subcommands (incl. `--redact`).
- Reuse existing golden fixtures under `samples/`.

## Issue / roadmap mapping

- **Phase 1 → re-scope #215**: split acceptance criteria so track-only
  `convert geojson`/`convert kml` lands first; footprint polygons become a
  follow-up checklist item.
- **Phase 2 → new issue**: standalone HTML flight-path viewer.
- **Phase 3 → new issue** linked to #170: interactive map panel in the web UI.
- **Roadmap**: a short "Geospatial / mapping" entry in
  `docs/development_roadmap.md` grouping the three phases.
