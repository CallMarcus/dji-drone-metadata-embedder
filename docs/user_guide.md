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

## Footage verification (sun / shadow check)

For chronolocation and footage verification you can cross-check the **shadows** in a clip against where the sun actually was. Given each GPS point's position and UTC time, `dji-embed` computes the sun's **azimuth** (compass bearing) and **elevation** (height above the horizon).

```bash
# Summarise the sun track over a clip
dji-embed verify-sun DJI_0001.SRT

# Force a known UTC offset instead of auto-detecting from the file mtime
dji-embed verify-sun DJI_0001.SRT --tz-offset +02:00

# Machine-readable summary
dji-embed verify-sun DJI_0001.SRT --format json
```

The CSV export also gains `datetime_utc`, `sun_azimuth`, and `sun_elevation` columns:

```bash
dji-embed convert csv DJI_0001.SRT
```

Notes:
- Accuracy is within ~0.5 deg, ample for shadow direction/length checks.
- The tool gives the *expected* sun geometry; comparing it to the footage is the analyst's step.
- SRT formats without an absolute wall-clock datetime can't be resolved to UTC, so the sun columns stay blank and `verify-sun` reports `sun_not_computable`.
- UTC auto-detection relies on the file's modification time still reflecting the recording; if the file was copied or edited, pass `--tz-offset` explicitly for reliable results.

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
