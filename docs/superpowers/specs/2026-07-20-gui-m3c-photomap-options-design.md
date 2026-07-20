# GUI 2.0 — M3c: Photo map curated options + Advanced expander

**Parent spec:** `docs/superpowers/specs/2026-07-18-gui-full-workspace-design.md`
(GUI 2.0 full-workspace design; this is the M3c milestone slice.)

**Predecessors:** M3a shipped `CommandBuilder` (per-mode argv, one source of
truth for run + strip) and the live CLI transparency strip. M3b gave **Flight
map** its curated options panel and set the pattern this slice follows.

## Goal

Give the **Photo map** mode a curated options panel between the MODE strip and
the ACTION button, plus an Advanced expander. Every control maps to an existing
`photomap` CLI flag; the typed option state flows through `CommandBuilder` into
both the executed run and the live CLI strip. No new CLI features — M3c surfaces
capability that already exists.

## Context: the real `photomap` flag surface

`photomap` (`src/dji_metadata_embedder/cli.py:535-586`) accepts: `directory`
(from the Source picker), `-o/--output`, `-f/--format`
(`html`/`kml`/`geojson`/`all`, default `html`), `-r/--recursive`, `--title`,
`--link-originals`, `--link-base PREFIX`, `--popup-fields LIST`, `--redact`
(`none`/`fuzz`, default `none`), `--serve`, `--tile-style`, plus
`--progress`/`-v`/`-q`.

Differences from `flightmap` that shape this slice:

- **No `--tz-offset`, no `--join-gap`** — both are SRT-telemetry concerns.
- **`--serve` is impossible in the GUI.** `cli.py:616-620` raises a
  `UsageError` when `--serve` is combined with `--progress jsonl`, and
  `DjiEmbedRunner` appends that flag unconditionally at execution. The need it
  serves (360° panoramas over HTTP) is already met by the M2 `MapServer`
  loopback behind the inline preview, so nothing is lost.
- **`--link-originals` is already hardcoded on** in the M3a argv
  (`CommandBuilder.cs:33`). M3c turns it into a default-ON control, not a new
  opt-in.

Tile-style keys (`src/dji_metadata_embedder/geo/tiles.py`): `osm` (default),
`osm-hot`, `opentopomap`, `cyclosm` — the same set Flight map offers.

Popup fields (`src/dji_metadata_embedder/geo/photomap_html.py:49`):
`POPUP_FIELDS = ("name", "timestamp", "camera", "altitude", "credit")`.

## Curated controls (always visible when Photo map is selected)

| Control | Shape | Default | argv effect |
|---|---|---|---|
| **Include subfolders** | `ToggleSwitch` | ON | `-r` when on; omit when off |
| **Map style** | `ComboBox` (4) | Standard (`osm`) | `--tile-style osm-hot`/`opentopomap`/`cyclosm` when non-default; omit for Standard |
| **Privacy** | `ComboBox` (2) | Keep exact | `--redact fuzz` when Fuzz; omit when Keep |
| **Link pins to the original photos** | `CheckBox` | ON | `--link-originals` when on; omit when off |
| **Popup details** | 5 `CheckBox`es | all ticked | see encoding below |

Map-style and Privacy reuse M3b's label→key mappings verbatim (Standard→`osm`,
Humanitarian→`osm-hot`, Topographic→`opentopomap`, Cycling→`cyclosm`; "Keep
exact locations"→omit, "Fuzz to ~100 m"→`--redact fuzz`).

**Link-to-originals** carries a hint that the 360° panorama viewer needs it.
Turning it off produces a self-contained map whose popups do not reference local
file paths — the shareable-single-file case.

**Popup details** are labelled Name / Time / Camera / Altitude / Credit, with a
one-line explanation that unticked details are left out of the HTML file
entirely (the original photos are never modified).

### `--popup-fields` encoding

`CommandBuilder` owns this mapping; the options record stays dumb data.

| State | argv |
|---|---|
| All five ticked | flag omitted (CLI default = show everything) |
| None ticked | `--popup-fields none` |
| Any subset | `--popup-fields a,b,c` in the canonical `POPUP_FIELDS` order: `name,timestamp,camera,altitude,credit` |

