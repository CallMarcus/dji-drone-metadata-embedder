# MP4 Timed Metadata (sidecar-less footage: DJI and Parrot)

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
| Mavic 4 Pro | 13.59 (verified; may work earlier) |

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

`GPSDateTime` in a DJI stream is true UTC, so GPX/CoT timestamps, CSV
`datetime_utc`, and `verify-sun` are correct without any timezone guessing.
Parrot records carry no wall-clock time; their UTC is the file's QuickTime
`CreateDate` (UTC by specification) plus each sample's offset, so a wrong
camera clock shifts the whole clip by the same amount.
Field coverage varies by model (e.g. Air 3S includes gimbal angles; Mini 5 Pro
is GPS + altitude only). CSV from an MP4 fills geo/altitude/`datetime_utc`/solar
columns; SRT-only camera columns (iso, shutter, …) stay blank.

## Parrot Anafi

Anafi recordings carry a `mett` metadata track whose sample description is
`application/octet-stream;type=com.parrot.videometadata3`: one packed record
per frame (30 Hz) with position, altitude, ground distance, velocity, drone and
camera orientation quaternions, exposure, field of view, link and battery
state. ExifTool decodes it in every release we tested (12.76 and 13.59 give
identical results), so the version table above is DJI-only.

What `dji-embed` maps (verified on an Anafi 4K, firmware 1.8.2):

| Parrot tag | Sample field | Meaning |
|------------|--------------|---------|
| `GPSLatitude`/`GPSLongitude` | lat/lon | WGS84 |
| `GPSAltitude` | abs. altitude | EGM96 mean sea level (Parrot's own datum) |
| `Elevation` | rel. altitude | the drone's estimated distance to ground |
| `FrameView` (quaternion) | gimbal yaw/pitch | camera heading (from north) and pitch (negative = down), derived from the world-frame camera quaternion; roll is always 0 |
| `SampleTime` | cue | offset into the clip |

Not read: the per-sample field of view, velocities, battery and link state, and
the takeoff location in the file header. `embed` does not apply (nothing to
merge into the MP4 it does not already carry), and the CSV camera columns stay
blank. The Anafi Ai writes a protobuf variant (`...videometadataproto`); it is
recognised but untested, and `dji-embed` says so if it decodes nothing.

`flightmap` and `map` now also read videos that have no `.SRT` beside them:
each such video costs one quick ExifTool header probe, and those that carry a
telemetry track (Parrot, or sidecar-less DJI models) are read in full, roughly
15 seconds per gigabyte. Videos with an `.SRT`, and plain videos without
telemetry, are not read in full.

## Bundled ExifTool config

`dji-embed` passes its own ExifTool user config (`data/exiftool.config` inside
the package) on every call. It adds tag mappings ExifTool does not have yet;
today that is the Mavic 4 Pro gimbal block (protobuf field `3-4-3`, the same
layout ExifTool names `GimbalInfo` on the Air 3/Air 3S), so
`flightmap --3d --gimbal-from-video` works on Mavic 4 Pro footage. Plain
`exiftool` on the command line will not show those tags unless you pass
`-config <that file>` yourself. An ExifTool too old to know the table being
extended ignores the config.

> UTC note: an MP4's time is intrinsic, so `--tz-offset` is ignored for video.
