# DJI Drone Metadata Embedder

[![GitHub Release](https://img.shields.io/github/v/release/CallMarcus/dji-drone-metadata-embedder?logo=github)](https://github.com/CallMarcus/dji-drone-metadata-embedder/releases)
[![Version](https://img.shields.io/badge/version-2.18.0-blue)](https://github.com/CallMarcus/dji-drone-metadata-embedder/releases)
[![PyPI](https://img.shields.io/pypi/v/dji-drone-metadata-embedder?logo=pypi)](https://pypi.org/project/dji-drone-metadata-embedder/)
[![Winget](https://img.shields.io/winget/v/CallMarcus.DJIMetadataEmbedder?logo=windows&label=winget)](https://github.com/microsoft/winget-pkgs/tree/master/manifests/c/CallMarcus/DJIMetadataEmbedder)

A free tool that puts your DJI drone footage on the map. It reads the
telemetry your drone records with every flight (GPS position, altitude,
camera settings) and turns it into interactive maps, GPS files, and location
data embedded in the videos themselves. Everything runs on your own computer;
nothing is uploaded.

<p align="center">
  <img src="https://raw.githubusercontent.com/CallMarcus/dji-drone-metadata-embedder/master/docs/assets/gui/workspace-home.png" alt="The DJI Metadata Embedder workspace" width="49%" />
  <img src="https://raw.githubusercontent.com/CallMarcus/dji-drone-metadata-embedder/master/docs/assets/gui/workspace-preview.png" alt="Inline map preview" width="49%" />
</p>

## What can it do?

- **See every flight on one map**, each as its own coloured track. Switch to
  3D to fly it back over real terrain and see what the camera was looking at.
- **See where every photo was taken**, thumbnails included. 360° panoramas
  open in an interactive viewer.
- **Make videos searchable by location** in Windows Photos, Google Photos
  and similar apps. No re-encoding, no quality loss.
- **Cut faster** with a DaVinci Resolve timeline that has the steady shots,
  reveals and climbs already marked.
- **Keep a flight logbook** with official airspace zones for the countries
  covered so far.
- **Export tracks** for Google Earth, spreadsheets, and GIS tools.
- **Keep locations private** when you share: any output can be coarsened to
  about 100 m.

## Get started

### Desktop app (Windows and macOS)

Download it from the
[latest release](https://github.com/CallMarcus/dji-drone-metadata-embedder/releases/latest):
drop in a folder, pick what you want, and the map opens right in the app.

- **Windows:** run `dji-metadata-embedder-setup-<version>.exe`. FFmpeg and
  ExifTool come bundled, and no admin rights are needed.
- **macOS** (Apple Silicon, macOS 14 or later): open the `.dmg`, drag the app
  to Applications, then run `brew install ffmpeg exiftool`. The app's Setup
  screen confirms it found them.

Both include the full `dji-embed` command line too.

### Command line only

You'll need Python 3.10+ and FFmpeg; ExifTool is optional but unlocks photo
maps and newer drones.

```bash
pip install dji-drone-metadata-embedder   # Windows, Linux
pipx install dji-drone-metadata-embedder  # macOS (after: brew install ffmpeg exiftool pipx)
```

winget, a one-line PowerShell installer, Intel Macs, Docker, and how to
verify your download are all in the
[installation guide](https://callmarcus.github.io/dji-drone-metadata-embedder/installation/).

### Your first map

```bash
dji-embed doctor                        # 1. confirm everything is installed
dji-embed flightmap /path/to/footage    # 2. all flights in a folder -> flightmap.html
dji-embed photomap /path/to/photos      # 3. all photos in a folder  -> photomap.html
```

Open the `.html` file in any browser. The maps carry your data inside them
but load the background map from the internet, so they need a connection
to display.

No terminal at all? On Windows, drag your footage folder onto
`dji-embed.exe`: it maps every flight and geotagged photo in the folder and
opens the result in your browser.

> **Privacy note:** maps and exports reveal where you fly. Share them
> deliberately, or add `--redact fuzz` to coarsen every position to ~100 m.

## Which command do I need?

| I want to… | Run |
|---|---|
| See all my flights on one map | `dji-embed flightmap /path/to/footage` |
| See my photos on a map | `dji-embed photomap /path/to/photos` |
| Map a mixed folder (photos + flights) | `dji-embed map /path/to/folder` |
| See official drone zones along my flights | `dji-embed flightmap /path/to/footage --airspace` |
| Map one flight in detail | `dji-embed convert html DJI_0001.SRT` |
| Make videos searchable by location | `dji-embed embed /path/to/footage` |
| Get a GPX track for Google Earth | `dji-embed convert gpx DJI_0001.SRT` |
| Open a flight in DaVinci Resolve with the good bits marked | `dji-embed timeline /path/to/footage` |
| See what metadata a file already has | `dji-embed check DJI_0001.MP4` |
| Check my setup | `dji-embed doctor` |

Every option for every command is in the
[command reference](https://callmarcus.github.io/dji-drone-metadata-embedder/cli-reference/),
or at the terminal via `dji-embed COMMAND --help`.

## Supported drones

Tested with sample footage: Mini 3 Pro, Mini 4 Pro, Mini 5 Pro, Air 3,
Air 3S, Mavic 4 Pro, Mavic 3 Enterprise, Avata 2, Avata 360, Neo 2,
Matrice 300 and Phantom 4 RTK. The Air 2S, Mavic 3 and other models with
similar telemetry work too, and the Parrot Anafi works for maps and exports.
Newer drones that store telemetry inside the video need a recent ExifTool;
`dji-embed doctor` tells you if yours is too old. Format details are in
[SRT formats](https://callmarcus.github.io/dji-drone-metadata-embedder/SRT_FORMATS/).

**Don't see your model?**
[Open an issue](https://github.com/CallMarcus/dji-drone-metadata-embedder/issues/new)
and attach one or two raw `.SRT` files from your drone (a short clip is
plenty), and we'll add support for it.

## Learn more

- [Desktop app guide](https://callmarcus.github.io/dji-drone-metadata-embedder/desktop-app/)
- [User guide](https://callmarcus.github.io/dji-drone-metadata-embedder/user_guide/) and
  [recipes](https://callmarcus.github.io/dji-drone-metadata-embedder/recipes/) for end-to-end examples
- [Maps & panoramas](https://callmarcus.github.io/dji-drone-metadata-embedder/geospatial/),
  including the 3D view and airspace overlays
- [Troubleshooting](https://callmarcus.github.io/dji-drone-metadata-embedder/troubleshooting/)
  if something fails

**Asking an AI assistant for help?** Upload
[`HELP.md`](https://github.com/CallMarcus/dji-drone-metadata-embedder/blob/master/HELP.md)
to Claude, ChatGPT, Copilot or similar first. It gives the assistant accurate,
current facts about this tool, so you can ask in your own words.

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

## Contributing

Contributions are welcome: see the
[contributing guide](https://github.com/CallMarcus/dji-drone-metadata-embedder/blob/master/CONTRIBUTING.md).
Working with an AI coding agent? Point it at
[`AGENTS.md`](https://github.com/CallMarcus/dji-drone-metadata-embedder/blob/master/AGENTS.md).

## License

MIT License. See [LICENSE](https://github.com/CallMarcus/dji-drone-metadata-embedder/blob/master/LICENSE).

## Acknowledgments

- Thanks to the DJI drone community for format documentation
- DJI Stockholm (Grev Turegatan) for flying and sharing the Mavic 4 Pro sample
  footage that confirmed the format and located its gimbal telemetry
- FFmpeg and ExifTool teams for their excellent tools

## Disclaimer

This tool is not affiliated with or endorsed by DJI. Use at your own risk.
