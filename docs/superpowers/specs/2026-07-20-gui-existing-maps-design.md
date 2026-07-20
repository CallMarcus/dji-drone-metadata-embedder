# GUI — Surface maps that already exist in the chosen folder (#328)

**Issue:** #328 — found during a manual UI test of v1.26.0 on Windows 11.
**Parent spec:** `docs/superpowers/specs/2026-07-18-gui-full-workspace-design.md`
(GUI 2.0 full-workspace design.) This is a standalone fix under that design,
not an M3 milestone slice.

## Goal

Pick a folder that already contains `flightmap.html` or `photomap.html` and the
app currently pretends they don't exist — the only route back to a map you
already made is to make it again. This change probes for those maps on folder
pick, lists them in the left column, and lets you open one in the app's own
preview pane.

No CLI work. No persistence.

## What exists today

- `FolderInspector.Inspect` classifies by extension only (`.srt` / photos /
  videos) and stops early once all three are found. `.html` matches nothing.
- `WorkspaceViewModel.PreviewUrl` is written only by `PrimePreviewAsync`, which
  reads `Outputs` — populated exclusively from a run's terminal JSONL event.
- Both preview panes are gated on `Step == FlowStep.Done`, so nothing can render
  while `Step == Pick`.
- The idle pane is a static hero: background image plus two fixed lines.

The GUI never passes `-o` by default, so the CLI's defaults apply and the paths
are deterministic: `<folder>/flightmap.html` (`cli.py:854`) and
`<folder>/photomap.html` (`cli.py:699`). 360° panoramas are not separate files —
the Pannellum viewer is embedded inside `photomap.html`.

## Decisions (2026-07-20 brainstorm)

| Question | Decision |
|---|---|
| Where do existing maps surface? | A row in the **left column**, between MODE and OPTIONS. The preview pane's idle hero is untouched. |
| What does **Open** do? | Renders the map **inline** in the app's preview pane — the same WebView a finished run uses. |
| Staleness | **Yes** — a quiet line when the map predates the newest media of its own kind. |
| Does the action button relabel to "Regenerate"? | **No.** The row already says a map exists, and M3b's "Save map to" override would make "Regenerate" a lie. |

## Detection

### `FolderContents` gains per-kind timestamps

```csharp
public sealed record FolderContents(
    bool HasFlightLogs, bool HasPhotos, bool HasVideos,
    DateTime? NewestFlightLogUtc, DateTime? NewestPhotoUtc);
```

Per-kind, not one global "newest media": new photos must not mark the flight map
stale, and vice versa. Videos get no timestamp — they produce no map.

`Inspect` loses its `break`-when-all-three-found shortcut, because the newest
write time is only known after the full walk. The scan already runs on a
background thread (`Task.Run` in `SetFolderAsync` and `RunAsync`), and it is
already recursive, so this costs a full enumeration on folders that would
previously have exited early.

### `ExistingMapFinder`

```csharp
public sealed record ExistingMap(
    string Path, string Title, DateTime WrittenUtc, bool Stale);

public static class ExistingMapFinder
{
    public static IReadOnlyList<ExistingMap> Find(
        string directory, FolderContents contents);
}
```

Probes exactly two paths — `flightmap.html`, `photomap.html` — directly in the
chosen directory (not recursive; the CLI writes them at the top level).
Titles are `"Flight map"` and `"Photo map"` — the same strings as
`WorkspaceMode.Title` for those kinds, so the row and the mode strip agree.
Order is flight map first, then photo map. A folder with neither yields an empty
list.

`WrittenUtc` is `File.GetLastWriteTimeUtc`. Staleness pairs each map with its own
source kind:

- `flightmap.html` → `Stale` when `contents.NewestFlightLogUtc > WrittenUtc`
- `photomap.html` → `Stale` when `contents.NewestPhotoUtc > WrittenUtc`

A null timestamp (no media of that kind) is never stale.

A file that vanishes or throws between `Exists` and the timestamp read is
skipped, not surfaced — the scan must never fail a folder pick.

### `RelativeTime`

```csharp
public static class RelativeTime
{
    public static string Describe(DateTime whenUtc, DateTime nowUtc);
}
```

`nowUtc` is a parameter so tests need no clock seam.

| Age | Output |
|---|---|
| negative (clock skew) or < 1 minute | `just now` |
| < 1 hour | `1 minute ago` / `N minutes ago` |
| < 1 day | `1 hour ago` / `N hours ago` |
| otherwise | `1 day ago` / `N days ago` |

No week/month/year tiers and no absolute-date fallback: `"412 days ago"` is
unambiguous, and tiers are more code and more test surface than the readability
buys. Values truncate (2 h 55 m reads `2 hours ago`).

## Browsing an existing map

### ViewModel

`WorkspaceViewModel` gains:

```csharp
public ObservableCollection<ExistingMap> ExistingMaps { get; } = [];
```

- Populated at the end of `SetFolderAsync`, from the same `FolderContents` the
  mode suggestion already uses — one scan, not two. `Find` runs inside that same
  background `Task.Run`, so its `File.Exists` probes stay off the UI thread; the
  collection is then filled on the awaited continuation.
- Cleared and repopulated on every folder pick; cleared by `ClearFolder`.
- Mode-agnostic: the row reflects what is on disk regardless of the selected
  mode, because it answers "what's already here", not "what would this run do".

Row buttons bind to commands taking the item as a parameter — no per-row
ViewModel:

