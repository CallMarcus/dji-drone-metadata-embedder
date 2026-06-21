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

Use `dji-embed convert` to export telemetry to GPX, CSV, GeoJSON, KML, HTML,
or CoT:

```bash
dji-embed convert gpx DJI_0001.SRT
```

Swap `gpx` for `csv`, `geojson`, `kml`, `html`, or `cot` to pick the format.

For detailed how-to guides such as creating Windows bundles or redacting location data, see the files in `docs/how-to`.

### Sidecar-less footage (MP4 with embedded telemetry)

Newer DJI models record telemetry inside the MP4 instead of a `.SRT`. Pass the
video directly — `convert` and `verify-sun` auto-detect it:

    dji-embed convert gpx DJI_0001.MP4
    dji-embed verify-sun  DJI_0001.MP4

This needs a recent ExifTool (see `docs/MP4_TIMED_METADATA.md`). `--tz-offset`
is ignored for MP4 input because its embedded time is already UTC.

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

## Extracting the HOME (launch) point

`--extract-home` is opt-in because the HOME point reveals the operator's launch location. It never touches the MP4 and always respects `--redact`:

```bash
dji-embed embed FOOTAGE/ --extract-home              # HOME in the .json sidecar
dji-embed convert gpx flight.SRT --extract-home      # HOME waypoint in the GPX
dji-embed convert geojson flight.SRT --extract-home --redact fuzz   # HOME coarsened ~100 m
```

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

### Map tab

The **Map** tab lets you visualise a flight path from an SRT file without
leaving the browser.

**Steps:**

1. Open the Map tab (appears alongside Doctor, Embed, etc.).
2. Type or paste the path to an SRT file in the file-path field.
3. Optionally select a GPS redaction mode:
   - **None** — coordinates are passed to the browser as-is.
   - **Drop** — all GPS data is removed server-side; the map shows an empty
     state (no coordinates ever reach the browser).
   - **Fuzz** — coordinates are coarsened to approximately 100 m accuracy
     server-side before being sent to the browser.
4. Click **Load**.

**What you see after loading:**

- The flight path drawn on an OpenStreetMap basemap (powered by Leaflet).
  Map tiles are fetched from `*.tile.openstreetmap.org`; Leaflet itself and
  all other UI assets are served locally.
- The path is colour-coded by altitude, with a clickable green marker at the
  start and a red marker at the end. Per-frame telemetry (timestamp) is shown
  via the playback scrubber below.
- An altitude-profile chart below the map.
- A **Play / Pause** button and a scrubber that animate a marker moving along
  the path while a cursor tracks the altitude chart.

**Notes:**

- Redaction is enforced on the server — when `drop` or `fuzz` is selected the
  browser receives only the already-redacted GeoJSON, so exact coordinates are
  never transmitted to the client.
- The GeoJSON produced here is identical to what `dji-embed convert geojson`
  generates on the command line (one shared code path).
- **Video-synced scrubbing is not yet supported.** The scrubber animates the
  flight track only; it does not control or synchronise with a video file.
