# DJI Drone Metadata Embedder

[![Winget]][winget]
[![GitHub Release]][release]
[![PyPI]][pypi]

A Python tool to embed telemetry data from DJI drone SRT files into MP4 video files.
This tool extracts GPS coordinates, altitude, camera settings and other telemetry data from SRT files and embeds
them as metadata in the corresponding video files.

> **Note**
> 
> The core functionality should work for embedding telemetry from DJI drones,
> but the tool is still undergoing active testing and refinement. Expect
> breaking changes and incomplete features as stability issues are addressed.

See the [Development Roadmap](docs/development_roadmap.md) for plans to expand this CLI tool into a Windows
application with a graphical interface.
For detailed setup instructions and a quick-start tutorial, see
[docs/installation.md](docs/installation.md) and [docs/user_guide.md](docs/user_guide.md).
Common problems are covered in [docs/troubleshooting.md](docs/troubleshooting.md).
Answers to frequently asked questions can be found in the [FAQ](docs/faq.md).

## Easy Windows install

```powershell
iwr -useb https://raw.githubusercontent.com/CallMarcus/dji-drone-metadata-embedder/master/tools/bootstrap.ps1 | iex
```

```powershell
winget install -e --id CallMarcus.DJI-Embed
```

If winget reports **"No package found"**, the package is still pending publication. Use the PowerShell one-liner above instead.

You can also download a ready-to-run **dji-embed.exe** from the [GitHub Releases page](https://github.com/CallMarcus/dji-drone-metadata-embedder/releases) if `winget` is unavailable.

### Windows – manual path

```powershell
winget install -e --id Python.Python.3
winget install -e --id Gyan.FFmpeg
winget install -e --id PhilHarvey.ExifTool
pip install dji-metadata-embedder
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

- Build from source with `pip install -r requirements.txt`
- Use the provided `Dockerfile` for custom images
- Review CI scripts under `.github/workflows`

</details>


## Features

- **Batch Processing**: Process entire directories of DJI drone footage automatically
- **GPS Metadata Embedding**: Embed GPS coordinates as standard metadata tags
- **Subtitle Track Preservation**: Keep telemetry data as subtitle track for overlay viewing
- **Multiple Format Support**: Handles different DJI SRT telemetry formats
- **Telemetry Export**: Export flight data to JSON, GPX, or CSV formats
- **DAT Flight Log Support**: Merge `.DAT` flight logs into metadata
- **Cross-Platform**: Works on Windows, macOS, and Linux
- **Progress Bar**: See processing status while videos are being embedded

## Supported DJI Models

The tool has been tested with:
- DJI Mini 3 Pro
- DJI Mini 4 Pro
- DJI Mavic 3
- DJI Air 2S
- Other models using similar SRT formats

## Requirements

- Python 3.6 or higher
- FFmpeg
- ExifTool (optional, for additional metadata embedding)

## Usage

If the command `python` is not recognized, use `py` instead.

### Basic Usage

Process a single directory:
```bash
dji-embed /path/to/drone/footage
```

### Options

```bash
dji-embed [OPTIONS] [DIRECTORY]

Arguments:
  DIRECTORY          Directory containing MP4 and SRT files

Options:
  -o, --output      Output directory (default: ./processed)
  --exiftool        Also use ExifTool for GPS metadata
  --check           Only check dependencies
  --doctor          Show system information and dependency status
  --dat FILE        Merge specified DAT flight log
  --dat-auto        Auto-detect DAT logs matching videos
  --redact MODE     Redact GPS data (none, drop, fuzz)
  --verbose         Show detailed progress
  --quiet           Suppress progress bar and most output
```

By default, processing shows a progress bar for each file.
Use `--verbose` for detailed output or `--quiet` to reduce messages.
The `--doctor` option does not require a directory argument.

### Examples

Process footage with custom output directory:
```bash
dji-embed "D:\DroneFootage\Flight1" -o "D:\ProcessedVideos"
```

Process with ExifTool for additional metadata:
```bash
dji-embed "D:\DroneFootage\Flight1" --exiftool
```

Check dependencies:
```bash
dji-embed --check "D:\DroneFootage"
```

Run the environment doctor:
```bash
dji-embed --doctor
```

### Convert Telemetry to Other Formats

Extract GPS track to GPX:
```bash
python -m dji_metadata_embedder.telemetry_converter gpx DJI_0001.SRT
```

Export telemetry to CSV:
```bash
python -m dji_metadata_embedder.telemetry_converter csv DJI_0001.SRT -o telemetry.csv
```

Batch convert directory to GPX:
```bash
python -m dji_metadata_embedder.telemetry_converter gpx /path/to/srt/files --batch
```

Batch convert directory to CSV:
```bash
python -m dji_metadata_embedder.telemetry_converter csv /path/to/srt/files --batch
```

### Check Existing Metadata

You can check if your videos or photos already contain GPS or altitude
information using the metadata checker script:

```bash
python -m dji_metadata_embedder.metadata_check DJI_0001.MP4
python -m dji_metadata_embedder.metadata_check /path/to/footage
```

See [docs/METADATA_CHECKER.md](docs/METADATA_CHECKER.md) for details.

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

See [docs/troubleshooting.md](docs/troubleshooting.md) for additional tips.
### "Python was not found"
Use `py` instead of `python`:
```bash
dji-embed /path/to/footage
```

### "ffmpeg is not recognized"
Ensure FFmpeg is in your PATH. Test with:
```bash
ffmpeg -version
```
`ffmpeg` uses a single dash here. Typing `ffmpeg --version` will result in `Unrecognized option '--version'`.

### No GPS data in JSON
Check that your SRT files contain GPS coordinates. Open an SRT file to verify the format.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

### Adding Support for New Models

If your DJI model uses a different SRT format:
1. Open an issue with a sample SRT file
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

[Winget]: https://img.shields.io/badge/winget-CallMarcus.DJI--Embed-blue?logo=windows
[winget]: https://winget.run/pkg/CallMarcus/DJI-Embed
[GitHub Release]: https://img.shields.io/github/v/release/CallMarcus/dji-drone-metadata-embedder?logo=github
[release]: https://github.com/CallMarcus/dji-drone-metadata-embedder/releases
[PyPI]: https://img.shields.io/pypi/v/dji-drone-metadata-embedder?logo=pypi
[pypi]: https://pypi.org/project/dji-drone-metadata-embedder/
