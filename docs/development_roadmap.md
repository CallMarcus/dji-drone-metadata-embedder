# Development Roadmap

_Last updated: 2026-06-21 · Current version: **v1.27.0** · Status: **Production Ready**_

This roadmap tracks the evolution of **DJI Drone Metadata Embedder**. The
original Phase 1–6 plan (standalone Windows GUI, dependency bootstrap,
packaging, release automation) is complete. This document now focuses on
what's been shipped and the remaining, forward-looking work.

Before starting new work, run the baseline checks documented in
[`ci_baseline.md`](ci_baseline.md) so you can distinguish real regressions
from pre-existing environmental gaps.

## Shipped

### Packaging & distribution
- Single-source versioning driven by `src/dji_metadata_embedder/__init__.py`
  and `tools/sync_version.py`.
- Tag-driven releases for PyPI, the Windows EXE, and winget (the winget
  workflow is currently parked and fires only on manual dispatch).
- PyInstaller spec (`dji-embed.spec`) and build script (`tools/build_exe.py`).
- PowerShell bootstrap installer (`tools/bootstrap.ps1`) for Windows users.
- `uv`-managed dependency set with a hash-verified `uv.lock`.

### CLI & processing
- Professional subcommand CLI (`dji-embed embed|validate|convert|check|doctor|ui`).
- Core embedding pipeline (`core/processor.py`) and SRT/MP4 drift validator
  (`core/validator.py`).
- Parsers for Mini 3/4 Pro, Air 3, Avata 2, and Mavic 3 Enterprise SRT
  formats, with golden fixtures in `samples/` and `tests/fixtures/`.
- Lenient parser mode with structured warnings, unit normalisation, and
  sanity checks for altitude/speed.
- CLI options for time offsets, resample strategy, GPS redaction (drop /
  fuzz), and machine-readable JSON logs (`--log-json`).
- Telemetry export to JSON, GPX, and CSV.
- DAT flight-log parsing and per-frame embedding helpers.

### UI
- Local web UI shipped as an optional extra (`pip install
  'dji-drone-metadata-embedder[ui]'`) and launched via `dji-embed ui`.
  Implemented in `src/dji_metadata_embedder/ui/` (Flask + templates + static
  assets + background job runner).
- The web UI is the supported interactive surface. A legacy `gui/` Tk
  skeleton was removed in the 2026-06 cleanup pass; no Tk work is planned.

### Testing & CI
- Unit test suite (`tests/`, 264 tests) covering parsing, embedding, DAT,
  redaction, sync, UI server, and CLI smoke.
- End-to-end validation suite (`validation_tests/`) for release verification
  when FFmpeg/ExifTool and real media are available.
- GitHub Actions CI matrix for Windows + Linux on Python 3.10–3.12
  (`.github/workflows/ci.yml`).
- Auto-changelog workflow from Conventional Commits
  (`auto-changelog.yml`, see `docs/CHANGELOG_AUTOMATION.md`).
- MkDocs documentation site built and deployed via `docs.yml`.

### Documentation
- User-facing: `README.md`, `docs/installation.md`, `docs/user_guide.md`,
  `docs/decision-table.md`, `docs/recipes.md`, `docs/troubleshooting.md`.
- Technical: `docs/SRT_FORMATS.md`, `docs/api.md`,
  `docs/external-tool-versions.md`, `docs/requirements-lock-policy.md`,
  `docs/validation_tests.md`.
- Contributor: `CONTRIBUTING.md`, `AGENTS.md`, `docs/RELEASE.md`,
  `docs/CHANGELOG_AUTOMATION.md`, and this roadmap.

## In progress / near-term

- **Keep the baseline honest.** When you touch parsing, FFmpeg command
  assembly, or the UI, re-run `uv run pytest -q` and — if you have the
  binaries — `validation_tests/run_all_tests.py`, then update
  `docs/ci_baseline.md` if expectations change.
- **Housekeeping follow-ups.** See `HOUSEKEEPING.md` for the current
  recommendations (branch hygiene, root-level scripts, `.gitignore`).

## Future direction

