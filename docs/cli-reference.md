# Command reference

[← Back to Home](index.md)

Every `dji-embed` command with its options. The same help is available at
the terminal via `dji-embed COMMAND --help`. New here? The
[User Guide](user_guide.md) and [Decision Table](decision-table.md) are the
gentler starting points.

Scripting or building a frontend? Every command except `panoedit` and
`serve` accepts `--progress jsonl` — one JSON event per line on stdout,
documented in [Progress Events (JSONL)](PROGRESS_JSONL.md).

```bash
dji-embed [OPTIONS] COMMAND [ARGS]...

Commands:
  embed       Embed telemetry from SRT files into MP4 videos
  validate    Validate SRT/MP4/MOV pairs and report drift
  convert     Convert SRT telemetry to GPX, CSV, GeoJSON, KML, CoT, or HTML
  timeline    Build an editor timeline (FCPXML) with flight moments marked
  flightmap   Map every flight in a folder on one combined map
  map         One map of everything in a folder: photos, panoramas, flights
  photomap    Map GPS-tagged still photos as HTML, KML, or GeoJSON
  panoedit    Edit the opening view of 360° panoramas
  serve       Serve a generated map folder at a private local address
  check       Check media files for embedded metadata
  verify-sun  Summarise the sun's position over a clip for shadow checks
  fetch-log   Decrypt TXT flight records via the Flight Reader API (opt-in)
  doctor      Show system information and verify dependencies

Global Options:
  --version   Show the version and exit
  --log-json  Output structured JSON logs for machine processing
  -h, --help  Show this message and exit
```

## `dji-embed embed` - Process Videos

