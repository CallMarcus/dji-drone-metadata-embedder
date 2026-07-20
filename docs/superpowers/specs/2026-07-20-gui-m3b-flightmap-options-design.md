# GUI 2.0 — M3b: Flight map curated options + Advanced expander

**Parent spec:** `docs/superpowers/specs/2026-07-18-gui-full-workspace-design.md`
(GUI 2.0 full-workspace design; this is the M3b milestone slice.)

**Predecessor:** M3a shipped `CommandBuilder` (per-mode argv, one source of
truth for run + strip) and the live CLI transparency strip. M3b is the first
mode to grow curated options that feed that seam.

## Goal

Give the **Flight map** mode a curated options panel between the MODE strip and
the ACTION button. Each control maps to an existing `flightmap` CLI flag; the
typed option state flows through `CommandBuilder` into both the executed run and
the live CLI strip. No new CLI features — M3b surfaces capability that already
exists.

## Context: the real `flightmap` flag surface

`flightmap` (src/dji_metadata_embedder/cli.py) accepts: `directory` (the folder,
from the Source picker), `-o/--output`, `-f/--format` (`html`/`kml`/`geojson`/
`all`, default `html`), `-r/--recursive`, `--title`, `--redact` (`none`/`fuzz`,
default `none`), `--join-gap SECONDS` (default `15.0`), `--tz-offset` (default
`auto`), `--tile-style` (default `osm`), plus `--progress`/`-v`/`-q`.

Tile-style keys (src/dji_metadata_embedder/geo/tiles.py): `osm` (default),
`osm-hot`, `opentopomap`, `cyclosm`.

**Footprints are NOT a flightmap capability.** `--footprint`/`--footprint-interval`
live only on `convert` (per-clip, redact=none only, needs the FOV/model table).
The parent spec's "footprints toggle" for Flight map was aspirational; per the
2026-07-20 brainstorm it is **dropped from M3b** and belongs to Convert mode
(M3c+). No CLI work is added here.

## Curated controls (always visible when Flight map is selected)

| Control | Shape | Default | argv effect |
|---|---|---|---|
| **Include subfolders** | `ToggleSwitch` | ON | `-r` when on; omit when off |
| **Map style** | `ComboBox` (4) | Standard (`osm`) | `--tile-style osm-hot`/`opentopomap`/`cyclosm` when non-default; omit for Standard |
| **Privacy** | 2-way (segmented / `ComboBox`) | Keep exact | `--redact fuzz` when Fuzz; omit when Keep |
| **Join split recordings within** | `Slider` + value readout | 15 s | `--join-gap N` when N ≠ 15; `0` reads as "don't join" |

Map-style labels → keys: Standard→`osm`, Humanitarian→`osm-hot`,
Topographic→`opentopomap`, Cycling→`cyclosm`.

Privacy labels → keys: "Keep exact locations"→`none`, "Fuzz to ~100 m"→`fuzz`.

Join-gap slider range 0–60 s, integer step, default 15. `0` is labelled as
disabling the join.

## Advanced expander (collapsed by default)

| Control | Shape | Default | argv effect |
|---|---|---|---|
| **Also export KML + GeoJSON** | `CheckBox` | off | `--format all` when on; omit (`html`) when off |
| **Time zone of clips** | `TextBox` | `auto` | `--tz-offset X` when ≠ `auto` (and non-empty) |
| **Map title** | `TextBox` | empty (→ folder name) | `--title X` when non-empty |
| **Save map to** | file picker (`TextBox` + Browse) | empty (→ source folder) | `--output PATH` when set |

