# User Guide

This guide shows the basics of processing DJI footage with `dji-embed`.

## Quick start

Process a directory of videos and matching SRT files:

```bash
dji-embed embed /path/to/footage
```

A `processed` folder will be created containing new videos with embedded metadata and telemetry summary files.

## Just want a map? Drag and drop

Passing a bare folder — no command — maps it instead: every `.SRT` flight
log (and geotagged photos, subfolders included) is drawn and the map opens
in your browser. On Windows this means you can simply **drag your footage
folder onto `dji-embed.exe`**:

```bash
dji-embed /path/to/footage    # -> flightmap.html (and photomap.html) open in the browser
```

## 3D terrain view

`dji-embed flightmap <folder> --3d` writes a second map, `flightmap-3d.html`,
next to (never instead of) the regular `flightmap.html` — `-o` still picks
the output path:

```bash
dji-embed flightmap /path/to/footage --3d    # -> footage/flightmap-3d.html
```

Instead of a flat basemap, tracks are draped on the terrain surface: tilt
the camera and they follow the ground below, with altitude available from
the track popups. Terrain tiles come from Mapterhorn (Copernicus elevation
data) over the network — like every map here, it needs a connection to
render — and if the terrain tiles can't load, the map falls back to a flat
view with an on-map notice. `--tile-style` doesn't apply in 3D (it's
ignored, with a warning).

## Common options