Embed telemetry from SRT files into the matching MP4 videos. Processing shows
a progress bar for each file; results go to a `processed` subdirectory (see
[Output](#output)).

```bash
dji-embed embed /path/to/drone/footage                      # basic usage
dji-embed embed "D:\DroneFootage\Flight1" -o "D:\Processed" # custom output directory
dji-embed embed "D:\DroneFootage\Flight1" --exiftool        # also write EXIF GPS tags
```

<details>
<summary>All options</summary>

```bash
dji-embed embed [OPTIONS] DIRECTORY

Options:
  -o, --output DIRECTORY     Output directory (ignored if --overwrite)
  --overwrite                Overwrite original video files in place
                             (destination = input folder)
  --exiftool                 Also use ExifTool for GPS metadata
  --dat PATH                 DAT flight log to merge
  --dat-auto                 Auto-detect DAT logs matching videos
  --audio-sidecar            Auto-detect a same-basename .m4a audio sidecar
                             (e.g. DJI Neo 2) and mux it into the output (no
                             re-encode).
  --redact [none|drop|fuzz]  Redact GPS coordinates  [default: none]
  --container [mp4|mkv]      Output container. Use 'mkv' to preserve DJI
                             djmd/dbgi data streams (dropped by the mp4
                             muxer).  [default: mp4]
  --extract-home             Opt-in: extract the HOME/launch point (operator
                             location) into the JSON sidecar. Never written to
                             the MP4. Subject to --redact.
  --progress [jsonl]         Emit machine-readable progress events on stdout,
                             one JSON object per line (see
                             docs/PROGRESS_JSONL.md). Suppresses human output
                             on stdout; warnings and logs still go to stderr.
  -v, --verbose              Verbose output
  -q, --quiet                Suppress progress output
```

</details>

## `dji-embed validate` - Check SRT/MP4 Sync

Validate SRT/MP4 pairs and generate a drift analysis report — useful when
subtitles seem out of step with the video.

```bash
dji-embed validate /path/to/footage
```

<details>
<summary>All options</summary>

```bash
dji-embed validate [OPTIONS] DIRECTORY

Options:
  --drift-threshold FLOAT  Drift threshold in seconds for warnings
  --format [text|json]     Output format for drift report
  --progress [jsonl]       Emit machine-readable progress events on stdout,
                           one JSON object per line (see
                           docs/PROGRESS_JSONL.md). Suppresses human output on
                           stdout; warnings and logs still go to stderr.
  -v, --verbose            Verbose output
  -q, --quiet              Suppress info output
```

</details>

## `dji-embed convert` - Export Telemetry

Convert SRT telemetry to GPX, CSV, GeoJSON, KML, CoT, or a standalone HTML
map. On sidecar-less models (Air 3S, Mini 5 Pro, …) the input can be the MP4
itself.

```bash
dji-embed convert gpx DJI_0001.SRT               # GPS track for Google Earth
dji-embed convert csv DJI_0001.SRT -o telemetry.csv
dji-embed convert gpx /path/to/srt/files --batch # whole directory in one go
dji-embed convert html DJI_0001.SRT              # single-flight map -> DJI_0001.html
dji-embed convert html DJI_0042.MP4              # sidecar-less models: telemetry from the MP4
```

GPX/CoT timestamps are written in UTC. DJI SRT times are local with no
timezone, so the offset is auto-detected from the file's modification time.
Override it when the mtime is unreliable (e.g. copied files):

```bash
dji-embed convert gpx DJI_0001.SRT --tz-offset +05:30
```

<details>
<summary>All options</summary>

```bash
dji-embed convert [OPTIONS] {gpx|csv|geojson|kml|html|cot} INPUT

Arguments:
  {gpx|csv|geojson|kml|html|cot}  Output format
  INPUT                           .SRT, .MP4 or .MOV file, or a
                                  directory with --batch

Options:
  -o, --output PATH           Output file path
  -b, --batch                 Batch process directory
  --tz-offset OFFSET          UTC offset for GPX/CoT timestamps, e.g. '+05:30'
                              or '-8'. 'auto' detects it from the SRT file
                              mtime. Ignored for MP4 input (its GPSDateTime is
                              already UTC).  [default: auto]
  --redact [none|drop|fuzz]   GPS redaction, applied to the track in every
                              format: drop removes the track
                              (gpx/geojson/kml/html/cot) or blanks the GPS+sun
                              columns (csv, rows kept); fuzz coarsens to ~100
                              m. The opt-in HOME marker is redacted the same
                              way.  [default: none]
  --interval FLOAT            cot only: seconds between sampled track points.
                              [default: 1.0]
  --cot-type CODE             cot only: CoT event type/affiliation code
                              (default neutral air).  [default: a-n-A]
  --footprint                 Add camera footprint polygons (geojson/kml,
                              redact=none only)
  --footprint-interval FLOAT  Seconds between footprint samples  [default:
                              2.0]
  --model TEXT                Drone model for the footprint FOV table (e.g.
                              air3, mini4pro)
  --extract-home              Opt-in: extract the HOME/launch point (operator
                              location) into gpx/csv/geojson output. Subject
                              to --redact.
  --progress [jsonl]          Emit machine-readable progress events on stdout,
                              one JSON object per line (see
                              docs/PROGRESS_JSONL.md). Suppresses human output
                              on stdout; warnings and logs still go to stderr.
  -v, --verbose               Verbose output
  -q, --quiet                 Suppress info output
```

</details>

**CoT (Cursor-on-Target)** — for ATAK/TAK; see [FMV interoperability](fmv-interop.md):

```bash
dji-embed convert cot DJI_0001.SRT                       # -> DJI_0001.cot.xml
dji-embed convert cot DJI_0001.SRT --interval 2 --cot-type a-u-A
```

**Camera footprints** — overlay per-interval ground-coverage polygons in
GeoJSON/KML for down-looking footage (suppressed under `--redact`; see
[Maps & Panoramas](geospatial.md)):

```bash
dji-embed convert geojson DJI_0001.SRT --footprint --model air3
dji-embed convert kml DJI_0001.SRT --footprint --footprint-interval 5
```

## `dji-embed timeline` - Editor Timeline With Flight Moments

Builds one FCPXML timeline from a folder of clips, laid end to end in
recording order, with the moments worth cutting to already marked. Open it
in DaVinci Resolve (File > Import > Timeline) or another FCPXML editor.
Your clips are only read.

```bash
dji-embed timeline /path/to/footage                  # writes <footage>/<folder>.fcpxml
dji-embed timeline /path/to/footage --moments steady,rise
dji-embed timeline /path/to/footage --no-video-gimbal   # faster; no camera moves on Air 3S and later
```

Markers come in three families. **Steady stretches** are spans where the
aircraft and gimbal hold smooth, labelled hover or glide. **Reveals, tilts
and pans** are gimbal moves. **Rises** are climbs with a level camera.
Camera moves need gimbal angles: from the SRT on models that write them,
otherwise from the video's own telemetry on the Air 3, Air 3S, Mini 4 Pro,
Mavic 3 family and Mavic 4 Pro. Reading the video costs roughly 15 seconds
per gigabyte. Neo 2 gets steady and rise markers only. The file holds
absolute paths to your clips, so it can reveal folder or user names if you
share it.

<details>
<summary>All options</summary>

```bash
dji-embed timeline [OPTIONS] FOLDER

Options:
  -o, --output PATH   Output .fcpxml file or directory (default:
                      <folder>/<folder-name>.fcpxml).
  --moments TEXT      Which moments to mark: steady, reveal (reveals, tilts
                      and pans), rise.  [default: steady,reveal,rise]
  --no-video-gimbal   Don't read gimbal angles from the video when the SRT
                      lacks them. Saves roughly 15 seconds per GB of video;
                      reveals, tilts and pans are then skipped on those clips.
  --progress [jsonl]  Emit machine-readable progress events on stdout, one
                      JSON object per line (see docs/PROGRESS_JSONL.md).
                      Suppresses human output on stdout; warnings and logs
                      still go to stderr.
  -v, --verbose       Verbose output
  -q, --quiet         Suppress info output
```

</details>

## `dji-embed flightmap` - Combined Flight Map

Map every flight in a folder of DJI `.SRT` logs and telemetry-carrying videos
on one combined map. `.SRT` sidecars are read directly; a video with no
`.SRT` beside it is probed for an embedded telemetry track and, when it
carries one, read via ExifTool. A video that already has an `.SRT` is never
opened by the scan, so a folder of paired SRT/MP4 clips stays fast. Each
flight becomes its own coloured track with a popup (start time, duration,
altitude range, GPS points) and a layer toggle; the KML imports into Google
Earth and Google My Maps as one line per flight. SRT files without GPS
telemetry (e.g. ordinary subtitles) are skipped and counted in a summary;
`-v` lists them.

```bash
dji-embed flightmap /path/to/footage                        # -> footage/flightmap.html
dji-embed flightmap /path/to/footage -f all                 # -> footage/flightmap.{html,kml,geojson}
dji-embed flightmap /path/to/footage -r --title "Road trip" # recurse + custom title
dji-embed flightmap /path/to/footage --airspace            # overlay official drone zones
dji-embed flightmap /path/to/footage -f record             # printable flight record
```

Prefer one map per clip? `dji-embed convert html /path/to/footage --batch`
writes a separate `.html` next to each video.

<details>
<summary>All options</summary>

```bash
dji-embed flightmap [OPTIONS] DIRECTORY

Options:
  -o, --output FILE               Output file; used as the base name when
                                  --format all
  -f, --format [html|kml|geojson|record|all]
                                  Map output format. 'record' (also written by
                                  'all') writes a printable flight record;
                                  building it fetches airspace data from
                                  official feeds (FAA / ED-269) and terrain
                                  tiles from Mapterhorn. These fetches — and
                                  --airspace's — are the command's only
                                  network access; responses are cached beside
                                  the output.  [default: html]
  --airspace-refresh              Refetch airspace data past the cache (-f
                                  record or --airspace).
  --airspace                      Overlay official airspace zones (FAA UAS
                                  Facility Maps / ED-269) on the HTML map,
                                  flat or --3d — announced, cached network
                                  fetches, exactly like -f record. Zones draw
                                  in one neutral style (in 3D, published
                                  ceilings become translucent volumes); the
                                  map states facts and makes no determination.
  -r, --recursive                 Scan subdirectories too
  --title TEXT                    Map title (default: directory name)
  --redact [none|fuzz]            GPS redaction: fuzz coarsens every flight to
                                  ~100 m before writing  [default: none]
  --join-gap SECONDS              Chain size-split recordings (DJI starts a
                                  new file at the 4 GB limit) into one flight
                                  when the next file's telemetry starts within
                                  SECONDS and resumes where the previous file
                                  ended. 0 disables joining.  [default: 15.0]
  --tz-offset OFFSET              UTC offset of the SRT timestamps, e.g.
                                  '+05:30' or '-8'. 'auto' detects it from
                                  each file's mtime; pass it explicitly when
                                  the files were copied through zip/cloud
                                  transfers that rewrote the mtimes.
                                  [default: auto]
  --3d                            Write a 3D terrain map (MapLibre GL, draped
                                  tracks) instead of the flat map. HTML only;
                                  defaults to flightmap-3d.html so the 2D map
                                  is never overwritten.
  --link-originals                Embed a link to each flight's source video,
                                  enabling the 3D map's video crossfade.
                                  Originals still carry exact GPS in their own
                                  metadata even when --redact fuzz coarsens
                                  the map.
  --link-base PREFIX              Folder or URL prefix for --link-originals
                                  hrefs, for when the videos do not sit beside
                                  the map.
  --flight-log CSV                Flight-log CSV export (Airdata, Flight
                                  Reader, ...) whose gimbal pitch/yaw is
                                  merged into the matching flight by timestamp
                                  — for drones whose SRT carries no gimbal
                                  data, this upgrades the 3D map's estimated
                                  camera footprints to measurements. Repeat
                                  for several flights. Enable the UTC
                                  timestamp and the gimbal pitch/yaw fields in
                                  the decoder's export settings.
  --gimbal-from-video             Read gimbal pitch/yaw from each flight's MP4
                                  timed metadata when the SRT carries none
                                  (Air 3S and newer), upgrading the 3D map's
                                  estimated camera footprints to measurements.
                                  Needs ExifTool (dji-embed doctor --install
                                  exiftool) and opens every video, roughly 15
                                  seconds per gigabyte. SRT values are never
                                  overwritten.
  --tile-style [osm|osm-hot|opentopomap|cyclosm]
                                  Basemap style for the HTML map: standard
                                  OSM, Humanitarian (osm-hot), topographic
                                  (opentopomap), or cycling (cyclosm).
                                  [default: osm]
  --progress [jsonl]              Emit machine-readable progress events on
                                  stdout, one JSON object per line (see
                                  docs/PROGRESS_JSONL.md). Suppresses human
                                  output on stdout; warnings and logs still go
                                  to stderr.
  -v, --verbose                   Verbose output
  -q, --quiet                     Suppress info output
```

</details>

Notes:
- With `-r`, flights are labelled by their path relative to `DIRECTORY`
  (`session1/DJI_0001`), so per-session folders that reuse DJI's restarting
  file numbering stay distinct.
- Long recordings that DJI split at the 4 GB file limit are stitched back
  into one flight when the next file's telemetry continues (in time and
  position) where the previous one ended — measured on the SRT's own
  timestamps, so it survives copied files with rewritten mtimes. The popup
  lists the joined files; tune or disable with `--join-gap`.
- The 3D map's camera footprints are estimates unless the SRT logs gimbal
  angles. `--gimbal-from-video` reads them from the MP4's own telemetry (Air
  3/3S, Mavic 3/4 Pro, Mini 4 Pro; needs ExifTool, opens every video), and
  `--flight-log CSV`
  merges them from a decoded flight record for drones that log none.
