# GUI: Flight map 3D terrain toggle (#366)

**Date:** 2026-07-25
**Issue:** #366 — follow-up to #268 / PR #365 (CLI `flightmap --3d`, shipped in v2.1.0)
**Scope:** GUI-only, one PR. The CLI is untouched.

## Goal

Expose `flightmap --3d` in the desktop app's Flight map mode: a curated
toggle that switches the run to the MapLibre 3D terrain map
(`flightmap-3d.html`), with the CLI transparency strip, the existing-map
panel, and the inline preview all following along.

## CLI facts the design rests on

Verified against `cli.py` (v2.1.0):

- `--3d` writes **only** `flightmap-3d.html` in that run (instead of, not
  alongside, `flightmap.html`). The default filename keeps the 2D map from
  being overwritten.
- `--3d` with `--format` other than `html` (including `all`) raises a
  **UsageError** — an illegal argv, not a warning.
- `--3d` with a non-default `--tile-style` is a **warning** (flag ignored):
  the 3D map has its own terrain/hillshade rendering.
- `--redact fuzz`, `--join-gap`, `--tz-offset`, `--title`, and `--output`
  all apply normally in 3D.
- The JSONL `result` event carries the written path, so the GUI's existing
  `Outputs` → `PrimePreviewAsync` plumbing previews the 3D map with no
  changes.

## Decisions (design round, 2026-07-25)

1. **Conflicting options disable + suppress** (Marcus's pick): while 3D is
   on, the Map style combo and the Advanced "Also export KML + GeoJSON"
   checkbox grey out, and the builder omits `--tile-style`/`--format` from
   the argv. User choices are preserved and return when 3D is unchecked.
   The strip stays honest: it never shows a flag the CLI would ignore or
   reject.
2. **Suppression lives in `CommandBuilder.FlightMap`** (approach A):
   `FlightMapOptions` stays a faithful snapshot of the UI; knowledge of CLI
   flag semantics belongs in the builder, whose charter is "single source
   of truth for the argv". Directly golden-testable.

## Design

### Options state

- `FlightMapOptions` gains `bool ThreeD`, default `false` in `Defaults` —
  the untouched-argv invariant `flightmap <folder> -r` is unchanged.
- `FlightMapOptionsViewModel` gains `[ObservableProperty] bool ThreeD`
  (default `false`) and passes it through `ToOptions()`.
- Like every option except `Output`, `ThreeD` survives a folder change.

### CommandBuilder.FlightMap

- Emits `--3d` immediately after `-r` (fixed position for golden tests):
  an untouched 3D run reads `flightmap <folder> -r --3d`.
- When `opts.ThreeD` is true, the `--tile-style` and `--format all`
  branches are skipped regardless of their values. All other flags pass
  through unchanged.
- Every argv reachable from the panel remains legal by construction — no
  new pre-run guards needed.

### Panel (WorkspaceView.axaml, Flight map options)

- New `ToggleSwitch`, label **"3D terrain map"**, `Name` +
  `AutomationProperties.Name` per house pattern. Placed in the curated
  section directly under "Include subfolders" and above Map style, so the
  greyed combo sits under its cause.
- Map style `ComboBox`: `IsEnabled` bound to `!FlightOptions.ThreeD`
  (composes with the panel-level `!IsBusy`).
- Advanced "Also export KML + GeoJSON" `CheckBox`: same `IsEnabled`
  binding.
- One quiet note (FontSize 11, Opacity 0.5 — the `LinkReachNote`
  precedent), visible only while 3D is on: *"Map style and KML/GeoJSON
  export don't apply to the 3D map."* It exists because the export toggle
  hides inside the collapsed Advanced expander, where its greying would
  otherwise be invisible.

### ExistingMapFinder

- Third probe: `<folder>/flightmap-3d.html`, title **"Flight map (3D)"**,
  staleness against `NewestFlightLogUtc` exactly like the 2D probe.
- List order: Flight map, Flight map (3D), Photo map.
- Doc comment updated: the deterministic default paths are now three.
- Out-of-scope unchanged (#328 spec): maps redirected by "Save map to"
  are not discovered.

### Save picker

- The "Save the flight map as" picker's suggested filename
  (`WorkspaceView.axaml.cs`, currently hardcoded `flightmap.html`)
  becomes `flightmap-3d.html` while the toggle is on.

### Preview

- No plumbing changes. WebView2 is Chromium, so WebGL renders the
  MapLibre map; terrain tiles arrive over the network, and the HTML's own
  terrain-failure banner covers the offline case.
- Real-hardware verification of the inline 3D preview stays a manual
  checklist item (issue #366) for Marcus.

## Tests (TDD, house pattern)

- **CommandBuilderTests goldens:** `--3d` position after `-r`; the
  suppression case (`ThreeD` + non-default tile style + `ExportAll` →
  argv contains neither `--tile-style` nor `--format`); pass-through case
  (`ThreeD` + fuzz + join-gap + title + output all emitted); defaults
  unchanged.
- **FlightMapOptionsViewModelTests:** `ThreeD` defaults false;
  `ToOptions()` carries it.
- **ExistingMapFinderTests:** 3D probe found / absent / stale; ordering
  with all three present.
- **XAML binding tests (#336 pattern):** named toggle +
  `Assert.Same`-style binding check to `FlightOptions.ThreeD`;
  disabled-state assertions for the Map style combo and export checkbox
  with 3D on.
- **A11y contract:** picks the new named control up automatically (it is
  unconditionally visible in Flight map mode — no new representative
  window state needed).
- The strip needs no separate test: it renders builder output, and #334's
  strip/run parity concern is unchanged by this slice.

## Docs

- One-line mentions in `HELP.md` and `docs/desktop-app.md` (Flight map
  mode: 3D terrain toggle).

## Non-goals

- No CLI changes; no `--3d` for photomap (doesn't exist).
- No pitch/hillshade tuning controls (taste constants accepted 2026-07-25
  after Marcus's real-footage check).
- No re-probe of existing maps after a run (known #328 limitation,
  unchanged).
