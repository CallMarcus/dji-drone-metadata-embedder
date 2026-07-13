# Photomap 360° panorama support — design

**Date:** 2026-07-13
**Issue:** [#271](https://github.com/CallMarcus/dji-drone-metadata-embedder/issues/271)
**Status:** Approved

## Problem

`dji-embed photomap --link-originals` already maps geotagged panoramas, but a
pin click opens the flat equirectangular JPEG — distorted and nearly useless
for 360° spherical shots (the main ask from the mavicpilots thread). Photomap
also lacks the `--redact fuzz` option flightmap has, so a shared map exposes
exact coordinates.

## Scope

One PR covering the full #271 checklist:

1. Detect XMP GPano panoramas in the existing ExifTool scan.
2. Open panoramas in an embedded 360° viewer (Pannellum) from the HTML map.
3. Add `--redact [none|fuzz]` to `photomap`.
4. Docs (`docs/geospatial.md` + README). Demo GIF/video is a manual
   follow-up for the maintainer, not part of the code change.

Out of scope: any build-time image processing (tiling, cube faces,
downscaling). The viewer loads originals lazily in the browser; panoramas
wider than the device's WebGL max texture size (common on phones at 8192 px)
fall back to the plain "open original" link via Pannellum's own error path.

## Approach decision

Chosen: **CDN-pinned Pannellum in a lightbox overlay, loading originals
lazily.** Matches the existing asset pattern in `photomap_html.py` — Leaflet
and markercluster load from unpkg with pinned versions + SRI hashes (the map
already needs the network for OSM tiles). Zero cost at map-build time.

Rejected:

- *Inlining Pannellum into the HTML* — ~130 KB added to every map, diverges
  from how the other three assets are handled, third-party blob in the repo.
- *Build-time multires/cube-face preprocessing* — decodes every 30–70 MB
  panorama during `photomap`; the performance trap this design explicitly
  avoids. Revisit only if the mobile texture-limit case is actually reported.

## Design

### 1. Detection — `geo/photomap.py`

- Add `-XMP-GPano:ProjectionType` to `_SCAN_TAGS`. Same single batch ExifTool
  subprocess; GPano XMP sits in the same metadata block already being read,
  so scan cost is unchanged.
- `PhotoPoint` gains `is_pano: bool = False`, set when
  `ProjectionType == "equirectangular"` (case-insensitive). GPano is written
  by DJI, Insta360, Google Camera and others — vendor-neutral.
- `photos_to_geojson`: pano points get a `"pano": true` property **only when
  `link_base is not None`** — without a link the viewer has nothing to load,
  and the standalone GeoJSON export stays unchanged.

### 2. Viewer — `geo/photomap_html.py`

Active only when `--link-originals` is set **and** the scan found ≥1 pano:

- Emit Pannellum 2.5.6 `<link>`/`<script>` tags from unpkg, pinned + SRI
  (hashes computed from the downloaded assets at implementation time).
  Maps with no panoramas emit no Pannellum tags at all.
- A hidden full-screen overlay `<div>`: viewer container + ✕ close button.
- Popup behaviour: for `pano` features, the thumbnail/name click opens the
  overlay and starts
  `pannellum.viewer({type: "equirectangular", panorama: p.link, autoLoad: true})`
  instead of navigating. The popup **keeps a plain "open original" link** for
  panos, so a failed viewer (missing file, GPU texture limit) never strands
  the user; Pannellum also renders its own error text in the container.
- Escape key and ✕ close the overlay; the viewer instance is destroyed on
  close so GPU/texture memory is released.
- Non-pano photos behave exactly as today.

### 3. Redaction — `cli.py` + `geo/photomap.py`

- `--redact [none|fuzz]` on the `photomap` command, mirroring flightmap's
  choices and help text (`drop` makes no sense for discrete photo points —
  it would empty the map).
- Applied immediately after `scan_photos()` using the existing
  `redact_coords` rounding (3 decimals ≈ 100 m), so all output formats
  (html/kml/geojson) see only fuzzed coordinates.
- Interaction warning: `--redact fuzz --link-originals` still links to
  originals whose EXIF carries exact GPS. Emit a stderr note and document
  it — the combination is only private if the map is shared without the
  original files.

### 4. Docs

- `docs/geospatial.md`: 360° viewer section (what GPano is, opt-in via
  `--link-originals`, texture-limit caveat) + `--redact fuzz` for photomap.
- README: mention pano support in the photomap feature bullets.

### 5. Testing

- Unit (`tests/`): GPano JSON → `is_pano` mapping (equirectangular, absent,
  other values); `pano` property gated on `link_base`; fuzz rounding reaches
  all writers; HTML contains Pannellum tags/overlay only when a pano point
  exists; pano popup retains the plain link; stderr warning on
  fuzz+link-originals.
- Fixtures: a GPano entry added to the existing ExifTool-JSON test data —
  the scan is mocked JSON, no binary sample required.
- E2E: exiftool-shim run of the CLI; manual open-in-browser check of a
  generated map with a real panorama.