- Tracks are thinned to ~1 GPS point per second for the map (DJI logs ~30
  per second) — visually identical but far smaller files; use
  `dji-embed convert` on a single flight when you need every sample.
- Popup start times are converted to UTC using each file's mtime. On archives
  whose mtimes were rewritten (zip/cloud transfers) the tool warns once and
  falls back to the mtime; pass `--tz-offset` with your recording timezone to
  get correct absolute times. Joining itself is unaffected either way.
- Leaflet and the OpenStreetMap basemap tiles load from the internet; the
  flight data itself is embedded, so the HTML file is portable but needs a
  connection to render. A flight map publishes where you fly — share it
  deliberately, or use `--redact fuzz`.
- `--3d` renders the flights over real 3D terrain (MapLibre + Mapterhorn/
  Copernicus, keyless) as a separate `flightmap-3d.html`, instead of the
  flat basemap. The 3D map adds altitude curtains, a cockpit view, playback,
  the camera's ground footprint, and — with `--link-originals` — a crossfade
  between the terrain and your footage. Each is documented in
  [Maps & Panoramas](geospatial.md#3d-terrain-view); note that
  `--redact fuzz` withholds the footprint and the crossfade, because
  coarsened coordinates cannot honestly say which ground was filmed.

## `dji-embed map` - One Map Of Everything

The simple mode: point it at a mixed folder and get a single HTML map of
the geotagged photos, 360° panoramas, and DJI flight tracks inside. It
always scans subfolders, chains recordings split at the 4 GB limit back
into single flights, and needs no decisions — photos and sidecar-less
videos require ExifTool; SRT flight tracks don't.

```bash
dji-embed map /path/to/folder                 # -> folder/map.html
dji-embed map /path/to/folder --serve         # local server + 360° viewer
dji-embed map /path/to/folder --redact fuzz   # coarsen all GPS to ~100 m
dji-embed map /path/to/folder --3d            # -> folder/map-3d.html, over terrain
```

Photos cluster and toggle exactly like `photomap`; flights draw and play
back exactly like `flightmap`, and `--3d` gives the whole folder the 3D
terrain view. Reach for those two commands when you need KML/GeoJSON
output, popup control, linked originals, basemap styles, or airspace.

<details>
<summary>All options</summary>

```bash
dji-embed map [OPTIONS] DIRECTORY

Options:
  -o, --output FILE     Output HTML file (default: map.html inside the folder)
  --redact [none|fuzz]  GPS redaction: fuzz coarsens every photo and flight to
                        ~100 m before writing. Original files still carry
                        exact GPS.  [default: none]
  --serve               After writing the map, serve its folder at a private
                        local address (http://127.0.0.1, this computer only)
                        and open the browser. Links each pin to its original
                        photo and enables the 360° viewer, which browsers
                        block on maps opened straight from disk.
  --3d                  Render over 3D terrain (MapLibre + Mapterhorn) instead
                        of the flat map; writes map-3d.html. Needs WebGL and a
                        network connection for the terrain tiles. With
                        --serve, flight videos also play inside the 3D cockpit
                        view.
  --progress [jsonl]    Emit machine-readable progress events on stdout, one
                        JSON object per line (see docs/PROGRESS_JSONL.md).
                        Suppresses human output on stdout; warnings and logs
                        still go to stderr.
  -v, --verbose         Verbose output
  -q, --quiet           Suppress info output
```

</details>

## `dji-embed photomap` - Map Still Photos

Map GPS-tagged still photos (JPG/JPEG/DNG) as an HTML, KML, or GeoJSON map.
Requires ExifTool (`dji-embed doctor` checks it). Photos without GPS data are
skipped and counted in a summary; `-v` lists the skipped filenames. On the
HTML map, regular photos are blue markers and 360° panoramas orange ones,
with a checkbox to show/hide each type when a folder mixes both.

```bash
dji-embed photomap /path/to/photos                                    # -> photos/photomap.html
dji-embed photomap /path/to/photos -f all                             # -> photos/photomap.{html,kml,geojson}
dji-embed photomap /path/to/photos -r --title "Churches of Finland"   # recurse + custom title
dji-embed photomap /path/to/photos --link-originals                   # popups open the original photos
dji-embed photomap /path/to/photos --link-originals --link-base ../DCIM   # originals live elsewhere
dji-embed photomap /path/to/photos --redact fuzz                      # ~100 m coarsened pins
dji-embed photomap /path/to/photos --popup-fields none                # popups show thumbnails only
dji-embed photomap /path/to/photos --serve                            # serve + open browser (360° viewer works)
```

<details>
<summary>All options</summary>

```bash
dji-embed photomap [OPTIONS] DIRECTORY

Options:
  -o, --output FILE               Output file; used as the base name when
                                  --format all
  -f, --format [html|kml|geojson|all]
                                  Map output format  [default: html]
  -r, --recursive                 Scan subdirectories too
  --title TEXT                    Map title (default: directory name)
  --link-originals                HTML popups link the thumbnail/filename to
                                  the original photo file (resolves while the
                                  map stays next to the photos)
  --link-base PREFIX              Folder or URL prefix for --link-originals
                                  hrefs, for when the originals do not sit
                                  beside the HTML (e.g. photos/ or
                                  https://example.com/photos/)
  --popup-fields LIST             Limit what the HTML popups show: 'none' or a
                                  comma list of name, timestamp, camera,
                                  altitude, credit (default: all of them).
                                  Excluded details are left out of the HTML
                                  file entirely; the original photos are
                                  untouched. Other formats are unchanged.
  --redact [none|fuzz]            GPS redaction: fuzz coarsens every photo
                                  location to ~100 m before writing (all
                                  formats). Linked/attached original files
                                  still carry exact GPS in their EXIF.
                                  [default: none]
  --serve                         After writing the map, serve its folder at a
                                  private local address (http://127.0.0.1,
                                  this computer only) and open the browser.
                                  Implies --link-originals. Needed for the
                                  360° viewer, which browsers block when the
                                  map is opened straight from disk. With -v,
                                  each HTTP request is logged.
  --pano-view-thumbs              Render square popup thumbnails at each
                                  panorama's saved opening view (GPano
                                  initial-view tags; set them with 'dji-embed
                                  panoedit'). Panoramas without a saved view
                                  keep the 2:1 strip.
  --tile-style [osm|osm-hot|opentopomap|cyclosm]
                                  Basemap style for the HTML map: standard
                                  OSM, Humanitarian (osm-hot), topographic
                                  (opentopomap), or cycling (cyclosm).
                                  [default: osm]
  --progress [jsonl]              Emit machine-readable progress events on
                                  stdout, one JSON object per line (see
                                  docs/PROGRESS_JSONL.md). Suppresses human
                                  output on stdout; warnings and logs still go
                                  to stderr.
  -v, --verbose                   Verbose output
  -q, --quiet                     Suppress info output
```

</details>

Notes:
- With `-r`, pins are labelled by their path relative to `DIRECTORY`, so
  per-session folders that reuse DJI's restarting `DJI_0001.JPG` names stay
  distinct on the map.
- Popup previews use the small EXIF thumbnail, falling back to a size-capped
  embedded preview for DNGs that carry no thumbnail.
- A **Hover previews** toggle in the map's top-right corner (off by default,
  mouse devices only, remembered by the browser) shows each pin's thumbnail
  and filename in a tooltip, so a map can be skimmed without clicking every
  pin (HTML output).
