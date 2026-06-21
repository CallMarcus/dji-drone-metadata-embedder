# Design: Opt-in HOME-point (launch location) extraction

_Date: 2026-06-21_

## Context

DJI SRT telemetry carries a **HOME point** — the drone's recorded launch
location — in two documented variants (`docs/SRT_FORMATS.md`):

```
HOME(39.906206,116.391400) D=5.2m H=1.5m
HOME (-58.847509, -34.232707, -57.98m), D 698.70m, H 85.80m,
```

The parser does **not** extract it today (confirmed: every `home` reference in
`src/` is `Path.home()` / config-dir code). This was noticed while
cross-referencing `JuanIrache/DJI_SRT_Parser`, which does surface HOME.

HOME is the **single most sensitive field** in the SRT: it is the operator's
launch position, more revealing than the flight track itself. So the goal is not
"parse another field" — it is to make HOME available for **provenance /
verification** ("confirm this flight launched from X", the project's
[use-for-good direction](https://github.com/CallMarcus/dji-drone-metadata-embedder#intended-use--scope))
**only on explicit opt-in**, never by default, and always under the existing GPS
redaction guard.

### The constraint that shaped the design

Redaction is wired **unevenly** across the three telemetry paths:

| Path | Output | Redaction today |
| --- | --- | --- |
| `embed` → `embedder.parse_dji_srt` | JSON sidecar | `apply_redaction()` (`utilities.py`) |
| `convert geojson/kml/html/cot` → `geo/track.py` `Track` | GeoJSON etc. | redaction at the `Track` layer (`build_track_from_samples`) |
| `convert gpx` / `convert csv` → `telemetry_converter.py` | GPX, CSV | **none** — `cli.py` calls `extract_telemetry_to_gpx(srt, out, tz_offset=…)` with no `redact`; the `--redact` help already scopes itself to "geojson/kml/html/cot" |

Because HOME must always honor `--redact`, and GPX/CSV have no redaction
pathway, this spec threads redaction into the GPX/CSV path **for the HOME marker
only**. The pre-existing fact that the per-frame *track* in GPX/CSV is
un-redactable is a separate gap, left to a follow-up issue (see Roadmap).

## Goals

- Extract the HOME point **only** when an explicit `--extract-home` flag is set,
  on both `embed` and `convert`. Default behaviour and default output bytes are
  unchanged.
- Surface HOME as a first-class geographic **marker** in JSON, GPX, GeoJSON, and
  CSV.
- HOME is **always** subject to `--redact` (`drop` → removed; `fuzz` → ~100 m).
- HOME is **never** written into the embedded MP4.
- No new runtime dependencies.

## Non-goals

- **HOME in the embedded MP4 metadata.** Never — the MP4 stays as today.
- **KML / HTML viewer / CoT** HOME markers. Deferred; the same marker idiom can
  extend to them later.
- **Closing the GPX/CSV track-redaction gap.** Out of scope; follow-up issue.
  This spec only makes the *HOME marker* redaction-aware in GPX/CSV.
- **GPS smoothing/averaging** (as `DJI_SRT_Parser` does). Rejected: smoothing
  fabricates positions and works against provenance fidelity.

## Approach: gate the parse itself (Approach A)

Chosen over "always parse, gate at output" (B) and "separate post-processor"
(C). A is the only one that makes "by default never extracted" a literal,
testable property: the HOME regex never runs unless the flag is set, so the
value never enters the telemetry structures by default. It also reuses the exact
threading pattern `--redact` already established.

A boolean `extract_home` (default `False`) is threaded through all three paths,
mirroring `redact`:

```
embed     : DJIEmbedder(extract_home=…) → parse_dji_srt → JSON sidecar
convert    : extract_home param → telemetry_converter (gpx/csv)
           : extract_home param → geo/track.py Track (geojson)
```

## Parsing

One regex handles both documented variants (optional leading space, optional
third altitude value with a trailing `m`):

```
HOME\s*\(\s*([+-]?\d+\.?\d*)\s*,\s*([+-]?\d+\.?\d*)(?:\s*,\s*([+-]?\d+\.?\d*)\s*m?)?\s*\)
```

Captures: lat (g1), lon (g2), optional alt (g3). HOME is constant within a file,
so we capture the **first** match and stop scanning for it.

- When `extract_home` is `False`: the regex is never evaluated; the `home` key is
  **omitted entirely** from the telemetry dict / not added as a column — default
  output stays byte-identical (no golden-fixture churn, and reinforces the
  guarantee).
- When `extract_home` is `True` and no HOME line is present: `home` is `None`
  (JSON `null`); no GPX/GeoJSON marker; CSV columns present but empty.

The field is added as an **optional** attribute on `TelemetrySample`
(`utilities.py`) defaulting to `None`, so existing consumers are untouched (same
pattern the footprint spec used for `rel_alt`/`focal_len`/`gb_*`).

## Flag / CLI

`--extract-home` (Click flag, default off) on both `embed` and `convert`. Help
text:

> Opt-in: extract the HOME/launch point (operator location) into JSON/GPX/
> GeoJSON/CSV outputs. Never written to the MP4. Subject to `--redact`.

## Redaction coverage (the safety guarantee)

Redaction always runs **after** parse, so it always wins over `--extract-home`.

- **JSON / embed path:** extend `apply_redaction()` (`utilities.py`) to cover
  `home`: `drop` → `None`; `fuzz` → lat/lon rounded to 3 decimals (~100 m),
  matching how it already treats `first_gps`/`avg_gps`. Altitude, if present, is
  rounded too (it is not locating, but kept consistent).
- **GeoJSON / Track path:** apply the same `drop`/`fuzz` rule to the HOME marker
  where the `Track` layer already applies redaction (`build_track_from_samples`),
  so HOME rides the existing redaction point.
- **GPX / CSV path:** thread `redact` into `extract_telemetry_to_gpx` /
  `extract_telemetry_to_csv` **for the HOME marker only** — `drop` emits no
  waypoint / empty columns; `fuzz` rounds to 3 decimals. The per-frame track in
  these two formats is unchanged (pre-existing behaviour; see Roadmap).

When both `--extract-home` and `--redact drop` are passed (contradictory but
safe), emit a single one-line log note so the user understands no HOME was
written.

## Output representation (marker idiom)

Emitted only when `extract_home` is on **and** HOME survived redaction:

- **JSON** (embed sidecar + any JSON): `"home": {"lat": .., "lon": .., "alt": ..|null}`
- **GPX**: a waypoint before the track —
  `<wpt lat=".." lon=".."><name>HOME</name>[<ele>..</ele>]</wpt>`
- **GeoJSON**: a `Point` feature alongside the track `LineString` —
  `{"type":"Feature","geometry":{"type":"Point","coordinates":[lon,lat]},"properties":{"type":"home"}}`
- **CSV**: repeated `home_lat,home_lon` columns (one constant value per row;
  `home_alt` only if the variant carried altitude)

## Verification

- **Parser:** both HOME variants → `home` populated when flag on; **absent** when
  flag off; `None` when flag on but no HOME line. Altitude captured for the
  3-value variant, `None` for the 2-value variant.
- **Precedence:** `extract_home` + `redact drop` → `home` is `None` / no marker
  in every format; `+ fuzz` → lat/lon rounded to 3 decimals.
- **Per-format markers:** GPX `<wpt name="HOME">` present; GeoJSON `Point`
  feature with `properties.type == "home"`; CSV `home_lat`/`home_lon` columns;
  JSON `home` key.
- **No-regression (the core privacy test):** with the flag **off**, every output
  (JSON, GPX, GeoJSON, CSV) is byte-identical to current output — no `home` key,
  no waypoint, no columns.
- **Fixtures:** current `samples/` use the bracketed `[latitude: …]` format and
  likely contain no HOME line — verify, then add a minimal SRT fixture for each
  HOME variant (`HOME(...)` no-space/no-alt, and `HOME (..., ..., ...m)`
  space/alt).

## Docs

- `README` — `--extract-home` under usage, with the **operator-location caveat**
  and that it is opt-in + redaction-aware + never in the MP4.
- `docs/user_guide.md` — a short example for `embed` and `convert`.
- `docs/SRT_FORMATS.md` — note HOME is parsed only on opt-in, and which formats
  carry it.
- Privacy/redaction docs — HOME is covered by `--redact`.

## Roadmap / follow-up

- **Follow-up issue:** thread `--redact` through the GPX/CSV *track* (not just
  HOME), closing the pre-existing gap where per-frame coordinates in GPX/CSV are
  un-redactable.
- **Possible later:** HOME markers in KML / HTML viewer / CoT exporters, and a
  HOME pin in the web-UI map panel (#222), reusing this marker.
