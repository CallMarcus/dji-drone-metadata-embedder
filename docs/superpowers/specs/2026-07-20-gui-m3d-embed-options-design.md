# GUI 2.0 — M3d: Embed telemetry curated options + Advanced expander

**Parent spec:** `docs/superpowers/specs/2026-07-18-gui-full-workspace-design.md`
(GUI 2.0 full-workspace design; this is the M3d milestone slice, and the last
one in the M3 arc.)

**Predecessors:** M3a shipped `CommandBuilder` (per-mode argv, one source of
truth for run + strip) and the live CLI transparency strip. M3b and M3c gave
**Flight map** and **Photo map** their curated options panels and set the
pattern this slice follows.

## Goal

Give the **Embed telemetry** mode a curated options panel between the MODE strip
and the ACTION button, plus an Advanced expander. Every control maps to an
existing `embed` CLI flag; the typed option state flows through `CommandBuilder`
into both the executed run and the live CLI strip. No new CLI features — M3d
surfaces capability that already exists.

## Context: the real `embed` flag surface

`embed` (`src/dji_metadata_embedder/cli.py:252-294`) accepts: `directory` (from
the Source picker), `-o/--output` **DIR**, `--overwrite`, `--exiftool`,
`--dat PATH`, `--dat-auto`, `--audio-sidecar`, `--redact`
(`none`/`drop`/`fuzz`, default `none`), `--container` (`mp4`/`mkv`, default
`mp4`), `--extract-home`, plus `--progress`/`-v`/`-q`.

Differences from the two map modes that shape this slice:

- **No `-r/--recursive` at all.** `embed` processes one directory level. There is
  therefore no "Include subfolders" control — the first curated toggle both map
  panels open with is simply absent here.
- **`--redact` is three-valued** (`none`/`drop`/`fuzz`), where both map commands
  accept only `none`/`fuzz`. `drop` is not a value the map modes declined to
  surface; it is one their commands would **reject**.
- **`-o/--output` is a directory**, not a file. `photomap`/`flightmap` take an
  output *file* and needed a save-file picker; `embed` reuses the existing folder
  picker. Default output is `<folder>/processed/`
  (`src/dji_metadata_embedder/embedder.py:163-164`).
- **No preview.** Embed produces videos, not HTML, so `PrimePreviewAsync` never
  runs for this mode and the done **card** (output directory + warnings) is the
  terminal state. Unchanged by M3d.

## Amendments to the parent spec's curation table

The 2026-07-18 spec proposed, for Embed: curated *privacy, container, extract
HOME point*; Advanced *audio sidecar, ExifTool GPS injection, DAT log (+auto),
overwrite, output*. Two entries are amended here, decided during the M3d
brainstorm:

1. **`--overwrite` is dropped from the GUI entirely — it stays CLI-only.** It
   rewrites the original videos in place and is the only irreversible flag in
   the product. A GUI whose premise is "drop a folder, press the button" must
   not put one-click destruction of the user's originals behind a checkbox, and
   a confirmation modal would be the app's first modal built solely to make a
   dangerous option survivable. The CLI strip still teaches the command, so a
   user who genuinely wants in-place embedding copies the line and adds the flag
   deliberately. **The GUI always writes copies.**