- **Additional DJI model coverage.** Tracked in
  [#182](https://github.com/CallMarcus/dji-drone-metadata-embedder/issues/182):
  survey Mini 5 Pro, Air 3S, Mavic 4 Pro, Neo, Avata 3, Mini 4K, Inspire 3,
  Matrice 4 / M30 / M350 RTK, and FPV v2 for SRT documentation and sample
  availability, then spin off per-model parser issues following the "Adding
  Support for New DJI Models" checklist in `AGENTS.md`.
- **Geospatial / mapping — SHIPPED.** The three-phase plan in
  [`docs/superpowers/specs/2026-06-04-flight-path-mapping-design.md`](superpowers/specs/2026-06-04-flight-path-mapping-design.md)
  is complete: GeoJSON/KML **track export** (#215/#223, `dji-embed convert
  geojson|kml`), the **standalone HTML viewer** (#221, `convert html`,
  Leaflet/OSM, no API key, v1.7.0), the **interactive map panel in the web UI**
  (#222, v1.9.0), and **camera-footprint polygons** (#215, `--footprint`,
  v1.9.0). Every renderer consumes the same GeoJSON. Remaining follow-ups are
  now tracked as issues:
  [#265](https://github.com/CallMarcus/dji-drone-metadata-embedder/issues/265)
  oblique-trapezoid / view-frustum footprints — **shipped**: frames with
  gimbal pitch project as ground trapezoids (clamped near the horizon),
  nadir rectangles remain the attitude-less fallback;
  [#266](https://github.com/CallMarcus/dji-drone-metadata-embedder/issues/266)
  terrain/DEM support via an optional `[terrain]` extra;
  [#267](https://github.com/CallMarcus/dji-drone-metadata-embedder/issues/267)
  flight playback animation in the flightmap viewer — **shipped** (play/
  pause, speed, scrubbing; per-point `times_s` in the flight GeoJSON); and
  [#268](https://github.com/CallMarcus/dji-drone-metadata-embedder/issues/268)
  a 3D terrain view (MapLibre `--3d` template, deliberately parked).
- **Richer web UI.** Incremental improvements to the Flask UI
  (`src/dji_metadata_embedder/ui/`) – nicer job progress, downloadable
  per-job artefacts, and richer previews – instead of new GUI frameworks.
- **Performance work on large batches.** Candidates include parallel
  per-clip embedding and streaming SRT parsing for long flights.
- **Winget catalog publish — live.** `CallMarcus.DJIMetadataEmbedder` is
  published in the public winget source (`winget install
  CallMarcus.DJIMetadataEmbedder`). The first-publisher submission
  [microsoft/winget-pkgs#391183](https://github.com/microsoft/winget-pkgs/pull/391183)
  (v1.11.0) merged 2026-07-06; version updates are filed manually per release via
  `gh workflow run release-winget.yml -f version=X.Y.Z`. The workflow stays
  `workflow_dispatch`-only and the three hand-maintained manifests in `winget/`
  remain in use. Remaining follow-up: fold the winget update step into the normal
  release cadence so the catalog stops lagging PyPI/EXE (a `winget-releaser`
  rewrite is one option, not required).

## Explicitly out of scope

- **Standalone Tk/Win32 GUI.** The `gui/` experiment was superseded by the
  packaged Flask UI and removed in the 2026-06 cleanup pass; no further Tk
  work is planned.
- **Winget-first install story.** Winget is demoted in the README until the
  manifests ship on a cadence that matches PyPI and the EXE release.
- **Re-encoding pipelines.** The project's contract is "no re-encode"; any
  feature that forces transcoding needs an RFC first.

## Milestone history

- **M1 – Stabilise & Version Cohesion** (Aug 2025) – single-source versioning,
  tag-driven release flow.
- **M2 – CI/Build Reliability** (Aug 2025) – Windows + Linux matrix, CLI
  smoke tests, locked dependency set.
- **M3 – Parser Hardening & CLI UX** (Aug 2025) – golden fixtures, lenient
  parser, professional subcommand CLI, validate command, JSON logging.
- **M4 – Docs, Samples & Release Hygiene** (Aug 2025) – decision table,
  recipes, troubleshooting expansion, auto-changelog.
- **v1.2 – UI & release polish** (2026) – Flask-based `dji-embed ui`, winget
  workflow parked, README install order reshuffled, Dependabot enabled.
