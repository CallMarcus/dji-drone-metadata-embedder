# GUI full-feature workspace design ("GUI 2.0")

**Date:** 2026-07-18
**Status:** Approved design, pre-implementation
**Amends:** `2026-07-14-desktop-gui-design.md` (issue #264 Stage 3 design)

## Problem

The shipped desktop app deliberately covers three fixed flows with zero
configurable options — 4 of the CLI's 10 user-facing commands, none of its
~50 flags. That minimalism was the right first release. It also leaves the
app a launcher, not a tool: users who outgrow the defaults fall off a cliff
straight into the terminal, and most of the project's capability (convert,
verify, redaction, tile styles, footprints, formats) is invisible to the
audience the GUI was built for.

This design takes the deliberate next step: one modern, uncluttered window in
which **every CLI task is a mode** with curated options, novices still succeed
on defaults alone, and the CLI remains a fully supported first-class UX. The
direction, structure, and theme were decided with the maintainer in a
mockup-driven brainstorm on 2026-07-18.

## Decisions and rationale

| Decision | Choice | Why |
|---|---|---|
| Feature scope | All tasks, curated options | Every CLI task becomes a GUI mode; meaningful options surface as controls; exotic flags stay CLI-only (~90 % of real-world capability without option sprawl) |
| Structure | Split workspace, one window | Controls run down the left (source → mode → options → action); preview fills the right. No menu bar, no tabs, no navigation chrome |
| Result display | **Inline preview pane (WebView)** | Avalonia 12 bundles WebView for free; MapServer loopback already exists. Repeals the 07-14 "no webview" non-goal — see Amendments |
| Home screen | Reborn as the preview pane's idle state | Photo identity, task cards, recent folders live where the eyes land, then get out of the way. No splash screen to click through |
| Theme | **SukiUI** (MIT, v7 2026-05, desktop-only) | Richly animated controls, glass cards, toasts/dialogs/busy states out of the box — the "2026 feel" comes from the library, not hand-built polish |
| Engine boundary | Unchanged: thin frontend over `--progress jsonl` | The Python CLI stays the only engine; no logic reimplemented in C# |
| Mode count | Six: Embed, Flight map, Photo map, Convert, Verify, Setup | `check`+`validate`+`verify-sun` merge into Verify; `serve`/`dragdrop` are plumbing; `ui` is deprecated |

## Amendments to the anti-bloat rules

The 2026-07-14 rules stay binding in spirit; three are formally amended here
rather than worked around:

1. **"Exactly three cards" → six modes.** Still task-first: a mode strip, not
   a menu system. Still no menu bar, no tabs, no settings dialog.
2. **"Every option defaults to CLI-only" → curated options in the GUI.**
   An option earns a control when it changes a novice-meaningful outcome *and*
   is expressible as a dropdown, slider, toggle, or chip set (free text only
   where unavoidable: title, timezone). Each mode gets exactly one *Advanced*
   expander for the long tail. Exotic flags (`--dat`, `--cot-type`,
   `--link-base`, serve plumbing, `--force`…) stay CLI-only.
3. **"The escape hatch is a sentence" → the escape hatch is the truth.**
   A CLI transparency strip under the action button shows the equivalent
   command building live as controls change, with a copy button — the #293
   discovery screen grown into a teaching bridge.
4. **"No embedded webview of any kind" — repealed.** The cost rationale is
   gone (WebView is open source and bundled in Avalonia 12) and the serve
   infrastructure the pane needs shipped with #305/#271.

**Unchanged invariants:** GUI shells out to the bundled `dji-embed` over the
JSONL contract; originals never modified; stdout-is-a-contract; no self-update;
no settings dialog — the only persisted GUI state is MRU folders and window
bounds; the CLI remains fully supported and documented.

## The workspace

Resizable window, default ~1140×720, minimum ~980×640. Left pane, top to
bottom (scrolls if needed):

- **Source** — drag-and-drop hero plus Browse buttons; selected items as
  removable chips. Folders always; single files where the mode allows
  (Convert, Verify).
- **Mode strip** — the six modes as compact cards. Dropping a source makes
  `FolderInspector` highlight a suggested mode; the user can always override.
  Switching modes re-renders the options area.
- **Options** — curated controls per mode (table below). Smart defaults: the
  action button produces a useful result with nothing touched. One *Advanced*
  expander per mode.
