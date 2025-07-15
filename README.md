# DJI Drone Metadata Embedder

A Python tool to embed telemetry data from DJI drone SRT files into MP4 video files. This tool extracts GPS coordinates, altitude, camera settings, and other telemetry data from SRT files and embeds them as metadata in the corresponding video files.

## Features

- **Batch Processing**: Process entire directories of DJI drone footage automatically
- **GPS Metadata Embedding**: Embed GPS coordinates as standard metadata tags
- **Subtitle Track Preservation**: Keep telemetry data as subtitle track for overlay viewing
- **Multiple Format Support**: Handles different DJI SRT telemetry formats
- **Telemetry Export**: Export flight data to JSON, GPX, or CSV formats
- **Cross-Platform**: Works on Windows, macOS, and Linux

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

## Installation

### 1. Install Python Dependencies

No external Python packages required - uses only standard library!

### 2. Install FFmpeg

#### Windows:
1. Download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) (get the "full" build)
2. Extract to `C:\ffmpeg`
3. Add `C:\ffmpeg\bin` to your PATH:
   ```cmd
   setx /M PATH "%PATH%;C:\ffmpeg\bin"
   ```

#### macOS:
```bash
brew install ffmpeg
```

#### Linux:
```bash
sudo apt update
sudo apt install ffmpeg
```

### 3. Install ExifTool (Optional)

#### Windows:
1. Download from [exiftool.org](https://exiftool.org/)
2. Rename `exiftool(-k).exe` to `exiftool.exe`
3. Place in `C:\exiftool` and add to PATH

> **What does "add to PATH" mean?**
> The `PATH` environment variable tells Windows where to find executable
> programs. Adding a folder such as `C:\ffmpeg\bin` or `C:\exiftool` lets you
> run `ffmpeg` or `exiftool` from any command prompt. You can modify `PATH`
> through *System Properties → Environment Variables* or by running the `setx`
> command shown above.

#### macOS:
```bash
brew install exiftool
```

#### Linux:
```bash
sudo apt install libimage-exiftool-perl
```

## Usage

If the command `python` is not recognized, use `py` instead.

### Basic Usage

Process a single directory:
```bash
python src/dji_metadata_embedder.py /path/to/drone/footage
```

### Options

```bash
python src/dji_metadata_embedder.py [OPTIONS] DIRECTORY

Arguments:
  DIRECTORY          Directory containing MP4 and SRT files

Options:
  -o, --output      Output directory (default: ./processed)
  --exiftool        Also use ExifTool for GPS metadata
  --check           Only check dependencies
```

### Examples

Process footage with custom output directory:
```bash
python src/dji_metadata_embedder.py "D:\DroneFootage\Flight1" -o "D:\ProcessedVideos"
```

Process with ExifTool for additional metadata:
```bash
python src/dji_metadata_embedder.py "D:\DroneFootage\Flight1" --exiftool
```

Check dependencies:
```bash
python src/dji_metadata_embedder.py --check "D:\DroneFootage"
```

### Convert Telemetry to Other Formats

Extract GPS track to GPX:
```bash
python src/telemetry_converter.py gpx DJI_0001.SRT
```

Export telemetry to CSV:
```bash
python src/telemetry_converter.py csv DJI_0001.SRT -o telemetry.csv
```

Batch convert directory to GPX:
```bash
python src/telemetry_converter.py gpx /path/to/srt/files --batch
```

Batch convert directory to CSV:
```bash
python src/telemetry_converter.py csv /path/to/srt/files --batch
```

### Check Existing Metadata

You can check if your videos or photos already contain GPS or altitude
information using the metadata checker script:

```bash
python src/metadata_check.py DJI_0001.MP4
python src/metadata_check.py /path/to/footage
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

### "Python was not found"
Use `py` instead of `python`:
```bash
py src/dji_metadata_embedder.py /path/to/footage
```

### "ffmpeg is not recognized"
Ensure FFmpeg is in your PATH. Test with:
```bash
ffmpeg -version
```

### No GPS data in JSON
Check that your SRT files contain GPS coordinates. Open an SRT file to verify the format.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

### Adding Support for New Models

If your DJI model uses a different SRT format:
1. Open an issue with a sample SRT file
2. Or submit a PR with regex patterns for the new format

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
