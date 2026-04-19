# Development Roadmap

_Last updated: 2026-04-19 · Current version: **v1.2.0** · Status: **Production Ready**_

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
- Legacy `gui/` Tk skeleton remains as a placeholder but is **not** the
  direction of travel; the web UI is the supported interactive surface.

### Testing & CI
- Unit test suite (`tests/`, 55 tests) covering parsing, embedding, DAT,
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
- Contributor: `CONTRIBUTING.md`, `CLAUDE.md`, `docs/RELEASE.md`,
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
  Support for New DJI Models" checklist in `CLAUDE.md` §7.
- **Richer web UI.** Incremental improvements to the Flask UI
  (`src/dji_metadata_embedder/ui/`) – nicer job progress, downloadable
  per-job artefacts, and richer previews – instead of new GUI frameworks.
- **Performance work on large batches.** Candidates include parallel
  per-clip embedding and streaming SRT parsing for long flights.
- **Winget re-enablement.** Blocked on
  [#175](https://github.com/CallMarcus/dji-drone-metadata-embedder/issues/175):
  `CallMarcus.DJIMetadataEmbedder` needs a manual first-publisher submission
  to `microsoft/winget-pkgs`, after which `release-winget.yml` should be
  rewritten on top of `winget-releaser` and the three hand-maintained
  manifests in `winget/` retired. The workflow currently fires only on
  manual dispatch.

## Explicitly out of scope

- **Standalone Tk/Win32 GUI.** The experiment in `gui/` is superseded by the
  packaged Flask UI; no further Tk work is planned. The folder stays until a
  cleanup pass removes the skeleton.
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