- `-o DIR` – choose an output directory
- `--exiftool` – also write metadata via ExifTool (requires ExifTool)
- `--dat FILE` – merge a DAT flight log with the video
- `--audio-sidecar` – auto-pair a same-basename `.m4a` audio file and mux it in
  (see [Drones with separate audio](#drones-with-separate-audio-neo-2))

Run `dji-embed --help` to see all available options.

## Drones with separate audio (Neo 2)

Some DJI drones — notably the **Neo 2** — record video and audio as **two
files**: a silent `DJI_0001.MP4` plus a `DJI_0001.m4a` alongside it. Pass
`--audio-sidecar` to have `embed` find the matching `.m4a` and mux it into the
output automatically:

```bash
dji-embed embed /path/to/footage --audio-sidecar
```

- Audio is stream-copied (no re-encode), consistent with the rest of the tool.
- The telemetry subtitle track is preserved.
- Clips without a matching `.m4a` are processed as usual (a warning is logged).
- A large video/audio length mismatch is flagged as a warning but still muxed.

## Converting telemetry

Use `dji-embed convert` to export telemetry to GPX, CSV, GeoJSON, KML, HTML,
or CoT:

```bash
dji-embed convert gpx DJI_0001.SRT
```

Swap `gpx` for `csv`, `geojson`, `kml`, `html`, or `cot` to pick the format.

For detailed how-to guides such as creating Windows bundles or redacting location data, see the files in `docs/how-to`.

## Scripting and frontends

`photomap`, `flightmap`, `embed`, `check`, and `doctor` accept `--progress jsonl`,
which switches stdout to machine-readable progress events (one JSON object
per line) for scripts and GUI frontends. The event contract is documented
in [Progress Events (JSONL)](PROGRESS_JSONL.md).

Log messages always go to stderr, so redirecting stdout (`dji-embed convert
gpx flight.SRT > out.gpx` style pipelines) captures only real output, never
log lines.

### Sidecar-less footage (MP4 with embedded telemetry)

Newer DJI models record telemetry inside the MP4 instead of a `.SRT`. Pass the
video directly — `convert` and `verify-sun` auto-detect it:

    dji-embed convert gpx DJI_0001.MP4
    dji-embed verify-sun  DJI_0001.MP4

This needs a recent ExifTool (see `docs/MP4_TIMED_METADATA.md`). `--tz-offset`
is ignored for MP4 input because its embedded time is already UTC.

## Mapping still photos

`dji-embed photomap` plots GPS-tagged still photos (JPG/JPEG/DNG) on a map —
useful when you've been shooting stills rather than (or alongside) video and
want to see where each shot was taken.

```bash
dji-embed photomap /path/to/photos                                    # -> photos/photomap.html
dji-embed photomap /path/to/photos -f kml                             # -> photos/photomap.kml
dji-embed photomap /path/to/photos -f geojson                         # -> photos/photomap.geojson
dji-embed photomap /path/to/photos -f all -o archive/photomap         # -> archive/photomap.{html,kml,geojson}
dji-embed photomap /path/to/photos -r --title "Churches of Finland"   # scan subdirectories too
dji-embed photomap /path/to/photos --link-originals                   # popups open the original photos
dji-embed photomap /path/to/photos --redact fuzz                      # ~100 m coarsened pins
```

The command scans the whole directory in one pass, so even large archives
scan quickly (ExifTool must be installed — `dji-embed doctor` checks this).
The HTML map clusters nearby shots into an expandable numbered marker so a
dense session doesn't turn into a wall of overlapping pins; clicking a photo
shows its EXIF thumbnail, filename, timestamp, altitude, and camera settings.
A **Hover previews** toggle in the map's top-right corner (off by default)
adds a thumbnail-and-filename preview on mouse-over for skimming large maps;
the browser remembers your choice. On phones and tablets there is no hover,
so the map skips the toggle and previews entirely and gives every pin a
larger tap target instead — one tap opens the photo popup.
Sharing the map? `--popup-fields` chooses what the popups disclose (`none`,
or a comma list of `name`, `timestamp`, `camera`, `altitude`); excluded
details are left out of the HTML file entirely.
KML opens the same thumbnails in Google Earth Pro (Google My Maps import may
drop the images but keeps the placemarks). GeoJSON is interchange-only — no
thumbnails, just `name`/`timestamp`/`alt`/`camera` properties (plus
`"pano": true` on 360° panoramas) — for use in GIS tools.

With `--link-originals`, the HTML popups' thumbnail and filename become a
click-through to the full-resolution original in a new browser tab (JPGs
render inline; browsers download DNGs instead). The links are relative, so
they work while the map file sits next to the photos and break if it's moved
or shared without them — the popup still identifies the file by name and date
either way. If the originals live elsewhere, point at them with
`--link-base ../DCIM` (relative folder) or `--link-base https://example.com/photos/`
(absolute URL).

360° panoramas (GPano photos from DJI, Insta360, Google Camera, …) are
detected automatically and drawn as orange markers (regular photos are blue);
when a folder mixes both, a checkbox control on the map lets you show or hide
each type independently. With `--link-originals`, clicking a panorama opens an
embedded interactive 360° viewer instead of a flat, distorted JPEG — an
"open original" link stays in the popup as a fallback.

This is not DJI-specific: any camera whose software exports GPS-tagged
equirectangular JPEGs — including 360° action cameras like the GoPro Max and
Insta360 — produces files `photomap` can place and open in the viewer today.
(GPS *video* telemetry from action cameras is a separate exploration, tracked
in [issue #276](https://github.com/CallMarcus/dji-drone-metadata-embedder/issues/276).)

```bash
dji-embed photomap /path/to/photos --serve
```

Writes the map, then serves it at a private local address and opens your
browser — required for the built-in 360° panorama viewer, which browsers
block when the map is opened straight from disk.

Photos without GPS coordinates are skipped and counted in a summary, e.g.
`Mapped 412 of 430 photos; 18 had no GPS data (use -v to list them)`; add
`-v` to list the skipped filenames.

Like the other HTML maps, Leaflet and the OpenStreetMap basemap tiles load
from the internet; the photo thumbnails themselves are embedded in the file.

A photo map publishes your shooting locations — share it deliberately, or
pass `--redact fuzz` to coarsen every pin to ~100 m first. Note that linked
originals (`--link-originals`) still carry exact GPS in their EXIF.

## Footage verification (sun / shadow check)

For chronolocation and footage verification you can cross-check the **shadows** in a clip against where the sun actually was. Given each GPS point's position and UTC time, `dji-embed` computes the sun's **azimuth** (compass bearing) and **elevation** (height above the horizon).

```bash
# Summarise the sun track over a clip
dji-embed verify-sun DJI_0001.SRT

# Force a known UTC offset instead of auto-detecting from the file mtime
dji-embed verify-sun DJI_0001.SRT --tz-offset +02:00

# Machine-readable summary
dji-embed verify-sun DJI_0001.SRT --format json
```

The CSV export also gains `datetime_utc`, `sun_azimuth`, and `sun_elevation` columns:

```bash
dji-embed convert csv DJI_0001.SRT
```

Notes:
- Accuracy is within ~0.5 deg, ample for shadow direction/length checks.
- The tool gives the *expected* sun geometry; comparing it to the footage is the analyst's step.
- SRT formats without an absolute wall-clock datetime can't be resolved to UTC, so the sun columns stay blank and `verify-sun` reports `sun_not_computable`.
- UTC auto-detection relies on the file's modification time still reflecting the recording; if the file was copied or edited, pass `--tz-offset` explicitly for reliable results.

## Extracting the HOME (launch) point

`--extract-home` is opt-in because the HOME point reveals the operator's launch location. It never touches the MP4 and always respects `--redact`:

```bash
dji-embed embed FOOTAGE/ --extract-home              # HOME in the .json sidecar
dji-embed convert gpx flight.SRT --extract-home      # HOME waypoint in the GPX
dji-embed convert geojson flight.SRT --extract-home --redact fuzz   # HOME coarsened ~100 m
```
