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
  a folder of `.SRT` logs on one map.
- **Convert telemetry** — SRT to GPX, CSV, GeoJSON, KML, CoT, or an HTML
  map, for use in other apps (Google Earth, GIS tools, video editors).
- **Privacy controls** — `--redact fuzz` coarsens locations to ~100 m;
  `--popup-fields` limits what a shared map discloses.

Two ways to use it — same engine:

1. **Windows app** ("DJI Metadata Embedder"): install, open, pick a folder,
   click *Make a map*, *Embed telemetry*, or *Check my setup*. No terminal.
2. **`dji-embed` command line**: every feature, all platforms. The Windows
   app's installer puts `dji-embed` on your PATH automatically.

## Installing

| Situation | Do this |
| --- | --- |
| **Windows, simplest** | Download `dji-metadata-embedder-setup-<version>.exe` from the GitHub Releases page. One installer = app + CLI + FFmpeg + ExifTool, nothing else needed. Windows shows an "Unknown publisher" SmartScreen warning (the project is unsigned so far): click **More info → Run anyway**. |
| Windows, CLI only | `winget install CallMarcus.DJIMetadataEmbedder` (portable exe), or `pip install dji-drone-metadata-embedder` with Python 3.10–3.12. |
| macOS | `brew install pipx ffmpeg exiftool` then `pipx install dji-drone-metadata-embedder` (plain `pip3` is blocked on Homebrew Python). |
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
dji-embed photomap <folder>     HTML map of GPS-tagged photos (-r = subfolders too)
dji-embed flightmap <folder>    HTML map of all flights from the .SRT logs
dji-embed convert <fmt> <file>  SRT → gpx | csv | geojson | kml | cot | html
dji-embed check <folder>        What metadata do these files already carry?
dji-embed validate <folder>     Are SRT and MP4 in sync? (drift report)
dji-embed doctor                Diagnostics: versions, FFmpeg/ExifTool present?
dji-embed verify-sun <file>     Sun position over a clip (shadow plausibility)
```

Every command accepts `--help` for its options.

## Recipes the user will most likely ask about

- **"Map everything in this folder, including subfolders":**
  `dji-embed photomap D:\Photos -r` → writes `photomap.html` into the
  folder; open it in a browser. Videos' flights: `dji-embed flightmap D:\Footage`.
- **"My 360° panoramas won't open / black viewer":** browsers block the 360°
  viewer on maps opened straight from disk (`file://`). Rebuild with
  `dji-embed photomap <folder> --serve` — it serves the map at a private
  local address (`127.0.0.1`, your computer only) and opens the browser.
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
- The Windows app is a front end over the same CLI: anything the app does,
  the `dji-embed` command can do with more options.
- On mobile browsers the map skips hover previews and enlarges pin tap
  targets; tap a pin to open its popup, tap the popup photo to open a 360°.

## When something fails

1. `dji-embed doctor` — is FFmpeg/ExifTool found? What version is running?
2. `dji-embed <command> --help` — check the exact option names.
3. The full docs: <https://callmarcus.github.io/dji-drone-metadata-embedder/>
   (installation, user guide, troubleshooting, SRT format reference).
4. Still stuck → open an issue with the `doctor` output:
   <https://github.com/CallMarcus/dji-drone-metadata-embedder/issues>

*This document ships with the project and is updated alongside it; it
describes v1.21+ behavior.*