- Photos with no EXIF altitude are clamped to the ground in KML (Google Earth)
  instead of being buried at 0 m below terrain.
- `--link-originals` makes each popup's thumbnail and filename a click-through
  to the full-resolution original (HTML output only). The links are plain
  relative hrefs, so they resolve while the HTML sits next to the photos and
  break if the map is moved or emailed without them — the popup always names
  the file regardless. Use `--link-base` when the originals live elsewhere
  (a relative folder like `../DCIM`, or an absolute URL). Browsers download
  rather than display DNG files; JPGs open in a new tab.
- 360° panoramas (DJI, Insta360, Google Camera, …) are detected during the
  same scan; clicking one opens an embedded interactive viewer instead of a
  flat, distorted JPEG when the map is served with `--serve` (or opened over
  HTTP with `--link-originals`) — browsers block the viewer on maps opened
  straight from disk.
- `--redact fuzz` coarsens every pin to ~100 m before the map is written —
  use it for maps you plan to share. Combined with `--link-originals`, the
  linked originals still carry exact GPS in their EXIF, so share those
  deliberately too.
- Leaflet and the OpenStreetMap basemap tiles load from the internet; the
  photo thumbnails themselves are embedded, so the HTML file is portable but
  needs a connection to render. A photo map publishes your shooting
  locations — share it deliberately.

