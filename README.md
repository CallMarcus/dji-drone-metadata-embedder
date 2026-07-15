# DJI Drone Metadata Embedder

[![GitHub Release]][release]
[![Version](https://img.shields.io/badge/version-1.19.0-blue)][release]
[![PyPI]][pypi]
[![Winget]][winget]

A free tool that puts your DJI drone footage on the map — literally. It reads
the telemetry DJI records with every flight (GPS position, altitude, camera
settings) and turns it into interactive maps, standard GPS files, and location
metadata embedded in the videos themselves.

New to command-line tools? Start with [Get started](#get-started) below —
it's a handful of copy-paste commands. For a guided tour see
[docs/user_guide.md](docs/user_guide.md), and if anything fails,
[docs/troubleshooting.md](docs/troubleshooting.md) has the fixes.

## What can it do?

- **See every flight on one map** — point `dji-embed flightmap` at a folder of
  footage and get a single interactive map with each flight as its own
  coloured track *(experimental)*.
- **See where every photo was taken** — `dji-embed photomap` pins a whole
  folder of stills on one clustered map, thumbnails included, and opens 360°
  panoramas in an interactive viewer.
- **Make videos searchable by location** — `dji-embed embed` writes the GPS
  data into the video files so Windows Photos, Google Photos, and similar apps
  can find them by place. No re-encoding, no quality loss, and the full
  telemetry is preserved as a subtitle track for overlays in video editors.
- **Export flight tracks** — GPX for Google Earth, CSV for spreadsheets,
  GeoJSON/KML for GIS tools, CoT for ATAK/TAK
  (see [docs/geospatial.md](docs/geospatial.md) and
  [docs/fmv-interop.md](docs/fmv-interop.md)).
- **Verify footage** — see what metadata files already carry
  (`dji-embed check`), and cross-check shadows in the footage against the
  astronomical sun (`dji-embed verify-sun`).
- **Keep locations private when sharing** — `--redact` drops or coarsens GPS
  data to ~100 m in any output.

Works on Windows, macOS, and Linux; whole folders are processed in one go,
with a progress bar. `.DAT` flight logs can be merged in where available.

## Get started

You'll need Python 3.10+ and FFmpeg (ExifTool is optional, but unlocks the
photo map and a few other features). On Windows the bootstrap script below
installs all of it for you.

### Windows

Open PowerShell and paste:

```powershell
iwr -useb https://raw.githubusercontent.com/CallMarcus/dji-drone-metadata-embedder/master/tools/bootstrap.ps1 | iex
```

<details>
<summary>Other ways to install on Windows</summary>

- **Direct download:** grab the ready-to-run **dji-embed.exe** from the
  [GitHub Releases page](https://github.com/CallMarcus/dji-drone-metadata-embedder/releases).

- **Windows Package Manager:**

  ```powershell
  winget install CallMarcus.DJIMetadataEmbedder
  ```

  Already installed? Upgrade with `winget upgrade CallMarcus.DJIMetadataEmbedder`.
  winget installs the portable `dji-embed.exe` only — install FFmpeg and
  ExifTool separately (`winget install Gyan.FFmpeg OliverBetz.ExifTool`), or
  use the bootstrap script above, which bundles them.

- **Python package:**

  ```powershell
  pip install dji-drone-metadata-embedder
  ```

  If the command `python` is not recognized on Windows, use `py` instead.

</details>

### macOS / Linux

```bash
brew install ffmpeg exiftool                          # macOS
sudo apt update && sudo apt install ffmpeg exiftool   # Debian/Ubuntu
pip install dji-drone-metadata-embedder
```

<details>
<summary>Docker and building from source</summary>

```bash
docker run --rm -v "$PWD":/data callmarcus/dji-embed -i *.MP4
```

- Build from source with `uv sync --extra dev` (or `pip install -e .`)
- Use the provided `Dockerfile` for custom images
- Review CI scripts under `.github/workflows`

</details>

### Your first map

```bash
dji-embed doctor                        # 1. confirm everything is installed
dji-embed flightmap /path/to/footage    # 2. all flights in a folder -> flightmap.html
dji-embed photomap /path/to/photos      # 3. all photos in a folder  -> photomap.html
```

Open the resulting `.html` file in any browser — done. The maps embed your
data but load the background map tiles from the internet, so they need a
connection to render.

**No terminal at all?** On Windows, drag your footage folder onto
`dji-embed.exe` — it maps every flight log (and geotagged photos) in the
folder, including subfolders, and opens the result in your browser. The same
works in a terminal by passing just a folder: `dji-embed /path/to/footage`.

**Prefer a browser over the terminal?** There's an optional local web UI that
wraps the main commands:

```bash
pip install 'dji-drone-metadata-embedder[ui]'
dji-embed ui
```

It runs entirely on your own machine (`127.0.0.1`) — details under
[`dji-embed ui`](#dji-embed-ui---local-web-ui) below.

> **Privacy note:** maps and exports reveal where you fly. Share them
> deliberately, or add `--redact fuzz` to coarsen every position to ~100 m.

## Which command do I need?

| I want to… | Run |
|---|---|
| See all my flights on one map | `dji-embed flightmap /path/to/footage` |
| See my photos on a map | `dji-embed photomap /path/to/photos` |
| Map one flight in detail | `dji-embed convert html DJI_0001.SRT` |
| Make videos searchable by location | `dji-embed embed /path/to/footage` |
| Get a GPX track for Google Earth | `dji-embed convert gpx DJI_0001.SRT` |
| See what metadata a file already has | `dji-embed check DJI_0001.MP4` |
| Check my setup | `dji-embed doctor` |

More scenarios: [docs/decision-table.md](docs/decision-table.md) and
end-to-end examples in [docs/recipes.md](docs/recipes.md).

## Supported DJI Models

**Fully Tested & Documented** (with sample fixtures):
- **DJI Mini 3/4 Pro** - Square bracket format `[latitude: xx.xxx] [longitude: xx.xxx]`
- **DJI Mini 5 Pro** - HTML-style bracket format with decimal aperture (`[fnum: 1.8]`)
- **DJI Air 3** - HTML-style format with extended telemetry data
- **DJI Air 3S** - HTML-style bracket format with decimal `focal_len` and HLG color mode (`[color_md: hlg]`); MP4 also carries embedded `djmd`/`dbgi` data streams
- **DJI Avata 360** - HTML-style bracket format with stabilization (`pp_*`) fields; footage ships as `.OSV` (360 video) + `.LRF` proxy
- **DJI Neo 2** - HTML-style bracket format with stabilization (`pp_*`) fields; MP4 also carries embedded `djmd`/`dbgi` data streams
- **DJI Avata 2** - Legacy GPS format `GPS(lat,lon,alt)` with BAROMETER data
- **DJI Mavic 3 Enterprise** - Extended format with RTK precision data
- **DJI Matrice 300 (legacy-with-unit)** - `GPS(lat,lon,alt M)` with `BAROMETER:` colon notation
- **DJI Phantom 4 RTK / P4P (compact single-line)** - `F/N, SS N, ISO N, EV N, GPS (lat, lon, alt), HOME (...), D, H, H.S, V.S, F.PRY, G.PRY`

**Community Supported**:
- DJI Air 2S, Mavic 3, and other models using similar SRT formats
- See [troubleshooting guide](docs/troubleshooting.md) for model-specific issues

**Don't see your model?** We're happy to add support in exchange for sample SRT files we can parse the telemetry format from. Open an [issue](https://github.com/CallMarcus/dji-drone-metadata-embedder/issues/new) and attach one or two raw `.SRT` files from your drone (a short clip is plenty), and we'll add a parser for it. See the [Contributing Guide](CONTRIBUTING.md) for details.

**Sidecar-less models (Air 3S, Mini 5 Pro, …):** telemetry is read straight from
the MP4's embedded `djmd`/`dbgi` track via ExifTool — no `.SRT` needed —
for `dji-embed convert <fmt> FILE.MP4` and `dji-embed verify-sun FILE.MP4`.
Requires a recent ExifTool (Air 3S ≥ 13.39, Mini 5 Pro ≥ 13.52); see
[docs/MP4_TIMED_METADATA.md](docs/MP4_TIMED_METADATA.md).

## Intended use & scope

This is a tool for **transparency and accountability**. Drone telemetry is
dual-use, and this project deliberately focuses on the open side of that:
verifying and documenting footage, georeferencing it for mapping, and making it
interoperable with open GIS workflows. The uses we build for include
open-source verification and journalism, human-rights and conflict
documentation, search-and-rescue and disaster response, humanitarian damage
assessment, environmental monitoring, agriculture, and infrastructure
inspection.

Feature and documentation decisions favor **provenance, verification,
georeferencing, and standards interoperability**. We do not build targeting or
other offensive capabilities.

## Command reference

Everything below is also available at the terminal via
`dji-embed COMMAND --help`. Scripting or building a frontend? `photomap`,
`flightmap`, `embed`, and `check` accept `--progress jsonl` — one JSON
event per line on stdout, documented in
[`docs/PROGRESS_JSONL.md`](docs/PROGRESS_JSONL.md).

```bash
dji-embed [OPTIONS] COMMAND [ARGS]...

Commands:
  embed      Embed telemetry from SRT files into MP4 videos
  validate   Validate SRT/MP4 pairs and report drift
  convert    Convert SRT telemetry to GPX, CSV, GeoJSON, KML, HTML, or CoT
  flightmap  Map every flight in a folder of SRT logs on one combined map
  photomap   Map GPS-tagged still photos to an HTML/KML/GeoJSON map
  check      Check media files for embedded metadata
  doctor     Show system information and verify dependencies
  ui         Launch the local web UI in your browser
  verify-sun Summarise the sun's position over a clip for shadow cross-checking

Global Options:
  --version   Show the version and exit
  -h, --help  Show this message and exit
```

### `dji-embed embed` - Process Videos

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

Arguments:
  DIRECTORY          Directory containing MP4 and SRT files

Options:
  -o, --output DIRECTORY     Output directory (ignored if --overwrite)
  --overwrite                Overwrite original video files in place
                             (destination = input folder)
  --exiftool                 Also use ExifTool for GPS metadata
  --dat PATH                 DAT flight log to merge
  --dat-auto                 Auto-detect DAT logs matching videos
  --audio-sidecar            Auto-detect a same-basename .m4a audio sidecar
                             (e.g. DJI Neo 2) and mux it in (no re-encode)
  --redact [none|drop|fuzz]  Redact GPS coordinates (default: none)
  --container [mp4|mkv]      Output container; 'mkv' preserves DJI djmd/dbgi
                             data streams (default: mp4)
  --extract-home             Extract the drone's HOME / launch point into the
                             JSON sidecar. **The HOME point is the operator's
                             launch location** — it is off by default, never
                             written to the MP4, and always honours `--redact`
                             (`drop` removes it, `fuzz` coarsens to ~100 m).
  --progress [jsonl]         Emit machine-readable progress events on stdout,
                             one JSON object per line (docs/PROGRESS_JSONL.md)
  -v, --verbose              Verbose output
  -q, --quiet                Suppress progress output
```

</details>

### `dji-embed validate` - Check SRT/MP4 Sync

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
  -v, --verbose            Verbose output
  -q, --quiet              Suppress info output
```

</details>

### `dji-embed convert` - Export Telemetry

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
  {gpx|csv|geojson|kml|html|cot} Output format
  INPUT                      SRT file or directory to convert

Options:
  -o, --output PATH          Output file path
  -b, --batch                Batch process directory
  --tz-offset OFFSET         UTC offset for GPX/CoT timestamps, e.g. '+05:30' or
                             '-8' ('auto' detects from file mtime; default: auto)
  --redact [none|drop|fuzz]  GPS redaction (default: none), applied to the track
                             in every format: drop removes the track (or blanks
                             the GPS+sun columns in csv, rows kept); fuzz
                             coarsens to ~100 m. HOME marker redacted the same way
  --interval FLOAT           cot only: seconds between sampled points (default: 1.0)
  --cot-type CODE            cot only: CoT type/affiliation code (default: a-n-A)
  --footprint                geojson/kml only: add camera footprint polygons
                             (requires --redact none)
  --footprint-interval FLOAT geojson/kml only: seconds between footprints (default: 2.0)
  --model NAME               footprint FOV-table entry, e.g. air3, mini4pro
  --extract-home             Opt-in: extract the HOME / launch point (operator
                             location) into gpx/csv/geojson output. Off by
                             default; subject to --redact
  -v, --verbose              Verbose output
  -q, --quiet                Suppress info output
```

</details>

**CoT (Cursor-on-Target)** — for ATAK/TAK; see [docs/fmv-interop.md](docs/fmv-interop.md):

```bash
dji-embed convert cot DJI_0001.SRT                       # -> DJI_0001.cot.xml
dji-embed convert cot DJI_0001.SRT --interval 2 --cot-type a-u-A
```

**Camera footprints** — overlay per-interval ground-coverage polygons in
GeoJSON/KML for down-looking footage (suppressed under `--redact`; see
[docs/geospatial.md](docs/geospatial.md)):

```bash
dji-embed convert geojson DJI_0001.SRT --footprint --model air3
dji-embed convert kml DJI_0001.SRT --footprint --footprint-interval 5
```

### `dji-embed flightmap` - Combined Flight Map (experimental)

Map every flight in a folder of DJI `.SRT` logs on one combined map. Reads
only the `.SRT` telemetry sidecars — the videos are never opened and no
external tool is needed — so scanning a large archive is fast. Each flight
becomes its own coloured track with a popup (start time, duration, altitude
range, GPS points) and a layer toggle; the KML imports into Google Earth and
Google My Maps as one line per flight. SRT files without GPS telemetry
(e.g. ordinary subtitles) are skipped and counted in a summary; `-v` lists them.

> **Experimental:** `flightmap` is new and its size-split joining heuristics
> may still be tuned based on real-world feedback. If it joins flights it
> shouldn't (or misses ones it should), please
> [open an issue](https://github.com/CallMarcus/dji-drone-metadata-embedder/issues)
> with the SRT file names and timestamps.

```bash
dji-embed flightmap /path/to/footage                        # -> footage/flightmap.html
dji-embed flightmap /path/to/footage -f all                 # -> footage/flightmap.{html,kml,geojson}
dji-embed flightmap /path/to/footage -r --title "Road trip" # recurse + custom title
```

Prefer one map per clip? `dji-embed convert html /path/to/footage --batch`
writes a separate `.html` next to each video.

<details>
<summary>All options</summary>

```bash
dji-embed flightmap [OPTIONS] DIRECTORY

Arguments:
  DIRECTORY                       Directory containing .SRT flight logs

Options:
  -o, --output FILE               Output file; used as the base name when
                                  --format all
  -f, --format [html|kml|geojson|all]
                                  Map output format (default: html)
  -r, --recursive                 Scan subdirectories too
  --title TEXT                    Map title (default: directory name)
  --redact [none|fuzz]            GPS redaction: fuzz coarsens every flight to
                                  ~100 m before writing (default: none)
  --join-gap SECONDS              Chain size-split recordings (DJI starts a new
                                  file at the 4 GB limit) into one flight when
                                  the next file's telemetry starts within
                                  SECONDS and resumes where the previous file
                                  ended. 0 disables joining (default: 15.0)
  --tz-offset OFFSET              UTC offset of the SRT timestamps, e.g.
                                  '+05:30' or '-8'. 'auto' detects it from each
                                  file's mtime; pass it explicitly when the
                                  files were copied through zip/cloud transfers
                                  that rewrote the mtimes (default: auto)
  --progress [jsonl]              Emit machine-readable progress events on
                                  stdout, one JSON object per line
                                  (docs/PROGRESS_JSONL.md)
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
- Tracks are thinned to ~1 GPS point per second for the map (DJI logs ~30
  per second) — visually identical but far smaller files; use
  `dji-embed convert` on a single flight when you need every sample.
- Popup start times are converted to UTC using each file's mtime. On archives
  whose mtimes were rewritten (zip/cloud transfers) the tool warns once and
  falls back to the mtime; pass `--tz-offset` with your recording timezone to
  get correct absolute times. Joining itself is unaffected either way.
- Sidecar-less models whose telemetry lives inside the MP4 (Air 3S,
  Mini 5 Pro, …) are not scanned; map those per clip with
  `dji-embed convert html VIDEO.MP4`.
- Leaflet and the OpenStreetMap basemap tiles load from the internet; the
  flight data itself is embedded, so the HTML file is portable but needs a
  connection to render. A flight map publishes where you fly — share it
  deliberately, or use `--redact fuzz`.

### `dji-embed photomap` - Map Still Photos

Map GPS-tagged still photos (JPG/JPEG/DNG) as an HTML, KML, or GeoJSON map.
Requires ExifTool (`dji-embed doctor` checks it). Photos without GPS data are
skipped and counted in a summary; `-v` lists the skipped filenames.

```bash
dji-embed photomap /path/to/photos                                    # -> photos/photomap.html
dji-embed photomap /path/to/photos -f all                             # -> photos/photomap.{html,kml,geojson}
dji-embed photomap /path/to/photos -r --title "Churches of Finland"   # recurse + custom title
dji-embed photomap /path/to/photos --link-originals                   # popups open the original photos
dji-embed photomap /path/to/photos --link-originals --link-base ../DCIM   # originals live elsewhere
dji-embed photomap /path/to/photos --redact fuzz                      # ~100 m coarsened pins
dji-embed photomap /path/to/photos --serve                            # serve + open browser (360° viewer works)
```

<details>
<summary>All options</summary>

```bash
dji-embed photomap [OPTIONS] DIRECTORY

Arguments:
  DIRECTORY                       Directory containing JPG/JPEG/DNG photos

Options:
  -o, --output FILE               Output file; used as the base name when
                                  --format all
  -f, --format [html|kml|geojson|all]
                                  Map output format (default: html)
  -r, --recursive                 Scan subdirectories too
  --title TEXT                    Map title (default: directory name)
  --link-originals                HTML popups link the thumbnail/filename to
                                  the original photo file
  --link-base PREFIX              Folder or URL prefix for --link-originals
                                  hrefs, for when the originals do not sit
                                  beside the HTML
  --redact [none|fuzz]            Coarsen every photo location to ~100 m
                                  before writing (default: none)
  --serve                         Serve the map on 127.0.0.1 and open the
                                  browser (implies --link-originals; not
                                  combinable with --progress jsonl)
  --progress [jsonl]              Emit machine-readable progress events on
                                  stdout, one JSON object per line
                                  (docs/PROGRESS_JSONL.md)
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
- Hovering a marker shows the thumbnail and filename in a tooltip, so a map
  can be skimmed without clicking every pin (HTML output, desktop browsers).
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

### `dji-embed check` - Check Existing Metadata

Check whether videos or photos already contain GPS or altitude information.

```bash
dji-embed check DJI_0001.MP4
dji-embed check /path/to/footage
```

`check` uses `ffprobe` for QuickTime tags and `exiftool` for EXIF data
when available. Pass `--verbose` for debug output or `--quiet` to only
show warnings and errors. `--progress jsonl` switches stdout to
machine-readable events (see `docs/PROGRESS_JSONL.md`).

### `dji-embed verify-sun` - Sun-Position Cross-Check

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
                        '-8'. 'auto' detects it from the SRT file mtime
                        (default: auto)
  --format [text|json]  Output format (default: text)
  -v, --verbose         Verbose output
  -q, --quiet           Suppress info output
```

</details>

### `dji-embed doctor` - System Diagnostics

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

### `dji-embed ui` - Local Web UI

Launch the local web UI in your browser (requires the `[ui]` extra). It runs
entirely on `127.0.0.1` and uses your installed browser, so there is no
separate signed app to trust.

```bash
pip install 'dji-drone-metadata-embedder[ui]'
dji-embed ui                       # opens http://127.0.0.1:<free-port>
dji-embed ui --no-browser          # print the URL instead of opening
dji-embed ui --port 8765           # pin to a fixed port
```

Every tab (Doctor / Embed / Validate / Convert / Check) is a thin wrapper
over the matching CLI command. The **Map** tab renders a processed clip's
flight path on an interactive map (Leaflet + OpenStreetMap) with an altitude
profile and a play-the-flight scrubber — only the basemap tiles load from the
network; the flight data and all other assets stay local, and redaction is
applied server-side so exact coordinates never reach the browser when set.
Access is gated by a per-session token that is injected into the opened URL;
requests without the token return `403`. Chromium-based browsers will offer
"Install app" for a standalone window.

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
[docs/SRT_FORMATS.md](docs/SRT_FORMATS.md).

## Troubleshooting

See [docs/troubleshooting.md](docs/troubleshooting.md) for comprehensive troubleshooting.

### Check tool versions
Display the application, FFmpeg and ExifTool versions:
```bash
dji-embed --version
```

### Quick Fixes

#### "Python was not found"
Use `py` instead of `python`:
```bash
dji-embed doctor
```

#### "ffmpeg is not recognized"
Ensure FFmpeg is in your PATH. Test with:
```bash
ffmpeg -version
```
Note: `ffmpeg` uses a single dash. Using `ffmpeg --version` will result in `Unrecognized option '--version'`.

#### "Command not found: dji-embed"
If the command isn't found after installation:
```bash
python -m pip install --user dji-drone-metadata-embedder
# or
pipx install dji-drone-metadata-embedder
```

#### No GPS data in JSON output
1. Check that your SRT files contain GPS coordinates:
   ```bash
   dji-embed check /path/to/your/files
   ```
2. Open an SRT file in a text editor to verify the format
3. Run diagnostics to check for parsing issues:
   ```bash
   dji-embed doctor
   ```

#### Processing fails with "No matching MP4/SRT pairs"
Ensure your files follow the naming convention:
- Video: `DJI_0001.MP4`
- Subtitle: `DJI_0001.SRT`

#### Permission errors on Windows
Run PowerShell as Administrator or use the bootstrap installer:
```powershell
iwr -useb https://raw.githubusercontent.com/CallMarcus/dji-drone-metadata-embedder/master/tools/bootstrap.ps1 | iex
```

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

### Commit Message Format

This project uses [Conventional Commits](https://www.conventionalcommits.org/) for automatic changelog generation:

```bash
feat(cli): add new validate command
fix(parser): handle malformed SRT timestamps  
docs: update troubleshooting guide
```

See [docs/CHANGELOG_AUTOMATION.md](docs/CHANGELOG_AUTOMATION.md) for detailed guidelines.

### Adding Support for New Models

If your DJI model uses a different SRT format, we're happy to add support in exchange for sample SRT files we can parse the telemetry format from:
1. Open an issue and attach one or two raw `.SRT` files from your drone (a short clip is plenty) — we'll add a parser for it
2. Or submit a PR with regex patterns for the new format

## Release

See [docs/RELEASE.md](docs/RELEASE.md) for instructions on publishing a new version.
There are also plans to grow this CLI tool into a Windows application with a
graphical interface — see the [Development Roadmap](docs/development_roadmap.md).

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Thanks to the DJI drone community for format documentation
- FFmpeg and ExifTool teams for their excellent tools

## Related Projects

- [exiftool](https://exiftool.org/) - Read/write metadata in media files
- [ffmpeg](https://ffmpeg.org/) - Media processing framework
- [gpx.py](https://github.com/tkrajina/gpxpy) - GPX file parser (for further processing)

## Disclaimer

This tool is not affiliated with or endorsed by DJI. Use at your own risk.

[GitHub Release]: https://img.shields.io/github/v/release/CallMarcus/dji-drone-metadata-embedder?logo=github
[release]: https://github.com/CallMarcus/dji-drone-metadata-embedder/releases
[PyPI]: https://img.shields.io/pypi/v/dji-drone-metadata-embedder?logo=pypi
[pypi]: https://pypi.org/project/dji-drone-metadata-embedder/
[Winget]: https://img.shields.io/winget/v/CallMarcus.DJIMetadataEmbedder?logo=windows&label=winget
[winget]: https://github.com/microsoft/winget-pkgs/tree/master/manifests/c/CallMarcus/DJIMetadataEmbedder
