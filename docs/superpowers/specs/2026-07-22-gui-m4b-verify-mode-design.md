# GUI M4b — Verify mode

*Design round 2026-07-22 (Marcus + Claude). Amends nothing; implements the
Verify row of the mode-curation table in the GUI 2.0 workspace spec
(2026-07-18) on top of the M4a source lift. Completes the M4 milestone —
the second of the two PRs decided in the M4a round.*

## Decisions taken in the round

- **Mismatched sub-actions grey out.** The sub-action switch disables
  segments the current source shape cannot feed, instead of the
  block-with-guidance run guard used for mode/source mismatches. The
  geometry makes this safe: a file disables only Validate pairing, a
  folder disables only Sun check, no source disables nothing — so at most
  one segment is ever grey, and it gets an inline note explaining itself.
- **`check` learns directories in the CLI**, not in the GUI. The
  subcommand today ffprobes a directory argument itself (the media glob
  lives only in the standalone `metadata_check` entry point); expanding it
  in the CLI keeps the frontend thin, keeps the transparency strip short
  and honest (`check <folder>`), and fixes the quirk for terminal users
  too. Rejected: GUI-side enumeration (strip becomes a file dump) and
  file-only Check (a folder of embedded MP4s is the natural post-Embed
  spot-check).
- **Validate's report card is verdict + issue rows.** The per-file drift
  table (`file_analyses`) stays CLI-only (`validate --format json`) —
  analyst-grade detail per the curated-options philosophy. The issue and
  warning strings already name the offending files.

## Sub-action model

- `VerifySubAction { Check, Validate, Sun }`. The options panel leads with
  a three-segment switch: **Check metadata / Validate pairing / Sun
  check**. Default: Check — the only sub-action valid for both source
  shapes, and the defaults invariant (untouched Verify runs bare
  `check <source>`).
- Verify's `SourceKinds` = `Folder | File`; the M4a source slot works
  unchanged. File drops keep suggesting Convert (M4a rule untouched);
  Verify is never auto-suggested.
- Enablement from the source shape:

  | Source | Check | Validate | Sun |
  |---|---|---|---|
  | none | ✓ | ✓ | ✓ |
  | file | ✓ | greyed | ✓ |
  | folder | ✓ | ✓ | greyed |

  The one greyed segment gets a quiet inline note beneath the switch
  (pinned strings, GUI language): Validate greyed → "Validate pairing
  compares a whole folder of videos with their flight logs — choose a
  folder." Sun greyed → "Sun check reads one flight log or video — drop a
  single file." No source → no note.
- **Snap-back:** when a source change disables the selected sub-action,
  selection moves to Check metadata. The switch never rests on a disabled
  segment, so the action button and strip never describe a run that can't
  happen. (`verify-sun` accepts SRT *and* MP4/MOV — `load_gps_points`
  routes videos through the ExifTool extractor — so every file the source
  slot accepts keeps Sun check enabled.)
- The action verb adapts to the sub-action: "Check metadata" / "Validate
  pairing" / "Check the sun". Running message: "Checking…" /
  "Validating…" / "Checking the sun…". Failure message: "Something went
  wrong while verifying the footage."

## CLI work item: `check` directory expansion (first commit, additive)

- The `check` subcommand expands a directory argument to its top-level
  media files, sharing one helper with the standalone entry's glob
  (`*.mp4/MP4/mov/MOV/jpg/JPG`); top level only, consistent with the
  non-recursive-command guards. File arguments unchanged.
- JSONL stays contract-shaped: `start.total` and the `progress` events
  count the *expanded* file list; `summary.files` keys are file paths. An
  empty directory yields `{"checked": 0, "files": {}}` with a warning —
  the GUI's #346-style pre-run guard should normally prevent that run.
- One added paragraph in `docs/PROGRESS_JSONL.md` under `### check`.
  Python-side TDD; suite baseline 687.

## Options and argv

- Curated controls: the sub-action switch **is** the curated control. No
  output/save section — Verify writes nothing.
