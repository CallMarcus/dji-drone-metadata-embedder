# Requires: GitHub CLI (gh) and `gh auth login`
# Run: pwsh -File .\create-issues.ps1
$ErrorActionPreference = "Stop"

# --- Helpers --------------------------------------------------------------
function Get-Repo() {
  (gh repo view --json nameWithOwner | ConvertFrom-Json).nameWithOwner
}

function Ensure-Label {
  param([string]$Name, [string]$Color = "6E7681", [string]$Description = "")
  $existing = gh api repos/:owner/:repo/labels --paginate | ConvertFrom-Json
  if (-not ($existing | Where-Object name -eq $Name)) {
    gh api -X POST repos/:owner/:repo/labels `
      -f name="$Name" -f color="$Color" -f description="$Description" | Out-Null
  }
}

function Ensure-Milestone {
  param([string]$Title)
  $ms = gh api repos/:owner/:repo/milestones | ConvertFrom-Json
  if (-not ($ms | Where-Object title -eq $Title)) {
    gh api -X POST repos/:owner/:repo/milestones -f title="$Title" | Out-Null
  }
}

function New-IssueRaw {
  param([string]$Title, [string]$Body, [string]$MilestoneName)
  # Create issue WITHOUT labels first (avoid hard failure)
  $url = gh issue create --title $Title --body $Body --milestone "$MilestoneName"
  # Return URL printed by gh
  return $url.Trim()
}

function Add-Labels-To-Issue {
  param([string]$IssueUrl, [string[]]$Labels)
  if (-not $Labels -or $Labels.Count -eq 0) { return }
  $issue = gh issue view $IssueUrl --json number | ConvertFrom-Json
  $labelsArg = ($Labels -join ",")
  gh issue edit $issue.number --add-label "$labelsArg" | Out-Null
}

# --- Setup ---------------------------------------------------------------
$repo = Get-Repo
Write-Host "Repo: $repo"

# Labels (name -> color)
$LabelMap = @{
  "enhancement"   = "A2EEEF"
  "bug"           = "D73A4A"
  "help wanted"   = "008672"
  "good first issue" = "7057FF"
  "priority:high" = "B60205"
  "priority:med"  = "FBCA04"
  "blocked"       = "000000"
  "type:build"    = "BFD4F2"
  "type:ci"       = "C5DEF5"
  "type:parser"   = "F9D0C4"
  "type:cli"      = "C2E0C6"
  "type:docs"     = "E4E669"
  "type:release"  = "BFDADC"
}

Write-Host "Ensuring labels exist…"
$LabelMap.GetEnumerator() | ForEach-Object {
  Ensure-Label -Name $_.Key -Color $_.Value
}

Write-Host "Ensuring milestones exist…"
$M1 = "M1 – Stabilise & Version Cohesion (Week 1–2)"
$M2 = "M2 – CI/Build Reliability (Week 2–3)"
$M3 = "M3 – Parser Hardening & CLI UX (Week 3–5)"
$M4 = "M4 – Docs, Samples & Release Hygiene (Week 5–6)"
@($M1,$M2,$M3,$M4) | ForEach-Object { Ensure-Milestone $_ }

# --- Issues spec ---------------------------------------------------------
$issues = @(
  @{ t="tools: add sync_version.py to propagate version"; m=$M1; labs=@("type:build","priority:high","good first issue","enhancement"); body=@"
**Why**
Keep version single-source from `pyproject.toml` across README badge, winget manifest, bootstrap script, and PyInstaller spec.

**What**
- Create `tools/sync_version.py`
- `python tools/sync_version.py 1.2.3` updates all targets
- `--check` mode exits non-zero if drift detected

**Acceptance Criteria**
- [ ] Running with a version updates all targets
- [ ] `--check` fails CI on drift
- [ ] Unit test covering version parsing and file updates
"@ },
  @{ t="ci: fail when tag ≠ pyproject version"; m=$M1; labs=@("type:release","priority:high","enhancement"); body=@"
**Why**
Prevent broken releases where git tag and package version diverge.

**What**
- Add a CI job that runs on tag builds
- Assert tag `vX.Y.Z` == version in `pyproject.toml` via `tools/sync_version.py --check`

**Acceptance Criteria**
- [ ] Tag mismatch produces a clear, actionable failure message
- [ ] Happy path demonstrated in a test tag on a branch
"@ },
  @{ t="ci: split tag-driven releases (PyPI / EXE / winget)"; m=$M1; labs=@("type:ci","type:release","priority:high","enhancement"); body=@"
**Why**
Make releases deterministic and observable per artefact.

**What**
- `.github/workflows/release-pypi.yml` (push tags: `v*`)
- `.github/workflows/release-exe.yml` (Windows build; attach to GitHub Release)
- `.github/workflows/release-winget.yml` (submit/update via wingetcreate)

**Acceptance Criteria**
- [ ] Tagging `vX.Y.Z` runs all three in order
- [ ] Each job runs `sync_version.py --check` before publishing
- [ ] Job summaries link to artefacts / PRs
"@ },
  @{ t="release: attach SHA256 and print toolchain versions"; m=$M1; labs=@("type:release","type:build","enhancement"); body=@"
**Why**
Provenance and easier user support.

**What**
- Compute and upload SHA256 for EXE and wheel
- `dji-embed --version` prints app, FFmpeg, ExifTool versions

**Acceptance Criteria**
- [ ] Release assets include `SHA256SUMS.txt`
- [ ] `--version` outputs toolchain versions
"@ },
  @{ t="ci: test matrix (Windows + Linux; py310–py312)"; m=$M2; labs=@("type:ci","priority:med","enhancement"); body=@"
**Why**
We ship Windows EXE but also support Linux users.

**What**
- `.github/workflows/test.yml` with OS × Python matrix
- Cache `pip` and build directories

**Acceptance Criteria**
- [ ] Matrix runs for 3.10, 3.11, 3.12 on windows-latest & ubuntu-latest
- [ ] All legs green
"@ },
  @{ t="ci: smoke test wheel & EXE using tiny fixtures"; m=$M2; labs=@("type:ci","priority:high","enhancement"); body=@"
**Why**
Catch runtime regressions early.

**What**
- After build, run:
  - `dji-embed --version`
  - `dji-embed embed --dry-run -i tests/fixtures/sample.mp4 -s tests/fixtures/sample.srt`

**Acceptance Criteria**
- [ ] Non-zero exit fails the job
- [ ] Logs show summarised result
"@ },
  @{ t="build: pin FFmpeg/ExifTool versions and expose via --version"; m=$M2; labs=@("type:build","priority:med","enhancement"); body=@"
**Why**
Reproducible builds and debuggability.

**What**
- Dockerfile/installer: ARGs for FFmpeg/ExifTool exact versions
- Binary embeds tool versions

**Acceptance Criteria**
- [ ] Fixed versions documented
- [ ] `--version` prints FFmpeg/ExifTool versions
"@ },
  @{ t="deps: introduce requirements.lock for reproducible builds"; m=$M2; labs=@("type:build","priority:med","enhancement"); body=@"
**Why**
Stability across CI runs.

**What**
- Generate `requirements.lock`
- CI verifies the lock; document policy for updates

**Acceptance Criteria**
- [ ] Build uses exact locked versions
- [ ] Docs explain how to refresh the lock
"@ },
  @{ t="tests: add golden fixtures for SRT & HTML-SRT across 4 DJI model families"; m=$M3; labs=@("type:parser","type:ci","priority:high","enhancement"); body=@"
**Why**
Parser stability across model/firmware differences.

**What**
- Add permissively-licensed tiny SRT/HTML-SRT fixtures for Mavic/Air/Mini/Avata
- Snapshot-style tests

**Acceptance Criteria**
- [ ] `pytest -k parser` passes with fixtures
- [ ] Fixtures < 1MB each
"@ },
  @{ t="parser: lenient mode with structured warnings"; m=$M3; labs=@("type:parser","priority:high","enhancement"); body=@"
**Why**
Do not hard-fail on unknown tags in wild SRT variants.

**What**
- `--lenient` flag: tolerate unknown fields
- Emit warnings at end and via optional JSON log

**Acceptance Criteria**
- [ ] Strict mode unchanged (fails on unknowns)
- [ ] Lenient mode completes with non-zero warning count (exit 2)
"@ },
  @{ t="parser: unit normalisation & sanity checks (altitude/speed)"; m=$M3; labs=@("type:parser","priority:med","enhancement"); body=@"
**Why**
Consistent units and guard against nonsense values.

**What**
- Normalise altitude/speed units
- Range guards + warning summaries

**Acceptance Criteria**
- [ ] Tests cover unit conversions and out-of-range detection
"@ },
  @{ t="cli: add --time-offset and resample strategy for SRT↔MP4 alignment"; m=$M3; labs=@("type:parser","type:cli","priority:med","enhancement"); body=@"
**Why**
Handle VFR edits and drift.

**What**
- Flags: `--time-offset`, `--resample-strategy` (document options)
- Dry-run shows proposed alignment

**Acceptance Criteria**
- [ ] Integration test demonstrates offset applied
"@ },
  @{ t="cli: implement validate command (drift report)"; m=$M3; labs=@("type:cli","priority:high","enhancement"); body=@"
**Why**
Let users assess sync quality before writing.

**What**
- `dji-embed validate -i video.mp4 -s log.srt`
- Report mean/max drift; threshold configurable
- Exit non-zero when drift > threshold

**Acceptance Criteria**
- [ ] Tests cover pass/fail scenarios
- [ ] Docs include examples
"@ },
  @{ t="cli: subcommands (embed, validate, export, probe) + consistent exit codes"; m=$M3; labs=@("type:cli","priority:high","enhancement"); body=@"
**Why**
Clear UX and scriptability.

**What**
- Subcommands: `embed`, `validate`, `export [gpx|csv|json]`, `probe`
- Exit codes: 0 OK, 2 warnings, 1/≥3 error
- Shared flags: `--lenient`, `--time-offset`, `--log-json`

**Acceptance Criteria**
- [ ] `--help` shows concise examples
- [ ] Integration tests enforce exit codes
"@ },
  @{ t="cli: optional --log-json (machine-readable warnings/errors)"; m=$M3; labs=@("type:cli","priority:med","enhancement"); body=@"
**Why**
Tooling/automation friendliness.

**What**
- JSON Lines output for events when enabled

**Acceptance Criteria**
- [ ] Valid JSON lines emitted with timestamps and categories
"@ },
  @{ t="docs: decision table — which path do I take?"; m=$M4; labs=@("type:docs","priority:med","enhancement"); body=@"
**Why**
Reduce user confusion and support load.

**What**
- Add a table mapping scenarios → exact commands
- SRT-only, SRT+DAT, GPX export, validate-then-embed

**Acceptance Criteria**
- [ ] README updated with copy-paste commands and expected outputs
"@ },
  @{ t="docs: end-to-end recipes (4 common flows)"; m=$M4; labs=@("type:docs","priority:med","enhancement"); body=@"
**Why**
Concrete, testable guidance.

**What**
- Four recipes with inputs/outputs and pitfalls

**Acceptance Criteria**
- [ ] Recipes render on GitHub Pages if enabled
"@ },
  @{ t="docs: troubleshooting guide (model quirks, VFR drift, codecs)"; m=$M4; labs=@("type:docs","priority:med","enhancement"); body=@"
**Why**
Common failure modes are predictable.

**What**
- Error messages → likely causes → fixes/flags to try
- Links to `probe` and `validate` usage

**Acceptance Criteria**
- [ ] At least 10 FAQ-style entries with commands
"@ },
  @{ t="tests: add public tiny sample MP4/SRT fixtures"; m=$M4; labs=@("type:ci","type:docs","priority:med","enhancement"); body=@"
**Why**
Enable local and CI smoke tests.

**What**
- Add tiny permissively-licensed fixtures
- Or scripted download from a stable public URL

**Acceptance Criteria**
- [ ] Size < 1MB each
- [ ] Used by CI smoke tests
"@ },
  @{ t="release: auto-changelog from conventional commits"; m=$M4; labs=@("type:release","priority:med","enhancement"); body=@"
**Why**
Consistent release notes.

**What**
- `release-please` or `git-cliff` to generate notes
- Include breaking changes, features, fixes, upgrade tips

**Acceptance Criteria**
- [ ] Tagging `vX.Y.Z` produces a well-structured changelog
"@ },
  @{ t="release: winget manifest sync from pyproject via sync_version.py"; m=$M4; labs=@("type:release","priority:med","enhancement"); body=@"
**Why**
Keep winget aligned without manual edits.

**What**
- Update manifest from `pyproject.toml` during release
- Submit via `wingetcreate` or open PR automatically

**Acceptance Criteria**
- [ ] Logs link to the winget submission/PR
"@ }
)

# --- Create issues, then add labels -------------------------------------
$created = @()
foreach ($i in $issues) {
  Write-Host "Creating: $($i.t)"
  $url = New-IssueRaw -Title $i.t -Body $i.body -MilestoneName $i.m
  Write-Host " -> $url"
  $created += @{ url=$url; labels=$i.labs }
}

Write-Host "`nAdding labels to created issues…"
foreach ($c in $created) {
  Add-Labels-To-Issue -IssueUrl $c.url -Labels $c.labels
}

Write-Host "`nDone."
