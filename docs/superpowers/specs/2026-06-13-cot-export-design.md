# CoT (Cursor-on-Target) export — design

_Date: 2026-06-13 · Issue: #217 (CoT half) · Status: approved, pre-implementation_

## Summary

Add `dji-embed convert cot <SRT>` to export a DJI flight as a **Cursor-on-Target
(CoT) XML** file for the ATAK/TAK ecosystem. This is the small, self-contained
half of #217 — **export only, file output only**. The Large/fiddly **MISB 0601
KLV** half and any **network push** to a TAK server are explicitly out of scope
and remain follow-ups.

CoT slots into the project's [use-for-good direction](../../../README.md#intended-use--scope):
SAR, disaster response, and verification tooling (ATAK/TAK, ArcGIS FMV, QGIS) is
exactly where open conversion helps the good side. The default CoT affiliation is
**neutral** to match that civilian/verification framing.

## Scope decisions (settled during brainstorming)

| Decision | Choice |
| --- | --- |
| Output target | **File only** (`<srt>.cot.xml`). No sockets / network push. |
| Flight representation | **Both** a route polyline **and** per-point timed PLI events. |
| Default CoT type | **`a-n-A`** (neutral air), overridable via `--cot-type`. |
| Track course/speed | **Included** — derived from consecutive points (great-circle bearing + haversine speed). |
| New runtime deps | **None** (stdlib `xml`/serialization only). |

## Background

