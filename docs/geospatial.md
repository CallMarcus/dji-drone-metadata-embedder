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
ground-footprint polygons in the output — one polygon per sampled frame
showing the area imaged by the lens at that moment (a rectangle under a
straight-down camera, a trapezoid when the gimbal is tilted — see below).

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

### Oblique frames become trapezoids

If the SRT carries gimbal pitch (`gb_pitch`), each footprint is a true
view-frustum projection: the four camera-corner rays are intersected with the
ground plane, so a tilted camera yields a ground **trapezoid** instead of a
rectangle (wider at the far edge, exactly as the lens sees it). In GeoJSON
these polygons carry `"oblique": true` and a `"pitch"` property so they can
be styled apart from nadir rectangles.

Two guard rails keep near-horizon frames sane: frames with the camera at or
above the horizon (pitch ≥ 0°) are skipped outright, and corner rays that
miss the ground — or would land implausibly far away — are clamped to 8× the
height above ground, so a slightly-tilted frame degrades to a capped
trapezoid instead of stretching to the horizon.

When gimbal pitch is absent (most formats), nadir is assumed for every frame
and the original rectangle model applies; `-v` logs a note that footprints
assume a straight-down camera.

The bundled `samples/Avata360/clip.SRT` is a horizon-pointing (gimbal pitch ≈ 0°)
360 capture — every frame sits at the horizon gate and produces no
footprints.

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

