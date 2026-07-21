# AGENTS.md — guidance for AI coding agents and new contributors

> **Purpose:** This file is the starting point for anyone — human or AI
> assistant — making changes to this repository. It describes how the project
> is built, tested, and released, and the conventions changes must follow.
> It is a **living document**: keep it accurate when workflows change, and
> keep it **generic** — no maintainer-specific setup, credentials, private
> context, or environment details belong here.

## What this project is

**dji-drone-metadata-embedder** processes DJI drone footage locally:
it embeds SRT telemetry into MP4 videos (via FFmpeg, no re-encoding),
converts telemetry to GPX/CSV/GeoJSON/KML/CoT/HTML, and maps flights and
GPS-tagged photos as interactive HTML maps. Two front doors share one
engine: the `dji-embed` CLI (Python) and a Windows desktop app
(`gui/`, Avalonia/.NET) that shells out to the CLI over a JSONL contract.
Everything runs on the user's machine; nothing is uploaded anywhere.

## Repository map

```
src/dji_metadata_embedder/   Python package (CLI entry point: dji-embed)
├── cli.py                   Click commands
├── embedder.py              SRT→MP4 metadata embedding + SRT parsers
├── geo/                     photomap/flightmap/exports (one module per format)
├── core/                    processing pipeline, SRT validation
└── utils/                   ExifTool resolution + pinned provisioning
gui/                         Avalonia desktop app + headless xunit.v3 tests
tests/                       unit tests (pytest) — fast, run on every change
validation_tests/            E2E tests
samples/                     golden fixtures per DJI model
docs/                        user + developer docs (MkDocs)
tools/, scripts/             build/release/maintenance helpers
installer/                   Inno Setup script for the Windows installer
.github/workflows/           CI + tag-driven release automation
```

## Development setup

```bash
uv sync --extra dev            # install project + dev tools into .venv
uv run pytest -q               # unit tests
uv run dji-embed doctor        # verify the tool runs and finds dependencies
```

The GUI needs the .NET SDK (version per `gui/*/[*.csproj]` TargetFramework):

```bash
dotnet test gui/DjiEmbed.Gui.sln
```

## Before every commit — all three must pass

```bash
uv run pytest -q
uv run ruff check .
uv run mypy
```

CI enforces all three on Linux and Windows (Python 3.10–3.12) plus the GUI
test suite. If you touched `gui/`, also run `dotnet test gui/DjiEmbed.Gui.sln`.

## Conventions

- **Tests first.** Every behavior change ships with a test in `tests/` (or
  `gui/DjiEmbed.Gui.Tests/`). Use the golden fixtures in `samples/` for
  parser work.
- **Conventional Commits** (`feat:`, `fix:`, `docs:`, `ci:`, `test:`,
  `chore:`, `refactor:`) — the changelog is generated from them.
- **Branch names:** `feat/issue-<N>-<slug>`, `fix/issue-<N>-<slug>`,
  `docs/<slug>`, `ci/<slug>`, `chore/<slug>`.
- **PRs:** one issue/feature per PR, conventional-commit title, reference
  the issue (`Closes #N`).
- **Style:** PEP 8 via ruff, type hints on new functions, comment every
  non-obvious regex.

## Invariants — do not break these

- **No re-encoding.** Embedding must never transcode video.
- **Users' files are never modified.** Outputs are new files; originals
  (including their EXIF) stay untouched.
- **stdout is a contract.** Under `--progress jsonl`
  (see `docs/PROGRESS_JSONL.md`), stdout carries only JSONL events; all
  logging goes to stderr. The desktop app depends on this.
- **Pinned tooling.** ExifTool is provisioned at a pinned, checksum-verified
  version (`utils/provision.py`); the installer pins FFmpeg the same way.
  Bumps change the pin *and* the checksums, nothing else.
- **Privacy features are load-bearing.** `--redact`, `--popup-fields`, and
  friends exist so shared outputs disclose only what the user chose. Don't
  weaken them for convenience.
- **Never commit real footage or GPS-bearing media.** Test media lives in
  `samples/` as small, synthetic, or explicitly cleared fixtures.
- **Don't bump version numbers.** Versions are synchronized by
  `tools/sync_version.py` and driven by release tags; release automation is
  maintainer-run (see `docs/RELEASE.md`).

## When you change user-facing behavior, update the docs

| Change | Update |
| --- | --- |
| New CLI command/option | `README.md` + `docs/user_guide.md` |
| New DJI model support | `docs/SRT_FORMATS.md` + `README.md` model list |
| Mapping/geo features | `docs/geospatial.md` |
| Common problem solved | `docs/troubleshooting.md` |
| Anything an end-user's AI should know | `HELP.md` |

## Adding support for a new DJI model

1. Get sample SRT (and ideally MP4) files.
2. Add a parser pattern in `embedder.py` with the regex documented.
3. Add fixtures under `samples/<model>/` and tests against them.
4. Update `docs/SRT_FORMATS.md` and the README model list.

## GUI design constraints (binding)

The binding spec is now `docs/superpowers/specs/2026-07-18-gui-full-workspace-design.md`
("GUI 2.0") — read it before extending the desktop app. It amends the
original 2026-07-14 design: a single window, split into a source/mode/action
column on the left and a preview pane on the right, replaces the three
task-flow pages. The mode strip tops out at six modes (Embed, Flight map,
Photo map, Convert, Verify, Setup); M1 wires up four (Flight map, Photo map,
Embed, Setup), with Convert and Verify joining in M4. Options stay curated,
not exhaustive: they arrive in M3+, one *Advanced* expander per mode for the
long tail, exotic flags remain CLI-only. As of M4a, the SOURCE door also
accepts a single telemetry file (`.SRT`/`.MP4`/`.MOV`), not just a folder,
and Convert turns it (or a folder) into GPX/CSV/GeoJSON/KML/an HTML map/CoT. A WebView is now allowed, but
solely for the preview pane (arrives M2) — no other embedded browser
surface. There is still no settings dialog; the only state the app persists
is MRU folders and window bounds. The thin-frontend architecture is
unchanged: it shells out to the bundled CLI over the `--progress jsonl`
contract, users' original files are never modified, and no logic is
reimplemented in C#. The CLI remains fully supported and documented as a
first-class interface, not a fallback.
