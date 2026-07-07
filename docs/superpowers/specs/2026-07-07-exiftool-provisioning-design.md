# Design: cross-platform, version-aware ExifTool provisioning (#235)

_Date: 2026-07-07_

## Context

The MP4 timed-metadata extractor (#206, `mp4_telemetry.py`) shells out to
ExifTool, and decode coverage is **version-gated per model**: baseline
`djmd`/`dbgi` needs ≥ 13.05, Air 3S (`dvtm_Air3s.proto`) ≥ 13.39, Mini 5 Pro
(`dvtm_Mini5Pro.proto`) ≥ 13.52. A too-old ExifTool *recognises* the streams
but decodes zero GPS — the worst failure mode, because it looks like "no
telemetry" rather than "old tool".

Findings that shape this design (verified 2026-07-07):

1. **`utils/dependency_manager.py` is dead code.** Nothing in `src/` or
   `tests/` imports it; no CLI path has ever called its `download_exiftool()`
   (pinned to a stale 13.32 Windows zip). The real resolver is
   `utils/exiftool.py`: `DJIEMBED_EXIFTOOL_PATH` env override, else `exiftool`
   on `PATH`. There is **no provisioning today on any platform**.
2. **Windows is mostly fine already**: winget delivers `OliverBetz.ExifTool`
   13.59 (current) and `tools/bootstrap.ps1` pins 13.33 (slightly stale). The
   broken platforms are **Linux/macOS via distro packages** — Ubuntu 24.04
   ships 12.76, which decodes no DJI GPS at all. (`brew` is current.)
3. **exiftool.org hosts only the current release** — a pinned
   `exiftool.org/exiftool-13.59_64.zip` URL 404s as soon as 13.60 ships. The
   SourceForge project mirror keeps every historic version. Hardcoded SHA-256
   pins make the mirror trustless: integrity comes from the checksum, not the
   host.
4. Current production release: **13.59**, with published SHA-256 checksums
   (`https://exiftool.org/checksums.txt`).
5. `docs/external-tool-versions.md` currently **recommends 12.76** — the exact
   version that silently decodes nothing. Must be fixed as part of this work.

Decisions taken during brainstorming (2026-07-07):

- **Explicit provisioning only** ("approach A"): normal commands never touch
  the network. A single documented command downloads a pinned ExifTool; error
  messages tell the user exactly that command.
- **Command surface**: `dji-embed doctor --install exiftool` — doctor is the
  established "is my system OK?" entry point; diagnosis and fix live together.
- **No ffmpeg provisioning** (evaluated, rejected): our ffmpeg use
  (`-c copy` remux, subtitle/metadata tags) is not version-sensitive, distro
  packages are adequate, ffmpeg.org publishes no official binaries (pinning
  means trusting three third-party build providers), and static builds are
  25–80 MB. The `--install` flag takes a `Choice` so `ffmpeg` can be added
  later without CLI redesign if a real need appears (e.g. #252 macOS users
  without brew).

## Goals

- One command provisions a pinned, checksum-verified, current ExifTool on
  Windows, Linux, and macOS — no system ExifTool or admin rights required.
- The resolver and `doctor` become version-aware: a too-old ExifTool is
  diagnosed by version and floor, never silently yielding zero telemetry.
- Keep the "new models for free by upgrading ExifTool" property: bumping the
  pin (version + 2 checksums) is the whole upgrade.

## Non-goals

- ffmpeg provisioning (see above).
- Auto-download during normal commands (embed/convert/photomap never touch
  the network).
- Changing the winget / brew / bootstrap install stories (they already
  deliver adequate versions; bootstrap's pin just gets bumped).
- Bundling ExifTool into the wheel or EXE (licence + size, per #235).

## Design

### 1. Provisioning module — new `utils/provision.py`

Pins one ExifTool version and its artifact checksums:

```python
EXIFTOOL_VERSION = "13.59"
# From https://exiftool.org/checksums.txt at pin time.
EXIFTOOL_SHA256 = {
    # Windows: standalone exe bundle
    "exiftool-13.59_64.zip": "44b512b25af500724ba579d0a53c8fc5851628b692dd5e5d94ae4a15c2cba9ec",
    # Linux/macOS: Perl distribution (runs wherever perl exists)
    "Image-ExifTool-13.59.tar.gz": "668ea3acececb7235fbd0f4900e72d5f12c9b07e5c778fd36cb1e9b5828fd65a",
}
```

Download sources, tried in order (same artifact, same checksum — the host is
untrusted):

1. `https://exiftool.org/<artifact>` (current release only)
2. `https://downloads.sourceforge.net/project/exiftool/<artifact>` (all
   versions, survives the next release)

Install flow (`provision_exiftool(force: bool = False) -> Path`):

1. If `tools_dir/exiftool-<ver>/` already exists and its executable answers
   `-ver` with the pinned version → no-op, return the path (unless `force`).
2. Download the platform artifact to a temp file inside `tools_dir`.
3. Verify SHA-256; mismatch → delete temp file, raise with a clear message.
   **Nothing is installed on any failure.**
4. Extract into `tools_dir/exiftool-<ver>/`:
   - **Windows**: extract zip; rename `exiftool(-k).exe` → `exiftool.exe`;
     keep the `exiftool_files/` directory beside it (same layout
     bootstrap.ps1 produces).
   - **Linux/macOS**: extract tarball (strip the `Image-ExifTool-<ver>/`
     top-level dir); the `exiftool` Perl script (shebang `#!/usr/bin/perl`)
     plus `lib/`; `chmod +x exiftool`. Requires Perl, which is effectively
     universal on these platforms; if `perl` is missing, fail with a message
     naming the distro package (`apt install perl` / preinstalled on macOS).
5. Smoke-check: run the installed executable with `-ver`; must print the
   pinned version.
6. Extraction uses a safe helper that rejects path-traversal member names
   (defence in depth — the checksum already gates content).

Per-user tools directory (`tools_dir`), no new dependency — a small helper:

- Windows: `%LOCALAPPDATA%\dji-embed\tools\`
- macOS: `~/Library/Application Support/dji-embed/tools/`
- Linux: `$XDG_DATA_HOME/dji-embed/tools/` (default `~/.local/share/…`)

Older `exiftool-<ver>/` directories from previous pins are left in place
(cheap, ~10 MB) but no longer resolved; `--install` prints a note when it
supersedes one.

### 2. Version-aware resolver — `utils/exiftool.py`

Resolution order for `exiftool_exe()`:

1. `DJIEMBED_EXIFTOOL_PATH` env var (absolute override — unchanged).
2. The **provisioned copy** at `tools_dir/exiftool-<EXIFTOOL_VERSION>/`
   (exists only if the user ran `--install`; pinned-current by construction,
   so it beats PATH without a version comparison).
3. `exiftool` on `PATH`.

New helpers in the same module:

- `exiftool_version() -> str | None` — run resolved executable with `-ver`.
- Version floors as data:

  ```python
  # Minimum ExifTool for DJI djmd/dbgi timed-metadata decode.
  EXIFTOOL_FLOORS = {
      "baseline": "13.05",          # djmd/dbgi recognised + decoded at all
      "dvtm_Air3s.proto": "13.39",  # Air 3S
      "dvtm_Mini5Pro.proto": "13.52",  # Mini 5 Pro
  }
  ```

- `decode_floor(schema: str | None) -> str` — floor for a probed schema
  (falls back to baseline). Version comparison is a numeric two-part compare
  (ExifTool versions are `MAJOR.MINOR`), not string compare.

`mp4_telemetry.py`'s private `_exiftool_version()` moves here (it already
back-compat-aliases the shared resolver).

`utilities.check_dependencies()` (used by `doctor`) additionally looks in the
provisioned tools dir, mirroring its existing Windows-bin-dir handling.

### 3. CLI — `dji-embed doctor --install exiftool`

- New option: `--install <tool>`, `click.Choice(["exiftool"])`. Runs the
  provisioning flow with progress via the standard logger, prints the
  installed path + version, then falls through to the normal doctor report
  (immediate confirmation that resolution now picks it up).
- `run_doctor()` output gains, for exiftool:
  - resolved **version, path, and source** (`env` / `provisioned` / `PATH`);
  - a decode-capability line:
    - `timed-metadata decode: OK (13.59 >= 13.52, covers all supported models)`
    - `timed-metadata decode: LIMITED — 13.20 < 13.39, Air 3S/Mini 5 Pro clips will not decode; run: dji-embed doctor --install exiftool`
    - `timed-metadata decode: UNAVAILABLE — 12.76 < 13.05 baseline; run: dji-embed doctor --install exiftool`
- ffmpeg reporting is unchanged (FOUND/MISSING), except it also shows the
  version when available — cheap symmetry, no capability logic.

### 4. Error-path integration — `mp4_telemetry.py`

- The "ExifTool not found" hint and the "stream present but zero GPS decoded"
  error both end with the concrete fix:
  `Run: dji-embed doctor --install exiftool`.
- When `probe()` returns a schema, the error names the exact floor via
  `decode_floor()`: `Telemetry stream (dvtm_Air3s.proto) needs ExifTool >=
  13.39; you have 12.76.`

### 5. Deletions and housekeeping

- **Delete `utils/dependency_manager.py`** (dead code; superseded by
  `provision.py`) and remove its line from `CLAUDE.md`'s architecture tree.
- Bump `tools/bootstrap.ps1`'s ExifTool pin 13.33 → 13.59 (URL + any
  version-derived paths).

## Testing

All CI tests are offline (mocked downloads); one optional real-network test is
gated behind `DJIEMBED_NETWORK_TESTS=1` and skipped by default.

- **Resolver**: env override wins; provisioned dir beats PATH; PATH fallback;
  version parse/compare (incl. `13.5` vs `13.39` ordering).
- **Floors**: `decode_floor()` schema lookup + baseline fallback; doctor's
  OK/LIMITED/UNAVAILABLE classification at boundary versions.
- **Provisioning**: build tiny fixture archives in-test (a stub `exiftool`
  script / fake `exiftool(-k).exe` + `exiftool_files/`), serve via a mocked
  downloader; assert final layout per platform, exe rename, chmod, smoke
  check.
- **Checksum failure**: corrupted payload → raises, temp file removed,
  nothing installed, second attempt works.
- **Fallback URL**: first source 404s → second source used.
- **No-op reinstall**: existing pinned install short-circuits; `--force`
  reinstalls.
- **Path traversal**: archive member with `../` is rejected.
- **CLI smoke**: `doctor --install exiftool` invokes provisioning (mocked)
  and prints path/version; `doctor` shows version + decode line.
- **Error messages**: too-old version produces the model-specific floor text.

## Documentation

- `docs/MP4_TIMED_METADATA.md`: per-model minimum-version table (from
  `EXIFTOOL_FLOORS`), how provisioning works, where the tools dir lives.
- `docs/external-tool-versions.md`: recommended ExifTool 12.76 → 13.59
  (12.76 explicitly called out as inadequate for MP4 timed metadata), refresh
  the compatibility matrix.
- `docs/installation.md` + `docs/troubleshooting.md`: `dji-embed doctor
  --install exiftool` as the no-admin path to a current ExifTool on any OS
  (esp. Linux distros with old packages).
- `README.md`: one line under the doctor/install section.
- `CLAUDE.md`: architecture tree update (provision.py in, dependency_manager
  out).

## Acceptance criteria (from #235)

- [ ] Pinned ExifTool bumped to current production (13.59) — `provision.py`
- [ ] Provisioning works on Linux/macOS/Windows without system ExifTool —
      tarball/zip flows above
- [ ] Downloads integrity-verified — hardcoded SHA-256, fail-safe on mismatch
- [ ] Too-old ExifTool never silently yields zero telemetry — doctor decode
      line + model-specific floor errors, both naming the fix command
- [ ] `doctor` reports ExifTool version + decode capability — §3
- [ ] Tests for version detection + provisioning, network-mocked — §Testing

## Release-time note

At implementation and at each future pin bump, re-check
`https://exiftool.org/ver.txt` and `checksums.txt`; the pin is
version + two SHA-256 strings, nothing else.