- **Action** — one big verb per mode ("Generate flight map", "Embed
  telemetry"…), the CLI transparency strip beneath it.

Right pane — the **preview pane**, four states:

| State | Content |
|---|---|
| Idle | The reborn home: photo background, task cards (preselect a mode), recent folders |
| Running | Progress ring + per-file detail ("DJI_0042.SRT · 3 of 12", from `FlowViewModel.ProgressDetail`) + Cancel |
| Done (map modes) | The interactive map / 360° pano in a WebView over the MapServer loopback; toolbar: Open in browser ↗, Show in folder |
| Done (other modes) | Result card: summary line, warnings expander, output path, quick actions (Open folder, Process another) |

## Mode-by-mode option curation

| Mode | Source | Curated controls | Advanced expander |
|---|---|---|---|
| Flight map | folder | map style, privacy (keep/fuzz), join-gap slider, footprints toggle (+interval slider) | timezone, extra formats (KML/GeoJSON chips), title, output location |
| Photo map | folder | map style, privacy, recursive, link-to-originals | popup fields (chips), title, formats, output |
| Embed | folder | privacy (none/drop/fuzz), container (MP4/MKV), extract HOME point | audio sidecar, ExifTool GPS injection, DAT log (+auto), overwrite, output |
| Convert | file or folder (batch) | format (GPX/CSV/GeoJSON/KML/HTML/CoT), privacy | timezone, footprints (+interval), CoT interval+type (visible only when CoT), model, output |
| Verify | files/folder | sub-action switch: Check metadata / Validate pairing / Sun check | drift threshold, timezone |
| Setup | none | doctor checklist, Install-ExifTool button | update-check consent toggle (#277 philosophy) |

Grace notes: contextual-within-contextual is allowed (CoT settings appear only
when CoT is the chosen format); Verify renders reports as cards in the preview
pane, never raw text dumps.

## Architecture

```
┌──────────────────────────────────────────────┐
│ Avalonia 12 app (SukiUI theme)               │
│  WorkspaceView                               │
│   ├─ per-mode ViewModel + CommandBuilder ────┼── argv (single source of
│   ├─ preview pane (WebView ⇄ MapServer)      │   truth: run + CLI strip)
│   └─ FlowViewModel machinery (reused)        │
└──────────────┬───────────────────────────────┘
               │ subprocess + stdout JSONL (unchanged)
┌──────────────▼───────────────────────────────┐
│ dji-embed CLI (bundled PyInstaller EXE)      │
└──────────────────────────────────────────────┘
```

- **Command builder per mode** — each mode ViewModel owns typed option state
  and one builder producing the argv, consumed by both the runner and the
  transparency strip. Golden-testable: option state in, expected argv out.
- **Runner and contract unchanged** — `DjiEmbedRunner`, strict-success rule,
  cancellation all carry over.
- **CLI work item (additive):** extend `--progress jsonl` to `convert`,
  `validate`, and `verify-sun` (the schema's catch-all already tolerates new
  emitters). Ships before M4.
- **Preview** — `WebView` pointed at the MapServer loopback URL (`serve`
  already emits the `serving` event before `result`); panos and playback work
  because loopback HTTP solved the `file://` restrictions in #305/#271.
- **GUI state on disk** (decision previously deferred from #292): one small
  JSON in the user config dir (e.g. `%APPDATA%/DjiEmbed/state.json`) holding
  MRU folders and window bounds. Nothing else, ever, without a spec amendment.
- **Theme adoption** — SukiUI replaces the plain Fluent theme; the five
  existing views are restyled or absorbed into the workspace during M1.

## Errors and degradation

- Failure state lives in the preview pane: friendly message, last-lines stderr
  tail + Copy details (reuse the #303 `ErrorDetailsTail`/`ClipboardCopy`
  machinery), per-file failures via the existing warnings pattern.
- Missing OS WebView runtime (old Win10 without Edge WebView2): degrade
  gracefully to today's behavior — results open in the browser, one calm
  note in the pane. Never an error dialog.

## Testing

- GUI: headless xunit suite carries over. The locked "three cards + footer
  link" home-contract tests are **formally retired**, replaced by workspace
  contract tests: six modes present, options render per mode, Advanced
  expanders close by default, argv golden tests per command builder.
- Screenshot matrix via `DJIEMBED_CAPTURE_DIR` covering every mode × pane
  state for visual review.
- Python: golden JSONL tests for the three newly instrumented commands.
- Manual E2E against the local real-footage stash before each milestone
  release.

## Milestones (each independently releasable)

1. **M1 — Workspace shell.** SukiUI, resizable window, Source/Mode-strip/
   Action layout wiring only today's tasks; the strip shows four modes
   (Flight map, Photo map, Embed, Setup — Convert and Verify appear in M4),
   no options yet; preview pane does idle/running/done-card states
   (no WebView). Ships as a visible refresh on its own.
2. **M2 — Inline preview.** WebView + MapServer in the pane, browser pop-out,
   pano state, WebView-missing degradation.
3. **M3 — Options + CLI strip.** Command builders, curated controls for the
   map modes + Embed, Advanced expanders, live transparency strip.
4. **M4 — New modes.** Convert and Verify join the strip (after the CLI
   JSONL extension), completing the six modes.
5. **M5 — Polish.** Animations, empty-state hero, MRU, accessibility pass,
   docs/screenshots, announcement.

## Non-goals

- No settings screen or preferences beyond MRU folders + window bounds.
- No processing logic in C#; the CLI remains the only engine.
- No self-update (unchanged, #277 rationale).
- No macOS/Linux packaging in this arc (Avalonia + SukiUI keep it possible).
- No telemetry of any kind.
- Exotic flags stay CLI-only; "can the GUI also do X?" is still answered with
  the transparency strip and documentation before another control.
