# GUI M5b — visual polish + queued cleanup

*Design round 2026-07-22 (Marcus + Claude). Second and final M5 PR — closes
the M5 row of the GUI 2.0 workspace spec (2026-07-18): animations,
empty-state hero, accessibility, docs/screenshots. MRU shipped in M5a. The
announcement and the release bump both follow separately on Marcus's word;
the README demo GIF is Marcus's manual recording step after this merges.*

## Decisions taken in the round

- **One PR.** Visual polish, the riding minors from the M5a/M4b reviews,
  and the #354 crash guard all land together, leaving master clean for the
  release + announcement. Rejected: splitting cleanup into its own PR
  (two review cycles for no isolation benefit).
- **Subtle transitions only.** Short enter animations on the big state
  swaps; nothing decorative. Rejected: SukiUI-defaults-only (the abrupt
  panel pops stay) and a richer micro-interaction pass (more XAML to
  maintain than the value returned).
- **Hero effort goes to the idle preview pane.** It is the largest blank
  region on first launch; the drop zone is already decent and gets light
  touch-ups only.
- **Accessibility = accessible-names sweep only.** Keyboard-order and
  contrast audits are deliberately deferred; reduced-motion handling is
  out of scope with them.
- **Docs = MkDocs page + README screenshots.** The demo GIF needs real
  footage on real Windows and stays manual.

## Transitions (enter-only)

- **Mechanism:** pure-XAML keyframe animations via
  `Style Selector="...[IsVisible=True]"` with `Style.Animations` — a
  ~200 ms ease-out opacity fade that plays when the region appears. The
  hero/recents region and the preview state cards additionally get a small
  ~6 px rise via `TranslateTransform`; the options panel fades only (a
  large region sliding reads as layout shift, not polish).
- **Disappearances stay instant.** Animating hide against an `IsVisible`
  binding is where Avalonia timing bugs live, and instant-hide keeps the
  headless tests deterministic — they assert `IsVisible`, never opacity.
- **Where it plays:** the hero/recents region appearing, the per-mode
  options panel on mode change, and the preview pane's state cards (done
  card, error card, verify cards) appearing.
- **Rejected mechanisms:** restructuring the `IsVisible`-switched panels
  into `TransitioningContentControl` cross-fades (invasive rework of a
  working layout) and code-behind animation orchestration (untestable
  timing).
- **Test impact:** none by design — no test asserts opacity, and the
  freeze/screenshot suite keeps passing because visibility semantics are
  untouched.

## Empty-state hero (idle preview pane)

- The idle pane's lone sentence becomes a calm welcome: the app icon
  (existing installer asset), one line on what the app does, the existing
  "everything stays on this computer" reassurance, and the pointer toward
  the drop zone on the left.
- Shown only in the idle/no-source state; every other pane state is
  unchanged.
- Drop zone: light touch-ups only (spacing, optionally a small icon). No
  copy rewrite.

## Accessible-names sweep

- Every interactive control (buttons, toggle switches, combo boxes, text
  boxes, expander headers) in `WorkspaceView` and `CliDiscoveryView` gets
  an `AutomationProperties.Name` — today only 6 controls have one.
- Pinned by a new contract test that walks the visual tree and fails on
  any unnamed interactive control, so future controls cannot regress
  silently. Controls whose visible text already serves as their
  automation name (plain `Button` with text content) pass the test
  without an explicit attribute; the test encodes that rule.

## Issue #354 guard

- `RunCoreAsync` checks the captured folder still exists before the
  folder scan; gone → fail into the status panel with reach-aware copy
  ("That folder is no longer there — was the card ejected? Pick it
  again.") and refresh the recents prune so a vanished folder also drops
  out of the hero list.
- Regression test, red-verified against the current crash.
- No global exception handler this leg — #354 records it as a separate
  consideration.

## Riding minors (triaged)

Fix in this PR:

- `GuiState.Save` doc comment overpromises "never throws" vs the narrow
  catch list — align the wording with the actual catch filter.
- Failed `Save` leaves the `.tmp` file behind — best-effort delete in the
  failure path.
- `SaveNow` pruning dead folders as a side effect of `SaveWindow` — add
  the explaining comment on `SaveWindow`.
- `RememberFolder` rebuilds the observable list unconditionally — rebuild
  only when the pruned list actually differs, avoiding redundant
  `CollectionChanged` churn.
- `FolderLeafName` returns an empty string for bare root paths
  (`C:\`, `/`) — fall back to the path itself.
- Maximize → unmaximize round-trip has no test — add one to
  `MainWindowStateTests`.
- cli.py check-expansion loop: `p.is_dir()` unguarded against
  ancestor-traversal `PermissionError` — wrap in a try/except that skips
  the entry (M4b minor).

No-fix, adjudication recorded here:

- `VerifySubAction` switched three times — reviewer confirmed this is the
  spec-mandated exhaustive-switch pattern; leave as is.
- `ValidateStream` fixture duplicated between two GUI test files — house
  style favors inline literals; drift risk accepted.
- `MainWindow` never unsubscribes its Position/Size/Closing handlers —
  single-window app whose window lives for the process lifetime; gets a
  comment, not a teardown path.

## Docs + screenshots

- New MkDocs page `docs/desktop-app.md`, added to the site nav: install
  (installer download + winget), a tour of the six modes with
  screenshots, the `%APPDATA%\DjiEmbed\state.json` note (what it stores,
  delete to reset), and the WebView2-missing fallback note.
- README gains a short desktop-app section with 2–3 screenshots linking
  to the docs page.
- Screenshots come from the existing `DJIEMBED_CAPTURE_DIR` capture
  matrix — synthetic fixture data only, so no real-GPS leakage risk.
  Committed images live under the docs tree with the site's other assets.

## Non-goals

- Announcement and release/version bump (both follow separately).
- Demo GIF production (Marcus records it manually after merge).
- Keyboard-order, contrast, reduced-motion, screen-reader E2E.
- Any change to persisted state, command builders, or argv — the M5a hard
  boundary and the "state never affects argv" invariant stand untouched.

## Testing

- Suite stays green with zero warnings; freeze/screenshot tests
  unaffected by the enter-only animation rule.
- New tests: accessible-names contract test (visual-tree walk), #354
  regression, maximize→unmaximize round-trip, `FolderLeafName` bare-root
  case, `RememberFolder` no-churn case, failed-Save `.tmp` cleanup,
  cli.py `PermissionError` skip (Python side).
- Screenshot matrix re-captured after the visual changes; the docs/README
  images are generated from it.
- Manual E2E: Marcus reviews the polish on a real Windows build before
  merge sign-off.
