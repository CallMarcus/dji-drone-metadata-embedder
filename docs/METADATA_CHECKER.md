# Metadata Presence Checker

This script checks whether GPS location, altitude and creation time metadata
already exist in DJI video or photo files. It uses `ffprobe` for QuickTime tags
and `exiftool` for EXIF data when available.

## Usage

```bash
python src/metadata_check.py FILE [FILE ...]
python src/metadata_check.py DIRECTORY
```

You can provide one or more files or directories. When a directory is given all
common DJI media types (`*.MP4`, `*.MOV`, `*.JPG`) are scanned.

The script prints a line for each file indicating whether the metadata was
found. Example output:

```
DJI_0001.MP4: GPS, altitude, creation_time
DJI_0002.JPG: no GPS, no altitude, creation_time
```

`ffprobe` must be installed. `exiftool` is optional but allows detecting EXIF
GPS tags in JPG files.
