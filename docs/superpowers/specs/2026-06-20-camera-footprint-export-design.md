# Design: Camera-footprint polygons for GeoJSON / KML export (#215 follow-up)

_Date: 2026-06-20_

## Context

The track-only half of #215 already shipped (v1.6.0): `dji-embed convert geojson`
and `convert kml` serialize the flight path as a `LineString` plus per-point
`Point` features, built from the canonical `geo/track.py` `Track` with redaction
applied once at the Track layer. See
`docs/superpowers/specs/2026-06-04-flight-path-mapping-design.md` (Phase 1).

This spec covers the remaining **camera-footprint** checklist on #215: project
each sampled frame's ground coverage as a polygon and add it to the GeoJSON and
KML output, for mapping / SAR coverage / OSINT verification / damage assessment
(the project's [use-for-good direction](https://github.com/CallMarcus/dji-drone-metadata-embedder#intended-use--scope)).

### The hard constraint

A true per-frame ground footprint needs **drone position + height-above-ground
(AGL) + gimbal pitch/yaw (or heading) + lens FOV**. Inventory of what the
telemetry actually carries (`docs/SRT_FORMATS.md`, `parse_telemetry_samples`):

- Position + altitude: present in every format.
- **Gimbal attitude (`gb_yaw`/`gb_pitch`/`gb_roll`): only the Avata 360 SRT
  variant.** Common models (Mini 3/4 Pro, Air 3, Mavic 3, …) carry no gimbal and
  no heading in their SRT.
- FOV: derivable from `focal_len` (present in some formats) + a per-model sensor
  table, otherwise a per-model / generic default.

So an SRT-only footprint is exact only for Avata 360. For everything else we
assume a **nadir (straight-down) camera** and size the footprint from AGL + FOV,
using real gimbal data when the format provides it. This is **Approach A**,
chosen over nadir-only (B) and DAT-attitude oblique projection (C). C — oblique
trapezoids from `dat_parser.py` attitude, time-aligned to the SRT — remains a
future follow-up.

## Goals

- Add per-interval ground **footprint polygons** to the existing GeoJSON and KML
  exports, behind a `--footprint` flag.
- Use a nadir model sized by AGL + FOV; rotate to flight heading, or to real
  gimbal yaw when the format carries it.
- Reuse the existing parser, `Track`, and redaction. No new runtime
  dependencies (pure-stdlib math).
- Degrade gracefully: missing AGL/FOV, strongly-oblique gimbal, or redaction all
  fall back to the track without footprints.

## Non-goals

- **Oblique-trapezoid projection** (camera not pointing straight down). Gated
  out in v1; deferred to the DAT-attitude follow-up (Approach C).
- **View frustums** (3D camera-to-ground volumes). Deferred with C.
- **DAT flight-log attitude** integration and SRT↔DAT time-sync.
- **Terrain / DEM-aware projection.** Flat-earth approximation only; documented.

## Architecture: augment, don't add a format

A footprint is not a new export format — it augments GeoJSON/KML. So the existing
`geo/` one-module-per-format pattern is preserved and a single new module adds
the geometry:

```
Track (geo/track.py, redaction applied here)
   │
   ├─ geo/footprint.py   NEW: Track + FOV spec → list[FootprintPolygon]
   │
   ├─ geo/geojson.py     gains optional footprints= param (Polygon features)
   └─ geo/kml.py         gains optional footprints= param (Polygon placemarks)
```

### Data-layer extension

The footprint needs height-above-ground, FOV inputs, and optional gimbal, none
of which the parser captures today. Extend `TelemetrySample` (utilities.py) and
`TrackPoint` (geo/track.py) with **optional** fields, all defaulting to `None`
so every existing consumer is untouched:

- `rel_alt: float | None` — from `[rel_alt: … abs_alt: …]` (adjacent to the
  existing `abs_alt` regex).
- `focal_len: float | None` — the **35 mm-equivalent** focal length, normalized
  to mm. The bracket formats write it two ways (legacy `240` = 24 mm ×10; newer
  literal `24.00`); normalize on parse. The ×10-vs-literal disambiguation is a
  heuristic (e.g. values ≥ 100 are ×10) refined against the format fixtures —
  the one edge case to validate is a ≥100 mm-equivalent literal (long tele).
- `gimbal_yaw: float | None`, `gimbal_pitch: float | None` — from `gb_yaw` /
  `gb_pitch` (Avata 360 format only).

**AGL source** (judgment call): use `rel_alt` when present; else fall back to
`abs_alt − first_fix_abs_alt` (the first GPS-fix point as the ground datum); if
neither yields a positive height, skip that point's footprint.

## Projection math

Per sampled point: center `(lat, lon)`, AGL height `h`, horizontal/vertical FOV
`HFOV`/`VFOV`, bearing `θ`.

```
half_width  = h * tan(HFOV / 2)     # across-track, metres
half_height = h * tan(VFOV / 2)     # along-track, metres
```

Four corners in a local east/north frame: `(±half_width, ±half_height)`. Rotate
the rectangle by `θ`:

- `θ` = great-circle course over ground from consecutive track points (the same
  bearing derivation `geo/cot.py` already uses for course/speed).
- **Gimbal yaw overrides `θ` when present** (Avata 360).

Local east/north → lat/lon via the equirectangular approximation (accurate at
footprint scale, tens–hundreds of metres):

```
dLat = dNorth / 111320
dLon = dEast  / (111320 * cos(lat))
```

The polygon is the four rotated/offset corners, ring-closed.

**Gimbal pitch is a gate, not a shape** (judgment call): if the camera is
strongly oblique — pitch more than a threshold off straight-down (default ~30°
from nadir; a module constant) — **skip the footprint** for that frame rather
than draw an inaccurate rectangle. Full oblique-trapezoid projection is Approach
C / future. In v1, gimbal therefore contributes rotation (yaw) plus an honesty
gate (pitch), not oblique geometry. Frames with no gimbal data are treated as
nadir.

## FOV / sensor table

Because the SRT reports a **35 mm-equivalent** focal length, FOV is computed
against a full-frame (36×24 mm) reference rather than the real sensor — this
keeps the table tiny and sidesteps the equivalent-vs-actual-focal mismatch:

```
HFOV = 2 * atan(36 / (2 * f_equiv))      # 4:3 readout uses 36×27;
VFOV = 2 * atan(27 / (2 * f_equiv))      # 16:9 readout uses 36×20.25
```

The reference height is chosen by the model's readout **aspect** (4:3 vs 16:9).
A module-level table keyed by model name supplies the aspect plus a native
equivalent focal for the no-`focal_len` fallback:

```python
@dataclass(frozen=True)
class LensSpec:
    native_focal_equiv_mm: float   # used when the SRT carries no focal_len
    aspect: tuple[int, int]        # sensor readout, e.g. (4, 3) or (16, 9)

FOV_TABLE: dict[str, LensSpec] = {
    "air3":     LensSpec(native_focal_equiv_mm=24.0, aspect=(4, 3)),
    "avata2":   LensSpec(native_focal_equiv_mm=12.7, aspect=(4, 3)),
    "mini4pro": LensSpec(native_focal_equiv_mm=24.0, aspect=(4, 3)),
    "avata360": LensSpec(native_focal_equiv_mm=24.0, aspect=(4, 3)),
}
```

(The numeric values above are first-pass estimates from published specs; they
are confirmed against each model's fixtures at implementation.) Use the SRT's
`focal_len` when present (handles zoom), else the model's
`native_focal_equiv_mm`.

The SRT rarely identifies the exact model, so model selection is **explicit**: a
`--model <name>` option picks the table entry. When no model is given and the SRT
carries no `focal_len`, fall back to a **generic wide default (~84° HFOV, 4:3
aspect)**. Document how to add entries (see CLAUDE.md §7).

## CLI & output

- `dji-embed convert geojson <SRT> --footprint [--footprint-interval 2.0] [--model air3]`
- `dji-embed convert kml <SRT> --footprint [--footprint-interval 2.0] [--model air3]`
- Batch support mirrors the existing `convert` subcommands; wired into the
  existing `convert` `run_one` in `cli.py`.
- `--footprint-interval` (seconds, default `2.0`) downsamples footprints so files
  stay small — one polygon per interval, not per frame. The track LineString and
  Points are unchanged.

**GeoJSON:** add `Polygon` features alongside the existing LineString + Points:

```json
{
  "type": "Feature",
  "geometry": {"type": "Polygon", "coordinates": [[[lon,lat], …, [lon,lat]]]},
  "properties": {"kind": "footprint", "index": 12, "timestamp": "00:00:24,000",
                 "agl": 41.2, "hfov": 73.7, "vfov": 58.7}
}
```

**KML:** a `<Folder>` named "Camera footprints" holding one `<Polygon>`
placemark per footprint, `<altitudeMode>clampToGround</altitudeMode>`.

## Redaction & fallback

- **Footprints render only under `--redact none`** (judgment call). A precise
  ~50 m polygon around a deliberately *fuzzed* centre re-sharpens exactly what
  `fuzz` blurred; `drop` already yields an empty track. So footprint generation
  is gated to `redact=none`; under `fuzz`/`drop` the output is track-only (no
  Polygon features).
- Per-point fallback: missing AGL or FOV, or too-oblique gimbal → skip that
  footprint, keep the track. A whole clip with no AGL → track only, plus a
  logged note. `--footprint` never removes the LineString/Point features.

## Verification

- **Projection unit tests:** known input → expected corners. e.g. 100 m AGL,
  80° HFOV → `half_width = 100·tan40° ≈ 83.9 m` → corner lat/lon within
  tolerance; nadir + zero heading → axis-aligned rectangle; non-zero heading →
  rotated corners.
- **Gimbal path:** Avata 360 fixture → footprint uses `gb_yaw`; a frame with
  oblique `gb_pitch` → skipped.
- **Parser:** `rel_alt` / `focal_len` (both ×10 and literal) / `gb_*` extraction
  across the format fixtures in `samples/`.
- **Privacy:** `--redact fuzz` and `--redact drop` → zero footprint features.
- **CLI smoke:** `convert geojson --footprint` and `convert kml --footprint`
  emit footprint Polygon features; golden-fixture structure check.

## Docs

- `docs/geospatial.md` — `--footprint` usage, the nadir/flat-earth assumptions
  and their limits, `--model` and the FOV table, how to add a model.
- README — note footprint export under the geospatial feature.
- `docs/SRT_FORMATS.md` — note which fields (`rel_alt`, `focal_len`, `gb_*`) feed
  the footprint and which formats carry them.

## Issue / roadmap mapping

- Completes the **camera-footprint follow-up** checklist on #215 (the track-only
  Phase 1 already shipped).
- Consumed by the map viewers: the standalone HTML viewer (#221, shipped) and the
  web-UI map panel (#222, next) can render the footprint `Polygon` features.
- **Deferred to a future issue:** oblique-trapezoid projection + view frustums
  via DAT-log attitude (Approach C), and terrain/DEM-aware projection.