The none-ticked case is **not cosmetic**: `parse_popup_fields`
(`photomap_html.py:71`) raises `ValueError` on an empty comma list
(`if unknown or not fields`), so emitting `--popup-fields ""` would fail the
run. `none` is the only valid encoding of "no popup fields".

### Fuzz caveat note

When Privacy is **Fuzz** *and* Link-to-originals is **on**, a quiet one-line
note appears under the privacy row:

> Linked originals still carry exact GPS in their EXIF.

This mirrors the note the CLI prints on stderr (`cli.py:665-671`), which the GUI
would otherwise bury in the warnings area. It is driven by a real bool property
on the options VM (not a XAML multi-binding) so it is assertable headless —
following the `ShowIdle` precedent from issue #328.

## Advanced expander (collapsed by default)

| Control | Shape | Default | argv effect |
|---|---|---|---|
| **Also export KML + GeoJSON** | `CheckBox` | off | `--format all` when on; omit (`html`) when off |
| **Map title** | `TextBox` | empty (→ folder name) | `--title X` when non-empty |
| **Save map to** | file picker (`TextBox` + Browse + "Use default") | empty (→ source folder) | `--output PATH` when set |

Same three controls, same save-picker and clear-output affordance as M3b — the
`FolderPicking` / `ClearOutputCommand` pattern is reused, not reinvented.

The single "Also export KML + GeoJSON" checkbox (rather than per-format chips)
follows M3b's reasoning unchanged: `--format` is single-valued and the inline
preview requires HTML output.

## Defaults invariant

With nothing touched, the Photo map argv is
**`photomap <folder> -r --link-originals`** — byte-identical to what M3a's
`CommandBuilder.Build(PhotoMap, folder)` produces today. Options only *add*
flags; omit-at-default keeps the strip clean and keeps M3a's golden tests valid.

`CommandBuilder` still omits `--progress jsonl`; `DjiEmbedRunner` appends it at
execution. The strip shows the human form with program name `dji-embed` and a
`<folder>` placeholder before a folder is picked.

## Styling constraint

All controls are the **standard Avalonia / SukiUI themed controls**
(`ToggleSwitch`, `ComboBox`, `CheckBox`, `TextBox`, `Expander`) inheriting the
app theme's default appearance in light and dark, with no bespoke restyling.
Layout spacing and labels are ours; control chrome stays themed default.

Known build gotcha carried from M3b: `TextBox.Watermark` is `[Obsolete]`
(AVLN5001) in this Avalonia — use `PlaceholderText`.

## Architecture

Mirrors M3b's seam layout.

- **`ViewModels/PhotoMapOptions.cs`** — an immutable record of typed option
  state (`Recursive`, `TileStyle`, `Privacy`, `LinkOriginals`, `PopupFields`,
  `ExportAll`, `Title`, `Output`) with a `Defaults` value. Reuses M3b's
  `MapPrivacy` enum, whose `Keep`/`Fuzz` values are exactly `photomap --redact`'s
  `none`/`fuzz`. `PopupFields` is a nested immutable record of five bools with an
  `All` value; it holds no formatting logic.
- **`ViewModels/PhotoMapOptionsViewModel.cs`** — `[ObservableProperty]` per
  control, bound to the panel; `ToOptions()` snapshots it into
  `PhotoMapOptions`. Exposes the fuzz-caveat bool and the `ClearOutputCommand`.
- **`Services/CommandBuilder.cs`** — new pure overload
  `PhotoMap(string folder, PhotoMapOptions opts)`. The existing
  `Build(kind, folder)` routes its PhotoMap arm through
  `PhotoMap(folder, PhotoMapOptions.Defaults)`, so M3a's default-behavior golden
  tests are unchanged.
- **`ViewModels/WorkspaceViewModel.cs`** — a `PhotoOptions` property; a new
  `IsPhotoMapMode` computed property notified alongside `IsFlightMapMode`
  (`WorkspaceViewModel.cs:144`); the PhotoMap `RunAsync` branch and
  `CommandPreview` both build argv via
  `CommandBuilder.PhotoMap(folder, PhotoOptions.ToOptions())`; the strip
  recomputes on the options VM's `PropertyChanged` (same subscription pattern as
  `FlightOptions`).
