# GUI: recursion-mismatch guards and busy gating (issues #333, #338, #340)

**Status:** approved 2026-07-21 (design discussed and accepted in session; option
"block with guidance" chosen by the maintainer).

## Problem

Three shipped defects share two root causes:

1. **A recursive folder scan feeds commands that are not recursive.**
   `FolderInspector.Inspect` always scans subfolders, so the workspace's
   pre-flight guards pass whenever media exists *anywhere* under the picked
   folder — but `embed` reads one directory level only, and
   `flightmap`/`photomap` recurse only with `-r` ("Include subfolders").
   Result: the CLI's `-r`-flavoured error surfaces in a GUI that has a toggle
   for exactly that (#333), and Embed reports a hollow "✅ Done" over a
   zero-file warning run (#338).
2. **Work outlives the UI state that owns it.** The left column stays live
   during a run (the CLI transparency strip can repaint to show flags the
   running process does not have), and there is a pre-`Running` window during
   the folder scan where the clear/replace guards are open (#340).

## Decision

Block mismatched runs **before** they start, with guidance in GUI language;
freeze the left column for the whole run, starting at the first line of
`RunAsync`; make the scan injectable so the busy window is testable.

## 1. Depth-aware `FolderInspector`

`FolderContents` grows three flags, computed in the **same single
enumeration** (no second I/O pass):

```csharp
public sealed record FolderContents(
    bool HasFlightLogs, bool HasPhotos, bool HasVideos,
    bool HasTopLevelFlightLogs, bool HasTopLevelPhotos, bool HasTopLevelVideos,
    DateTime? NewestFlightLogUtc, DateTime? NewestPhotoUtc);
```

A file is top-level when its parent directory equals the inspected folder
(path-compare the directory name `Path.GetDirectoryName(file)` against the
normalised root; `Path.TrimEndingDirectorySeparator` both sides,
`OrdinalIgnoreCase` — same-volume enumeration returns consistent casing, and
this comparison only ever runs on strings produced by one
`Directory.EnumerateFiles` call over one root).

Unchanged on purpose:

- The `#328` per-kind newest-write timestamps stay **recursive**. Freshness
  semantics shipped that way; not touched here.
- The scan still has no early exit (timestamps need every file).

## 2. Guards match the command's reach (#333, #338)

In `WorkspaceViewModel.RunAsync`, each mode's guard reads the flag matching
what the command will actually read:

| Mode | Toggle | Guard requires | On "media only deeper" | On "no media at all" |
|---|---|---|---|---|
| Flight map | Include subfolders ON | `HasFlightLogs` | n/a (reachable) | existing message, "subfolders are included automatically" clause kept |
| Flight map | OFF | `HasTopLevelFlightLogs` | "Those flight logs are in subfolders — turn on **Include subfolders**." | existing message **without** the subfolders clause |
| Photo map | ON | `HasPhotos` | n/a | existing message, clause kept |
| Photo map | OFF | `HasTopLevelPhotos` | "Those photos are in subfolders — turn on **Include subfolders**." | existing message without the clause |
| Embed | (no toggle) | `HasTopLevelVideos` | "The videos are in subfolders, and Embed reads only the folder you pick — pick the subfolder that holds the videos." | existing message |

Notes:

- The existing not-found messages currently always say "subfolders are
  included automatically" — untrue when the toggle is off. The clause becomes
  conditional on the mode's recursive setting.
- All guidance goes through the existing `Fail(...)` failure card; no new UI
  element.
- Mode-suggestion chips stay anywhere-based: the option defaults have
  recursion ON, so suggestions remain honest, and a subfolder-only Embed
  suggestion now lands on guidance instead of a hollow success.

## 3. Busy from the first line of `RunAsync` (#340 §2)

New observable `IsBusy` on `WorkspaceViewModel`:

- Set `true` at the top of `RunAsync`, cleared in a `finally` around the whole
  body — it spans the folder scan **and** the run (`Step == Running` starts
  later, inside `ExecuteFlowAsync`).
- `ClearFolder`, `SetFolderAsync` and the existing-map open path gate on
  `IsBusy` instead of `Step == FlowStep.Running`.
- The post-scan `SelectedFolder != folder` ownership re-check **stays** as
  defence in depth; its test keeps passing.
- `RunSetupAsync` (doctor) runs under the same flag — `RunAsync` is the single
  entry point, so the `finally` covers it.
- `SelectedMode` is a bare observable property (no command to gate), so
  `RunAsync` additionally captures the mode **and** its options snapshot
  before the awaited scan and uses only the captures afterwards — a mid-scan
  mode or option change (programmatic or otherwise) cannot pair folder A with
  mode/options B. The disabled strip (§4) closes the UI path; the captures
  close the ViewModel path.

## 4. Left column frozen while busy (#340 §1)

`WorkspaceView.axaml`: bind `IsEnabled` of the folder card (SOURCE), the mode
strip (MODE) and the options container (OPTIONS) to `!IsBusy`. The strip's
promise — what is shown is what runs — holds for the duration of a run because
nothing that feeds it can change. The strip's Copy button stays enabled.

## 5. Injection seam (#340 §3)

`WorkspaceViewModel` gains an optional ctor parameter following the existing
`cliResolver`/`previewAvailable` pattern:

```csharp
Func<string, FolderContents>? folderInspector = null   // defaults to FolderInspector.Inspect
```

Both scan sites (`SetFolderAsync`, `RunAsync`) call it. Tests wrap it in a
gate (e.g. block on a `TaskCompletionSource` inside `Task.Run`) to hold the
scan open and prove mid-scan interactions are inert.

## Out of scope (recorded decisions)

- **CLI `embed` semantics unchanged:** zero matching MP4s remains a warning
  with `ok: true` and exit 0. Scripts depend on exit codes; the
  recursion mismatch is a GUI concept and is now caught before the CLI runs.
- **#328 freshness stays recursive** (see §1).
- No auto-fix buttons (flip-the-toggle-and-rerun was considered and rejected:
  two different behaviours for map vs Embed, more code for marginal benefit).

## Testing

TDD throughout (current GUI suite: 318).

- `FolderInspectorTests`: per-kind top-level vs nested-only vs both fixtures.
- `WorkspaceViewModelTests`: guard matrix per mode × toggle state ×
  media depth — blocked runs never invoke the CLI (FakeCli not called), and
  each guidance string is pinned.
- Busy window via the seam: while the scan is held open, `ClearFolder` and
  `SetFolderAsync` are inert, and a mid-scan `SelectedMode`/option change does
  not alter the executed argv (captures win); `IsBusy` raises change
  notifications.
- View-level (headless): folder card, mode strip and options container are
  disabled while a run is in flight and re-enable after.
