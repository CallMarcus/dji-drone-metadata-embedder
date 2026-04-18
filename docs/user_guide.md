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

## Web UI

If you'd rather click buttons than type commands, install the `[ui]` extra
and launch the browser-based UI:

```bash
pip install 'dji-drone-metadata-embedder[ui]'
dji-embed ui
```

The UI binds to `127.0.0.1` only (never the network) and opens a page in
your default browser with tabs for Doctor, Embed, Validate, Convert, and
Check. Each tab maps 1:1 to the matching CLI command, so anything you can
do on the terminal is available here too.

Useful flags:

- `--port N` — pin to a fixed port instead of picking a free one.
- `--no-browser` — print the URL instead of auto-opening.

Access is gated by a per-session token that is injected into the URL that
opens. If you bookmark a page, that link will stop working when the server
restarts — relaunch `dji-embed ui` to get a fresh token.