- `OpenExistingMapCommand(ExistingMap)` — serve and preview (below).
  `CanExecute` is `Step != FlowStep.Running`; `OnStepChangedCore` calls
  `NotifyCanExecuteChanged` so the buttons grey out for the duration of a run.
- `ShowExistingMapInFolderCommand(ExistingMap)` — `Reveal.InFolder(map.Path)`.

`OpenExistingMap` mirrors `PrimePreviewAsync`: get a URL from `IMapServer`, set
`PreviewPath` first, then `PreviewUrl` (the view reads the path when the URL
lands). Where it differs: when the WebView is unavailable or the server returns
no URL, it **falls back to opening the map in the system browser** rather than
setting `PreviewUnavailable`. A done-card explaining why the preview can't
render belongs to a run that just finished; here the user asked for one specific
map, and the browser satisfies that ask. Reuses `OpenOutputCoreAsync`.

### Pane gates

| Property | Before | After |
|---|---|---|
| `ShowPreview` | `Step == Done && PreviewUrl is not null` | `PreviewUrl is not null && (Step == Done \|\| Step == Pick)` |
| `ShowDoneCard` | `Step == Done && PreviewUrl is null` | unchanged |
| idle hero | bound to `Step == Pick` in XAML | new `ShowIdle => Step == FlowStep.Pick && PreviewUrl is null` |

`ShowIdle` is a real ViewModel property rather than a XAML multi-binding, so the
idle/preview split is testable without a visual tree.

### Collision safety

A browsed preview can never survive into a run, because all three existing exits
already call `ResetPreview()`:

- `SetFolderAsync` — a new folder clears the previous folder's map.
- `RunAsync` — resets past the awaited scan (deliberately, so a live map isn't
  flashed away early).
- `GoHomeCore` ("Process another"/"Close map") — back to the hero.

Plus `OpenExistingMapCommand` is disabled while `Step == Running`.

### Fixing a latent leak this exposes

`Outputs` and `Warnings` are cleared only at run start
(`FlowViewModel.cs:131-132`). Today that is invisible. Once a preview can render
during `Step == Pick`, a run in folder A would show its warnings over folder B's
browsed map. `SetFolderAsync` will clear both — which its own doc comment ("a
new folder is a fresh start") already claims.

## View

A new `ExistingMapsPanel` between the MODE `GlassCard` and `FlightOptionsPanel`,
visible on `ExistingMaps.Count`:

```
ALREADY IN THIS FOLDER
┌──────────────────────────────┐
│ 🗺  Flight map                │
│    2 days ago                │
│    ⚠ New footage since this  │
│      map was made            │
│    [Open]  [Show in folder]  │
└──────────────────────────────┘
```

- Zone label `ALREADY IN THIS FOLDER` using the existing `zone` class.
- One `GlassCard` per map inside an `ItemsControl` bound to `ExistingMaps`.
- The stale line is visible on `Stale`; the relative time comes from a converter
  over `WrittenUtc` (`WorkspaceConverters`, alongside `FileNameOnly`) that calls
  `RelativeTime.Describe(value, DateTime.UtcNow)` at bind time. Reading the clock
  in the view keeps `RelativeTime` itself clock-free and testable.
- Standard Avalonia / SukiUI themed controls throughout, inheriting the app
  theme in both light and dark — the M3b styling constraint carries over.

The preview header (`WorkspaceView.axaml:382-409`) is reused as-is. Its third
button's **text** switches on step — `Done` → "Process another", `Pick` →
"Close map" — because nothing has been processed when you are browsing a map
that was already there. The command (`GoHomeCommand`) is unchanged.

## Testing

- **`ExistingMapFinderTests`** (temp directories): empty folder → no maps; flight
  map only; photo map only; both → flight first; stale when the matching media is
  newer; not stale when the map is newer; not stale when no media of that kind
  exists; photos newer than the flight map do not stale it.
- **`RelativeTimeTests`**: each tier boundary plus singular/plural and a
  future timestamp.
- **`FolderInspectorTests`**: per-kind newest timestamps populated; null when
  that kind is absent; existing classification tests still pass.
- **`WorkspaceViewModelTests`**: pick populates `ExistingMaps`; a folder with no
  maps leaves it empty; a second pick replaces the contents; `ClearFolder`
  empties it; `OpenExistingMap` sets `PreviewUrl` while `Step == Pick` and flips
  `ShowPreview` true / `ShowIdle` false; starting a run resets the preview; the
  open command is disabled while `Step == Running`; a folder pick clears
  `Outputs` and `Warnings`.
- **`WorkspaceScreenTests`** (`AvaloniaFact`): the panel renders when maps exist
  and is hidden when the list is empty.

## Out of scope

- Finding maps saved outside the folder via M3b's "Save map to" override. The
  two default paths are the honest 95% case; an index or persisted record of
  past outputs is a different feature.
- Surfacing `flightmap.kml` / `flightmap.geojson` (from `--format all`). They are
  exports, not something the app can open.
- Recursive search for maps in subfolders.
- Any persistence: no MRU, no on-disk state (that is #319).
- The M5 recents/task-cards idle pane. If M5 lands later, these cards are a
  natural fit for the same pane — this change does not block or presume it.
- Deleting or renaming an existing map from the row.

## Release

Rides the next version bump alongside the already-merged #327 fix, M3a and M3b.
Release remains held per the small-userbase call.
