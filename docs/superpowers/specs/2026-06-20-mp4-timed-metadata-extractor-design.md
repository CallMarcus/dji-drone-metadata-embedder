# Design: ExifTool-backed MP4 timed-metadata extractor (#206)

_Date: 2026-06-20_

## Context

Newer DJI models (Air 3S, Mini 5 Pro, Mavic 4 Pro, Matrice 4E, Osmo 360, …) ship
footage with **no sidecar `.SRT`**. Their telemetry lives inside the MP4 as a
timed-metadata track — DJI's `djmd` / `dbgi` protobuf streams (`MetaFormat:
djmd`, handler `CAM meta` / `CAM dbgi`). ExifTool decodes these per model, so
`dji-embed` can read them by shelling out to the ExifTool binary the project
already documents — no reverse-engineering, no licence entanglement.

This is **Stage 1** of #206: an ExifTool-backed extractor that normalises the
MP4 timed metadata into the project's existing telemetry model, wired into the
**`convert` exporters and `verify-sun`** so every mapping/verification output
works on sidecar-less footage. (Stage 2 — native clean-room protobuf decoding —
remains a separate future effort, e.g. #202.)

### Empirical grounding (validated 2026-06-20)

Probed against real local fixtures with ExifTool **13.55** (the current CPAN
production release):

- **Air 3S** (`dvtm_Air3s.proto`): rich decode — 3214 samples each of GPS
  lat/lon, absolute + relative altitude, shutter, F-number, colour temperature,
  gimbal yaw/pitch, drone yaw/pitch/roll, plus `SampleTime`, `SampleDuration`,
  and `GPSDateTime` per sample.
- **Mini 5 Pro** (`dvtm_Mini5Pro.proto`): lean decode — GPS, absolute altitude,
  temperature only. **Field sets vary per model.**
- **Neo 2** (`dvtm_NEO2.proto`): stream present but **not decoded** by 13.55
  (proto not yet registered) — only `SampleTime` returns.

Decode coverage is per-model and tracks ExifTool's release cadence (Air 3S
landed ~13.39, Mini 5 Pro ~13.52; Neo 2 still pending). **New models become
supported by upgrading ExifTool — no code change in this extractor.**

Two findings shape the design:

1. **Consumption pattern:** `exiftool -ee -j -g3 -n -api LargeFileSupport=1
   <file>` returns JSON whose first element holds `Doc1 … DocN` nested objects —
   one per timed sample, each carrying only the fields present for that sample.
   This is robust to varying/missing fields (`.get()` mapping). The `-p`
   print-format alternative is rejected: it silently *skips* any sample missing
   a referenced tag.
2. **Absolute UTC for free:** `GPSDateTime` is true per-sample UTC
   (`2026:05:16 23:55:53.000Z`). The MP4 path therefore supplies wall-clock UTC
   *directly*, unlike the SRT path, which must infer the local→UTC offset from
   the file mtime. This makes `verify-sun` strictly more reliable on MP4 input.

## Goals

- Read DJI `djmd`/`dbgi` timed metadata from an MP4/MOV via ExifTool and
  normalise it to the project's canonical `TelemetrySample` model.
- Make `dji-embed convert <fmt> FILE` and `dji-embed verify-sun FILE` accept a
  **video** file as input (auto-detected by extension), in addition to `.SRT`.
- Thread the MP4 path's **true UTC** through so timestamped outputs (GPX, CoT,
  CSV `datetime_utc`, sun geometry) are correct without mtime guessing.
- Stay **model-agnostic**: gain models purely through ExifTool upgrades.
- Fail loudly and usefully when a stream is present but undecodable.

## Non-goals

- **Embed fall-through** (`dji-embed embed` on sidecar-less MP4s). The issue's
  Stage 1 named this; we deliberately target the higher-value convert/verify-sun
  surface first. The embed mux requires an SRT subtitle track, so embed support
  is a clean follow-up (synthesise an SRT from samples, or a GPS-tags-only mode).
- **Native protobuf decoding** (Stage 2 / #202). We shell out to ExifTool.
- **Stream preservation through the mux** (#197) — orthogonal.
- **New CSV columns / richer schema.** CSV from an MP4 fills the columns the
  stream provides; it does not add columns.
- **A `--telemetry-source` flag.** Single-file `convert`/`verify-sun` dispatch on
  the input's extension; the flag was an embed-batch concern (both files present
  side-by-side), out of scope here.
- **ffprobe dependency.** ExifTool itself is the detector.

## Architecture

```
                         ┌─ .srt  → parse_telemetry_samples()      (dt = local wall-clock)
