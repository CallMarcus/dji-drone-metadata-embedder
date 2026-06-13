# FMV / GIS interop: Cursor-on-Target (CoT)

`dji-embed` can export a flight as **Cursor-on-Target (CoT)** XML for the
ATAK/TAK ecosystem — useful for SAR, disaster response, and verification
workflows. This is export-only; embedding metadata into the video and MISB 0601
KLV are tracked separately (see "Roadmap" below).

## Usage

```bash
# Write <name>.cot.xml next to the SRT
dji-embed convert cot FLIGHT.SRT

# Choose an output path, sample one point per 2 s, set the CoT type
dji-embed convert cot FLIGHT.SRT -o flight.cot.xml --interval 2 --cot-type a-f-A-M-H-Q

# Redact coordinates (drop removes the track; fuzz coarsens to ~100 m)
dji-embed convert cot FLIGHT.SRT --redact fuzz

# Override the local->UTC offset (default: auto-detect from file mtime)
dji-embed convert cot FLIGHT.SRT --tz-offset +02:00
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--interval` | `1.0` | Seconds between sampled track points (DJI SRT is ~30 blocks/s). |
| `--cot-type` | `a-n-A` | CoT type/affiliation code. Default is **neutral air**. |
| `--redact` | `none` | `drop` empties the track; `fuzz` coarsens to ~100 m. |
| `--tz-offset` | `auto` | Local->UTC offset for timestamps, e.g. `+05:30`, `-8`. |

## What the file contains

A single well-formed XML document with an `<events>` root holding:

- **Timed PLI events** — one `<event>` per sampled point, sharing the UID stem
  `DJI-<name>-<i>`, with UTC `time`/`start`, a `<point>` (lat/lon/`hae`), and
  `<detail>` carrying `<contact>`, `<precisionlocation>`, and a derived
  `<track course=... speed=...>` (great-circle bearing + speed between consecutive
  sampled points; omitted at the final point).
- **One route event** (`type="b-m-r"`) whose `<link>` elements trace the path.

## Ingestion notes & caveats

- **The timed PLI track is the primary, standards-clean representation.** The
  `b-m-r` route is best-effort: full TAK route semantics (control points,
  `__routeinfo`, `__navcues`) are intentionally not reproduced.
- **Altitude** is DJI `abs_alt` placed in `hae` (height above ellipsoid). DJI
  altitude is not strictly WGS-84 ellipsoidal, so treat it as approximate.
- **`ce`/`le`** (positional error) are set to the CoT "unknown" sentinel
  `9999999.0`.
- **Timestamps** are real UTC when the SRT carries an absolute datetime;
  otherwise they are synthesized from the file mtime plus cue spacing
  (monotonic, approximate).

## Roadmap

- **MISB 0601 / STANAG 4609 KLV** encoding (and muxing into the MP4) — the
  larger, fiddly half of issue #217, tracked separately.
- **Network push** (UDP multicast / TCP to a TAK server) — file export first.
