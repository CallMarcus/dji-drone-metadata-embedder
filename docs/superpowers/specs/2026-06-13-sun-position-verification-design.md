# Design: Sun-position (shadow) check for footage verification

_Date: 2026-06-13_

_Issue: [#216](https://github.com/CallMarcus/dji-drone-metadata-embedder/issues/216)_

## Context

For each GPS point a DJI clip already gives us `(lat, lon)`. If we also know the
**absolute UTC time** of that point, we can compute the **sun's azimuth and
elevation** — and an analyst can then cross-check shadow direction and length in
the footage against the astronomical sun position. This is a standard
chronolocation / footage-verification technique, squarely on the project's
[use-for-good direction](https://github.com/CallMarcus/dji-drone-metadata-embedder#intended-use--scope)
(open-source verification, journalism, human-rights documentation).

The UTC prerequisite is already met: **#211** added timezone-correct UTC
timestamps to the telemetry pipeline (`_parse_srt_datetime`, `estimate_utc_offset`,
and a `convert --tz-offset` override). Without correct UTC, sun angles are
meaningless, so that work is the foundation this builds on.

### Current state of the code (what this design has to work with)

- `parse_telemetry_points()` (utilities) and the canonical `Track`
  (`geo/track.py`) carry only `(lat, lon, alt, raw-cue-timestamp)` — **no
  absolute datetime**.
- The full UTC-datetime resolution (`_parse_srt_datetime` + `estimate_utc_offset`
  + `--tz-offset` application) lives **only inside `extract_telemetry_to_gpx`**.
- `extract_telemetry_to_csv` is a separate block-parser that emits the **raw cue
  time** (`HH:MM:SS,mmm`), with no date and no UTC.

So the central problem is: sun angles need `(lat, lon, UTC datetime)`, but UTC is
currently computed in exactly one exporter and not exposed anywhere reusable.

## Goals

- A clean-room solar-position function: `(lat, lon, UTC datetime) → (azimuth,
  elevation)`, no new runtime dependencies, unit-tested against published
  reference values.
- Sun angles surfaced in **CSV export**, alongside the resolved **UTC
  timestamp** they were computed for (so the cross-check is auditable).
- A **`dji-embed verify-sun <SRT>`** command giving a human/JSON summary of the
  sun track over a clip.
- Graceful handling when UTC can't be resolved (SRT formats without an absolute
  datetime): no crash, blank/!computed rather than wrong numbers.

## Non-goals (deferred)

- **Sun angles as GeoJSON / GPX extensions.** Natural follow-up, not in this cut.
- **Pushing absolute datetime into the canonical `Track` / `parse_telemetry_points`.**
  This is the clean long-term single-source-of-truth (Approach C below) and the
  base the deferred GeoJSON/GPX extensions should build on — but it touches the
  Track model, redaction, and every geo exporter, which is more than this issue
  warrants. Recorded here as the intended future direction.
- **Any image/CV analysis of the actual shadows in-frame.** We compute the
  *expected* sun geometry; comparing it to the footage stays a human step.

## Chosen approach: shared UTC resolver + isolated `solar.py`

Considered three ways to get UTC + sun angles to the CSV/`verify-sun` paths:

- **A (chosen) — Extract a shared UTC resolver; add a self-contained solar
  module.** Pull the datetime-parse + offset-estimate/apply logic out of
  `extract_telemetry_to_gpx` into a reusable helper (GPX refactored to call it,
  no behavior change). Add `geo/solar.py`. CSV and `verify-sun` consume both.
  Removes the "UTC logic only exists in one exporter" smell; each unit is
  independently testable; small blast radius.
- **B — Standalone, leave GPX alone.** Duplicate UTC resolution into the
  CSV/verify-sun path. Less to touch now, but a second copy of the offset logic
  that will drift. Rejected.
- **C — Push absolute datetime into the canonical `Track`/`parse_telemetry_points`.**
  Cleanest long-term and the base for the deferred extensions, but touches the
  Track model, redaction interaction, and all geo exporters. Larger than "not
  massive." Deferred (see Non-goals).

## Architecture

```
                  ┌─ resolve_utc_offset(abs_dts, tz_offset, mtime) ─┐ (extracted
                  │   (_parse_srt_datetime, estimate_utc_offset)     │  from GPX,
                  │   → single per-file offset; point_utc = dt-offset│  reused)
                  └──────────────────────┬───────────────────────────┘
                                         │  timedelta | None
        ┌───────────────┬─────────────────┼──────────────────────┐
        ▼               ▼                                         ▼
   GPX exporter     CSV exporter ── sun_position(lat,lon,utc) ─► verify-sun
   (unchanged        (+datetime_utc,      (geo/solar.py)          (summary,
    behavior)         sun_azimuth,                                 text/json)
                      sun_elevation)
```

### 1. `geo/solar.py` — clean-room solar position (no new deps)

- `sun_position(lat: float, lon: float, when_utc: datetime) -> tuple[float, float]`
  returning `(azimuth_deg, elevation_deg)`.
  - Azimuth: 0–360°, clockwise from true north.
  - Elevation: −90…+90° (negative = sun below the horizon).
- Standard NOAA solar-geometry algorithm: Julian day → solar declination +
  equation of time → hour angle → altitude/azimuth. Pure stdlib `math`.
- Accuracy comfortably under ±0.5°, ample for shadow direction/length checks.
- `when_utc` is treated as UTC (naive-UTC or tz-aware accepted; normalized
  internally).

### 2. Shared UTC resolver (refactor, no behavior change)

- Extract from `extract_telemetry_to_gpx` a helper that resolves the **single
  per-file** local→UTC offset (matching today's behavior: `estimate_utc_offset`
  yields one offset applied to every point), e.g.
  `resolve_utc_offset(abs_datetimes, tz_offset, file_mtime_utc) -> timedelta | None`,
  reusing the existing `_parse_srt_datetime` / `estimate_utc_offset`. Each point's
  UTC is then `point_datetime - offset`. Returns `None` when no absolute datetime
  is present (the no-UTC case).
- `extract_telemetry_to_gpx` is rewired to call it and must behave **identically**
  (guarded by the existing GPX tests).

### 3. CSV export changes

- `extract_telemetry_to_csv(srt_file, output_file=None, tz_offset=None)` gains
  three trailing columns: `datetime_utc` (ISO 8601), `sun_azimuth`,
  `sun_elevation`.
- Per point: if UTC resolves for that clip, fill all three; if not (format with
  no absolute datetime), leave all three **blank**. Existing columns are
  unchanged and keep their order.
- `convert csv` passes through the same `--tz-offset` option the command already
  exposes (currently only consumed by the `gpx` branch).

### 4. `dji-embed verify-sun <SRT>` command

- Resolves UTC, computes the sun track, prints a summary:
  - clip UTC start/end,
  - sun elevation min → max,
  - azimuth start → end,
  - flags: **night** (elevation < 0 throughout), **very-low-sun** (peak < 5°),
    **sun not computable** (no resolvable UTC).
- Options: `--tz-offset` (default `auto`) and `--format text|json`, mirroring the
  existing `validate` command.
- Exit code: non-zero only on real errors (bad file, parse failure). "It was
  night" / "very low sun" are reported, not error exits.

## Privacy

`verify-sun` and the CSV sun columns operate on coordinates the user already
holds locally; nothing is sent anywhere. Redaction interaction is out of scope
here because sun computation lives on the CSV/verify-sun path, not the
redaction-aware `Track` path. (When the deferred Approach-C work moves datetime
into `Track`, sun angles will inherit `--redact` for free.)

## Verification

- **`solar.py` unit tests** vs published NOAA reference values: a few known
  `(lat, lon, UTC) → (az, el)` cases within ~0.5° tolerance, including a
  southern-hemisphere case and a high-latitude case.
- **CSV tests:** an SRT fixture *with* absolute datetimes → the three new columns
  present and within tolerance; a fixture *without* absolute datetimes → the
  three columns present but blank. Existing CSV columns unchanged.
- **GPX regression:** existing GPX tests must still pass unchanged after the
  resolver extraction.
- **`verify-sun` CLI smoke tests:** text and json output on a sample SRT;
  graceful path on a no-UTC fixture.

## Docs

- A short **"Footage verification"** section in `README.md` and
  `docs/user_guide.md`: what the shadow cross-check is, the new CSV columns, and
  the `verify-sun` command.
- Note the ±0.5° accuracy and that the tool gives *expected* sun geometry — the
  comparison to the footage is the analyst's step.

## Issue / roadmap mapping

- Implements the required acceptance criteria of **#216** (solar function +
  tests, sun angles in CSV, graceful no-UTC handling, docs) plus the issue's
  optional `verify-sun` summary command.
- GeoJSON/GPX sun extensions and the `Track`-level datetime refactor (Approach C)
  are explicitly deferred and noted as the follow-up direction.
