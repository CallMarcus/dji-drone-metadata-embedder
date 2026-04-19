# CI Baseline – Known Good Expectations

_Last verified: 2026-04-19 on Linux with Python 3.11.15 and `uv` 0.8.17._

The project's roadmap expects contributors to run validation before adding new
work. This page records the "known good" pass/fail baseline so you can tell a
real regression from a pre-existing environmental gap.

## How to reproduce

```bash
uv sync --extra dev --extra ui
uv run ruff check src/ tests/
uv run pytest -q
uv run python validation_tests/run_all_tests.py   # requires FFmpeg + samples
```

## Baseline results

| Suite | Command | Expected result |
|-------|---------|-----------------|
| Lint | `uv run ruff check src/ tests/` | `All checks passed!` |
| Unit tests | `uv run pytest -q` | **55 passed** (fast, < 5 s) |
| CLI smoke | `uv run dji-embed --version` | Prints version plus availability of FFmpeg/ExifTool |
| Validation – Installation & Dependencies | `validation_tests/test_installation_and_dependencies.py` | Passes only when FFmpeg + ExifTool are on `PATH`. FFmpeg/ExifTool missing ⇒ expected failure outside release CI |
| Validation – SRT Parsing | `validation_tests/test_srt_parsing.py` | Passes against the bundled `samples/` fixtures |
| Validation – Video Processing / Advanced / E2E | remaining scripts in `validation_tests/` | Require both FFmpeg and real MP4 media; they are **expected to fail** in minimal environments that only ship the small public SRT samples |

## Environmental gaps that look like failures

The validation suite was originally written for Windows developer machines
with FFmpeg, ExifTool, and private MP4 fixtures installed. In a clean clone
(or in containerised CI without those dependencies) you should expect:

- `ffmpeg not available` and `exiftool not available` in `dji-embed doctor`
  and `--version` output.
- `validation_tests/run_all_tests.py` reporting **1/5 suites passing** (only
  the `Error Handling` subset of the End-to-End integration runner green),
  because the other suites bail out on missing binaries or missing `.MP4`
  inputs.

None of these are regressions. Treat them as blocking only when you are
testing a build that is supposed to ship FFmpeg (e.g. the PyInstaller
artifact or the Docker image).

## What CI actually enforces today

GitHub Actions workflows in `.github/workflows/`:

- `ci.yml` – runs `ruff` + `pytest` on Windows and Linux across Python
  3.10–3.12. This is the authoritative gate for PRs.
- `release-pypi.yml`, `release-exe.yml`, `release-winget.yml` – triggered on
  `vX.Y.Z` tags. These stages install FFmpeg/ExifTool as needed.
- `auto-changelog.yml` – updates `CHANGELOG.md` from Conventional Commits.
- `docs.yml` – builds the MkDocs site.

If `uv run pytest -q` is green and `uv run ruff check` is clean, your branch
matches the PR gate. Run the validation suite before cutting a release or
whenever you change parsing / FFmpeg command assembly; otherwise the unit
tests and golden fixtures are sufficient for day-to-day development.

## Updating this baseline

Bump the "Last verified" date and adjust the pass counts whenever you add
tests or change dependencies. Keep the expectations terse – this file exists
so a new contributor can tell at a glance whether their local failures are
real bugs or pre-existing environmental gaps.
