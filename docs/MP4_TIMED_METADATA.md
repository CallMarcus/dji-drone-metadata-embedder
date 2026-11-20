# MP4 Timed Metadata (sidecar-less footage: DJI, Parrot, and Autel)

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
| Autel EVO (tx3g subtitles) | 13.00 (unverified against a file we hold) |

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
Autel tx3g times are the subtitle's wall clock with no zone. ExifTool marks
them as likely local and does not append a `Z`. `dji-embed` treats them as
local and applies `--tz-offset` or the file-mtime estimate, the same way it
does for an SRT. A wrong guess shifts sun position and GPX `<time>`.
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

## Autel EVO (embedded tx3g)

Some Autel firmware muxes the same telemetry the `.ass` sidecar carries
(see [SRT formats](SRT_FORMATS.md)) into the MP4 as a `tx3g` subtitle track.
ExifTool 13.00 and later decodes that track in `Process_tx3g`. `dji-embed`
asks ExifTool for it (`probe` reports `autel:tx3g`) and maps:

| ExifTool tag | Sample field | Meaning |
|--------------|--------------|---------|
| `GPSLatitude` / `GPSLongitude` | lat/lon | WGS84. ExifTool has already applied the `N`/`S`/`E`/`W` letters from the longitude-first `GPS()` line |
| `GPSAltitude` | abs. altitude | metres, as written (the sample uses an `m` suffix) |
| `GimbalYaw`, `GimbalRoll` | gimbal pitch, gimbal yaw | see below |
| `GPSDateTime` | local datetime | subtitle clock, no `Z`; not treated as UTC |
| `SampleTime` | cue | offset into the clip |

**Gimbal axes.** The subtitle writes `G.PRY (pitch, roll, yaw)`. ExifTool
stores those three numbers, in that order, under the names `GimbalYaw`,
`GimbalPitch`, `GimbalRoll`. On the published 2023 EVO II sample the third
components of `F.PRY` and `G.PRY` agree (-59.0° and -58.9°) and the middle
gimbal component is 0°, which is a stabilised roll, so the names do not
match the axes. `dji-embed` reads `GimbalYaw` as pitch (negative = down)
and `GimbalRoll` as yaw so camera footprints point the right way. This
reading is an interpretation of that one published sample. It has not been
checked on a real file.

Not read: ISO, shutter, aperture, EV, aircraft `F.PRY`, and the per-sample
`GPSHomeLatitude` / `GPSHomeLongitude`. `--extract-home` still works for an
`.ass` sidecar, because that path reads the text. Yuneec drones and ordinary
caption tracks also use a `tx3g` atom; if the payload does not decode as
Autel telemetry, `dji-embed` says so instead of inventing a track.

`flightmap` and `map` also read videos that have no `.SRT` or `.ass` beside
them: each such video costs one quick ExifTool header probe, and those that
carry a telemetry track (Parrot, Autel, or sidecar-less DJI models) are read
in full, roughly 15 seconds per gigabyte. Videos with an `.SRT` or `.ass`,
and plain videos without telemetry, are not read in full.

## Bundled ExifTool config

`dji-embed` passes its own ExifTool user config (`data/exiftool.config` inside
the package) on every call. It adds tag mappings ExifTool does not have yet;
today that is the Mavic 4 Pro gimbal block (protobuf field `3-4-3`, the same
layout ExifTool names `GimbalInfo` on the Air 3/Air 3S), so
`flightmap --3d --gimbal-from-video` works on Mavic 4 Pro footage. Plain
`exiftool` on the command line will not show those tags unless you pass
`-config <that file>` yourself. An ExifTool too old to know the table being
extended ignores the config.

> UTC note: DJI and Parrot MP4 times are intrinsic, so `--tz-offset` is
> ignored for those videos. Autel tx3g times are local; `--tz-offset` and
> the mtime estimate apply, as they do for an SRT or an `.ass` sidecar.
