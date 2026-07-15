# Geospatial export

`dji-embed convert` turns a DJI SRT flight track into geospatial formats that
open in mapping tools and feed the project's own map viewers.

## GeoJSON

```bash
dji-embed convert geojson DJI_0001.SRT          # -> DJI_0001.geojson
dji-embed convert geojson DJI_0001.SRT -o track.geojson
```

A `FeatureCollection` with one `LineString` for the flight path and one `Point`
per sample carrying `abs_alt` and `timestamp`. Coordinates are
`[longitude, latitude, altitude]` (RFC 7946). Opens in QGIS, geojson.io, and
most web maps; it is also the canonical format the HTML/web-UI viewers render.

## KML

```bash
dji-embed convert kml DJI_0001.SRT              # -> DJI_0001.kml
```

A `LineString` placemark with absolute altitude — double-click to open the
flight path in Google Earth.

## Camera footprints

Add `--footprint` to a `geojson` or `kml` conversion to include camera
ground-footprint polygons in the output — one rectangle per sampled frame
showing the area imaged by the lens at that moment.

```bash
dji-embed convert geojson DJI_0001.SRT --footprint --model air3
dji-embed convert kml DJI_0001.SRT --footprint --footprint-interval 5
```

### Sampling interval

`--footprint-interval SECONDS` (default `2.0`) controls how often a footprint
is sampled. One polygon is emitted per interval, not per frame. Increase the
interval to keep file sizes manageable on long flights.

### Model and field of view

FOV is derived from the SRT's `focal_len` field (a 35mm-equivalent, present on
Format 3/3b models) when available. When `focal_len` is absent, a per-model
native focal length is used instead. Pass `--model <name>` to select the
correct table entry:

| `--model` value | Equiv. focal length | Typical drone |
|-----------------|--------------------:|---------------|
| `air3`          | 24 mm               | DJI Air 3 |
| `mini4pro`      | 24 mm               | DJI Mini 4 Pro |
| `avata360`      | 24 mm               | DJI Avata 360 |
| `avata2`        | 12.7 mm             | DJI Avata 2 |

Omitting `--model` (or using an unrecognised name) falls back to a generic wide
lens (~84° HFOV). To add a new model, extend `FOV_TABLE` in
`src/dji_metadata_embedder/geo/footprint.py`.

### Gimbal-aware rotation

The footprint rectangle is oriented to the drone's course over ground by
default. On the **Avata 360** format, which carries `gb_yaw` in the SRT, the
real gimbal yaw is used instead, so the footprint follows where the lens
actually points.

### Oblique frames are skipped

If the SRT carries gimbal pitch (`gb_pitch`) and the camera is more than ~30°
off nadir, no footprint is drawn for that frame. Full oblique projection is
deferred future work. When gimbal pitch is absent (most formats), nadir is
assumed for every frame.

The bundled `samples/Avata360/clip.SRT` is a horizon-pointing (gimbal pitch ≈ 0°)
360 capture — the nadir model intentionally skips every frame and produces no
footprints. Gimbal yaw is used for footprint rotation only when the camera is
near-nadir (pitch below the ~30° threshold).

### Privacy — footprints suppressed under `--redact`

Footprint polygons are only emitted when `--redact none` (the default). Under
`--redact fuzz` or `--redact drop`, no footprints are written — a precise
polygon would re-sharpen a deliberately coarsened position.

### Output format details

**GeoJSON** — footprints are `Polygon` features alongside the existing track
`LineString` and `Point` features. Each footprint feature carries:

```json
{
  "type": "Feature",
  "geometry": { "type": "Polygon", "coordinates": [[[lon, lat], ...]] },
  "properties": {
    "kind": "footprint",
    "index": 12,
    "timestamp": "00:00:24,000",
    "agl": 28.5,
    "hfov": 73.7,
    "vfov": 58.0
  }
}
```

**KML** — footprints are collected in a `<Folder>` named "Camera footprints",
each as a `clampToGround` polygon.

### Limitations

- **Flat-earth projection.** Footprint size is computed with a plane-earth
  approximation (equirectangular). Errors grow with altitude and latitude but
  are negligible at the scales typical drone flights cover.
- **Nadir assumed when no gimbal data.** Most DJI formats do not carry gimbal
  attitude in the SRT. When `gb_pitch` is absent the camera is assumed to be
  pointing straight down. Strongly oblique or FPV flights will produce
  inaccurate footprints in that case.