- **`Views/WorkspaceView.axaml`** — a `PhotoOptionsPanel` border in the existing
  OPTIONS zone, `IsVisible="{Binding IsPhotoMapMode}"`, with its own collapsed
  Advanced `Expander`.

### Shared tile-style list (targeted cleanup)

The four `TileChoice` values currently live inside `FlightMapOptionsViewModel`.
Both map modes consume the identical `--tile-style` key set, so the `TileChoice`
record and the list move to a new `ViewModels/TileChoice.cs` exposing a static
`TileChoice.All`, which both options VMs read. This is a move, not a rewrite:
`FlightMapOptionsViewModel` keeps its `TileStyles` property, now returning the
shared list, so M3b's tests and XAML bindings are untouched.

The `MapPrivacy` enum stays where M3b put it (`ViewModels/FlightMapOptions.cs`)
and is referenced by name from `PhotoMapOptions` — same namespace, no move, no
churn in M3b's files beyond the tile-list extraction.

Runner, strict-success rule, cancellation, and the M2/#328 preview all carry over
unchanged. The done-map preview points at the run result's reported output path,
so a "Save map to" override previews correctly with no special handling.

## Behavior notes

- **Persistence:** in-memory VM state only — no disk persistence (respects the
  "no settings dialog; only MRU + window bounds" rule). Options survive mode
  switches while the app is open; a fresh launch starts at defaults.
- **Mode switch:** switching away from Photo map hides the panel; switching back
  shows it with state intact. Only one options panel is visible at a time.
- **Photo map with no photos:** the existing `PhotoMap when !contents.HasPhotos`
  guard (`WorkspaceViewModel.cs:376`) is unchanged; options do not affect it.

## Testing

TDD throughout; red before green.

- **Golden argv** (`CommandBuilderTests`): defaults
  (`photomap <f> -r --link-originals`); recursive-off drops `-r`;
  link-originals-off drops the flag; each non-default tile style; `fuzz`;
  popup-fields all-ticked omits the flag; none-ticked → `--popup-fields none`;
  a subset emits canonical order regardless of tick order; export-all →
  `--format all`; title with spaces; output override.
- **Options VM** (`PhotoMapOptionsViewModelTests`): default values;
  `ToOptions()` mapping per control; the fuzz-caveat bool is true only when
  Fuzz **and** LinkOriginals are both set; `ClearOutputCommand` resets Output.
- **Live preview** (`WorkspaceViewModelTests`): `CommandPreview` updates when a
  photo option changes; reflects Photo map argv when that mode is selected;
  `IsPhotoMapMode` flips and notifies on mode change.
- **Screen** (`AvaloniaFact`): Photo map renders the options panel with Advanced
  collapsed; Flight map does not render the photo panel (and vice versa).
  Per the #328 gotcha, any button assertion checks
  `Assert.Same(vm.SomeCommand, button.Command)` — a `Button` with a **null**
  `Command` still reports `IsEffectivelyEnabled == true`, so asserting
  enabled-ness proves nothing about a binding.

## Out of scope (M3c)

- `--link-base` (publish-elsewhere prefix; its "requires `--link-originals`"
  coupling is a GUI failure mode, and it is an exotic flag per the parent spec).
- `--serve` (structurally incompatible with `--progress jsonl`; the inline
  preview already covers it).
- Embed options (M3d), Convert/Verify options and footprints (M4).
- Any new CLI flag, or changes to the `--progress jsonl` contract.
- Independent KML-only / GeoJSON-only export (CLI is single-valued).
- Persisting options to disk.

## Milestone placement

M3c is one releasable milestone / one PR under the M3 arc (M3a, M3b and issue
#328 done). Remaining sibling slice: M3d (Embed options). Release remains
**held** per the small-userbase call — M3c rides the next version bump with the
already-merged #327 fix, M3a, M3b and #328.
