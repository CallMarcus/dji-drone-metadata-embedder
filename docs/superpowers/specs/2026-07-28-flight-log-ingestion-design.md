# Flight-log CSV ingestion — true gimbal attitude for SRT-only drones (#374)

**Date:** 2026-07-28
**Issue:** #374 (research trail in its comments is the full evidence base)

## Problem

Mini-series drones write no gimbal attitude anywhere on the SD card, so the
3D map's gaze footprint and ghost view honestly fall back to labelled
estimates. The attitude exists — in the encrypted phone/RC flight record —
and every decoder that can read it (Flight Reader, Airdata, PhantomHelp)
exports CSV. Decryption requires a network round-trip to DJI's key service
whichever tool is used; there is no offline path, for anyone.

## Decision: ingest CSV, not a vendor

`dji-embed flightmap … --flight-log LOG.csv` (repeatable). A mapping layer
recognises what the CSV contains and merges per-sample gimbal pitch/yaw into
the matching flight's track points. Everything downstream already keys off
whether gimbal attitude is present, so a filled field upgrades an estimate
to a measurement and the "estimated" badge retires itself.

Vendor-neutral by design (issue comment "Decoder landscape"): we cannot
vouch for any decoder's privacy, the column set is user-configurable in at
least one producer (confirmed by its developer — no stable schema exists),
and a documented mapping outlives any vendor. Known producers are
documented, not special-cased.

## The mapping layer (`geo/flightlog.py`)

**Column detection is semantic, never positional or exact-string:**

| Semantic | Match rule (case-insensitive) | Known producers |
| --- | --- | --- |
| gimbal pitch | contains `gimbal` + `pitch` | `GIMBAL.pitch` (Flight Reader), `gimbal_pitch(degrees)` (Airdata) |
| gimbal yaw | contains `gimbal` + (`yaw` or `heading`); the signed column preferred over a `[360]` variant | `GIMBAL.yaw`, `GIMBAL.yaw [360]`, `gimbal_heading(degrees)` |
| UTC time | contains `utc` | `datetime(utc)` (Airdata); Flight Reader's UTC option (Logs/Reports settings) |
| local date / time | contains `date` / `time` + `local` (or a combined `datetime` column) | `CUSTOM.date [local]` + `CUSTOM.updateTime [local]` |
| aircraft GPS (validation only) | contains `latitude`/`longitude`, excluding `home`/`rc`/`remote`/`tablet` | `OSD.latitude`, `latitude` |

Yaw is normalised to [-180, 180] true-north (DJI's own frame docs and the
Follow-Yaw cross-check in the spike prove the export is world-referenced).

**Locale rules (both confirmed permanent by the vendor):**

- Numbers accept `.` or `,` as the decimal separator; a value with both is
  an error. Clocks may be 12-hour with a locale-decimal seconds fraction
  (`5:28:49,2 pm`).
- **Fail loudly on an unparseable value; never treat it as missing.** A
  skip-on-error parser silently degrades a complete dataset into a
  plausible-looking sparse one (this exact failure happened during the
  spike). Empty cells are missing; garbage raises with column and row.
- Errors about missing columns say exactly which fields to enable in the
  export, because the column set is user-configurable.
- UTF-8 BOM and `;` delimiters tolerated (Windows exports).

## The join

1. **UTC column present → exact join.** Rows carry absolute UTC; match each
   track point to the nearest row within 1.0 s.
2. **Local-only → derived offset, said plainly.** The local→UTC offset is
   derived by rounding (log start − flight start) to the nearest 15 min
   (covers :30/:45 timezones). The report states the join was inferred and
   recommends enabling the UTC export option.
3. **GPS cross-validation when the log carries aircraft coordinates:**
   median distance between matched positions must stay under 500 m
   (tolerates `--redact fuzz`'s ~100 m). A log whose track is elsewhere is
   refused even if its clock overlaps.
4. Each log merges into the flight with the longest time overlap; SRT-borne
   gimbal values always win (merge fills only `None`).

## Non-goals (v1)

- No DAT parsing, no TXT decryption, no network anything (see the issue:
  the SDK door is closed for good, and this boundary is the point).
- No GUI exposure yet — CLI + docs first; GUI integration is a separate
  decision under the anti-bloat rules.
- No new dependencies: stdlib `csv` + `datetime` only.

## Documentation

`docs/how-to/flight-log-gimbal.md`: recommended export settings (enable the UTC
timestamp; include gimbal pitch/yaw), known-working producers, and the one
honest sentence about the ecosystem: *decrypting a DJI flight log requires
an internet connection whichever tool you use, because the decryption key
comes from DJI.*
