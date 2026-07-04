# Design: Photo map (`dji-embed photomap`)

_Date: 2026-07-04_

## Context

A user photographing every church in Finland with a drone asked for a way to
see *where his still photos were taken* on a map (Google or otherwise). The
project already renders flight tracks on maps (`geo/` package: GeoJSON, KML,
standalone Leaflet HTML viewer), but only from SRT video telemetry. DJI still
photos (JPG/DNG) carry GPS in EXIF, which no current command reads.

This is squarely in the project's stated use-for-good direction:
georeferencing, mapping, and provenance for photo archives.

## Goals

- New CLI command `dji-embed photomap DIRECTORY` that maps still photos.
- Output formats: standalone **HTML** map (default), **KML**, **GeoJSON**,
  or **all** — mirroring the `convert` command's format handling.
- Pin popups show an **embedded thumbnail** plus filename, timestamp,
  altitude, and camera settings, so the user can tell which church is which.
- Marker **clustering** in the HTML map, so many shots of one church collapse
  into an expandable cluster (the archive-scale case: hundreds of locations,
  thousands of photos).
- **No new Python dependencies.** ExifTool (already a managed external tool)
  does all EXIF reading and thumbnail extraction.

## Non-goals

- **Videos on the photo map.** Video locations/tracks already export via
  `convert`; merging photo pins and flight paths into one map is a follow-up.
- **GPS redaction.** The feature's purpose is publishing photo locations;
  `convert --redact` remains the tool for privacy-sensitive exports. Noted in
  docs.
- **Pillow-based thumbnail generation.** The EXIF-embedded preview that DJI
  writes into every photo is good enough for popups. A higher-quality
  optional-Pillow path can come later if users ask.
- **Google Maps JS API** — same rejection as the flight-path viewer (API key,
  billing, ToS). OpenStreetMap/Leaflet is the basemap.

## Command and UX

```
dji-embed photomap DIRECTORY [-o OUTPUT] [-f html|kml|geojson|all]
                             [-r/--recursive] [--title TEXT] [-v] [-q]
```

- Default format `html`; default output `photomap.html` (`.kml` /
  `.geojson`) written inside `DIRECTORY`; default title = directory name.
- `--recursive` is opt-in: a church archive is likely organized in
  per-church subfolders, and mapping the whole archive at once should be a
  deliberate choice.
- `-f all` writes all three files from one scan.

## Architecture: one PhotoPoint list, three writers

Mirrors the `Track` → renderers pattern from the flight-path design.

```
scan dir (*.jpg/*.jpeg/*.dng, case-insensitive)
   │
   ▼
one batch ExifTool call: exiftool -json -n -b <files>
   (GPS lat/lon/alt, DateTimeOriginal, Model, ISO, shutter, f-number,
    ThumbnailImage/PreviewImage as base64 — single subprocess for the folder)
   │
   ▼
geo/photomap.py ─► list[PhotoPoint]  (photos without GPS skipped + counted)
        ┌────────────┼─────────────────┐
        ▼            ▼                 ▼
     GeoJSON        KML          standalone HTML
```

- `geo/photomap.py` — `PhotoPoint` dataclass (lat, lon, alt, timestamp,
  filename, camera model/settings, `thumbnail_b64: str | None`), the
  ExifTool-JSON parser, and `photos_to_geojson()` / `photos_to_kml()`.
- `geo/photomap_html.py` —
  HTML writer modeled directly on `html_viewer.py`: pinned Leaflet 1.9.4 +
  SRI, plus pinned **Leaflet.markercluster** (1.5.3, unpkg, SRI hashes),
  photo GeoJSON embedded in a `<script type="application/json">` block.

## Output format details

- **HTML** (flagship): clustered pins; popup = thumbnail `<img>` (data URI),
  filename, timestamp, altitude, camera settings. Self-contained and
  shareable; basemap tiles + Leaflet load from the network (same documented
  tradeoff as the flight viewer). ~15–40 KB per photo of embedded thumbnail,
  so 500 photos ≈ 10–20 MB — acceptable for a local file.
- **KML**: one placemark per photo; balloon description contains the
  thumbnail as a data URI plus metadata. Opens in Google Earth Pro; imports
  into Google My Maps (which may strip balloon images — coordinates and
  names survive; documented).
- **GeoJSON**: `FeatureCollection` of `Point` features with metadata
  properties only — **no thumbnails** (base64 blobs don't belong in the GIS
  interchange format).

## Error handling

- ExifTool missing → clear error pointing at `dji-embed doctor`, non-zero
  exit.
- No photos found in the directory → error message, non-zero exit.
- Photo without GPS or unreadable EXIF → skipped; summary line
  ("Mapped 412 of 430 photos; 18 had no GPS data"), per-file detail with
  `-v`.
- Photo with GPS but no extractable thumbnail → pin without preview, not an
  error.

## Verification

- Unit tests: canned ExifTool JSON → expected `PhotoPoint` list (GPS
  present/absent, thumbnail present/absent, DNG vs JPG tags).
- Writer tests: GeoJSON structure, well-formed KML, HTML invariants matching
  the existing viewer tests (embedded JSON block present and parseable, SRI
  attributes pinned, markercluster included).
- CLI smoke tests with a mocked `exiftool` subprocess: default run, `-f all`,
  missing-ExifTool error path, empty-directory error path.
- Fixtures: two tiny (few-KB) JPGs with synthetic GPS EXIF (placed at
  Helsinki Cathedral, 60.170°N 24.952°E) in `samples/photos/`.

## Documentation

- `README.md` — feature bullet + quick-start example.
- `docs/user_guide.md` — usage section.
- `docs/decision-table.md` — "I have still photos and want a map" row.
- `docs/recipes.md` — "Map your photo archive" recipe (the church use case).

## Issue / roadmap mapping

- New GitHub issue for the feature; single implementation plan (no phases —
  the three writers share one data model and land together).
- Follow-up candidates (separate issues, only if requested): photos + flight
  tracks on one map; optional Pillow thumbnails; web-UI photo layer.