**Extra-formats refinement (deviates from parent spec's "chips"):** `flightmap
--format` is single-valued and the inline preview requires the HTML output. Two
independent KML/GeoJSON chips cannot map onto a single-valued flag without both
still emitting `all`. M3b therefore uses **one honest checkbox** — "Also export
KML + GeoJSON" → `--format all` — instead of chips. Approved in the 2026-07-20
brainstorm.

## Defaults invariant

With nothing touched, the Flight map argv is **`flightmap <folder> -r`** —
byte-identical to what M3a's `CommandBuilder.Build(FlightMap, folder)` produces
today. Options only *add* flags; omit-at-default keeps the strip clean and keeps
M3a's golden tests valid.

`CommandBuilder` still omits `--progress jsonl`; `DjiEmbedRunner` appends it
unconditionally at execution (unchanged from M3a). The strip shows the human
form with program name `dji-embed` and a `<folder>` placeholder before a folder
is picked.

## Styling constraint

All controls are the **standard Avalonia / SukiUI themed controls**
(`ToggleSwitch`, `ComboBox`, `Slider`, `CheckBox`, `TextBox`, `Expander`) and
inherit the app theme's default appearance — including light/dark — with no
bespoke restyling. Do not hand-paint control chrome; rely on the theme defaults
so the panel is visually consistent with the rest of the workspace. (Layout
spacing/labels are fine to set; the *controls themselves* stay themed defaults.)

## Architecture

Follows the parent spec's per-mode-builder direction ("each mode ViewModel owns
typed option state and one builder producing the argv").

- **`FlightMapOptions`** — an immutable record of typed option state
  (`Recursive`, `TileStyle`, `Privacy`, `JoinGap`, `ExportAll`, `TzOffset`,
  `Title`, `Output`) with a `Defaults` value. Pure input to the builder =
  golden-testable.
- **`FlightMapOptionsViewModel`** (`ObservableObject`, `[ObservableProperty]`
  per control) — bound to the controls; exposes `ToOptions()` producing a
  `FlightMapOptions` snapshot. Holds the display lists for the ComboBoxes.
- **`CommandBuilder.FlightMap(string folder, FlightMapOptions opts)`** — new
  pure overload returning the argv. The existing `Build(kind, folder)` routes
  its FlightMap arm through `FlightMap(folder, FlightMapOptions.Defaults)`, so
  M3a's default-behavior golden tests are unchanged.
- **`WorkspaceViewModel`** — exposes the `FlightMapOptions` VM as a property;
  its flightmap `RunAsync` branch builds argv via
  `CommandBuilder.FlightMap(folder, FlightMapOptions.ToOptions())`; and
  `CommandPreview` uses the same when Flight map is the selected mode.
  `CommandPreview` recomputes whenever any option changes (subscribe to the
  options VM's `PropertyChanged`).
- **`WorkspaceView`** — a new OPTIONS zone (between MODE and ACTION) hosting a
  Flight map options panel, visible only when `SelectedMode.Kind == FlightMap`
  (other modes render nothing yet — M3c/M3d add their own). Advanced is a
  collapsed `Expander`. The "Save map to" Browse button uses the existing
  code-behind file-picker pattern (a Control anchor, like the folder picker).

Runner, strict-success rule, cancellation, and the M2 preview all carry over
unchanged. The done-map preview already points at the run result's reported
output path, so a "Save map to" override previews correctly without special
handling.

## Behavior notes

- **Persistence:** options are in-memory VM state only — no disk persistence
  (respects the "no settings dialog; only MRU + window bounds" rule). They
  persist while the app is open and while switching modes away/back; a fresh
  launch starts at defaults.
- **Mode switch:** switching away from Flight map hides the panel; switching
  back shows it with its state intact. `CommandPreview` reflects the selected
  mode's argv.

## Testing

- **Golden argv** (`CommandBuilderTests`): defaults (`flightmap <f> -r`);
  recursive-off drops `-r`; each non-default tile style; `fuzz`; join-gap `0`
  and `30`; export-all → `--format all`; tz-offset; title with spaces (quoting);
  output override.
- **Options VM** (`FlightMapOptionsViewModelTests`): default values;
  `ToOptions()` mapping for each control.
- **Live preview** (`WorkspaceViewModelTests`): `CommandPreview` updates when an
  option changes; reflects Flight map argv when that mode is selected.
- **Screen** (`AvaloniaFact`): Flight map renders the options panel with the
  Advanced expander collapsed; a non-flightmap mode does not render the panel.

## Out of scope (M3b)

- Footprints on flightmap (no such CLI capability; belongs to Convert / M3c+).
- Photo map, Embed, Convert, Verify options (M3c/M3d and beyond).
- Any new CLI flag, or changes to the `--progress jsonl` contract.
- Independent KML-only / GeoJSON-only export (CLI is single-valued).
- Persisting options to disk.

## Milestone placement

M3b is one releasable milestone / one PR under the M3 arc (M3a done). Sibling
slices still open: M3c/M3d (Photo map, Embed options) and issue #328 (existing-map
detection). Release remains **held** per the small-userbase call — M3b rides the
next version bump with the already-merged #327 fix and M3a.
