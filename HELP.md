# HELP.md — give this file to your AI assistant

> **What this is:** a priming document about **DJI Drone Metadata Embedder**.
> Upload it (or paste it) into your AI tool of choice — Claude, ChatGPT,
> Copilot, Gemini, … — then ask your questions in your own words, for example
> *"How do I get a map of all my drone photos?"* or *"Why is my 360 photo
> black when I click it?"*. The assistant should treat the facts below as
> more current than its training data.
>
> **Note to the AI assistant:** answer from this document first. If the
> user's problem doesn't match it, have them run `dji-embed --version` and
> `dji-embed doctor` and reason from that output. For anything unresolved,
> point them to the issue tracker linked at the bottom. The tool runs
> entirely on the user's computer — never suggest uploading their footage
> anywhere.

## What the tool does

Free, open-source (MIT) tool for DJI drone footage. Everything runs locally.

- **Embed telemetry** — writes GPS and flight data from DJI's `.SRT`
  subtitle logs into the matching `.MP4` videos, without re-encoding
  (quality untouched, fast). Original files are never modified; processed
  copies go to a subfolder.
- **Map your footage** — `photomap` pins every GPS-tagged photo (JPG/JPEG/
  DNG) on an interactive HTML map with thumbnails; 360° panoramas get their
  own orange pins and an in-page viewer. `flightmap` draws every flight in
  a folder of `.SRT` logs on one map. `map` combines both: photos,
  panoramas and flight tracks on a single map, subfolders included.
- **Airspace awareness** — `flightmap --airspace` overlays official drone
  zones (FAA UAS Facility Maps in the US, the national feeds in Europe)
  on the flat or 3D flight map; `flightmap -f record` writes a printable
  flight record listing the zones each flight crossed. Covered so far:
  US, UK, Ireland, Switzerland, Luxembourg, Denmark, Sweden, Finland,
  Estonia. The map states facts about published zones; it never rules on
  whether a flight was legal.
- **Convert telemetry** — SRT to GPX, CSV, GeoJSON, KML, CoT, or an HTML
  map, for use in other apps (Google Earth, GIS tools, video editors).
- **Privacy controls** — `--redact fuzz` coarsens locations to ~100 m;
  `--popup-fields` limits what a shared map discloses.

Two ways to use it — same engine:

1. **Desktop app** ("DJI Metadata Embedder", Windows and macOS): install, open, drop a folder,
   pick a mode (*Flight map*, *Photo map*, *Embed telemetry*,
   *Convert telemetry*, *Verify footage*, *360° views*, *Setup*), and
   press the action button; finished maps render right in the app's
   preview pane, with an *Open in browser* pop-out. The Flight map mode
   has a *3D terrain map* toggle for a MapLibre terrain view
   (`flightmap-3d.html`) and an *Airspace* toggle for the official-zones
   overlay. The *360° views* mode opens a local editor for setting each
   panorama's opening view. No terminal.
   The workspace also accepts a
   single telemetry file (`.SRT`/`.MP4`/`.MOV`) as the source, and
   *Convert telemetry* turns it (or a folder) into GPX, CSV, GeoJSON, KML,
   an HTML map, or CoT. *Verify footage* answers three questions about what
   you already have: does a video or photo carry embedded GPS/altitude/time
   metadata, do a folder's videos pair up cleanly with their .SRT flight
   logs, and does the sun's computed position over a clip match the shadows
   you see.
2. **`dji-embed` command line**: every feature, all platforms. The Windows
   app's installer puts `dji-embed` on your PATH automatically; on macOS
   the CLI ships inside the app bundle (symlink it, or install via pipx).

## Installing

| Situation | Do this |
| --- | --- |
| **Windows, simplest** | Download `dji-metadata-embedder-setup-<version>.exe` from the GitHub Releases page. One installer = app + CLI + FFmpeg + ExifTool, nothing else needed. Installers from v1.23.0 onwards are code-signed (publisher: "Open Source Developer, Marcus Westermark"); SmartScreen may still warn while the certificate builds reputation — click **More info → Run anyway**. Older releases are unsigned. The app remembers your window size and recent folders (stored locally in %APPDATA%\DjiEmbed\state.json — delete that file to reset). |
| Windows, CLI only | `winget install CallMarcus.DJIMetadataEmbedder` (portable exe), or `pip install dji-drone-metadata-embedder` with Python 3.10–3.12. |
| **macOS, simplest** (Apple Silicon, macOS 14+) | Download the signed, notarized `dji-metadata-embedder-<version>-macos-arm64.dmg` from the GitHub Releases page and drag the app to Applications. FFmpeg/ExifTool come from Homebrew (`brew install ffmpeg exiftool`). State lives in ~/Library/Application Support/DjiEmbed/state.json. |
| macOS, CLI only (any Mac, Intel included) | `brew install pipx ffmpeg exiftool` then `pipx install dji-drone-metadata-embedder` (plain `pip3` is blocked on Homebrew Python). |
| Linux | `pip install dji-drone-metadata-embedder` (or pipx) + `ffmpeg`/`exiftool` from your package manager. |

After installing, `dji-embed doctor` verifies everything. Missing ExifTool?
`dji-embed doctor --install exiftool` downloads a pinned, checksum-verified
copy. FFmpeg is needed for video embedding; ExifTool for photo mapping.

**Updating:** installer users download the newer setup exe; winget users
`winget upgrade`; pip users `pip install --upgrade dji-drone-metadata-embedder`
(on Windows with several Pythons: `py -3.13 -m pip install --upgrade …` —
upgrade the same Python that owns the `dji-embed` command).