load_samples(path) ─dispatch┤
                         └─ .mp4/.mov → mp4_telemetry.extract_samples()  (dt = UTC)
                                            │  shells: exiftool -ee -j -g3 -n
                                            ▼
                                 list[TelemetrySample]
                          ┌──────────────────┼─────────────────────────┐
                          ▼                  ▼                          ▼
                   build_track()      gpx / verify-sun            csv (rich rows)
              (geojson/kml/cot/html)  (via _parse_gps_points     (bespoke; fills the
                                       dict shape)                fields the stream has)
```

One new module (`mp4_telemetry.py`), one dispatcher (`load_samples`), and a
small video-aware adapter for the legacy dict/CSV consumers. The `Track`-based
exporters (geojson/kml/cot/html) need no change beyond `build_track` dispatch.

## Component: `src/dji_metadata_embedder/mp4_telemetry.py`

A focused module with no dependency on the embedder pipeline.

- `VIDEO_SUFFIXES = {".mp4", ".mov"}` (case-insensitive) and
  `is_video(path) -> bool`.

- `probe(path) -> str | None` — cheap detection, **no `-ee`**:
  `exiftool -s -api LargeFileSupport=1 -MetaFormat -Category <file>`. Returns the
  schema descriptor (e.g. `dvtm_Air3s.proto;model_name:FC9113;…`) when a
  `djmd`/`dbgi` track exists, else `None`. Used to distinguish "no telemetry
  track" from "track present but undecoded".

- `extract_samples(path) -> list[TelemetrySample]` — the core:
  1. Run `exiftool -ee -j -g3 -n -api LargeFileSupport=1 <file>` via
     `subprocess.run(capture_output=True)`. The exiftool executable is resolved
     via the existing `utils.dependency_manager` (`_find_exiftool_executable`),
     falling back to `shutil.which("exiftool")`.
  2. `json.loads(stdout)`; take element `[0]`; iterate keys matching `^Doc\d+$`
     in numeric order.
  3. For each sample doc, map (all via `.get`, tolerant of absence):
     | TelemetrySample | ExifTool tag | notes |
     |---|---|---|
     | `lat` | `GPSLatitude` | float (from `-n`) |
     | `lon` | `GPSLongitude` | float |
     | `alt` | `AbsoluteAltitude` | float; `0.0` if absent |
     | `cue` | `SampleTime` | seconds → `HH:MM:SS,mmm` string |
     | `dt`  | `GPSDateTime` | parsed as UTC `datetime` (strip trailing `Z`); `None` if absent |
     | `rel_alt` | `RelativeAltitude` | optional |
     | `gimbal_yaw` | `GimbalYaw` | optional |
     | `gimbal_pitch` | `GimbalPitch` | optional |
     | `focal_len` | — | `None` (stream carries no 35mm-equiv focal length) |
  4. Drop samples without both `GPSLatitude` and `GPSLongitude`, and apply the
     same `(0, 0)` no-fix filter as the SRT path (`is_gps_fix`).
  5. **Undecoded-vs-no-fix distinction.** If `probe()` found a stream but the
     `Doc`s carry **no recognised telemetry at all** (only `SampleTime` — the
     Neo 2 signature), raise `Mp4TelemetryError`: this ExifTool can't decode the
     model. If telemetry fields *are* present but no sample is a valid GPS fix
     (a legitimately GPS-less clip), return an **empty list** — not an error.
     Concretely: track whether any `Doc` had a GPS or altitude key; raise only
     when none did.

- `Mp4TelemetryError(RuntimeError)` — module-specific exception with actionable
  messages.

`SampleTime` → cue formatting: `SampleTime` is elapsed seconds from track
start (e.g. `0`, `0.0166833…`). Format as `HH:MM:SS,mmm` so it matches the SRT
cue shape the rest of the code expects. (This is a *relative* cue, consistent
with how the SRT cue is relative; absolute time lives in `dt`.)

## Component: dispatcher + the UTC rule

Add to `utilities.py`, beside `parse_telemetry_samples`:

- `load_samples(path) -> list[TelemetrySample]` — `is_video(path)` →
  `mp4_telemetry.extract_samples(path)`; else `parse_telemetry_samples(path)`.

**The UTC rule (the crux):** SRT `dt` is *local wall-clock* (consumers subtract
an mtime-derived offset); MP4 `dt` is *already UTC*. So any consumer that
resolves an offset must use **offset 0 for video sources**.

`build_track` is refactored to make this explicit and reusable:

- Extract the Track-assembly body into
  `build_track_from_samples(name, samples, redact, *, assume_utc, tz_offset,
  mtime_utc) -> Track`.
- `build_track(path, redact, tz_offset)`:
  - `samples = load_samples(path)`.
  - If `is_video(path)`: `assume_utc=True` → each point's `utc = sample.dt`
    (no offset resolution). `name = path.stem`.
  - Else: today's behaviour exactly — resolve offset from
    `tz_offset`/mtime, `utc = dt - offset`, synthesise from cue when `dt is
    None`. **SRT output is unchanged, byte-for-byte.**

This single change lights up geojson, kml, cot, and html for MP4 input.

## Component: legacy dict + CSV consumers

`gpx`, `verify-sun`, and `csv` do not go through `build_track`; they parse SRT
text directly. They are routed through a shared video-aware loader so SRT
behaviour is untouched and video input is added.

- `load_gps_points(path) -> tuple[list[dict], bool]` (in `telemetry_converter.py`)
  — returns `(_parse_gps_points`-shaped dicts, `is_utc)`:
  - SRT: `(_parse_gps_points(content), False)` — unchanged.
  - Video: map `load_samples(path)` into the same dict shape
    (`lat`, `lon`, `ele`←alt, `time`←cue, `datetime`←`dt`), `is_utc=True`.
  - `extract_telemetry_to_gpx` and `summarize_sun` replace their
    `open()+_parse_gps_points(content)` with `load_gps_points(path)`, and use
    `offset = timedelta(0) if is_utc else resolve_utc_offset(...)`.

- **CSV** (`extract_telemetry_to_csv`) keeps its bespoke rich per-block parser
  for SRT. For a **video** input it builds its rows from `load_samples(path)`
  instead, populating the columns the canonical `TelemetrySample` carries —
  `latitude`, `longitude`, `rel_altitude`, `abs_altitude`, `datetime_utc` (from
  the true UTC `dt`), and `sun_azimuth`/`sun_elevation` (computed from `dt` +
  lat/lon). The camera columns (`iso`, `shutter`, `fnum`, `ev`, `ct`,
  `color_md`, `focal_len`) stay **blank** for MP4 sources — `TelemetrySample`
  does not model them, and adding them would mean bloating the track model.
  The column set is unchanged; only the source and which columns are filled
  differ. (Camera-column support from MP4 is a deliberate follow-up.)

## CLI surface

- `convert`'s `input` argument is already `click.Path(exists=True)` — it accepts
  a video path today with no signature change. Only `run_one` changes: it now
  receives any telemetry source and the exporters dispatch internally.
- `--batch` currently globs `*.SRT`. Extend to also glob `*.MP4`/`*.MOV` so a
  folder of sidecar-less clips converts in one call. (SRT-only folders behave as
  before.)
- `verify-sun`'s argument likewise accepts a video path; `summarize_sun`
  dispatches internally.
- No new flags. `--tz-offset` is ignored for video input (UTC is intrinsic); a
  one-line note in `--help`/docs states this.

## Data flow & redaction

Redaction is unchanged and still applied at the `Track`/exporter layer
(`redact_coords`, `redact` of `none`/`drop`/`fuzz`). The extractor returns raw
samples; `build_track`/exporters redact exactly as they do for SRT, so `drop`
still yields an empty track and `fuzz` still coarsens to ~100 m. No exact
coordinate handling changes.

## Error handling

`mp4_telemetry` raises `Mp4TelemetryError` with actionable text; the CLI surfaces
it as a `click.ClickException`:

- **Stream present, zero GPS decoded** (e.g. Neo 2 on 13.55):
  `"Telemetry stream present (<schema>) but ExifTool <ver> decoded no GPS — this
  model needs a newer ExifTool (see docs/MP4_TIMED_METADATA.md)."` Includes the
  schema from `probe()` and `exiftool -ver`.