- **No terrain / DEM.** AGL is taken from `rel_alt` in the SRT when present,
  otherwise estimated as `abs_alt − first-fix abs_alt`. Neither accounts for
  terrain relief below the drone.

## Standalone HTML map

```bash
dji-embed convert html DJI_0001.SRT              # -> DJI_0001.html
dji-embed convert html DJI_0001.SRT -o flight.html
```

Produces a single self-contained file that opens in any browser. The flight path
is drawn as a Leaflet/OpenStreetMap map, colored by altitude (blue = low,
red = high), with start/end markers and clickable points that show index,
altitude, and timestamp.

> **Network note:** Leaflet and the basemap tiles load from the internet; the
> flight data itself is embedded, so the file is portable but needs a connection
> to render the map.

`--redact` works the same as for GeoJSON/KML:

```bash
dji-embed convert html DJI_0001.SRT --redact drop   # empty track, no coords
dji-embed convert html DJI_0001.SRT --redact fuzz   # ~100 m coarsened coords
```

## Combined flight map (`flightmap`)

> **Experimental:** `flightmap` is new and its size-split joining heuristics
> may still be tuned based on real-world feedback. If it joins flights it
> shouldn't (or misses ones it should), please open an issue with the SRT
> file names and timestamps.

```bash
dji-embed flightmap ./footage                    # -> footage/flightmap.html
dji-embed flightmap ./footage -r                 # scan subdirectories too
dji-embed flightmap ./footage -f all             # html + kml + geojson
dji-embed flightmap ./footage --redact fuzz      # ~100 m coarsened tracks
```

Where `convert html` maps one flight, `flightmap` maps a whole folder: every
`.SRT` log becomes its own coloured track on a single standalone HTML map,
with a start marker, a summary popup (start time, duration, altitude range,
GPS point count), and a layer control to toggle flights. Only the SRT sidecars
are read — the videos are never opened — so scanning a large archive takes
seconds and needs no external tools.

The GeoJSON output is one `LineString` feature per flight carrying the same
summary properties (no per-sample points — at archive scale they would swamp
the file); the KML is one path placemark per flight, which Google Earth and
Google My Maps import as separate lines.

DJI logs one GPS point per video frame (~30 Hz), so `flightmap` thins every
track to about one point per second (always keeping the exact first and last
fix) — visually identical, but a 400-file archive drops from ~70 MB to a few
MB of HTML. Your SRT files are untouched; for full-rate output of a single
flight use `dji-embed convert` instead.

SRT files without GPS telemetry (ordinary subtitles, clips that never got a
fix) are skipped and counted; `-v` lists them. With `-r`, flights are labelled
by their path relative to the scanned folder so per-session directories that
reuse DJI's restarting file numbering stay distinct. Sidecar-less models whose
telemetry lives inside the MP4 (Air 3S, Mini 5 Pro, …) are not scanned — map
those per clip with `dji-embed convert html VIDEO.MP4`.

Popup start times are converted to UTC by auto-detecting the recording
timezone from each file's mtime. On archives whose mtimes were rewritten by
zip/cloud transfers the auto-detection fails; `flightmap` then warns once
(with a file count) and falls back to mtime-based times. Pass
`--tz-offset '+02:00'` (your recording timezone) for correct absolute times —
track shapes, durations, and joining are unaffected either way.

### Size-split recordings are joined

DJI closes the MP4/SRT pair when a recording hits the 4 GB file-size limit and
keeps recording into the next numbered file, so a long flight arrives as
several files. `flightmap` stitches these back into one flight when the next
file sits in the same directory and its telemetry starts within `--join-gap`
seconds (default 15) of the previous file ending *and* resumes within the
distance the drone could plausibly have covered in that gap. A joined flight
keeps the first segment's name; its popup, KML description, and GeoJSON
`segments` property list the source files.

Details worth knowing:

- Gaps are measured on the SRT's own per-block timestamps, never on file
  mtimes — so joining still works on archives whose mtimes were rewritten by
  zip/cloud transfers. Formats without a datetime line in the SRT are never
  joined for the same reason.
- Consecutive file numbers are *not* required: photos share DJI's numbering
  counter, so a split flight can legitimately jump `DJI_0010` → `DJI_0012`.
