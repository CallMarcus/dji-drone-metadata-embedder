# Design: Avata 360 + Mini 5 Pro support

_Date: 2026-05-30_

## Context

Two new model samples arrived via a mavicpilots.com submission:

- `samples/Avata360/` — `.OSV` (360 video), `.LRF` (low-res proxy), `.SRT`. No `.MP4`.
- `samples/Mini5PRO/` — `.MP4`, `.SRT`.

Both SRTs use the standard HTML-wrapped bracketed format
(`<font>...[iso:][shutter:][fnum:][latitude:][longitude:][rel_alt: abs_alt:]...`),
which the parser already supports. Running `DJIMetadataEmbedder.parse_dji_srt`
against both extracts GPS, altitude, ISO, shutter, EV, color mode, and focal
length; both validate as the existing `html_extended` format family.

`.OSV` and `.LRF` are ISO BMFF (MP4-family) containers — same
`ftyp isom/iso2/mp41` brands as a normal DJI `.MP4`, plus extra boxes for 360
metadata (`covr`, `snal`, `camd`). ffmpeg can read them.

## Goals

Full support for both models: parser fix, video discovery, golden fixtures,
tests, and docs.

## Non-goals

- Parsing the 360-projection metadata inside `.OSV` boxes.
- Transcoding or stitching 360 footage.
- DAT flight-log handling (none provided in the samples).

## Changes

### 1. Decimal `fnum` fix — `embedder.py`

The aperture regex `\[fnum\s*:\s*(\d+)\]` matches integers only, so
`fnum: 1.9` / `fnum: 1.8` is silently dropped — for these two models and for
every modern DJI model with a decimal aperture. Change to
`\[fnum\s*:\s*([+-]?\d+\.?\d*)\]`, matching the existing lat/lon/alt patterns.

Scope check: `utilities.parse_telemetry_points` does not read `fnum`, and
`core/validator.py` format detection does not depend on it. Single-site fix.

### 2. Video discovery — `.OSV` and `.LRF` — `embedder.py::process_directory`

Current discovery globs `*.mp4` + `*.MP4`. Extend the set to also include
`*.osv`, `*.OSV`, `*.lrf`, `*.LRF`. Output naming
(`{stem}_metadata{suffix}`) already preserves arbitrary extensions, so
Avata 360 yields `..._metadata.OSV` (and `..._metadata.LRF`) with the SRT
muxed in via the existing `-c copy` path. Mini 5 Pro is a plain `.MP4` and
needs nothing new.

Note: `.LRF` is a low-res proxy sharing the `.OSV` stem and the same `.SRT`.
Including it (per user decision) means each Avata clip is processed twice and
produces both `_metadata.OSV` and `_metadata.LRF` outputs. This is intended.

### 3. `.gitignore` safety

`*.OSV` / `*.LRF` are not currently ignored, so the raw 60–180 MB samples
could be committed by accident. Add `*.OSV`, `*.osv`, `*.LRF`, `*.lrf`.
Trimmed `clip.SRT` fixtures are force-added (`git add -f`), the same way the
existing model fixtures are tracked despite the `*.SRT` ignore rule.

### 4. Golden fixtures + tests

- `samples/Avata360/clip.SRT`, `samples/Mini5PRO/clip.SRT` — trimmed to ~5
  frames from the real SRTs, following the existing ~7-line `clip.SRT`
  convention.
- Add both to `GOLDEN_SAMPLES` in `tests/fixtures/golden_srt_samples.py` with
  expected point counts and coordinates, including a decimal-`fnum`
  assertion that locks the bug fix.
- Add two tests to `tests/test_golden_fixtures.py`; both assert
  `format_detected == "html_extended"` (they are genuinely that family — no
  new format vote is required in the validator).

### 5. Docs

- `README.md` "Supported DJI Models" — add **DJI Avata 360** (360 `.OSV`
  container) and **DJI Mini 5 Pro**.
- `docs/SRT_FORMATS.md` — document both; note Avata 360's extra
  `pp_*`/stabilization tokens and the `.OSV`/`.LRF` containers.
- `docs/troubleshooting.md` — short note on `.OSV` handling and that `.LRF`
  proxies are also processed.

## Verification

- `uv run pytest -q` (new golden tests pass, existing suite stays green).
- Parser run against the full real SRTs confirms `fnum` is now captured.
