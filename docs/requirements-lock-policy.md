# Dependency Lock Policy

This project uses [`uv`](https://docs.astral.sh/uv/) with a checked-in
`uv.lock` file to ensure reproducible builds across different environments
and CI runs.

## Overview

- **`pyproject.toml`** — declares runtime dependencies and optional groups
  (`dev`, `build`, `docs`) with flexible version ranges for end users.
- **`uv.lock`** — contains the fully resolved, hash-verified versions of
  every direct and transitive dependency. Checked into the repository.
- **CI builds** consume `uv.lock` via `uv sync` for byte-identical installs.
- **End users** installing with plain `pip install dji-drone-metadata-embedder`
  still get the flexible ranges from `pyproject.toml`.

## Updating the Lock File

### When to Update

Regenerate `uv.lock` when:

- Adding or removing dependencies in `pyproject.toml`
- Security advisories affecting a pinned version
- Bug fixes in a dependency we need
- Routine maintenance (e.g. monthly dependency bumps)

### How to Update

1. **Edit `pyproject.toml`** if you're adding or changing a dependency.

2. **Regenerate the lock file:**

   ```bash
   uv lock
   ```

   To bump everything to the latest compatible versions without touching
   `pyproject.toml`:

   ```bash
   uv lock --upgrade
   ```

   To bump just one package:

   ```bash
   uv lock --upgrade-package ruff
   ```

3. **Sync and run the tests** to make sure nothing broke:

   ```bash
   uv sync --extra dev
   uv run pytest
   uv run ruff check .
   uv run mypy
   ```

4. **Commit the updated `uv.lock`** alongside any `pyproject.toml` changes
   in the same commit so CI and local installs stay in sync.

## CI Integration

The CI pipeline uses `uv sync` with the checked-in `uv.lock` so every job
installs byte-identical dependencies. This gives us:

- Consistent behaviour across all builds
- Early detection of dependency-related regressions
- Reproducible release artefacts
- Hash-verified downloads (uv enforces this automatically)

The GitHub Actions `astral-sh/setup-uv` action caches `~/.cache/uv` keyed
on `uv.lock`, so lock-file changes automatically invalidate the cache.

## Troubleshooting

### `uv sync` fails locally

1. Make sure your Python version is supported (3.10+). `uv` can install a
   matching interpreter for you with `uv python install 3.12`.
2. Upgrade `uv` itself: `uv self update` (or reinstall from
   <https://docs.astral.sh/uv/>).
3. If the resolver reports a conflict, re-run `uv lock` to see the
   constraint that's failing and adjust `pyproject.toml` accordingly.

### Lock file drift

If `uv.lock` is out of sync with `pyproject.toml`, `uv sync` will fail with
a clear error. Run `uv lock` to regenerate, review the diff, then commit.