## `dji-embed panoedit` - Set 360° Opening Views

Opens a local editor (this computer only) where you drag and zoom each 360°
panorama to the view it should open with. Save writes the GPano
initial-view tags into the file via ExifTool and moves on to the next one.
Each original is kept beside it as `<name>_original` unless you pass
`--no-backup`. The photo map's 360° viewer and Google Photos both honour
the saved view; see [Maps & Panoramas](geospatial.md).

```bash
dji-embed panoedit /path/to/panoramas
dji-embed panoedit /path/to/panoramas --clean-backups   # delete the _original copies
```

<details>
<summary>All options</summary>

```bash
dji-embed panoedit [OPTIONS] DIRECTORY

Options:
  -r, --recursive     Include panoramas in subfolders.
  --port INTEGER      Local port to serve the editor on.  [default: (random)]
  --no-browser        Do not open the browser; just print the URL and serve.
  --url-only          Print the bare URL as the first output line — a stable
                      contract for wrapper apps that parse it.
  --exit-with-stdin   Stop serving when stdin closes, tying the server's
                      lifetime to the app that started it.
  --max-width PIXELS  Show panoramas wider than this downscaled to it (0
                      serves every file at full size; values below 512 are
                      raised to 512). Older graphics hardware fails to display
                      very large panoramas; the files themselves are never
                      modified.  [default: 6000; x>=0]
  --no-backup         Write views straight into the files instead of keeping a
                      <name>_original copy beside each edited panorama. The
                      tags are re-editable and never touch the image data, but
                      without backups a save that goes wrong cannot be undone.
  --clean-backups     Delete the <name>_original copies left by earlier edits
                      — only where the edited file still exists beside them —
                      then exit without opening the editor. Honours
                      -r/--recursive.
```

