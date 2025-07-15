# Metadata Presence Checker

This script checks whether GPS location, altitude and creation time metadata
already exist in DJI video or photo files. It uses `ffprobe` for QuickTime tags
and `exiftool` for EXIF data when available.

## Usage

```bash
python -m dji_metadata_embedder.metadata_check FILE [FILE ...]
python -m dji_metadata_embedder.metadata_check DIRECTORY
```
If the command `python` is not recognized, use `py` instead.


You can provide one or more files or directories. When a directory is given all
common DJI media types (`*.MP4`, `*.MOV`, `*.JPG`) are scanned.

The script logs a line for each file indicating whether the metadata was
found. Output is written using Python's ``logging`` module. By default the
tool logs at ``INFO`` level. Use ``--verbose`` to see debug messages or
``--quiet`` to only show warnings and errors. Example output:

```
INFO:dji_metadata_embedder.metadata_check:DJI_0001.MP4: GPS, altitude, creation_time
INFO:dji_metadata_embedder.metadata_check:DJI_0002.JPG: no GPS, no altitude, creation_time
```

### Logging Options

* ``--verbose``: Show debug output.
* ``--quiet``: Only log warnings and errors.

`ffprobe` must be installed. `exiftool` is optional but allows detecting EXIF
GPS tags in JPG files.
