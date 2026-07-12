# DJI Drone Metadata Embedder

[![GitHub Release]][release]
[![Version](https://img.shields.io/badge/version-1.16.1-blue)][release]
[![PyPI]][pypi]
[![Winget]][winget]

A Python tool to embed telemetry data from DJI drone SRT files into MP4 video files.
This tool extracts GPS coordinates, altitude, camera settings and other telemetry data from SRT files and embeds
them as metadata in the corresponding video files.

See the [Development Roadmap](docs/development_roadmap.md) for plans to expand this CLI tool into a Windows
application with a graphical interface.
For detailed setup instructions and a quick-start tutorial, see
[docs/installation.md](docs/installation.md) and [docs/user_guide.md](docs/user_guide.md).
Common problems are covered in [docs/troubleshooting.md](docs/troubleshooting.md).

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

## Easy Windows install

### Option 1: Bootstrap Script (Includes FFmpeg/ExifTool)
```powershell
iwr -useb https://raw.githubusercontent.com/CallMarcus/dji-drone-metadata-embedder/master/tools/bootstrap.ps1 | iex
```

### Option 2: Direct Download
Download the ready-to-run **dji-embed.exe** from the [GitHub Releases page](https://github.com/CallMarcus/dji-drone-metadata-embedder/releases).

### Option 3: Windows Package Manager (winget)
```powershell
winget install CallMarcus.DJIMetadataEmbedder
```
Already installed? Upgrade with `winget upgrade CallMarcus.DJIMetadataEmbedder`.

> Note: winget installs the portable `dji-embed.exe` only. Install FFmpeg and ExifTool separately (`winget install Gyan.FFmpeg OliverBetz.ExifTool`), or use the bootstrap script above, which bundles them.

### Option 4: Python Package
```powershell
pip install dji-drone-metadata-embedder
```

## macOS / Linux quick-start

```bash
brew install ffmpeg exiftool
sudo apt update && sudo apt install ffmpeg exiftool
pip install dji-drone-metadata-embedder
```

```bash
docker run --rm -v "$PWD":/data callmarcus/dji-embed -i *.MP4
```

<details>
<summary>Advanced</summary>

- Build from source with `uv sync --extra dev` (or `pip install -e .`)
- Use the provided `Dockerfile` for custom images
- Review CI scripts under `.github/workflows`

</details>


## Features

- **Batch Processing**: Process entire directories of DJI drone footage automatically
- **GPS Metadata Embedding**: Embed GPS coordinates as standard metadata tags
- **Subtitle Track Preservation**: Keep telemetry data as subtitle track for overlay viewing
- **Multiple Format Support**: Handles different DJI SRT telemetry formats
- **Telemetry Export**: Export flight data to JSON, GPX, CSV, GeoJSON, KML, or CoT (see [docs/geospatial.md](docs/geospatial.md))
- **Flight Map** *(experimental)*: `dji-embed flightmap DIR` draws every flight in a folder of `.SRT` logs on one combined HTML map (or KML/GeoJSON) — fast, the videos are never opened; `dji-embed convert html FLIGHT.SRT` maps a single flight with an altitude-coloured track — see [Put your flights and photos on a map](#put-your-flights-and-photos-on-a-map)
- **Photo Map**: `dji-embed photomap DIR` plots a whole folder of GPS-tagged still photos (JPG/JPEG/DNG) on a single clustered HTML map (or KML/GeoJSON) with EXIF thumbnail popups — requires ExifTool
- **Camera Footprint Polygons**: `convert geojson/kml … --footprint` adds nadir ground-footprint rectangles to GeoJSON/KML output (gimbal-aware on formats that carry attitude; suppressed under `--redact`). See [docs/geospatial.md](docs/geospatial.md).
- **CoT Export**: `dji-embed convert cot FLIGHT.SRT` writes Cursor-on-Target XML for ATAK/TAK (route + timed track). See [docs/fmv-interop.md](docs/fmv-interop.md).
- **Footage verification:** `dji-embed verify-sun clip.SRT` reports the sun's azimuth/elevation over a clip for shadow cross-checking; CSV export gains `datetime_utc` / `sun_azimuth` / `sun_elevation` columns.
- **DAT Flight Log Support**: Merge `.DAT` flight logs into metadata
- **Cross-Platform**: Works on Windows, macOS, and Linux
- **Progress Bar**: See processing status while videos are being embedded

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

## Requirements

 - Python 3.10 or higher
- FFmpeg
- ExifTool (optional, for additional metadata embedding)

## Usage

If the command `python` is not recognized, use `py` instead.

### Basic Usage

Process a single directory:
```bash
dji-embed embed /path/to/drone/footage
```

### Commands

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

### Web UI (optional)

Prefer a browser over the terminal? Install the `[ui]` extra and launch the
local UI — it runs entirely on `127.0.0.1` and uses your installed browser,
so there is no separate signed app to trust.

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

### Embed Command Options

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
  -v, --verbose              Verbose output
  -q, --quiet                Suppress progress output
```

By default, processing shows a progress bar for each file.
Use `--verbose` for detailed output or `--quiet` to reduce messages.

### Examples

Process footage with custom output directory:
```bash
dji-embed embed "D:\DroneFootage\Flight1" -o "D:\ProcessedVideos"
```

Process with ExifTool for additional metadata:
```bash
dji-embed embed "D:\DroneFootage\Flight1" --exiftool
```

Check existing metadata in files:
```bash
dji-embed check "D:\DroneFootage\Flight1"
```

Run system diagnostics:
```bash
dji-embed doctor
```

### Convert Telemetry to Other Formats

Extract GPS track to GPX:
```bash
dji-embed convert gpx DJI_0001.SRT
```

GPX timestamps are written in UTC. DJI SRT times are local with no timezone, so
the offset is auto-detected from the file's modification time. Override it when
the mtime is unreliable (e.g. copied files):
```bash
dji-embed convert gpx DJI_0001.SRT --tz-offset +05:30
```

Export telemetry to CSV:
```bash
dji-embed convert csv DJI_0001.SRT -o telemetry.csv
```

Batch convert directory to GPX:
```bash
dji-embed convert gpx /path/to/srt/files --batch
```

Batch convert directory to CSV:
```bash
dji-embed convert csv /path/to/srt/files --batch
```

### Put Your Flights and Photos on a Map

Two commands cover the "show me where this was shot" workflows:

**One flight → one HTML map.** Renders the flight path coloured by altitude,
viewable in any browser:

```bash
dji-embed convert html DJI_0001.SRT              # -> DJI_0001.html
dji-embed convert html DJI_0042.MP4              # sidecar-less models: read telemetry from the MP4
```

**A folder of flights → one combined map** *(experimental — feedback
welcome!)*. Reads only the `.SRT` telemetry sidecars (the videos are never
opened, so a whole archive scans in seconds) and draws each flight as its own
coloured track with a summary popup and a layer toggle. Recordings that DJI
split at the 4 GB file limit are automatically stitched back into one flight:

```bash
dji-embed flightmap /path/to/footage             # -> footage/flightmap.html
dji-embed flightmap /path/to/footage -r          # scan subdirectories too
dji-embed flightmap /path/to/footage -f kml      # Google Earth / My Maps instead
```

Prefer one map per clip? `dji-embed convert html /path/to/footage --batch`
writes a separate `.html` next to each video.

**A folder of still photos → one combined, clustered map** with an EXIF
thumbnail popup per pin (requires ExifTool):

```bash
dji-embed photomap /path/to/photos               # -> photos/photomap.html
dji-embed photomap /path/to/photos -f kml        # Google Earth instead
```

`photomap` scans JPG/JPEG/DNG stills; `flightmap` scans `.SRT` flight logs.
All HTML maps embed your data but load the basemap tiles from the internet, so
they need a connection to render — and they reveal your flying locations, so
share them deliberately (`flightmap --redact fuzz` coarsens tracks to ~100 m).
Details and more formats (KML, GeoJSON, CoT, camera footprints):
[docs/geospatial.md](docs/geospatial.md).

### Check Existing Metadata

You can check if your videos or photos already contain GPS or altitude
information using the check command:

```bash
dji-embed check DJI_0001.MP4
dji-embed check /path/to/footage
```

`check` uses `ffprobe` for QuickTime tags and `exiftool` for EXIF data
when available. Pass `--verbose` for debug output or `--quiet` to only
show warnings and errors.

## CLI Reference

### All Commands

#### `dji-embed embed` - Process Videos
Embed telemetry from SRT files into MP4 videos.

```bash
dji-embed embed [OPTIONS] DIRECTORY

Arguments:
  DIRECTORY                  Directory containing MP4 and SRT files

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
  --extract-home             Extract the HOME / launch point into the JSON
                             sidecar; off by default, never written to the
                             MP4, always honours --redact
  -v, --verbose              Verbose output
  -q, --quiet                Suppress progress output
```

#### `dji-embed check` - Check Metadata
Check media files for existing embedded metadata.

```bash
dji-embed check [OPTIONS] [PATHS]...

Arguments:
  PATHS...                   Files or directories to check

Options:
  -v, --verbose              Verbose output
  -q, --quiet                Suppress info output
```

#### `dji-embed convert` - Export Formats
Convert SRT telemetry to GPX, CSV, GeoJSON, KML, CoT, or a standalone HTML map.

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

**HTML map example** — produces a self-contained `flight.html` you can open in any browser:

```bash
dji-embed convert html DJI_0001.SRT              # -> DJI_0001.html
dji-embed convert html DJI_0001.SRT -o flight.html
dji-embed convert html /path/to/footage --batch  # one map per clip (not combined)
```

**CoT (Cursor-on-Target) example** — for ATAK/TAK; see [docs/fmv-interop.md](docs/fmv-interop.md):

```bash
dji-embed convert cot DJI_0001.SRT                       # -> DJI_0001.cot.xml
dji-embed convert cot DJI_0001.SRT --interval 2 --cot-type a-u-A
```

Leaflet and the basemap tiles load from the internet; the flight data itself is embedded, so the file is portable but needs a connection to render the map.

**Camera footprint example** — overlay per-interval ground-coverage polygons in GeoJSON/KML for down-looking footage (suppressed under `--redact`; see [docs/geospatial.md](docs/geospatial.md)):

```bash
dji-embed convert geojson DJI_0001.SRT --footprint --model air3
dji-embed convert kml DJI_0001.SRT --footprint --footprint-interval 5
```

#### `dji-embed flightmap` - Combined Flight Map (experimental)
Map every flight in a folder of DJI `.SRT` logs on one combined map.

> **Experimental:** `flightmap` is new and its size-split joining heuristics
> may still be tuned based on real-world feedback. If it joins flights it
> shouldn't (or misses ones it should), please
> [open an issue](https://github.com/CallMarcus/dji-drone-metadata-embedder/issues)
> with the SRT file names and timestamps.

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
  -v, --verbose                   Verbose output
  -q, --quiet                     Suppress info output
```

Reads only the `.SRT` telemetry sidecars — the videos are never opened and no
external tool is needed — so scanning a large archive is fast. Each flight
becomes its own coloured track with a popup (start time, duration, altitude
range, GPS points) and a layer toggle; the KML imports into Google Earth and
Google My Maps as one line per flight. SRT files without GPS telemetry
(e.g. ordinary subtitles) are skipped and counted in a summary; `-v` lists them.

```bash
dji-embed flightmap /path/to/footage                        # -> footage/flightmap.html
dji-embed flightmap /path/to/footage -f all                 # -> footage/flightmap.{html,kml,geojson}
dji-embed flightmap /path/to/footage -r --title "Road trip" # recurse + custom title
```

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

#### `dji-embed photomap` - Map Still Photos
Map GPS-tagged still photos (JPG/JPEG/DNG) as an HTML, KML, or GeoJSON map.

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
  -v, --verbose                   Verbose output
  -q, --quiet                     Suppress info output
```

Requires ExifTool (`dji-embed doctor` checks it). Photos without GPS data are
skipped and counted in a summary; `-v` lists the skipped filenames.

Notes:
- With `-r`, pins are labelled by their path relative to `DIRECTORY`, so
  per-session folders that reuse DJI's restarting `DJI_0001.JPG` names stay
  distinct on the map.
- Popup previews use the small EXIF thumbnail, falling back to a size-capped
  embedded preview for DNGs that carry no thumbnail.
- Photos with no EXIF altitude are clamped to the ground in KML (Google Earth)
  instead of being buried at 0 m below terrain.
- `--link-originals` makes each popup's thumbnail and filename a click-through
  to the full-resolution original (HTML output only). The links are plain
  relative hrefs, so they resolve while the HTML sits next to the photos and
  break if the map is moved or emailed without them — the popup always names
  the file regardless. Use `--link-base` when the originals live elsewhere
  (a relative folder like `../DCIM`, or an absolute URL). Browsers download
  rather than display DNG files; JPGs open in a new tab.

```bash
dji-embed photomap /path/to/photos                                    # -> photos/photomap.html
dji-embed photomap /path/to/photos -f all                             # -> photos/photomap.{html,kml,geojson}
dji-embed photomap /path/to/photos -r --title "Churches of Finland"   # recurse + custom title
dji-embed photomap /path/to/photos --link-originals                   # popups open the original photos
dji-embed photomap /path/to/photos --link-originals --link-base ../DCIM   # originals live elsewhere
```

Leaflet and the OpenStreetMap basemap tiles load from the internet; the photo
thumbnails themselves are embedded, so the HTML file is portable but needs a
connection to render the map. A photo map publishes your shooting locations —
share it deliberately.

#### `dji-embed doctor` - System Diagnostics
Show system information and verify all dependencies.

```bash
dji-embed doctor

No arguments or options required.
```

`dji-embed doctor --install exiftool` downloads a pinned, checksum-verified
ExifTool into your user directory — useful where system packages are too old
for MP4 timed metadata (most Linux distros).

#### `dji-embed wizard` - Interactive Setup
Launch interactive setup wizard (under development).

```bash
dji-embed wizard

No arguments or options required.
```

## Output

The tool creates a `processed` subdirectory containing:

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

## SRT Format Support

The tool supports multiple DJI SRT formats:

### Format 1 (DJI Mini 3 Pro):
```
[latitude: 59.302335] [longitude: 18.203059] [rel_alt: 1.300 abs_alt: 132.860]
```

### Format 2 (Older models):
```
GPS(59.302335,18.203059,132.860)
```

## Use Cases

- **Photo Management**: Videos become searchable by location in Windows Photos, Google Photos, etc.
- **Video Editing**: Telemetry subtitle track can be used for overlay effects
- **Flight Analysis**: Export GPX tracks for Google Earth visualization
- **Archival**: Preserve all flight data within the video file itself

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