- **No djmd/dbgi track at all:** `"No embedded telemetry found in <file>; is
  there a sidecar .SRT for this clip?"`
- **exiftool not found:** reuse the existing install hint
  (`pip install …[ui]`-style message already used elsewhere for ExifTool).
- **exiftool nonzero exit / unparseable JSON:** raise with stderr tail.
- Empty or fully redacted tracks flow through identically to the SRT path (no
  crash; exporters emit their empty-state output).

## Testing & verification

Fixture strategy: **no media or real GPS committed.**

- Commit `tests/fixtures/mp4_telemetry/air3s_g3j.json` — a real
  `exiftool -ee -j -g3 -n` capture from the Air 3S fixture, **trimmed to a
  handful of `Doc` samples** and with **GPS coordinates offset to a safe
  location**. This is the golden input for the mapper.
- **Unit tests** (`tests/test_mp4_telemetry.py`), mocking
  `subprocess.run`/the exiftool call to return the committed JSON:
  - mapper field-mapping → correct `TelemetrySample` list (lat/lon/alt/cue/dt/
    rel_alt/gimbal).
  - `dt` parsed as UTC and **not shifted** when threaded through `build_track`
    (`assume_utc`) / `load_gps_points` (`is_utc`).
  - `SampleTime` → `HH:MM:SS,mmm` cue formatting.
  - `(0, 0)` and missing-GPS samples filtered.
  - `probe()` returns the schema vs `None`.
  - stream-present-but-zero-GPS → `Mp4TelemetryError` (drive via a JSON capture
    that has `Doc`s without GPS).
