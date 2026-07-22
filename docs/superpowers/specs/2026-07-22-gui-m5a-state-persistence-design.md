# GUI M5a — persisted state (MRU + window bounds)

*Design round 2026-07-22 (Marcus + Claude). Amends nothing; implements the
"GUI state on disk" decision and the MRU/window-bounds items of the M5 row
in the GUI 2.0 workspace spec (2026-07-18). First of the two M5 PRs — M5b
(visual polish: animations, empty-state hero styling, accessibility pass,
docs/screenshots) follows separately.*

## Decisions taken in the round

- **M5 splits in two.** M5a is the persistence machinery (this spec); M5b
  is the visual/finish pass. Persistence is crisply testable on its own,
  and the visual pass wants Marcus's eyes on a real Windows build without
  persistence risk mixed in.
- **MRU surfaces in the hero and the Browse dialog.** The empty source
  hero shows a short "Recent" list (click to re-select), and the folder
  picker starts in the most recent folder. Rejected: picker-start-only
  (drag-and-drop users never see a benefit) and a flyout next to Browse
  (an extra control for the same value).
- **A folder is remembered when a run starts on it** — including the
  existing-map open (#328), which is real work with the folder. Rejected:
  on-selection (mis-drops pollute the list) and successful-runs-only (a
  failed run is often exactly the folder you retry).
- **Folders only.** The workspace spec says "MRU folders"; single files
  (Convert/Verify sources) are never remembered.

## Hard boundary (from the workspace spec, restated)

The only persisted GUI state is MRU folders and window bounds, in one
small JSON in the user config dir. Nothing else, ever, without a spec
amendment. No telemetry; the file holds local paths only and never leaves
the machine.

## GuiState service

`Services/GuiState.cs`, house style — immutable record + pure static
methods, unit-testable with a temp path, no UI types:

- `record WindowBounds(int X, int Y, int Width, int Height, bool Maximized)`.
- `record GuiState(WindowBounds? Window, IReadOnlyList<string> RecentFolders)`
  with an `Empty` **singleton** (record equality over `IReadOnlyList`
  needs reference identity — the `VerifyReport.Empty` lesson).
- `GuiState.Load(path)`: missing, corrupt, or unreadable file → `Empty`;
  unknown JSON fields ignored (forward compatibility); never throws and
  never blocks startup — the DoctorReport degradation rule applied to
  config.
- `GuiState.Save(state, path)`: creates the directory, writes a temp file
  in the same directory, then moves over the target (atomic); swallows
  I/O and permission failures — losing recents must never crash the app.
- `state.WithRecent(folder)`: returns a new state with the folder pushed
  to the front — de-duplicated case-insensitively (`OrdinalIgnoreCase`,
  Windows paths), capped at **5**, order most-recent-first.
- Default path: `%APPDATA%/DjiEmbed/state.json` via
  `Environment.SpecialFolder.ApplicationData`; every method takes the
  path as a parameter so tests never touch the real config dir.
- Wire format: System.Text.Json, camelCase —
  `{ "window": { "x", "y", "width", "height", "maximized" }, "recentFolders": [ ... ] }`.
  Numbers are integers (device-independent pixels as Avalonia reports
  them, truncated); no culture-sensitive formatting anywhere.

One small **store** object (`Services/GuiStateStore.cs`) owns the file at
runtime: it loads once at startup, holds the current state, and exposes
`PushRecent(folder)` (apply `WithRecent` + save immediately — a crash
must not lose the list) and `SaveWindow(bounds)` (called on close). The
store is created in `App.OnFrameworkInitializationCompleted` and handed
down; view models never see file paths.

## Window bounds

- Saved when the main window closes: position, size, and whether it was
  maximized (with the normal bounds saved behind the maximized flag, so
  un-maximizing later lands somewhere sane).
- Restored at startup **only when the saved rectangle intersects a
  visible screen's working area** (the undocked-laptop case); otherwise
  the 1140×720 defaults stand. Maximized restores as maximized after the
  normal bounds are applied.
- All of this lives in `MainWindow` code-behind (it is windowing, not
  view-model logic); the intersection check is a pure static helper on
  `GuiState` (`RestorableOn(bounds, screens)` over plain rectangles) so
  it is unit-tested without a window.

## MRU behaviour

- **Push point:** `RunAsync`, before the work starts, when the captured
  source is a folder **and the mode uses it** — Setup runs ignore the
  source and push nothing, and `SelectedFile` runs push nothing; plus
  `OpenExistingMapAsync`, same rule. Guard-blocked runs still count — the
  user chose to work with that folder.
- **Display prune:** entries whose folder no longer exists are hidden
  from the hero list and dropped on the next save. The stored file may
  briefly hold dead paths; the UI never shows them.
- **Browse start:** the folder picker's `SuggestedStartLocation` is the
  most recent folder that still exists; none → picker default behaviour.
- **State never affects argv.** The transparency strip and
  `CommandBuilder` are untouched by everything in this spec — one
  explicit test pins it.

## Hero "Recent" list

- Shown inside the SOURCE card beneath the drop zone, only when no
  source is selected and at least one recent folder survives the prune.
  Selecting a source (or a run in flight) hides it; clearing the source
  brings it back.
- Pinned copy: header **"Recent folders"** (quiet zone-label styling).
  Each entry is a link-style button showing the folder's leaf name, full
  path as tooltip and `AutomationProperties.Name`.
- Clicking an entry calls the normal `SetFolderAsync` flow — identical to
  dropping the folder: mode suggestion, existing-map probe, fresh-start
  reset all included.
- `WorkspaceViewModel` exposes `RecentFolders` (observable) and receives
  the store's push/read functions via constructor injection in the
  established `_inspectFolder`-style seam, so VM tests run with an
  in-memory store and no disk.

## Testing

House pattern: TDD throughout. GuiState unit tests — round-trip,
missing/corrupt/unreadable file, unknown-field tolerance, atomic write
(temp file gone after save), `WithRecent` dedupe/cap/order/case rules,
`RestorableOn` intersection cases. VM tests — push on run start (folder
yes, file no, existing-map open yes), hero list prune, click-recent flows
through `SetFolderAsync`, `CommandPreview` unaffected by state. Screen
tests — recent list visible/hidden per source state, click selects, the
shared freeze test grows the recents region. Screenshot capture of the
hero with recents (interleaved-tick idiom). GUI suite baseline 407
passed / 15 skipped; Python side untouched.
