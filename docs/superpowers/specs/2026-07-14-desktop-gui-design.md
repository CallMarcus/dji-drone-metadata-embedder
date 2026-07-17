# Desktop GUI design (issue #264, Stage 3)

**Date:** 2026-07-14
**Status:** Approved design, pre-implementation
**Interactive mockup:** https://claude.ai/code/artifact/0943eab6-45a0-481f-996b-3468fc5c96b8

## Problem

The v1.16 map features surfaced a non-technical audience (Reddit r/dji, mavicpilots)
that wants photo/flight maps but cannot use a terminal — for them, even
installation is a blocker. Issue #264 staged a path toward a no-CLI experience;
this document designs its end state: a genuine desktop application covering a
small set of novice tasks, while the full feature set remains CLI-only.

## Decisions and rationale

| Decision | Choice | Why |
|---|---|---|
| Relation to #264 | Design the end state now; quick wins still ship first | Stages build toward the app instead of being throwaway |
| GUI scope | Maps (photomap + flightmap), embed, check-my-setup | The proven novice draws; convert/export stays CLI-only |
| Distribution | Signed installer download from GitHub releases | Familiar to every Windows user; bootstrap.ps1 still means a terminal |
| External tools | Bundle pinned FFmpeg + ExifTool in the installer | Eliminates the #1 support pain; licenses permit redistribution with attribution |
| Shell technology | Native C# with **Avalonia** (Fluent theme) | See "Why not X" below |
| Map display | Generated HTML opens in the default browser | The GUI renders no web content at all |
| GUI/engine boundary | GUI shells out to the bundled `dji-embed` CLI | Clean process contract; engine stays 100 % Python |
| Repo layout | Same repo, `gui/` directory, .NET job in CI | Unified issues/releases/versioning; can split later if contributors appear |

### Why not the alternatives

- **pywebview wrapping the Flask UI** — rejected: "Flask in a frame" (a localhost
  server with a token inside a webview) is architecturally mushy, and the result
  looks like a web page, not Windows software.
- **Tauri** — rejected: fixes the server but the UI is still HTML/CSS in a
  WebView2; a native look would mean hand-rebuilding Fluent in CSS, plus a
  permanent Rust + npm toolchain tax on a solo-maintained Python project.
- **WPF / WinUI 3** — viable, but Windows-only forever. Avalonia keeps the door
  open to the #252 macOS audience (map users already exist there) with the same
  small codebase. Cross-platform is **deferred, not promised** — macOS needs its
  own packaging/notarization story later.

## Anti-bloat rules (binding)

The explicit design goal is to never become a long-lived open-source media tool
with a trillion features in irrational navigation paths.

1. **Task-first, not feature-first.** The home screen is a question
   ("What do you want to do?") with exactly three cards. Each task is one linear
   flow: folder in → progress → one result screen. No menu bar, no tabs, no
   settings dialog.
2. **Every option defaults to CLI-only.** A capability enters the GUI only when
   a real novice user asks for it *and* it fits an existing flow without adding
   a screen. The GUI is the decision-table made physical.
3. **The escape hatch is a sentence, not a pane.** Power users are pointed at
   the CLI in a footer line ("Need more control? `dji-embed --help`"). "Can the
   GUI also do X?" is answered with documentation, not another checkbox.
   *Amended 2026-07-17 (#293): the footer sentence became a link to a
   read-only CLI discovery screen — curated examples, a shell-launch button,
   the live `--help` output. Still no fourth task card, no settings.*

## Architecture

```
┌─────────────────────────────┐
│  Avalonia app (C#, gui/)    │   three task flows, folder picker,
│  - no web content           │   progress bar, done screen
│  - no Python interop        │
└──────────┬──────────────────┘
           │ subprocess + stdout JSONL
┌──────────▼──────────────────┐
│  dji-embed CLI (bundled     │   existing PyInstaller EXE,
│  PyInstaller EXE)           │   new --progress jsonl flag
└──────────┬──────────────────┘
           │
   bundled FFmpeg / ExifTool
```

### CLI progress contract (`--progress jsonl`)

New flag on the relevant subcommands (`photomap`, `flightmap`, `embed`,
`check`/`doctor`): emit one JSON object per line on stdout, schema roughly:

```json
{"event": "start",    "total": 214}
{"event": "progress", "current": 96, "total": 214, "item": "DJI_0042.JPG"}
{"event": "result",   "ok": true, "output": "D:/Drone/trip — map.html", "summary": {"photos": 214, "panos": 3}}
{"event": "error",    "message": "...", "item": "..."}
```

Exact schema to be finalised in the implementation plan; it gets golden,
schema-validated tests in the Python suite. This contract is Python-repo work
with standalone value (scripting, any future frontend) and ships before any C#
exists.

### The three flows (per the mockup)

- **Make a map** — pick/drop a folder; auto-detect photos vs flight logs (run
  photomap and/or flightmap accordingly); done screen names the output file in
  plain words; "Open map" launches the default browser.
- **Embed telemetry** — pick/drop a folder of MP4+SRT; progress per file;
  originals never modified (new copies alongside), and the UI says so.
- **Check my setup** — doctor as a checklist with novice wording ("Video tools
  (FFmpeg) — bundled 7.1"). This screen is the only place the app checks for
  updates, reusing the #277 doctor consent philosophy and logic.

Copy tone throughout: novice-first ("Photos stay on this computer"), no flag
names, no jargon.

## Packaging

- Inno Setup installer (initially), signed, from GitHub releases: Avalonia app,
  the existing `dji-embed.exe`, pinned FFmpeg + ExifTool builds, Start-menu
  entry, uninstaller.
- Defender false-positive exposure of the bundled PyInstaller CLI persists;
  mitigations: sign the installer, pre-flight the binaries through WDSI before
  release (per the winget playbook), prefer one-dir PyInstaller layout.

## Revised staging (rewrites #264)

1. **Stage 1 (kept):** drag-a-folder-onto-the-EXE → map opens. Tiny, ships in a
   patch release.
2. **Stage 2 (replaced):** ~~bundle Flask UI into the EXE~~ → **CLI progress
   contract** (`--progress jsonl` + golden tests). The Flask-UI bundling stage
   is cut: it invests in the architecture this design rejects.
3. **Stage 3:** Avalonia app + installer, scope frozen to the mockup.

## Testing

- Python: golden JSONL-contract tests (schema-validated), normal unit/CI matrix.
- GUI: Avalonia headless test layer for flow logic; manual E2E against the
  local real-footage stash before releases.
- CI: add a .NET build/test job scoped to `gui/`.

## Non-goals

- No GUI settings screen, preferences file, or option panes.
- No convert/export in the GUI (CLI-only).
- No self-update mechanism (installer download instead; see #277 rationale).
- No inline map rendering, no embedded webview of any kind.
- No macOS/Linux packaging in the first release (Avalonia keeps it possible).