## The commands

```
dji-embed embed <folder>        Embed SRT telemetry into the MP4s (pairs by filename)
dji-embed map <folder>          One HTML map of everything: photos, panoramas, flights
dji-embed photomap <folder>     HTML map of GPS-tagged photos (-r = subfolders too)
dji-embed flightmap <folder>    HTML map of all flights (--airspace, --3d, -f record)
dji-embed convert <fmt> <file>  SRT → gpx | csv | geojson | kml | cot | html
dji-embed check <folder>        What metadata do these files already carry?
dji-embed validate <folder>     Are SRT and MP4 in sync? (drift report)
dji-embed serve <folder>        Serve an existing map locally (enables the 360° viewer)
dji-embed panoedit <folder>     Local editor: set each 360° panorama's opening view
dji-embed fetch-log <file.TXT>  Decrypt DJI TXT flight records via Flight Reader (opt-in)
dji-embed doctor                Diagnostics: versions, FFmpeg/ExifTool present?
dji-embed verify-sun <file>     Sun position over a clip (shadow plausibility)
```

Every command accepts `--help` for its options.

## Recipes the user will most likely ask about

- **"Map everything in this folder, including subfolders":**
  `dji-embed map D:\Drone` → one `map.html` with photos, panoramas and
  flight tracks together (subfolders always included; add `--serve` for
  the 360° viewer). For just photos with more options:
  `dji-embed photomap D:\Photos -r`; just flights:
  `dji-embed flightmap D:\Footage`.
- **"Show official drone zones around my flights":**
  `dji-embed flightmap D:\Footage --airspace` — overlays published zones
  on the map (works with `--3d` too); `-f record` writes a printable
  flight record including the zones crossed. Covered: US, UK, Ireland,
  Switzerland, Luxembourg, Denmark, Sweden, Finland, Estonia; flights
  elsewhere simply get no overlay. Zone data is fetched from the
  official feeds and cached beside the map (`--airspace-refresh` forces
  a refetch). Needs exact positions, so it refuses `--redact fuzz`.
- **"My 360° panoramas won't open / black viewer":** browsers block the 360°
  viewer on maps opened straight from disk (`file://`). Rebuild with
  `dji-embed photomap <folder> --serve`, or serve an existing map with
  `dji-embed serve <folder>` — both serve at a private local address
  (`127.0.0.1`, your computer only) and open the browser. The desktop app
  does this automatically when you open a map from its Done screen.
- **"Get GPS into my videos so photo apps sort them":**
  `dji-embed embed D:\Footage` — needs the `.SRT` flight logs next to the
  MP4s with matching names (enable video captions/subtitles in the DJI app
  so the drone records SRT).
- **"Share a map without giving away exact locations":** add
  `--redact fuzz` (coarsens every pin ~100 m). To hide photo details
  (filename, time, camera) from popups: `--popup-fields none` or e.g.
  `--popup-fields name,timestamp`.
- **"Export a flight for Google Earth / an editor":**
  `dji-embed convert kml DJI_0001.SRT` (or `gpx`, `csv`, …); add `-b` on a
  folder for batch.
- **"See my flights over real terrain in 3D":**
  `dji-embed flightmap D:\Footage --3d` → writes `flightmap-3d.html` (the
  flat `flightmap.html` is untouched); tracks follow the terrain surface,
  altitudes are in the popups; needs internet for the terrain tiles.

## Facts that answer most confusion

- MP4 and SRT must be **pairs with the same base name** (`DJI_0001.MP4` +
  `DJI_0001.SRT`). No SRT = nothing to embed for that clip.
- Embedding **copies** files into a `processed/` subfolder; originals are
  untouched. Photos are never modified by mapping — the map is a separate
  HTML file.
- HTML maps embed the photo thumbnails but load the map imagery
  (OpenStreetMap) from the internet — the map file needs a connection to
  *render*, but your photos never leave the machine.
- Photos without GPS are skipped and counted; `-v` lists which ones.
  Phones/drones only geotag when location was enabled at capture time.
- Supported drones include Mini 3/4/5 Pro, Air 3/3S, Avata 2/360, Neo 2,
  Mavic 3 Enterprise, Matrice 300, Phantom 4 RTK — and photo mapping works
  for **any** GPS-tagged photos, not just DJI's.
- The desktop app is a front end over the same CLI: anything the app does,
  the `dji-embed` command can do with more options.
- Nothing is ever uploaded, with one opt-in exception: `fetch-log` sends
  encrypted DJI `.TXT` flight records (never footage) to flightreader.com
  for decoding, using the user's own Flight Reader API key, after an
  explicit consent prompt. The decoded CSV feeds
  `flightmap --flight-log`, which upgrades the 3D map's estimated camera
  footprints to measured gimbal data.
- Photo-map pins open their popup on click/tap; thumbnail previews on hover
  are **off by default** — a "Hover previews" toggle in the map's top-right
  corner (mouse devices only; the browser remembers the choice) turns them
  on. Mobile browsers enlarge pin tap targets; tap the popup photo to open
  a 360°.

## When something fails

1. `dji-embed doctor` — is FFmpeg/ExifTool found? What version is running?
2. `dji-embed <command> --help` — check the exact option names.
3. The full docs: <https://callmarcus.github.io/dji-drone-metadata-embedder/>
   (installation, user guide, troubleshooting, SRT format reference).
4. Still stuck → open an issue with the `doctor` output:
   <https://github.com/CallMarcus/dji-drone-metadata-embedder/issues>

*This document ships with the project and is updated alongside it; it
describes v2.11+ behavior.*