2. **`--dat PATH` is dropped; only `--dat-auto` is surfaced.** Pointing at one
   specific DAT file is a per-file operation in a folder-shaped GUI, and it would
   add a second untestable picker handler (the gap already filed as #335) plus a
   mutual-exclusion rule against `--dat-auto`. The auto flag covers the realistic
   case: DAT logs pulled off the aircraft into the same folder as the videos.

## Curated controls (always visible when Embed telemetry is selected)

| Control | Shape | Default | argv effect |
|---|---|---|---|
| **Video container** | `ComboBox` (2) | MP4 (most compatible) | `--container mkv` when MKV; omit for MP4 |
| **Privacy** | `ComboBox` (3) | Keep exact locations | `--redact fuzz` / `--redact drop`; omit when Keep |
| **Record the launch point in the sidecar** | `CheckBox` | off | `--extract-home` when on |

**Video container** labels the trade-off rather than the format:
"MP4 (most compatible)" and "MKV (keeps DJI data streams)". The MKV note matters
— the mp4 muxer drops DJI `djmd`/`dbgi` data streams, which is exactly the
telemetry the ExifTool extractor (#206) reads back.

**Privacy** offers "Keep exact locations" (omit), "Fuzz to ~100 m" (`fuzz`), and
"Remove GPS entirely" (`drop`). The first two labels are word-for-word the map
panels' labels, so the same stance reads the same way in every mode.

**Record the launch point** is `--extract-home` with a plain-language subtitle:
where the aircraft took off — often the operator's home — written only to the
`.json` sidecar, never into the video. It sits in the curated zone rather than
Advanced because it is a privacy decision, and privacy decisions should not be
discoverable only by expanding "Advanced".

### Launch-point / privacy interaction note

`apply_redaction` (`src/dji_metadata_embedder/utilities.py:337-341`) redacts
`home` alongside the coordinates. With **Remove GPS entirely** the extracted home
point is emitted as `"home": null` (`embedder.py:756-763` writes the key as a
marker whenever extraction was requested). So the two controls can be set to a
combination that does nothing useful, and the panel says so in a quiet note under
the checkbox:

> This privacy stance writes the launch point as empty.

Shown only when Privacy is **Remove GPS entirely** *and* the checkbox is ticked.
Like M3c's fuzz caveat, it is a real bool property on the options VM (not a XAML
multi-binding) so it is assertable headless.

## Advanced expander (collapsed by default)

| Control | Shape | Default | argv effect |
|---|---|---|---|
| **Also write GPS with ExifTool** | `CheckBox` | off | `--exiftool` when on |
| **Mux .m4a audio sidecar (DJI Neo 2)** | `CheckBox` | off | `--audio-sidecar` when on |
| **Merge DAT flight logs found beside the videos** | `CheckBox` | off | `--dat-auto` when on |
| **Save copies to** | folder picker (path text + Choose… + "Use default") | empty (→ `processed/`) | `--output DIR` when set |

"Save copies to" reuses M3b/M3c's clear-output affordance verbatim — the
`ClearOutputCommand` plus a "Use default" button visible only while an override
is set — but opens a **folder** picker, reusing the existing `FolderPicking`
helper rather than the map modes' save-file picker. Its empty-state text reads
"(a 'processed' folder inside the source folder)".

The ExifTool row carries a one-line hint that it needs ExifTool installed, and
points at the Setup mode.

## Defaults invariant

With nothing touched, the Embed argv is **`embed <folder>`** — byte-identical to
what M3a's `CommandBuilder.Build(Embed, folder)` produces today, and the only
mode whose default argv carries no flags at all. Options only *add* flags.

Fully loaded, the fixed flag order (mirroring panel order, curated before
Advanced) is:

```
embed <folder> --redact fuzz --container mkv --extract-home \
      --exiftool --audio-sidecar --dat-auto --output <dir>
```

`CommandBuilder` still omits `--progress jsonl`; `DjiEmbedRunner` appends it at
execution. The strip shows the human form with program name `dji-embed` and a
`<folder>` placeholder before a folder is picked.

## Styling constraint

All controls are the **standard Avalonia / SukiUI themed controls**
(`ComboBox`, `CheckBox`, `TextBox`, `Expander`) inheriting the app theme's
default appearance in light and dark, with no bespoke restyling. Layout spacing
and labels are ours; control chrome stays themed default.

Known build gotcha carried from M3b: `TextBox.Watermark` is `[Obsolete]`
(AVLN5001) in this Avalonia — use `PlaceholderText`.

## Architecture

Mirrors M3b/M3c's seam layout.

- **`ViewModels/EmbedOptions.cs`** — an immutable record of typed option state
  (`Privacy`, `Container`, `ExtractHome`, `UseExifTool`, `AudioSidecar`,
  `DatAuto`, `Output`) with a `Defaults` value, plus a new
  **`EmbedPrivacy { Keep, Fuzz, Drop }`** enum. `Container` is the CLI key
  string (`"mp4"`/`"mkv"`), following `TileStyle` in the map option records.
- **`ViewModels/EmbedOptionsViewModel.cs`** — `[ObservableProperty]` per control,
  bound to the panel; `ToOptions()` snapshots it into `EmbedOptions`. Exposes the
  launch-point note bool and the `ClearOutputCommand`. Declares the one-line
  `EmbedPrivacyChoice(string Label, EmbedPrivacy Value)` display record and a
  `ContainerChoice(string Label, string Key)` list.
- **`Services/CommandBuilder.cs`** — new pure overload
  `Embed(string folder, EmbedOptions opts)`. The existing `Build(kind, folder)`
  routes its Embed arm through `Embed(folder, EmbedOptions.Defaults)`, so M3a's
  default-behavior golden tests are unchanged.
- **`ViewModels/WorkspaceViewModel.cs`** — an `EmbedOptions` property; a new
  `IsEmbedMode` computed property notified alongside `IsFlightMapMode` /
  `IsPhotoMapMode`; the Embed `RunAsync` branch and `CommandPreview` both build
  argv via `CommandBuilder.Embed(folder, EmbedOptions.ToOptions())`; the strip
  recomputes on the options VM's `PropertyChanged` (same subscription pattern as
  `FlightOptions` / `PhotoOptions`).
