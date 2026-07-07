# MP4 Timed Metadata (sidecar-less DJI footage)

Newer DJI models (Air 3S, Mini 5 Pro, and others) record telemetry **inside the
MP4** as DJI's `djmd`/`dbgi` protobuf timed-metadata track, with no sidecar
`.SRT`. `dji-embed` reads it via ExifTool, so the `convert` exporters and
`verify-sun` work directly on the video:

    dji-embed convert gpx     DJI_0001.MP4
    dji-embed convert geojson DJI_0001.MP4 --redact fuzz
    dji-embed verify-sun      DJI_0001.MP4

Input is auto-detected by extension: `.mp4`/`.mov` use the ExifTool extractor,
`.srt` uses the subtitle parser. A folder of clips works with
`dji-embed convert geojson FOLDER --batch`.

## ExifTool version matters

ExifTool decodes each model's protobuf schema in a specific release:

| Model | ExifTool ≥ |
|-------|-----------|
| baseline `djmd`/`dbgi` | 13.05 |
| DJI Neo | 13.35 |
| Air 3S | 13.39 |
| Mini 5 Pro | 13.52 |

Newer models land in later releases — check the ExifTool change history. If your
ExifTool is too old, the stream is recognised but no GPS is decoded, and
`dji-embed` reports which schema needs a newer ExifTool.

**Getting a current ExifTool** — distro packages lag badly (Ubuntu 24.04 ships
12.76, which decodes no DJI GPS at all). The built-in installer fetches a
pinned, checksum-verified copy into a per-user directory (no admin rights):

    dji-embed doctor --install exiftool

It lands in `%LOCALAPPDATA%\dji-embed\tools\` (Windows),
`~/.local/share/dji-embed/tools/` (Linux) or `~/Library/Application
Support/dji-embed/tools/` (macOS), and `dji-embed` prefers it automatically.
`dji-embed doctor` shows the resolved version and whether it can decode each
supported model. To use a specific binary instead, set
`DJIEMBED_EXIFTOOL_PATH`.

## What you get

`GPSDateTime` in the stream is true UTC, so GPX/CoT timestamps, CSV
`datetime_utc`, and `verify-sun` are correct without any timezone guessing.
Field coverage varies by model (e.g. Air 3S includes gimbal angles; Mini 5 Pro
is GPS + altitude only). CSV from an MP4 fills geo/altitude/`datetime_utc`/solar
columns; SRT-only camera columns (iso, shutter, …) stay blank.

> UTC note: an MP4's time is intrinsic, so `--tz-offset` is ignored for video.