`telemetry_converter.py` already extracts per-point lat/lon/alt and resolves real
UTC time for GPX (issue #202). The `geo/` package already hosts a shared `Track`
model plus GeoJSON/KML/HTML exporters (issues #215, #221). CoT follows the same
`convert <fmt>` + `geo/<fmt>.py` exporter pattern.

The one genuinely new problem CoT introduces: **every CoT event legally requires
a real ISO-8601 UTC timestamp**, but the shared `Track`/`TrackPoint` model today
carries only the raw SRT *cue* string (e.g. `00:00:01,000`). The UTC-resolution
machinery lives in `telemetry_converter.py`, which `geo/` **cannot import** —
`telemetry_converter` already does `from .geo.solar import sun_position`, so a
`geo → telemetry_converter` import would create a cycle.

## Architecture

### Approach (and rejected alternatives)

**Chosen — extend the `Track` layer with resolved UTC.** Move the UTC helpers down
into the lower-level `utilities.py` (which `geo/` already imports safely), enrich
the canonical parse with an aligned absolute datetime, and populate a `utc` field
on each `TrackPoint`. CoT — and any future exporter — reads `point.utc`. Redaction
stays centralized in the `Track` layer, preserving the project's "redaction
enforced once so no exporter can bypass `--redact`" invariant.

- **Rejected B — CoT resolves its own timestamps, Track for coords only.** Re-parse
  datetimes in the CoT module and zip onto Track points. Fragile: `Track` drops
  `(0,0)` no-fix frames and can redact/drop points, so a separately-parsed datetime
  list misaligns; also duplicates parsing.
- **Rejected C — separate CoT data path, bypass Track.** Violates the deliberate
  "redaction enforced once at `Track`" invariant; a future redaction change could
  silently miss CoT.

### 1. `utilities.py` — canonical parse + UTC helpers (cycle-breaking move)

- **New `parse_telemetry_samples(srt_path) -> list[TelemetrySample]`** where
  `TelemetrySample` is a small dataclass `(lat, lon, alt, cue, dt)`:
  - Reuses the **existing** regex/extraction logic of `parse_telemetry_points`
    (bracket format + `GPS(...)` compact + M300 `0.0M` suffix + `is_gps_fix`
    `(0,0)` filtering) so no format support is lost.
  - Additionally captures the block's absolute wall-clock datetime (`dt`, or
    `None` when the format carries none).
- **`parse_telemetry_points` becomes a thin wrapper** returning the existing
  4-tuple `(lat, lon, alt, cue)` from `parse_telemetry_samples`. Its signature and
  behavior are unchanged, so `per_frame_embedder.py` and all existing tests
  (`test_gps_nofix`, `test_golden_fixtures`, `test_samples`, `test_new_model_samples`)
  are untouched. A regression test pins this equivalence.
- **Move** `_parse_srt_datetime`, `parse_utc_offset`, `estimate_utc_offset`,
  `resolve_utc_offset` from `telemetry_converter.py` into `utilities.py`.
  `telemetry_converter.py` **re-exports** them (`from .utilities import ...`) so
  existing imports keep working — notably `tests/test_timezone.py`, which imports
  `estimate_utc_offset` / `parse_utc_offset` from `telemetry_converter`. This move
  is what breaks the import cycle; it is in-scope because `Track` legitimately needs
  UTC resolution and the lower-level home is the correct one.

### 2. `geo/track.py` — UTC on every point

- `TrackPoint` gains **`utc: datetime | None = None`**. The default keeps existing
  direct constructions in tests valid; geojson/kml/html ignore the field, so their
  output is unchanged.
- `build_track(srt, redact="none", tz_offset=None)` gains `tz_offset`:
  - Parses via `parse_telemetry_samples` (datetimes aligned to kept points by
    construction).
  - Resolves the local→UTC offset with `resolve_utc_offset(abs_times, tz_offset,
    mtime_utc)` — auto-detected from file mtime, or the explicit `--tz-offset`.
  - Sets each point's `utc`:
    - When the block has an absolute datetime → `utc = dt - offset`.
    - When it does not → **synthesized** as `mtime_utc + (cue − first_cue)` so CoT
      always has monotonic UTC time. Documented as approximate.
- geojson/kml/html callers keep calling `build_track(srt, redact=redact)` (auto
  tz); they don't read `utc`.

### 3. `geo/cot.py` — the exporter (mirrors `kml.py`)

Public surface, matching the existing exporter shape:

```python
def track_to_cot(track: Track, *, cot_type: str = "a-n-A",
                 interval: float = 1.0, stale_seconds: float = 300.0) -> str: ...
def write_cot(track: Track, output_path: Path, **kw) -> Path: ...
def convert_to_cot(srt_file, output_file=None, *, redact="none",
                   tz_offset=None, interval=1.0, cot_type="a-n-A") -> Path: ...
```

Exported from `geo/__init__.py` (`convert_to_cot`, `track_to_cot`).

**Downsampling.** SRT carries one block per video frame (~30/s). Both the PLI
events and the route vertices use a single **sampled** point list: walking the
track in cue-time order, keep the first point whose cue time is ≥ `interval`
seconds after the last kept point (default `interval = 1.0`). First and last
points are always kept.

**Output: one well-formed XML document, `<events>` root** containing:

- **Timed PLI events** — one `<event>` per sampled point:
  ```xml
  <event version="2.0" uid="DJI-{stem}-{i}" type="{cot_type}" how="m-g"
         time="{utc}" start="{utc}" stale="{utc + stale_seconds}">
    <point lat="{lat}" lon="{lon}" hae="{alt}" ce="9999999.0" le="9999999.0"/>
    <detail>
      <contact callsign="{stem}"/>
      <precisionlocation altsrc="GPS"/>
      <track course="{course}" speed="{speed}"/>   <!-- when derivable -->
      <remarks>frame {i}, abs_alt {alt} m</remarks>
    </detail>
  </event>
  ```
  - `type` defaults to `a-n-A` (neutral air); `--cot-type` overrides verbatim.
  - `how="m-g"` = machine / GPS-derived.
  - DJI `abs_alt` → `hae` (height above ellipsoid). DJI altitude is not strictly
    WGS-84 ellipsoidal; documented caveat in `docs/fmv-interop.md`.
  - Unknown position error → CoT's `9999999.0` sentinel for `ce`/`le`.
  - `time`/`start` = the point's UTC; `stale` = `time + stale_seconds`
    (default 300 s for PLI events). No CLI knob for stale (YAGNI).
- **One route event** — `type="b-m-r"`, with a `<link>` per sampled vertex
  carrying `point="lat,lon,hae"`, `<contact callsign="{stem} route"/>`, and a
  `<remarks>` point count. `stale` set generously (event end + 1 h).

**Course/speed derivation (included).** For each sampled point with a following
sampled point and `dt > 0` (using the resolved `utc` values):

- `speed` (m/s) = haversine great-circle distance between the two points ÷ `dt`.
- `course` (deg, `[0, 360)`) = initial great-circle bearing to the next point.
- The `<track>` element is **omitted** where undefined (the final point, or
  `dt == 0`). Small `_haversine_m` / `_initial_bearing_deg` helpers live in
  `geo/cot.py` (its only consumer for now).

**Representation honesty.** The PLI track is the **primary, schema-clean**
representation (standard, unambiguous CoT events). The `b-m-r` route is
**best-effort**: full TAK route semantics (control points, `__routeinfo`,
`__navcues`) are finicky and can't be validated offline without a TAK endpoint.
`docs/fmv-interop.md` states this plainly and points users to the PLI track as the
robust path. Tests validate the route at the "well-formed + expected
elements/attributes present" level, not full TAK semantic round-trip.

### 4. CLI (`cli.py`)

- Add `"cot"` to the `convert` command's `click.Choice`.
- Two new **shared** options on `convert` (the command already shares options
  across formats; non-cot formats ignore them, exactly as `--redact` is today
  documented as geojson/kml/html-only):
  - `--interval FLOAT` (default `1.0`, help notes "cot only: seconds between
    sampled points").
  - `--cot-type TEXT` (default `a-n-A`, help notes "cot only: CoT type/affiliation
    code").
- `--redact` and `--tz-offset` already exist on `convert` and flow through.
- Dispatch: `elif command == "cot": convert_to_cot(srt, out, redact=redact,
  tz_offset=offset, interval=interval, cot_type=cot_type)`.

## Edge cases

| Input | Output |
| --- | --- |
| 0 track points (no GPS fix, or `--redact drop`) | Well-formed empty `<events/>` + a `WARNING` log; exit success. |
| 1 track point | A single PLI event, **no** route (route needs ≥ 2 vertices, mirroring the geojson LineString ≥ 2 guard). No `<track>` (course/speed undefined). |
| No absolute datetime in SRT | `utc` synthesized from `mtime + cue` offset; CoT still valid, times approximate (documented). |
| `--redact fuzz` | Coarsened coordinates arrive via `Track`; CoT emits the fuzzed values. |

## Testing (offline, no new deps — stdlib `xml.etree.ElementTree`)

New `tests/test_geo_cot.py` and additions to `tests/test_cli_convert_geo.py`:

- Fixture SRT → output parses as well-formed XML with `<events>` root.
- Event count matches expectation for a given `--interval` (downsampling correct).
- PLI `time`/`start` are ISO-8601 UTC (`...Z`); `stale` > `time`.
- `point` `lat`/`lon`/`hae` match the (possibly redacted) track values.
- Default `type` is `a-n-A`; `--cot-type` override is emitted verbatim.
- Redaction: `fuzz` coarsens emitted coords; `drop` yields empty `<events/>`.
- A route `<event type="b-m-r">` exists with one `<link>` per sampled vertex.
- Course/speed: a hand-computed 2-point fixture yields the expected `course`/`speed`
  within tolerance; endpoint correctly omits `<track>`.
- Edge cases: 0-point and 1-point inputs (table above).
- CLI smoke test: `convert cot <fixture>` writes `<stem>.cot.xml`, exit 0.
- **Regression:** `parse_telemetry_points` returns the identical 4-tuple list
  before/after the `parse_telemetry_samples` refactor (golden fixtures).

## Documentation

- **New `docs/fmv-interop.md`**: CoT section (what it is, the `convert cot` command,
  `--interval`/`--cot-type`/`--redact`/`--tz-offset`, TAK ingestion notes, the
  `hae` altitude caveat, and the route best-effort caveat). A short **KLV stub**
  section marks the #217 follow-up.
- **README**: one bullet under the export/geospatial features; link to
  `docs/fmv-interop.md`.
- **`convert` help text**: mention `cot` and the two new options.

## Out of scope (follow-ups)

- **MISB 0601 / STANAG 4609 KLV** encoding + muxing — the Large half of #217.
- **Network push** (UDP multicast / TCP to a TAK server).
- Unifying `utilities.parse_telemetry_samples` with
  `telemetry_converter._parse_gps_points` (they differ on `(0,0)` filtering;
  left as-is to avoid an unrelated refactor / regression risk).

## Acceptance criteria (this slice)

- [ ] `dji-embed convert cot <SRT>` produces a well-formed CoT XML file.
- [ ] Output contains timed PLI events (downsampled by `--interval`) **and** a
      route event; PLI events carry UTC time and derived course/speed where defined.
- [ ] `--cot-type` overrides the default `a-n-A`; `--redact` and `--tz-offset` honored.
- [ ] Graceful handling of 0-/1-point and datetime-less inputs.
- [ ] Unit tests (XML structure, counts, UTC, redaction, course/speed) + CLI smoke
      test, all offline; `parse_telemetry_points` regression test passes.
- [ ] Docs: `docs/fmv-interop.md` + README bullet + `convert` help text.
- [ ] No new runtime dependencies.