- **`Views/WorkspaceView.axaml`** — an `EmbedOptionsPanel` border in the existing
  OPTIONS zone, `IsVisible="{Binding IsEmbedMode}"`, with its own collapsed
  Advanced `Expander`.

### Why a separate privacy enum

`MapPrivacy { Keep, Fuzz }` stays exactly as it is. Embed gets its own
`EmbedPrivacy { Keep, Fuzz, Drop }` rather than a `Drop` member being added to
the shared enum, because `flightmap`/`photomap` accept only `none|fuzz`
(`cli.py:567-570`, `cli.py:751-755`): a shared three-valued enum would make it
possible to build a map argv the CLI rejects. Each mode's enum stays total over
what its own command accepts. The cost is one 1-line display record — a generic
`PrivacyChoice<T>` is not worth the friction it causes in compiled XAML
bindings.

This follows the same judgment recorded in M3c: share what is genuinely
identical (`TileChoice`, extracted because both map modes take the same
`--tile-style` keys), keep separate what merely looks similar (the two options
ViewModels, deliberately not given a shared base class).

Runner, strict-success rule, cancellation, and the done card all carry over
unchanged.

## Behavior notes

- **Persistence:** in-memory VM state only — no disk persistence (respects the
  "no settings dialog; only MRU + window bounds" rule). Options survive mode
  switches while the app is open; a fresh launch starts at defaults.
- **Mode switch:** switching away from Embed hides the panel; switching back
  shows it with state intact. Only one options panel is visible at a time.
- **Path-valued option resets on a folder change.** `SetFolderAsync` already
  clears `FlightOptions.Output` and `PhotoOptions.Output`; `EmbedOptions.Output`
  joins them. An absolute output directory chosen for folder A must not silently
  collect folder B's copies. Every other option deliberately survives a folder
  change.
- **Embed with no videos:** the existing `Embed when !contents.HasVideos` guard
  is unchanged; options do not affect it.

## Testing

TDD throughout; red before green.

- **Golden argv** (`CommandBuilderTests`): defaults (`embed <f>`, no flags);
  each privacy value (`fuzz`, `drop`, Keep omits); `--container mkv` with MP4
  omitting; each Advanced flag alone; a composite asserting the full fixed order;
  an output path with spaces (display quoting).
- **Options VM** (`EmbedOptionsViewModelTests`): default values; `ToOptions()`
  mapping per control; the launch-point note bool is true only when **Drop** and
  **ExtractHome** are both set (and false for Fuzz+ExtractHome, and for
  Drop alone); `ClearOutputCommand` resets Output.
- **Live preview** (`WorkspaceViewModelTests`): `CommandPreview` updates when an
  embed option changes; reflects Embed argv when that mode is selected;
  `IsEmbedMode` flips and notifies on mode change; `EmbedOptions.Output` clears
  on a folder change; the run's recorded argv (via `FakeCli.WriteArgsRecorder`)
  equals what the strip shows.
- **Screen** (`AvaloniaFact`): Embed renders the options panel with Advanced
  collapsed; the map modes do not render the embed panel (and vice versa).
  Per the #328 gotcha, any button assertion checks
  `Assert.Same(vm.SomeCommand, button.Command)` — a `Button` with a **null**
  `Command` still reports `IsEffectivelyEnabled == true`, so asserting
  enabled-ness proves nothing about a binding.
- **Optional capture** (opt-in via `DJIEMBED_CAPTURE_DIR`): follows M3c's
  screenshot test, including the interleaved
  `ForceRenderTimerTick()`/`RunJobs()`/`UpdateLayout()` settling the `Expander`
  animation needs.

## Out of scope (M3d)

- `--overwrite` and `--dat PATH` — CLI-only by the decisions above.
- `-v`/`-q` (execution detail; `--progress jsonl` forces quiet anyway).
- The **nested-videos hollow success**: because the GUI's folder scan recurses
  but `embed` does not, a folder whose videos live only in subfolders passes the
  mode guard, embeds nothing, and reports "✅ Done" with a "No MP4 files found"
  warning (`embedder.py:588-592` — a warning, not an error, so `ok` stays true).
  Filed as a `type:gui` issue alongside #333: both share one root cause (a
  recursive folder scan feeding commands that are non-recursive or only
  opt-in recursive) and should be fixed once, together, not patched inside an
  options PR.
- Convert/Verify options and footprints (M4).
- Any new CLI flag, or changes to the `--progress jsonl` contract.
- Persisting options to disk.

## Milestone placement

M3d is one releasable milestone / one PR, and **completes the M3 arc** (M3a,
M3b, M3c and issue #328 done). Release remains **held** per the small-userbase
call: M3d rides the next version bump together with the already-merged #327
playback fix, M3a, M3b, #328 and M3c. A manual UI test plan covering that whole
held batch exists locally at
`docs/superpowers/plans/2026-07-20-m3-manual-ui-test-plan.md`.