```bash
dji-embed flightmap ./footage                    # -> footage/flightmap.html
dji-embed flightmap ./footage -r                 # scan subdirectories too
dji-embed flightmap ./footage -f all             # html + kml + geojson + flight record
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

Drones whose SRT carries no gimbal attitude (the Mini series) can borrow it
from a decoded flight log: `--flight-log my-flight.csv` merges per-sample
gimbal pitch/yaw into the matching flight by timestamp, upgrading the 3D
map's estimated camera footprints to measurements. See
[Gimbal from a flight log](how-to/flight-log-gimbal.md) for the export
settings that make the join exact.

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

### Basemap styles (`--tile-style`)

Both `flightmap` and `photomap` can swap the HTML map's basemap between
keyless OpenStreetMap renders:

```bash
dji-embed flightmap ./footage --tile-style opentopomap
dji-embed photomap ./photos --tile-style osm-hot
```

`osm` (default), `osm-hot` (Humanitarian style, high contrast),
`opentopomap` (topographic with contour lines — nice for mountain flights),
and `cyclosm` (cycling-oriented, detailed paths). Each style carries its
provider's attribution automatically. KML and GeoJSON outputs have no
basemap and are unchanged.

### 3D terrain view

```bash
dji-embed flightmap ./footage --3d               # -> footage/flightmap-3d.html
```

`--3d` writes a separate `flightmap-3d.html` next to (never instead of) the
regular `flightmap.html` — `-o` overrides the output path as usual, and
combining `--3d` with `--format kml|geojson|all` errors, since the 3D map is
HTML-only. Both maps read the same flight data and honor `--redact fuzz`
(~100 m coarsened tracks) before either file is written.

Rendered with MapLibre GL instead of Leaflet, tracks are draped on the
terrain surface — they follow the ground under a tilted camera rather than
floating at altitude; altitude numbers are still available in the track
popups. Terrain comes from Mapterhorn (Copernicus elevation data), loaded
keylessly over the network — like the 2D map it needs a connection to
render, and if the terrain tiles can't load, it falls back to a flat view
with an on-map notice. Browsers without WebGL get a plain HTML message
instead. `--tile-style` has no effect in 3D (ignored, with a warning).

### Ghost camera — see what the drone saw

In the 3D map, every flight's popup has a **View from here** button. It flies
the map camera to the drone's recorded pose at that moment — position, height
above takeoff, gimbal direction, and the camera's field of view — so the
rendered terrain shows what the real camera saw. Step through the flight with
the ‹ › buttons or arrow keys (hold an arrow key to scrub); press Esc or
× to return to
the overview.

This doubles as a verification aid: if the rendered ridgelines match the
skyline in your footage, the telemetry is telling the truth about where the
camera was.

The heads-up display always shows the *recorded* values and badges anything
that is not: *pitch clamped* (the recorded gimbal angle exceeds what the map
camera allows), *estimated view* (this format logs no gimbal direction, so
the view faces along the flight path), and *position fuzzed ~100 m* (the map
was generated with `--redact fuzz`). Heights come from the terrain model plus
the logged height above takeoff; without terrain, the logged altitude is used
as-is.

### Flight sculpture — altitude you can see

The 3D map draws each flight as a **sculpture**: a translucent curtain rising
from the ground to the drone, capped by a solid ribbon at flight altitude, in
the flight's own colour. Draped tracks all look alike from above — a 30 m
hover and a 300 m transit trace the same line. The curtain gives that line a
height, so the shape of the flight stands up out of the landscape.

The ribbon sits at the drone's true altitude, and the curtain beneath it
measures real ground clearance. The map derives that from the logged height
above takeoff (`rel_alt`) plus the terrain elevation at the takeoff point,
which keeps it consistent with the landscape you are looking at instead of
trusting an absolute altitude whose datum may not match. Fly level toward
rising ground and the curtain visibly shortens as the clearance closes.

Where the terrain model is unavailable the curtain falls back to plain height
above takeoff. Segments where the drone works out to be at or below the
rendered ground — a rooftop launch, a datum artefact near a cliff, or a low
flight over forest (the terrain model is a surface model, so it includes tree
canopy and buildings) — are left out rather than drawn flat, so the curtain
breaks there.

Use the **Sculpture** checkbox in the flights panel to hide it. A flight's own
checkbox hides its track and its sculpture together, and the sculpture steps
out of the way while you are in the ghost view.

Flights whose SRT format carries no `rel_alt` get no sculpture; if none of the
flights on a map has it, the checkbox does not appear at all.

Terrain hides the sculpture the way it hides anything else: a ridge between
you and the flight blocks it from view.

### Camera's gaze — what the camera saw, and when

The 3D map has a playback control at the bottom left: play/pause, a speed
button cycling 1×, 5×, 20×, 60×, a scrubber, a time readout, and — with more
than one playable flight on the map — a picker for which one is playing. As
the clock runs, the camera's ground footprint for that second is drawn on the
terrain, with four rays connecting the camera to its corners.

Press play while you are in the ghost view and the camera rides the recorded
flight in real time instead of stepping sample by sample. An arrow key still
pauses playback and hands control back to you, but it also carries the clock
to the sample you stepped to, so the ground patch stays in agreement with
where the camera is now looking. Clicking **View from here** on a flight that
is already playing seeks the clock to the sample you clicked rather than
leaving the camera to be overridden by wherever the clock currently is.
Leaving the ghost view keeps the clock running from outside.

**Click any spot on the ground** and the map answers which recording covered
it: `in frame 14 s over 3 passes`, with each pass a button that jumps the
clock there (and rides it, if you are in the ghost view). The stretches of
flight line that filmed the spot light up at the same time. Clicking ground
that was never in frame says so.

Two honesty limits, and a footprint can be an estimate for either of two
reasons. The gaze is switched off entirely with `--redact fuzz`, because a
footprint projected from a coordinate that has been moved ~100 m is a
confident claim about ground the camera never saw; the flights panel says so
when that happens, and playback still works. And where the telemetry carries
no gimbal attitude — every Mini-series drone at the time of writing — the
footprint is drawn from the same estimated 30-degree down-tilt the ghost view
assumes. A missing focal length has the same effect on the footprint's shape:
it is drawn from a generic wide lens instead of the camera's true field of
view, which makes the patch a little larger than the true frame — this is the
common case for sidecar-less MP4 clips, which log real gimbal attitude but no
focal length. Either reason (or both) marks the footprint with a dashed
outline and an "estimated footprint" badge naming what was guessed; a clip
can lose gimbal data or focal length partway through, so a spot's answer says
"estimated" when every pass over it was guessed and "some passes estimated"
when only some were. Footprints also assume flat ground at the drone's height
reference, the same simplification the `--footprint` KML/GeoJSON export
makes, so on terrain that rises into the frame the drawn patch is an
approximation rather than the true footprint.

### Crossfade to the footage

Point `flightmap` at a folder with `--link-originals` and the 3D map learns
where each flight's video sits:

```bash
dji-embed flightmap ./footage --3d --link-originals
```

In the ghost view a slider then appears in the HUD. Slide it and the terrain
reconstruction fades into the real video frame for the second you are looking
at; **v** swaps straight between the two extremes. Held half-way you see both
at once, which is the point: a horizon and landmarks that line up are
consistent with the recorded attitude being right. A mismatch is not proof it
is wrong — the same picture follows from an estimated or median field of view
(see below), a terrain model that includes canopy or rooftops, the flat
ground-plane approximation, or lens distortion the map does not model. Read it
as the most direct sanity check this tool offers, not a verdict.

The video follows the clock, but only the slowest speed keeps pace with it:
at 1× it plays alongside the flight, and at 5× and above it steps sample to
sample instead — roughly a second at a time — because no browser decodes
reliably that fast. A flight that DJI split across several files at the 4 GB
container limit switches source automatically as the clock crosses each
boundary, seeking into the new file at that sample's own offset rather than
the flight's elapsed time. A file that fails to load disables the slider and
names the file in a badge, and stays that way — not just for the frame it
broke on — until the clock moves into a different segment, even one backed
by the same file.

That badge only knows the browser refused to load the file, not why: a moved
file, a wrong link base and an undecodable codec all look identical to it.
DJI's 4K footage is commonly H.265/HEVC, which Firefox does not decode inside
MP4 at all and Chrome only where a platform decoder is present — an intact,
correctly-linked clip can still show as failed on those browsers.

Linking is opt-in because the map only works alongside the videos: share the
HTML on its own and the links have nothing to point at. `--link-base` gives
the hrefs a different prefix when the footage does not sit beside the map.

Opening the written file straight from disk (`file://`) works out of the box:
the video seeks natively with no server involved, and that is the common path.
`flightmap` itself has no `--serve` flag, but the standalone `serve` command
(below, under `photomap`) is what makes seeking work when the map is served
over HTTP instead — the path the desktop app and any hosted copy of the map
take, and the reason `geo/serve.py` answers HTTP Range requests. Either way,
it is the *playback* slider (or stepping through the flight) that seeks the
video; the blend slider only fades between the two layers at whatever second
the clock is already on.

