# User Guide

This guide shows the basics of processing DJI footage with `dji-embed`.

## Quick start

Process a directory of videos and matching SRT files:

```bash
dji-embed /path/to/footage
```

A `processed` folder will be created containing new videos with embedded metadata and telemetry summary files.

## Common options

- `-o DIR` – choose an output directory
- `--exiftool` – also write metadata via ExifTool (requires ExifTool)
- `--dat FILE` – merge a DAT flight log with the video

Run `dji-embed --help` to see all available options.

## Converting telemetry

The package also includes a converter for GPX or CSV output:

```bash
python -m dji_metadata_embedder.telemetry_converter gpx DJI_0001.SRT
```

Use `csv` instead of `gpx` to create a CSV file.

For detailed how-to guides such as creating Windows bundles or redacting location data, see the files in `docs/how-to`.
