# Design: redact the per-frame track in gpx/csv exports (#248)

_Date: 2026-07-07_

## Context

`dji-embed convert gpx|csv --redact drop|fuzz` currently redacts **only the
opt-in HOME marker** (`redact_home` at the top of each exporter); the
per-frame track is written at full resolution. The CLI help even documents
the gap. This is surprising for a privacy flag and inconsistent with
`geojson/kml/html/cot`, where `--redact` empties or coarsens the whole track.
The gap was a deliberate scoped follow-up from #237.

Additional hole found while scoping (2026-07-07): **CSV from MP4 input**
(`convert csv DJI_0001.MP4`) returns early through `_csv_from_samples()`
*before* any redact logic — `--redact` is silently ignored on that path.
GPX from MP4 flows through the common point loop, so fixing the loop fixes
it for free.

Decisions taken during brainstorming (2026-07-07, all confirmed by
maintainer):

1. **CSV `drop` blanks the GPS columns, keeps the rows** (not "drop whole
   rows" as the issue AC literally said). CSV is a telemetry table where GPS
   is 2 of ~15 columns; blanking lets users share a camera-settings/exposure
   log without revealing where they flew, while `drop` still honestly means
   "the GPS is gone". GPX has nothing to salvage (pure geometry), so GPX
   `drop` = empty `<trkseg>`, matching geojson's empty track.
2. **Sun columns are treated as location data.** `sun_azimuth`/
   `sun_elevation` are computed *from* lat/lon — precise solar angles can be
   inverted to a location fix (our own `verify-sun` exists because of
   exactly this property). So: `drop` blanks the sun columns; `fuzz`
   computes them from the *fuzzed* coordinates (at ~100 m the angles barely
   move — sun position shifts ~1° per ~111 km).
3. **Implementation = shared primitive per exporter** (option A): both
   exporters apply the same policy helpers (`redact_coords` semantics:
   3-decimal rounding ≈ 100 m) already used by the geo pipeline. No routing
   of gpx/csv through `geo/track.py` (option B rejected: CSV carries camera
   columns `Track` doesn't model; big refactor, zero user-visible gain).
4. **MP4 CSV path is in scope**: thread `redact` into `_csv_from_samples()`.

## Goals

- `--redact drop|fuzz` affects the per-frame track in gpx and csv (SRT and
  MP4 input alike), consistently with the geo exporters.
- Solar columns never disclose more location precision than the coordinate
  columns in the same file.
- HOME marker / `home_*` columns behave exactly as today.

## Non-goals

- No change to `geojson/kml/html/cot` (already correct).
- No change to redaction *policy* (3-decimal fuzz stays; no new modes).
- No unification of the gpx/csv exporters onto the `Track` pipeline.
- Timestamps and camera columns are not redacted (they reveal *when*, not
  *where*). Altitude columns (`rel_altitude`, `abs_altitude`, GPX `<ele>` on
  fuzzed points) are kept: rel-alt is takeoff-relative (harmless) and
  abs-alt alone is a very weak elevation-band signal; blanking them would
  gut the CSV's usefulness for no meaningful privacy gain.

## Design

### 1. GPX — `extract_telemetry_to_gpx` (`telemetry_converter.py`)

In the `<trkpt>` writing loop:

- `drop`: skip the loop entirely — header, optional HOME `<wpt>` (already
  redacted independently), empty `<trk><trkseg/></trk>`, footer. Valid GPX.
- `fuzz`: write `round(lat, 3)` / `round(lon, 3)` per point; `<ele>` and
  `<time>` unchanged.
- `none`: unchanged output, byte-identical to today.

### 2. CSV from SRT — `extract_telemetry_to_csv`

Apply fuzz **at parse time**: when `--redact fuzz`, round `lat_val`/
`lon_val` to 3 decimals before they are written into the row *and* before
they are appended to `solar_inputs` — the existing solar pass then computes
sun angles from the fuzzed coordinates with no further change.

When `--redact drop`: leave `latitude`/`longitude` cells blank and append
`(abs_dt, None, None)` to `solar_inputs`. Note the existing solar loop uses
one combined guard (`abs_dt is None or lat_val is None or lon_val is None →
continue`) that would also skip `datetime_utc`; **split it** so
`datetime_utc` fills whenever `abs_dt` is known (timestamps reveal *when*,
not *where*) and only the `sun_*` columns require coordinates. Rows, camera
columns, altitudes, timestamps all remain.

`home_*` columns: untouched (already handled via `redact_home`).

### 3. CSV from MP4 — `_csv_from_samples`

New parameter `redact: str = "none"`, passed from
`extract_telemetry_to_csv`'s early-return call site. Same policy:

- `drop`: `latitude`/`longitude`/`sun_azimuth`/`sun_elevation` blank;
  `timestamp`, altitudes, `datetime_utc` kept.
- `fuzz`: rounded coords written; `sun_position()` called with the rounded
  values.

### 4. CLI help + docs

- `cli.py` `--redact` help: delete the "For gpx/csv only the HOME marker is
  redacted (the track is unredacted there)" caveat; state that drop/fuzz
  applies to the track in every format.
- Grep docs for the same caveat (user_guide / recipes / geospatial docs)
  and update any occurrence.

## Testing

Extend the existing redaction/convert test modules (follow current test
style; use small inline SRT fixtures as the neighbouring tests do):

- **GPX**: `drop` → no `<trkpt` in output, `<trkseg>` still present, HOME
  `<wpt>` absent; `fuzz` → all trkpt lat/lon have ≤3 decimals and differ
  from the raw values; `none` → unchanged (guard against regression).
- **CSV (SRT)**: `drop` → same row count as unredacted, `latitude`/
  `longitude`/`sun_azimuth`/`sun_elevation` empty, `iso`/`shutter`/
  `rel_altitude`/`datetime_utc` still populated; `fuzz` → coords rounded to
  3 decimals and sun angles equal to `sun_position(fuzzed…)` (not the
  raw-coordinate angles).
- **CSV (MP4)**: with mocked `load_samples`, `--redact drop|fuzz` now
  affects the output (regression test for the silently-ignored path).
- **HOME**: `--extract-home --redact fuzz` still yields the 3-decimal HOME
  waypoint/columns exactly as today.

## Acceptance criteria (supersedes the issue's AC where they differ)

- [ ] `convert gpx --redact drop` writes no `<trkpt>`s (HOME wpt behaviour
      unchanged)
- [ ] `convert gpx --redact fuzz` coarsens trackpoints to ~100 m
- [ ] `convert csv --redact drop` keeps rows but blanks lat/lon **and sun
      columns**; camera/altitude/timestamp columns intact
- [ ] `convert csv --redact fuzz` coarsens coords; sun columns computed
      from fuzzed coords
- [ ] `convert csv <video>.MP4 --redact …` honours the flag (was silently
      ignored)
- [ ] `--redact none` output byte-identical to today for both formats
- [ ] Help text + docs updated; tests cover drop + fuzz × gpx + csv × SRT +
      MP4-csv