Two limits, not one. `--link-originals` is still permitted with `--redact
fuzz` — originals still carry exact GPS in their own metadata, so linking
warns rather than refusing — but the crossfade itself is switched off:
coarsened positions are deliberately ~100 m out, so overlaying real footage
would invite a comparison against geometry that is knowingly wrong. And
where a clip carries no focal length, the map's own field of view is an
estimate, so the alignment is approximate — the same caveat the gaze badge
already reports.

### Airspace overlay (`--airspace`)

`dji-embed flightmap FLIGHTS --airspace` overlays the official airspace zones
for the flight area on the HTML maps — the flat map and the 3D terrain view
(`--3d`) — FAA UAS Facility Maps in the US, and national UAS
geographical-zone feeds where a country publishes one (currently
Luxembourg, Finland and Switzerland via ED-269, and Ireland via the IAA's
published ED-318 file, which the IAA labels reference-only — that caveat
rides into the map). Zones draw in one neutral style; clicking one shows
the published facts: restriction class, vertical limits (or "not stated"),
applicability windows, and the feed, license and fetch time. Zones the
flight entered get a slightly stronger outline plus the entry/exit times and
maximum heights in the popup. The map states facts and makes no
determination.

On the flat map, zones with a published ceiling also carry a small ceiling
label once you zoom in past the point where a metro-area grid would drown
the map in text.

Like `-f record`, the flag is the opt-in for network access: every fetch is
announced before it happens, responses are cached in `airspace-cache/`
beside the output (`--airspace-refresh` refetches), and areas without a
supported feed get an honest "no data available" note on the map itself.
`--airspace` needs exact coordinates, so it refuses `--redact`.

On the 3D map, zones with a published ceiling rise from the terrain as
translucent volumes, so you can see a flight thread pass under or over
them. Ceilings published above ground level (all FAA grid cells) are exact
by construction. Ceilings published above mean sea level are converted
using the terrain elevation at the centre of each zone polygon — an
approximation the map notes openly; the popup always states the
published limit verbatim. Zones with no published ceiling stay flat on
the terrain: the map never draws a height nobody published. Inside a
zone, clicking shows the zone's facts; untick "Airspace zones" in the
panel to get the gaze lookup back — clicking a spot to see which
seconds of recording covered it.

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
thumbnail, filename, timestamp, altitude, and camera settings — plus an
attribution line when the photo carries `Artist`/`Copyright` metadata (see
below). Photos with no GPS are skipped and counted in a summary; `-v` lists
them.

With `--link-originals`, a popup's thumbnail and filename become a
click-through to the full-resolution original (JPGs open inline, DNGs
download). The links are relative to the HTML file, so they only resolve
while the map sits next to the photos — pass `--link-base` (a relative
folder or an absolute URL) when the originals live elsewhere.

### Choosing what the popups show (`--popup-fields`)

A map you share shouldn't have to disclose everything your camera recorded.
`--popup-fields` limits the popup to the details you pick — `none`, or a
comma list of `name`, `timestamp`, `camera`, `altitude`, `credit`:

```bash
dji-embed photomap ./photos --popup-fields none            # thumbnails only
dji-embed photomap ./photos --popup-fields name,timestamp  # no camera/altitude
```

Excluded details are stripped from the HTML file entirely, not merely
hidden — someone reading the map's source finds nothing either. Your
original photos are untouched (their EXIF keeps everything; pair with
`--redact fuzz` if the *locations* need coarsening too). Thumbnails, the
360° viewer, and marker colors are unaffected, and KML/GeoJSON outputs are
unchanged — they are data exports, not shared pages.

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