- Two flights flown back-to-back from the same launch point are kept apart by
  the time check; two files recorded around the same time in different
  locations are kept apart by the position check.
- `--join-gap 0` disables joining entirely; raise it if your drone pauses
  longer between segments.
- Known limitation: segments are only compared against the most recent
  flight in time order, so if two drones recorded into the same folder at
  the same time, a split flight interleaved with the other drone's files
  is not joined. Rare in practice — open an issue if it bites you.

## Photo map (`photomap`)

```bash
dji-embed photomap ./photos                     # -> photos/photomap.html
dji-embed photomap ./photos -f all               # html + kml + geojson
dji-embed photomap ./photos --link-originals     # popups open the original photos
```

Where `flightmap` plots video flight tracks, `photomap` plots individual
GPS-tagged still photos (JPG/JPEG/DNG). ExifTool scans the whole directory in
one pass (`dji-embed doctor` checks it's installed); the HTML map clusters
nearby shots into an expandable marker, and clicking a pin shows the EXIF
thumbnail, filename, timestamp, altitude, and camera settings. Photos with no
GPS are skipped and counted in a summary; `-v` lists them.

With `--link-originals`, a popup's thumbnail and filename become a
click-through to the full-resolution original (JPGs open inline, DNGs
download). The links are relative to the HTML file, so they only resolve
while the map sits next to the photos — pass `--link-base` (a relative
folder or an absolute URL) when the originals live elsewhere.

### 360° panoramas

Stitched spherical panoramas (DJI, Insta360, Google Camera, …) carry XMP
GPano tags. Photomap detects `ProjectionType=equirectangular` during the
same ExifTool scan. Detected panoramas draw as orange markers (regular
photos are blue), and mixed folders get a checkbox control to show or hide
each type; the exported GeoJSON marks them with `"pano": true`. When
`--link-originals` is set, clicking such a pin
opens the photo in an embedded 360° viewer
([Pannellum](https://pannellum.org/), loaded from the CDN like Leaflet)
instead of a flat, distorted JPEG. An "open original" link stays in the
popup as a fallback.

```bash
dji-embed photomap /path/to/panoramas --link-originals
```

The simplest way to use the viewer is `--serve` (it implies
`--link-originals`):

```bash
dji-embed photomap /path/to/panoramas --serve
```

This writes the map, serves its folder at a private local address
(`http://127.0.0.1:<port>` — reachable only from your own computer), and
opens it in your browser. Press Ctrl+C in the terminal to stop.

Notes:

- Opened straight from disk (double-clicking `photomap.html`), the 360°
  viewer is blocked by the browser — `file://` pages may not feed local
  images to WebGL. The map shows a short explanation instead; use `--serve`
  and the viewer works. The "open original" link works either way.
- Without `--link-originals` (or `--serve`, which implies it) the map is
  unchanged — the viewer needs the original files to be reachable from the
  HTML.
- Very large panoramas can exceed a device's WebGL texture size (phones are
  often limited to 8192 px wide); the viewer shows an error in that case and
  the "open original" link still works.
- With an absolute `--link-base` URL, the web server hosting the photos must
  send CORS headers (`Access-Control-Allow-Origin`) — the 360° viewer loads
  the image into WebGL, which browsers block cross-origin without them. The
  "open original" link works either way.

### Redacting photo locations

`--redact fuzz` coarsens every photo location to ~100 m before any
output is written (html/kml/geojson), same as flightmap. Caveat: if you
also pass `--link-originals` and share the original files, their EXIF still
contains the exact coordinates — the fuzz only applies to the map.

```bash
dji-embed photomap /path/to/photos --redact fuzz
```

## Privacy

All three geo formats honour `--redact`:

```bash
dji-embed convert geojson DJI_0001.SRT --redact drop   # empty track, no coords
dji-embed convert kml DJI_0001.SRT --redact fuzz       # ~100 m coarsened coords
```

Pre-GPS-lock `(0, 0)` frames are always excluded.

## Batch

```bash
dji-embed convert geojson ./footage --batch     # all *.SRT in the folder
dji-embed convert html ./footage --batch        # one .html map per *.SRT
```

For a single combined map of the whole folder instead, see
[`flightmap`](#combined-flight-map-flightmap) above.