- **Integration test** (`tests/test_mp4_telemetry_integration.py`),
  `@pytest.mark.skipif` on real `exiftool` ≥ 13.39 **and** a local, git-ignored
  sample MP4 (path via env var, e.g. `DJI_MP4_FIXTURE`): runs the real
  subprocess end-to-end and asserts a non-empty `Track`. Skips cleanly in CI.
- **Consumer tests:** `convert geojson FILE.mp4` (mocked extractor) yields a
  `FeatureCollection`; `verify-sun FILE.mp4` computes sun geometry from the true
  UTC; `convert csv FILE.mp4` fills geo + `datetime_utc` + sun, blanks SRT-only
  columns.
- `uv run pytest -q`, `uv run ruff`, and `uv run mypy` all green before commit.

## Docs

- New `docs/MP4_TIMED_METADATA.md`: how MP4 timed metadata works, the ExifTool
  version requirement (≥13.05 baseline; per-model: Air 3S ≥13.39, Mini 5 Pro
  ≥13.52; check the ExifTool changelog for newer models), how to install a
  recent ExifTool, and the per-model field-coverage caveat.
- `README.md`: note Air 3S / Mini 5 Pro are now usable **without** a sidecar SRT
  via `convert`/`verify-sun`, with the ExifTool-version caveat.
- `docs/user_guide.md` + `docs/decision-table.md`: mention `convert`/`verify-sun`
  accept an MP4 directly.

## Open decisions (resolved)

- **CSV camera columns from MP4:** **out of scope** for v1. CSV from an MP4 fills
  only the columns `TelemetrySample` models (geo, alt, `datetime_utc`, sun);
  camera columns stay blank rather than bloat the track model. A follow-up can
  add them via a richer CSV-specific extraction if there's demand.
- **Video suffixes:** `.mp4` + `.mov` only. `.lrf`/`.osv` proxies are out of
  scope (they carry no usable djmd GPS).
- **`shutter`/`fnum`/`ct` are decoded** by ExifTool for some models (Air 3S),
  but the extractor does not surface them in v1 — see the CSV decision above.

## Issue / roadmap mapping

- Implements the **convert + verify-sun** half of **#206 Stage 1** (ExifTool
  extractor). Embed fall-through and `--telemetry-source` are explicitly
  deferred to a follow-up.
- Unblocks sidecar-less **Air 3S** and **Mini 5 Pro** today; **Neo 2** and the
  rest of #182's model survey unlock automatically as ExifTool adds their
  protos (see the ExifTool DJI-protobuf changelog timeline).
- Aligns with the project's verification/provenance/mapping direction:
  sidecar-less footage gains GPX/GeoJSON/KML/CoT/CSV export and sun-based
  footage verification.