The viewer honors the standard GPano *initial view* tags, so you can choose
each panorama's opening direction and zoom once, in the photo itself, with
ExifTool:

```bash
exiftool -XMP-GPano:InitialViewHeadingDegrees=210 \
         -XMP-GPano:InitialHorizontalFOVDegrees=90 pano.jpg
```

The heading is compass degrees (`PoseHeadingDegrees`, written by the
stitcher, records where the image center points; without it the center is
assumed to face North). `InitialViewPitchDegrees` tilts the opening view
above/below the horizon.

### Setting the opening view

DJI cameras don't write initial-view tags in camera, and hand-typing
ExifTool commands per pano doesn't scale, so there is an editor:

```bash
dji-embed panoedit /path/to/panoramas
```

This opens a local editor page (your machine only): drag and zoom each
panorama to the view it should open with — the live readout shows the
exact GPano values — then Save writes `InitialViewHeadingDegrees`,
`InitialViewPitchDegrees` and `InitialHorizontalFOVDegrees` into the file
with ExifTool and moves on to the next panorama. Each original is kept
beside the file as `<name>_original`. In the desktop app this is the
"360° views" mode.

The backups exist so a batch edit can never destroy an original, but the
view tags themselves are re-editable and never touch the image data, so
you may reasonably decide you don't need them — they do double the
folder's size. `--no-backup` writes views straight into the files, and
`dji-embed panoedit /path/to/panoramas --clean-backups` deletes the
`_original` copies from earlier sessions once you're happy with the
edits (only ever where the edited file still exists beside the backup;
add `-r` to include subfolders). Either way the maps never reference
the `_original` files, so if you publish a generated map there is no
need to upload them.

Two keys matter when a panorama already has a view you like: **Esc**
resets the viewer to the view the file opened at, so you can look around
and then move on with `N` without rewriting anything, and **C** flips
between the saved view and the one you are composing, so you can see what
you would be replacing before you replace it. Saving is held back while
the saved view is on screen — that write would only put back what is
already there.

Panoramas wider than 6000 px are shown downscaled to that width. Very
large equirectangular images (8000 px and up) fail to render on older
graphics hardware — often erratically, one image loading and the next
staying black — and the saved heading, pitch and field of view are
resolution-independent, so the smaller copy costs nothing but on-screen
detail. Your files are never modified; the downscaled copy lives in a
temporary folder for as long as the editor runs. Raise or disable the
ceiling with `--max-width 12000` or `--max-width 0` if your machine can
take it. Downscaling needs Pillow 11 or newer (`pip install
'dji-drone-metadata-embedder[terrain]'`) — older versions cannot copy a
panorama's GPano tags into the smaller image, and the editor refuses a
rendition it cannot prove is framed like the original. Without a usable
Pillow the editor still runs and serves the originals.

With views saved, `photomap --pano-view-thumbs` renders each tagged
panorama's popup thumbnail as a square crop of that opening view instead
of the distorted 2:1 strip (panoramas without a saved view keep the
strip).

Photos that carry `Artist`/`Copyright` EXIF (or the XMP Dublin Core
equivalents) get an attribution line in their popup, and the 360° viewer
shows it as a byline — add it once with
`exiftool -Artist="Name" -Copyright="© 2026 Name" -overwrite_original DIR`
and every map you generate credits you. Drop it from a particular map with
`--popup-fields` if you prefer.

The simplest way to use the viewer is `--serve` (it implies
`--link-originals`):

```bash
dji-embed photomap /path/to/panoramas --serve
```

This writes the map, serves its folder at a private local address
(`http://127.0.0.1:<port>` — reachable only from your own computer), and
opens it in your browser. Press Ctrl+C in the terminal to stop.

To serve a map that already exists without rebuilding it, use the
standalone `serve` command:

```bash
dji-embed serve /path/to/panoramas                       # opens photomap.html
dji-embed serve ./footage --page flightmap.html
```

(The desktop app uses this under the hood: maps opened from its Done
screen are served automatically, so the 360° viewer just works there.)
Wrapper flags for that kind of integration: `--no-browser`, `--url-only`
(print the bare URL as the first line), and `--exit-with-stdin` (stop when
stdin closes, tying the server to the app that started it).

Both the `--serve` flag and the standalone `serve` command answer HTTP Range
requests (`206 Partial Content`), not just whole-file downloads — Python's
stock file server does not, and without it a browser scrubbing a served
video has to re-fetch from the start instead of jumping straight to the
requested second. This is what makes seeking smooth in the flightmap
crossfade above, on video files that can run well past the size of a photo.

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
