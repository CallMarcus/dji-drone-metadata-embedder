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

## Pending: first Dependabot run (2026-04-19)

Dependabot's first run opened two grouped PRs that will shift the numbers
above once merged. Re-run the commands in this file and update the recorded
versions when either lands:

- **[#180](https://github.com/CallMarcus/dji-drone-metadata-embedder/pull/180)
  — `actions` group (8 updates).** `actions/checkout 4→6`,
  `actions/setup-python 5→6`, `astral-sh/setup-uv 5→7`,
  `peter-evans/create-pull-request 6→8`, `actions/upload-pages-artifact 3→5`,
  `actions/configure-pages 4→6`, `actions/deploy-pages 4→5`,
  `softprops/action-gh-release 2→3`. No local effect, but the CI matrix in
  `.github/workflows/ci.yml` needs to go green on the new versions.
- **[#181](https://github.com/CallMarcus/dji-drone-metadata-embedder/pull/181)
  — `development-deps` group (9 updates).** `pytest 8.3.2→9.0.3`,
  `pytest-cov 5.0.0→7.1.0`, `coverage 7.6.0→7.13.5`, `black 24.4.2→26.3.1`,
  **`ruff 0.4.6→0.15.11`**, `mypy 1.8.0→1.20.1`, `build 1.2.1→1.4.3`,
  `hatchling 1.25.0→1.29.0`, `twine 5.1.1→6.2.0`. The ruff jump is the
  biggest risk — the 0.5–0.15 series enabled several new default rules, so
  "ruff clean" on `master` is not guaranteed to hold on this branch. Run
  `uv sync --extra dev` + `uv run ruff check src/ tests/` on the branch
  before merging and fix any new lint findings in the same PR.
  _Verified locally 2026-04-19: on the Dependabot branch
  `uv run ruff check src/ tests/` is clean and `uv run pytest -q` reports
  55 passed (41 passed + 14 UI tests when `--extra ui` is installed)._

## Updating this baseline

Bump the "Last verified" date and adjust the pass counts whenever you add
tests or change dependencies. Keep the expectations terse – this file exists
so a new contributor can tell at a glance whether their local failures are
real bugs or pre-existing environmental gaps.