</details>

## `dji-embed serve` - Serve A Map Locally

Serves a folder of generated maps at a private local address
(`http://127.0.0.1`) until Ctrl+C. Maps open fine straight from disk except
the 360° panorama viewer, which browsers block on `file://` pages. This is
the same server as `photomap --serve`, without rebuilding the map.

```bash
dji-embed serve /path/to/photos                    # opens photomap.html
dji-embed serve /path/to/footage --page map.html
```

<details>
<summary>All options</summary>

```bash
dji-embed serve [OPTIONS] DIRECTORY

Options:
  --page FILE        Map file to open, relative to DIRECTORY.  [default:
                     photomap.html]
  --no-browser       Do not open the browser; just print the URL and serve.
  --url-only         Print the bare URL as the first output line — a stable
                     contract for wrapper apps that parse it.
  --exit-with-stdin  Stop serving when stdin closes, tying the server's
                     lifetime to the app that started it.
  -v, --verbose      Log each HTTP request
  -q, --quiet        Suppress info output
```

</details>

## `dji-embed fetch-log` - Decrypt Flight Records (Opt-in)

Uploads DJI `.txt` flight records to Flight Reader with your own API key
(`FLIGHTREADER_API_KEY`) and writes the decoded `NAME.flightreader.csv`
beside each one, ready for `flightmap --flight-log`. It asks before
uploading, and never uploads a record whose CSV already exists. What gets
transmitted is described in
[Gimbal from a flight log](how-to/flight-log-gimbal.md).