- One **Advanced** expander, contextual sections in the Convert-CoT mould:
  - **DriftSection** (visible only for Validate): drift-threshold slider,
    snap-to-tick, 0.5–5.0 s in 0.5 steps, default 1.0 s (the CLI
    default; omitted from argv when untouched). Sliders, never
    double-bound TextBoxes — the CotInterval culture lesson.
  - **TzSection** (visible only for Sun): timezone offset text box in the
    Convert `--tz-offset` mould — string passthrough, empty = the CLI's
    `auto` default, culture-safe because it is never parsed as a number.
- Record `VerifyTelemetryOptions` (SubAction, DriftThreshold, TzOffset) +
  `VerifyOptionsViewModel`, VM property `VerifyOptions` — the M3d naming
  convention. Choice records co-located with the single-consumer VM.
- **`CommandBuilder.Verify(source, options)`** feeds run + strip, with the
  exhaustive-switch idiom:
  - Check → `check <source>`
  - Validate → `validate <folder>` (+ `--drift-threshold X` off-default;
    invariant-culture serialization)
  - Sun → `verify-sun <file>` (+ `--tz-offset X` when set)
- Idle strip placeholder before a source is picked: `check <source>`.

## Mode/source guards

`CanRun` semantics unchanged from M4a. The sub-action greying removes the
shape-mismatch class before the run, but the folder-content guard remains:
Check or Validate on a folder with no top-level media/flight logs blocks
with #346-style pinned guidance (Check needs top-level videos or photos;
Validate needs top-level videos or flight logs). Sun check needs no guard
beyond the file itself — the CLI's failure is the answer and surfaces
through the normal error card.

## Report cards

The done pane renders **report cards, never raw text** (spec grace note),
via the proven `DoctorReport.Parse` pattern: pure static parsers over the
result event's `Summary` JsonElement, one per sub-action, all producing one
shared display shape — a **headline** string plus rows of
`VerifyCard(Status, Title, Detail)` (status glyph ✓/⚠/✗). One display
record → one ItemsControl in the done pane; three parsers in
`Services/VerifyReport.cs`:

- **CheckReport**: headline "Checked 12 files"; one row per file — title =
  file name, detail = "GPS ✓ · Altitude ✓ · Recording time ✗", status =
  worst-of: ✓ when all three flags are present, ⚠ when some are missing.
  An unreadable entry (`{}`) → ✗ "Couldn't read this file."
- **ValidateReport**: headline verdict — "Everything pairs up — 12 of 12"
  when clean, "11 of 12 pairs check out" otherwise; one row per issue (⚠)
  and per report warning, in the report's own words.
- **SunReport**: stat rows (GPS points, UTC span, sun elevation range,
  azimuth start → end) plus flags translated to novice language: `night` →
  "Shot at night — the sun was below the horizon the whole time";
  `very_low_sun` → "The sun was very low — long shadows, near sunrise or
  sunset"; `sun_not_computable` → "Couldn't work out the sun's position —
  the file has no usable timestamps."
- Malformed or missing summaries parse to an empty card list, never throw
  (the DoctorReport degradation rule).
- **No double display:** validate's issues and sun's flags are *also*
  emitted as JSONL `warning` events, so a successful Verify run shows the
  report instead of the generic warnings expander. Failure paths keep the
  standard error card + stderr details.

## Testing

House pattern throughout: TDD; CommandBuilder golden tests (option state
in, argv out, defaults invariant `check <source>`); parser unit tests fed
real JSONL summary shapes including empty/malformed; named controls +
`Assert.Same(vm.X, control.Command)` binding-identity checks; every panel
mutation paired with a `CommandPreview` assertion; enablement + snap-back
tests for the switch; pinned-string tests for the inline notes and guards;
the shared freeze test grows the Verify panel; screenshot capture
`workspace-verify-options.png` (interleaved-tick idiom). Python side:
check-expansion tests + the PROGRESS_JSONL.md paragraph. GUI suite
baseline 385.
