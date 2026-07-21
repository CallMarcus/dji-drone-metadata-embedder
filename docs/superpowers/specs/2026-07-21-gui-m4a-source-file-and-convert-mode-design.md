# GUI M4a — single-file sources + Convert mode

*Design round 2026-07-21 (Marcus + Claude). Amends nothing; implements the
Convert row of the mode-curation table in the GUI 2.0 workspace spec
(2026-07-18), plus the source-area lift that row requires. Verify (M4b) is a
separate spec.*

## Decisions taken in the round

- **Source lift = one slot, file OR folder.** The SOURCE area keeps exactly
  one selected item; it may now be a single telemetry file where the mode
  allows it. The spec's "removable chips" plural is deliberately not built:
  only Check-metadata could ever use N items, and folder expansion covers
  that in M4b. Rejected: a multi-chip model (states multiply for no user
  win) and a per-mode file picker inside the options panel (splits source
  selection across two places, breaks drag-drop consistency).
- **M4 ships as two PRs.** M4a = this spec. M4b = Verify mode.

## Source model

- `WorkspaceMode` replaces `NeedsFolder` with `SourceKinds` (a `[Flags]`
  enum: `None`, `Folder`, `File`). Existing modes are `Folder`; Setup is
  `None`; Convert is `Folder | File`.
- `WorkspaceViewModel` gains `SelectedFile` (`string?`) beside
  `SelectedFolder`, **mutually exclusive** — setting either non-null clears
  the other. One source chip shows whichever is set (file chip shows the
  file name, folder chip unchanged); its ✕ runs `ClearSource` (the renamed
  `ClearFolder`), which clears both plus the folder-derived state it already
  clears today.
- `SetFile(string path)`: IsBusy-gated like `SetFolderAsync`; no
  FolderInspector scan, no existing-maps probe (both stay folder-only);
  clears `ExistingMaps`, outputs/warnings, output overrides, preview;
  `Step = Pick`; sets `SuggestedMode` = Convert and selects it (Convert is
  the only file-accepting mode in M4a). Synchronous — there is no scan to
  race, so no overtake re-check is needed.
- **Drag-drop**: `FolderPicking.EnableDrop` currently keeps only dropped
  directories. It grows a file branch: a dropped `.srt`/`.mp4`/`.mov` file
  routes to an `onFile` callback; anything else is still ignored. Folder
  drops keep priority when a drop contains both.
- **Browse**: the source card gets a second button — "Choose folder…"
  (today's) and "Choose file…" (`OpenFilePickerAsync`, filter
  `*.srt;*.SRT;*.mp4;*.MP4;*.mov;*.MOV`, single select), exposed through a
  `FilePicker` seam on `WorkspaceView` in the `SavePicker` mould so
  headless tests can drive it.

## Mode/source mismatch guards (#346 pattern)

`CanRun` becomes "the mode needs no source, or a source of *any* kind is
selected" — the button stays lit and the run blocks with guidance, matching
the recursion-mismatch design:

- Folder-only mode + file selected → `Fail` with a pinned string, e.g.
  Flight map: "Flight map works on a folder of footage — pick the folder
  that holds your flights, not a single file." (analogous wording per mode;
  exact strings pinned by tests, GUI language, never CLI flags).
- Convert + folder guard: `convert -b` globs **top-level** `*.SRT/MP4/MOV`
  only, so the guard requires `HasTopLevelFlightLogs || HasTopLevelVideos`;
  subfolder-only media gets "…are in subfolders — Convert reads only the
  folder you pick; pick the subfolder that holds the files." (the #333
  lesson; Convert has no recursive flag at all).

## Convert mode

- `WorkspaceModeKind.Convert`, card title "Convert telemetry", verb
  "Convert", failure message "Something went wrong while converting the
  telemetry.", strip position between Embed and Setup. Never auto-suggested
  for folder drops (flightmap > photomap > embed order unchanged); always
  suggested for file drops.
- **Options** (record `ConvertTelemetryOptions` + `ConvertOptionsViewModel`,
  VM property `ConvertOptions` — the M3d naming convention):
  - Curated: **Format** (GPX default; CSV, GeoJSON, KML, HTML map, CoT) and
    **Privacy** (Keep / Fuzz ~100 m / Drop) — reusing M3d's three-value
    enum, promoted from `EmbedPrivacy` to a shared `TelemetryPrivacy` in
    its own file (the minimal M4 revisit of the "shared shapes" note; no
    base-class extraction).
  - Advanced: **Timezone** (M3b-style text, `--tz-offset`); **Footprints**
    toggle + interval slider + **Model** field, *visible only for
    GeoJSON/KML* (`--footprint`, `--footprint-interval`, `--model`); **CoT
    interval + type**, *visible only for CoT* (`--interval`, `--cot-type`);
    **Save as** override via the existing `SavePicker` seam, *single-file
    sources only* — the CLI's batch loop has no `-o` (each output lands
    next to its source), so the control is hidden for folder sources.
  - `--extract-home` stays CLI-only (privacy-sensitive opt-in, same call
    as M3d's `--overwrite`).
- **`CommandBuilder.Convert(source, isFolder, options)`** feeds run + strip.
  Defaults invariant: untouched = `convert gpx <folder> -b` /
  `convert gpx <file>`. Flags emit only off-default (house style). The idle
  strip placeholder shows the folder form (`convert gpx <folder> -b`) —
  folders are the primary flow; picking a file flips the strip to the file
  form.
- **Run/done**: runner unchanged — PR #349 gave `convert` the JSONL
  contract (batch progress events drive `ProgressDetail`; per-file
  `Mp4TelemetryError` skips arrive as `warning` events into the existing
  expander; `outputs` = absolute written paths). Running message
  "Converting…". Done state: `PrimePreviewAsync` already previews the first
  `.html` output, so **HTML format gets the inline map preview for free**;
  every other format shows the done card (outputs + summary).

## Testing

House pattern throughout: TDD; CommandBuilder golden tests (option state in,
argv out, defaults invariant); guard tests with pinned strings; named
controls + `Assert.Same(vm.X, control.Command)` binding-identity checks for
the new panel; mismatch guards driven through real gated runs via the
`folderInspector` seam; drop-handler file/folder routing unit-tested against
`FolderPicking`. Suite baseline 340.