```bash
dji-embed fetch-log /path/to/FlightRecord.txt
```

<details>
<summary>All options</summary>

```bash
dji-embed fetch-log [OPTIONS] RECORDS...

Options:
  --yes               Skip the upload consent prompt. Required with --progress
                      jsonl, where nothing can be prompted, so whatever drives
                      the CLI must obtain consent first (the desktop app does
                      not offer fetch-log).
  --progress [jsonl]  Emit machine-readable progress events on stdout, one
                      JSON object per line (see docs/PROGRESS_JSONL.md).
                      Suppresses human output on stdout; warnings and logs
                      still go to stderr.
  -v, --verbose       Verbose output
  -q, --quiet         Suppress info output
```

</details>

## `dji-embed check` - Check Existing Metadata

Check whether videos or photos already contain GPS or altitude information.

```bash
dji-embed check DJI_0001.MP4
dji-embed check /path/to/footage
```

`check` uses `ffprobe` for QuickTime tags and `exiftool` for EXIF data
when available. Pass `--verbose` for debug output or `--quiet` to only
show warnings and errors. `--progress jsonl` switches stdout to
machine-readable events (see [Progress Events](PROGRESS_JSONL.md)).

<details>
<summary>All options</summary>

```bash
dji-embed check [OPTIONS] [PATHS]...

Options:
  --progress [jsonl]  Emit machine-readable progress events on stdout, one
                      JSON object per line (see docs/PROGRESS_JSONL.md).
                      Suppresses human output on stdout; warnings and logs
                      still go to stderr.
  -v, --verbose       Verbose output
  -q, --quiet         Suppress info output
```

</details>

## `dji-embed verify-sun` - Sun-Position Cross-Check

Summarise the sun's azimuth/elevation over a clip so analysts can compare
shadow direction and length in the footage against the astronomical sun.
Accepts an `.SRT` sidecar or, on sidecar-less models, the MP4 itself.
CSV export (`dji-embed convert csv`) gains matching `datetime_utc` /
`sun_azimuth` / `sun_elevation` columns.

```bash
dji-embed verify-sun DJI_0001.SRT
dji-embed verify-sun DJI_0042.MP4 --format json
```

