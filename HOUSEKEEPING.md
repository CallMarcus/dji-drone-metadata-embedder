# Repository Housekeeping Recommendations

**Last refreshed:** 2026-04-19
**Current state:** v1.2.0, production-ready, ~13 remote branches (13 at the
time of writing), root directory already slim

---

## Context

This file started life in August 2025 as a cleanup plan for what was then a
132-branch repository with several ad-hoc release scripts at the root. Most
of that cleanup has already happened:

- **Branch count** is down from 132 to ~13 remote branches (`master`, active
  `feat/*`, `fix/*`, `chore/*`, plus Dependabot and Claude session branches).
- **Ad-hoc root scripts** (`create_github_release.ps1`, `create_release.ps1`,
  `create_release.sh`, `get-exe-info.ps1`, `create-issues.ps1`,
  `test-exe.ps1`) have all been removed. The only scripts still at the root
  are the three user-facing convenience wrappers below.
- **Cleanup scripts** `scripts/delete-stale-branches.sh` and
  `scripts/delete-stale-branches.ps1` are still available when branches
  accumulate again.

This document is kept as a living reference for the ongoing "keep it tidy"
work rather than as a one-shot cleanup plan.

---

## Current layout

### Root scripts (all user-facing – keep)

| File | Purpose |
|------|---------|
| `process_drone_footage.bat` | Windows double-click wrapper around `dji-embed embed` |
| `process_drone_footage.sh` | macOS/Linux shell wrapper around `dji-embed embed` |
| `run_diagnostic.bat` | Windows shortcut for `tools/diagnostic_script.py` |

If you add another script, put it in `scripts/` (developer tooling) or
`tools/` (release/packaging tooling) unless it is intended to be invoked by
end users.

### Test directories (both needed)

- `tests/` – fast, focused pytest suite (16 files, 55 tests at last count).
- `validation_tests/` – integration / E2E runners that need FFmpeg, ExifTool
  and real media to exercise fully. See `docs/ci_baseline.md` for expected
  pass/fail in minimal environments.

### Tools directory

All of these are actively referenced by CI or documentation — do not remove
without checking `.github/workflows/` and the relevant docs first:

- `tools/bootstrap.ps1` – Windows one-click installer.
- `tools/sync_version.py` – single-source version sync across package,
  bootstrap, spec, and winget manifests.
- `tools/build_exe.py` – PyInstaller build wrapper.
- `tools/diagnostic_script.py` – user-facing diagnostics (`run_diagnostic.bat`).
- `tools/test_exe.py` – post-build smoke checks for the EXE.
- `tools/cleanup_and_restructure.ps1` – retained as a historical cleanup
  helper; review before use.

---

## Ongoing housekeeping practice

### Branch hygiene

- Enable "Automatically delete head branches" in the GitHub repo settings so
  merged feature branches disappear on their own.
- When a long-lived branch goes cold, run
  `bash scripts/delete-stale-branches.sh` (or the `.ps1` equivalent) in
  dry-run mode first and then actually delete.
- Keep branch names aligned with the convention in `CLAUDE.md` §4: `feat/`,
  `fix/`, `docs/`, `ci/`, `chore/`, `claude/<session-id>`.

### Root directory

- User-facing wrappers only at the root. Anything else belongs under
  `scripts/` or `tools/`.
- Ad-hoc release scripts are not needed — `release-pypi.yml`,
  `release-exe.yml`, and `release-winget.yml` own those flows.

### Documentation hygiene

- Update `docs/development_roadmap.md` whenever a milestone ships or the
  direction of travel changes.
- Update `docs/ci_baseline.md` when you add tests or change dependencies so
  contributors know what "green" looks like today.
- Update `CHANGELOG.md` via the auto-changelog workflow — see
  `docs/CHANGELOG_AUTOMATION.md`. Avoid hand-editing historical sections.

### Repeat-cleanup checklist

When the repository drifts again, re-run this short list:

1. `git fetch --all --prune` and skim `git branch -r` for branches that are
   merged or older than ~3 months.
2. `ls` the repo root — anything new that is not user-facing should move
   into `scripts/` or `tools/` or be deleted.
3. `uv run ruff check src/ tests/` and `uv run pytest -q` to confirm the
   baseline from `docs/ci_baseline.md` still holds.
4. If you ran the validation suite, update the "Last verified" date on
   `docs/ci_baseline.md`.

---

## Historical notes

The original Phase 1 / Phase 2 / Phase 3 cleanup plan (deleting 125+ merged
branches, removing six ad-hoc PowerShell scripts, adding `.gitignore`
entries for development helpers) was executed between August 2025 and early
2026. It is no longer a live plan — the information has been distilled into
the practices above. If you need the full original text, it is available in
this file's git history.
