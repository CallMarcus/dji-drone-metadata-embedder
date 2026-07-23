# Flightmap 3D terrain view (`--3d`) — design

*2026-07-23 · issue [#268](https://github.com/CallMarcus/dji-drone-metadata-embedder/issues/268) · status: approved*

## Summary

A second, separate HTML template for `dji-embed flightmap`: MapLibre GL JS
rendering flight tracks as colored 3D lines at recorded altitude, draped
over real terrain. The 2D Leaflet map stays the default and is untouched —
`--3d` writes a sibling file. Keyless end to end: OSM raster basemap,
Mapterhorn terrain tiles, MapLibre from a pinned CDN URL. No build step,
no API keys, no new Python dependencies.

Scope decisions (Marcus, 2026-07-23): **lean viewer** (no playback, one
basemap style), **`--3d` flag writing `flightmap-3d.html`** (2D map never
clobbered), **CLI-first** (GUI checkbox is a follow-up issue).

## CLI surface

- New `--3d` boolean option on `flightmap` (Click parameter name
  `three_d`; `3d` is not a valid Python identifier).
- Valid only with the HTML format: combining `--3d` with `--format
  kml|geojson|all` raises `click.UsageError` — those formats have no 3D
  variant.
- Default output: `<folder>/flightmap-3d.html`. `--output` overrides as
  usual. The 2D default (`flightmap.html`) is unaffected; both maps
  coexist in a folder.
- `--tile-style` is accepted but **ignored with a warning** under `--3d`
  (single basemap in this version) — warning, not error, because the GUI
  and shell history may pass it habitually.
- All other options behave identically: `-r`, `--redact`, `--join-gap`,
  `--tz-offset`, `--title`, `--progress jsonl` (the `result` event lists
  the 3D file in `outputs` exactly like any other target).

## New module: `geo/flightmap3d_html.py`

A sibling of `flightmap_html.py` with the same contract and structure:

- `flights_to_3d_html(tracks: list[Track], title: str) -> str`
- `write_flights_3d_html(tracks, output_path, title) -> Path`
- Consumes the **same** `flights_to_geojson()` output as the 2D map — no
  changes to `flightmap.py` or the GeoJSON shape. Data is embedded in the
  same `<script type="application/json">` block with the same
  backslash-u003c escaping of `<` (no `</script>` breakout).
- MapLibre GL JS **5.24.0** loaded from unpkg with pinned version **and
  SRI hashes**, matching the Leaflet pins in the 2D writers. (v6 was
  evaluated 2026-07-23 and rejected: it is ESM-only — no UMD bundle —
  and its multi-file module graph defeats the single-script-tag + SRI
  pattern every template here uses. v5 is the maintained UMD line.)
- Module docstring documents AWS Terrarium
  (`s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png`,
  `encoding: "terrarium"`) as the drop-in replacement terrain source if
  Mapterhorn ever disappears. Terrarium is NOT coded as a live fallback.

## Map composition (`_APP_JS`)

- **Basemap:** OSM raster tiles — same URL template and attribution text
  as `tiles.py`'s `osm` entry — draped over the terrain surface.
- **Terrain + hillshade:** Mapterhorn (`raster-dem`, TileJSON at
  `https://tiles.mapterhorn.com/tilejson.json`, keyless; Copernicus
  GLO-30 base, genuinely global coverage including >60°N). Separate
  terrain and hillshade sources per the MapLibre example idiom.
- **Camera:** starts pitched (~60°) and fitted to the union of track
  bounds.
- **Tracks:** one line layer per flight in the same color rotation as the
  2D map, **draped on the terrain surface** (MapLibre line layers are
  strictly 2D — see "Altitude representation" below). Single-fix `Point`
  features (degenerate flights) render as a circle layer, not a line —
  the data walk must not assume LineString.
- **Popups:** click a track → popup with the same summary fields the 2D
  map shows (name, start, duration, altitude summary).
- **Flight toggle:** a plain HTML overlay panel with one checkbox per
  flight (show/hide its layer). Not a ported Leaflet layer control.
- **Attribution:** OSM contributors + Mapterhorn/Copernicus, always
  visible per both providers' terms.

## Altitude representation (amended 2026-07-23)

The original design called for tracks rendered *at* recorded altitude
with a takeoff-anchoring correction. Verification against the MapLibre
style spec killed that: **MapLibre has no way to render line layers at
an elevation** — no `line-z-offset` (that is Mapbox-proprietary), and
elevated flight paths are an open upstream request
([maplibre-gl-js#644](https://github.com/maplibre/maplibre-gl-js/issues/644),
duplicate [#6755](https://github.com/maplibre/maplibre-gl-js/issues/6755)
filed for exactly this drone use case).

Decision (Marcus, 2026-07-23): **draped tracks.** Lines follow the
terrain surface like a GPS ground trace; the 3D value is the terrain
relief itself under a tilted camera. Altitude numbers stay in the
popups (height-above-takeoff preferred, as in 2D). The whole anchoring
scheme is dropped — there is nothing for it to act on. At-altitude
rendering (fill-extrusion "curtains" or a deck.gl overlay, or native
support if #644 lands) is explicitly a follow-up, not this slice.

## Degradation

- **Mapterhorn unreachable:** catch the MapLibre source `error` event,
  disable terrain, show a dismissible banner ("terrain tiles unavailable
  — showing flat view"). Tracks, popups, and the toggle keep working as
  a flat tilted map.
- **Fully offline:** same posture as the 2D map today — basemap tiles
  don't render, embedded data still loads, and the existing docs line
  ("the map file needs a connection to render") covers it.
- **WebGL unavailable:** MapLibre throws on construction; catch and show
  a plain-HTML message naming the 2D map as the alternative.

## Testing

Python (pytest, mirroring `test_flightmap_html` structure):

- CLI wiring: `--3d` default filename, `--output` override, UsageError on
  non-HTML formats, `--tile-style` warning, JSONL `result.outputs`.
- Generated HTML: embedded GeoJSON present and parseable, pinned MapLibre
  URL + SRI attributes, Mapterhorn TileJSON URL, both attribution
  strings, `<` escaping (no literal `</script>` in data), single-fix
  flight handled.

Browser (durable browser suite, Track B pattern): one test that loads a
generated `flightmap-3d.html` and asserts the map initializes and the
flight-toggle panel lists the expected flights. Terrain/WebGL behavior in
headless CI degrades along the paths above — the test asserts presence,
not rendered pixels.

## Docs

- `docs/user_guide.md`: flightmap section gains a 3D subsection (what it
  is, the anchoring note, the terrain-tiles network dependency).
- `docs/decision-table.md`: row for 2D vs 3D map.
- `docs/geospatial.md`: 3D view section.
- `README.md`: one-liner + flag in the flightmap section.
- `HELP.md`: recipe line for "see my flights in 3D".

## Out of scope / follow-ups

- Playback in 3D (file only if the viewer earns it; `times_s` is already
  in the data).
- Tracks rendered at altitude — blocked upstream (MapLibre #644);
  curtain-extrusion and deck.gl approaches were considered and deferred.
- Basemap style choice in 3D.
- GUI exposure: follow-up issue — Flight map options checkbox +
  `CommandBuilder` + `ExistingMapFinder` probing `flightmap-3d.html`
  (the WebView2 preview supports WebGL, so it will render inline).
- Live Terrarium fallback source.