<details>
<summary>All options</summary>

```bash
dji-embed verify-sun [OPTIONS] SRT

Options:
  --tz-offset OFFSET    UTC offset for the SRT timestamps, e.g. '+05:30' or
                        '-8'. 'auto' detects it from the SRT file mtime.
                        [default: auto]
  --format [text|json]  Output format  [default: text]
  --progress [jsonl]    Emit machine-readable progress events on stdout, one
                        JSON object per line (see docs/PROGRESS_JSONL.md).
                        Suppresses human output on stdout; warnings and logs
                        still go to stderr.
  -v, --verbose         Verbose output
  -q, --quiet           Suppress info output
```

</details>

## `dji-embed doctor` - System Diagnostics

Show system information and verify all dependencies.

```bash
dji-embed doctor
```

`dji-embed doctor --install exiftool` downloads a pinned, checksum-verified
ExifTool into your user directory — useful where system packages are too old
for MP4 timed metadata (most Linux distros).

**Opt-in update check.** Normal commands never touch the network. `doctor`
is the only command that may go online for version info, and it asks first:
the first interactive run prompts once (`Check online for newer versions
(PyPI + ExifTool)? [y/N]`, default No) and remembers your answer. When
enabled, doctor compares your dji-embed against PyPI and your ExifTool
against the bundled pin, and prints an upgrade command matched to how you
installed (winget/EXE, pipx, or the exact `python -m pip` for your
interpreter). Network failures degrade silently to the offline report.

```bash
dji-embed doctor --online     # enable for this run and remember it
dji-embed doctor --offline    # disable for this run and remember it
```

Set `DJIEMBED_NO_UPDATE_CHECK=1` to hard-disable the check regardless of the
remembered choice. Non-interactive runs (no terminal, or `CI` set) never
prompt and never check. The ExifTool-vs-pin comparison needs no network and
is always shown when your ExifTool is older than the pinned release.

<details>
<summary>All options</summary>

```bash
dji-embed doctor [OPTIONS]

Options:
  -v, --verbose         Verbose output
  -q, --quiet           Suppress info output
  --install [exiftool]  Download a pinned, checksum-verified copy of the tool
                        into the per-user tools directory (no admin rights
                        needed), then run the checks.
  --force               With --install: reinstall even when already
                        provisioned.
  --online / --offline  Enable/disable the online update check (PyPI +
                        ExifTool pin) for this run and remember the choice.
                        Default: remembered choice, asked once on interactive
                        terminals. DJIEMBED_NO_UPDATE_CHECK=1 hard-disables.
  --progress [jsonl]    Emit machine-readable progress events on stdout, one
                        JSON object per line (see docs/PROGRESS_JSONL.md).
                        Suppresses human output on stdout; warnings and logs
                        still go to stderr.
```

</details>

## Output

The `embed` command creates a `processed` subdirectory containing:

- `*_metadata.MP4` - Video files with embedded metadata and telemetry subtitles
- `*_telemetry.json` - Flight summary with GPS data, altitude, and camera settings

Example JSON output:
```json
{
  "filename": "DJI_0158.MP4",
  "first_gps": [59.302335, 18.203059],
  "average_gps": [59.302336, 18.203058],
  "max_altitude": 132.86,
  "max_relative_altitude": 1.5,
  "flight_duration": "00:00:00 - 00:00:32",
  "num_gps_points": 967,
  "camera_settings": {
    "iso": "2700",
    "shutter": "1/30.0",
    "fnum": "170"
  },
  "location": "Stockholm, Sweden"
}
```

## How It Works

1. **SRT Parsing**: Extracts telemetry data from DJI SRT subtitle files
2. **Metadata Embedding**: Uses FFmpeg to:
   - Add SRT as subtitle track (preserves all telemetry)
   - Embed GPS coordinates in video metadata
   - Add altitude and other metadata tags
3. **No Re-encoding**: Uses stream copy for fast processing without quality loss
4. **Summary Generation**: Creates JSON files with flight statistics

The tool recognises multiple DJI SRT dialects, from the bracketed
`[latitude: 59.302335] [longitude: 18.203059]` style of recent models to the
legacy `GPS(59.302335,18.203059,132.860)` form — the full catalogue lives in
[SRT Formats](SRT_FORMATS.md).
