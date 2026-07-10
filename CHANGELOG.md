# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Project Status: Production Ready** ✅
>
> All major milestones (M1-M4) have been completed. The project features comprehensive 
> documentation, automated testing, professional CLI, and streamlined release processes.
> Future releases will focus on new DJI model support and community enhancements.

## [Unreleased]

_No changes yet._

## [1.16.0] - 2026-07-10

### Added

- **flightmap**: Combined map of every flight in a folder of SRT logs (#262) (724fdc7)

### Documentation

- Auto-generate changelog for v1.15.0 (55922a3)

### Other

- Prepare version 1.16.0 (038a3b9)


## [1.15.0] - 2026-07-08

### Added

- **convert**: Redact the per-frame track in gpx/csv exports (#255) (5d85826)
- **deps**: Cross-platform, version-aware ExifTool provisioning (#254) (e518b84)

### Fixed

- **cli**: Accept a directory for convert -o, writing <stem>.<ext> into it (#260) (32798a1)
- **convert**: Clamp estimate_utc_offset to plausible timezones and warn on failure (#261) (8c7c654)
- **convert**: Exclude pre-GPS-lock (0,0) frames from GPX tracks (#258) (41da1b4)

### Documentation

- Add winget install instructions and badge (now live on winget) (89a69e8)
- Auto-generate changelog for v1.14.0 (7f37fba)

### Other

- Prepare version 1.15.0 (6fd5f65)


## [1.14.0] - 2026-07-06

### Added

- **photomap**: #245 follow-ups — recursive names, clampToGround, DNG previews + Windows CI (#250) (45f3e46)

### Fixed

- **embed**: Loosen --audio-sidecar duration-mismatch tolerance (#251) (fbdec3b)

### Documentation

- Auto-generate changelog for v1.13.0 (0fd2fc9)

### Other

- Prepare version 1.14.0 (1527c40)


## [1.13.0] - 2026-07-06

### Added

- **embed**: --audio-sidecar to mux Neo 2's separate .m4a audio (#247) (05c94c4)

### Documentation

- Auto-generate changelog for v1.12.0 (f0e7361)
- Replace stale model table with pointer to the canonical list (620b289)

### Other

- Prepare version 1.13.0 (0ec77aa)


## [1.12.0] - 2026-07-05

### Added

- **cli**: Photomap — map still-photo locations to HTML/KML/GeoJSON (#244) (b085a63)

### Fixed

- **winget**: Submit a staged manifest directory, not file args (4dd7fe9)

### Documentation

- Auto-generate changelog for v1.11.0 (4bea54b)
- Sync documentation with v1.11.0 reality (+ version-stamp auto-sync) (#240) (0a75ff2)

### CI/CD

- Bump actions/checkout from 6 to 7 in the actions group (#241) (b2b8b85)

### Maintenance

- **deps**: Bump the production-deps group with 5 updates (#242) (5049593)
- **winget**: Bump manifests to schema 1.12.0; drop invalid InstallModes (#239) (974f001)
- **winget**: Fix manifests + flow for first-time submission (#238) (463eca9)

### Other

- Prepare version 1.12.0 (47c9e72)


## [1.11.0] - 2026-06-21

### Added

- Opt-in HOME-point (launch location) extraction (#237) (2fea995)

### Documentation

- Auto-generate changelog for v1.10.0 (7797746)

### Other

- Prepare version 1.11.0 (c0ce4bb)


## [1.10.0] - 2026-06-20

### Added

- ExifTool-backed MP4 timed-metadata extractor for sidecar-less footage (#206) (#236) (4e5bd00)

### Documentation

- **readme**: Document v1.9.0 Map tab and footprint flags (e40e27c)
- Auto-generate changelog for v1.9.0 (1215392)

### Other

- Prepare version 1.10.0 (17da414)


## [1.9.0] - 2026-06-20

### Added

- **geo**: Camera-footprint polygons for GeoJSON/KML export (#215) (#233) (29cb2c4)
- **ui**: Interactive flight-path map panel in the web UI (#222) (#234) (18280b6)

### Documentation

🚨 - **geo**: Fix spec README link breaking mkdocs --strict (6b5c363) **[BREAKING]**
- Auto-generate changelog for v1.8.0 (ff15bdd)

### CI/CD

- **release**: Fix PowerShell parser error in EXE wheel-download retry (1d8a548)

### Other

- Prepare version 1.9.0 (ef75aa8)


## [1.8.0] - 2026-06-13

### Added

- **geo**: CoT (Cursor-on-Target) export (#217) (#232) (68c2182)
- **geo**: Sun-position (shadow) check for footage verification (#231) (98ad849)

### Documentation

- Auto-generate changelog for v1.7.0 (53d46aa)

### CI/CD

- **release**: Retry PyPI wheel download to ride out simple-index lag (e768b4f)

### Maintenance

- **deps**: Bump the production-deps group across 1 directory with 5 updates (#226) (d7d5138)
- **deps**: Sync uv.lock with hatchling 1.30.1 (41469da)
- **deps-dev**: Bump hatchling from 1.29.0 to 1.30.1 in the development-deps group (#227) (4513f8c)


## [1.7.0] - 2026-06-06

### Added

- **geo**: Standalone HTML flight-path viewer (Phase 2, #221) (#228) (1d2e17e)

### Documentation

- **housekeeping**: Log 2026-06 file sweep, refresh to v1.6.0 (25f6f22)
- **roadmap**: Note gui/ Tk skeleton removed in cleanup pass (7601826)
- Auto-generate changelog for v1.6.0 (9c45b6c)
🚨 - Fix broken README link breaking strict mkdocs build (474976e) **[BREAKING]**

### Maintenance

- **repo**: Prune stale artifacts and untrack local-only plans (832bbf1)

### Other

- Prepare version 1.7.0 (ddac3e9)


## [1.6.0] - 2026-06-05

### Added

- **geo**: GeoJSON + KML track export (Phase 1, #215) (#223) (90bf00a)
- **samples**: Formalize DJI Air 3S support (#220) (f23f46f)

### Documentation

- **release**: Correct winget submission as a manual step (347c2f2)
- **research**: Add 2026-05-20 ChatGPT + Gemini DJI telemetry reports (#225) (bc51691)
- Auto-generate changelog for v1.5.1 (5a42633)
- Refresh version stamps to v1.5.1 and mark mapping Phase 1 shipped (167a368)

### Maintenance

- **deps**: Bump urllib3, idna, pymdown-extensions for security advisories (155068b)
- **deps**: Regenerate uv.lock and switch Dependabot to uv ecosystem (53f8467)
- Ignore Windows .lnk shortcuts (cf89206)

### Other

- Prepare version 1.6.0 (220d537)


## [1.5.1] - 2026-06-03

### Added

- **samples**: Formalize DJI Neo 2 support (950e303)

### Fixed

- **parser**: Ignore pre-GPS-lock 0,0 frames in geotagging (2469d9b)

### Documentation

- Auto-generate changelog for v1.5.0 (345d754)
- State intended use & scope (transparency/verification focus) (e6b6856)

### Maintenance

- **deps-dev**: Bump the development-deps group with 4 updates (#219) (8fa7831)

### Other

- Prepare version 1.5.1 (8000cd4)


## [1.5.0] - 2026-05-30

### Added

- **embedder**: Add --container mkv to preserve djmd/dbgi data streams (6c4d512)
- **gpx**: UTC timestamps with timezone auto-detection (11a3419)
- **parser**: Capture FrameCnt counter and BAROMETER value (dfaf124)

### Fixed

- **gpx**: Annotate gps_points for mypy (482f746)

### Documentation

- Auto-generate changelog for v1.4.0 (d8765b2)

### Maintenance

- **release**: Bump version to 1.5.0 (122f813)


## [1.4.0] - 2026-05-30

### Added

- **parser**: Add Avata 360 + Mini 5 Pro support (b121b76)

### Fixed

- **changelog**: Skip the tag being published when finding the previous one (e16d8e9)

### Documentation

- **changelog**: Backfill v1.1.1 through v1.3.1 release notes (5edd48a)
- **spec**: Design for Avata 360 + Mini 5 Pro support (f79e24e)

### Maintenance

- **release**: Bump version to 1.4.0 (71b9ecb)


## [1.3.1] - 2026-05-17

Regression-fix release for v1.3.0.

### Fixed

- **embed**: Skip untaggable DJI data streams and switch validator from file-size to ffprobe duration check (#198). The v1.3.0 `-map 0 -map 1` change exposed an ffmpeg limitation on real Air 3S / Neo 2 footage — the proprietary `djmd` / `dbgi` data streams have valid FOURCC tags in the source but resolve to `codec=none`, which the MP4 muxer refuses to write. v1.3.1 keeps every video/audio stream plus the SRT, drops the unwritable data tracks, and validates output by comparing media durations.

### Documentation

- Invite sample SRT submissions for new model support (af67846)

### Acknowledgements

- Thanks to **David** for contributing Air 3S sample footage that exposed the data-stream issue while testing v1.3.0 end-to-end.

### Known follow-ups

- [#197](https://github.com/CallMarcus/dji-drone-metadata-embedder/issues/197) — preserving the dropped `djmd` / `dbgi` streams (likely via opt-in MKV output).

## [1.3.0] - 2026-05-16

### Added

- **parser**: M300 legacy-with-unit and P4 RTK compact SRT formats (#190)
- **chore**: `.gitattributes` to enforce LF line endings repo-wide (#194), preventing CRLF drift on Windows clones

### Fixed

- **embed**: Preserve all input streams with `-map 0 -map 1` (#193). Without explicit `-map`, ffmpeg silently picks one stream per type and drops the rest — losing proxy / data tracks on newer DJI models (Neo 2, Air 3S). Surfaced via [discussion #192](https://github.com/CallMarcus/dji-drone-metadata-embedder/discussions/192).
- **docs**: Exclude archival research dir from mkdocs strict build (#186)

### Documentation

- Model survey, raw research reports, and comparator analysis (#184)
- Deep-research brief for DJI model survey (#182)
- Roadmap and CI baseline refreshed against open issues (#183)
- Archive Reddit / MavicPilots sample-request post drafts (#191)
- Demote winget from install options until manifest is published (66414b1)

### CI

- Auto-create GitHub release from the EXE workflow, removing the manual "Draft release" step (#177)
- Stop auto-firing the winget workflow until [#175](https://github.com/CallMarcus/dji-drone-metadata-embedder/issues/175) is resolved (c97314f)
- Add Dependabot configuration (d23919c)
- Group GitHub Actions bumps via Dependabot (#180)

### Maintenance

- Dependabot dev-deps bumps (#181, #187) and aligned pre-commit pins (#185, #189)

### Acknowledgements

- Thanks to **Steve** for the original Neo 2 bug report on [discussion #192](https://github.com/CallMarcus/dji-drone-metadata-embedder/discussions/192) that drove #193.

## [1.2.0] - 2026-04-19

### Added

- **ui**: New `dji-embed ui` web UI built on Flask, with tabs for Embed, Check, Validate, Convert, and Doctor; SSE-based job progress; PWA manifest, service worker, and icons (#164 family — d9d0a7e, 59c1680, fa7c6c6, 0af4103, ce00e10, 4b58714, 517ba66)
- **embed**: `--overwrite` flag to embed metadata in place (#163, 2975718)
- **embed**: Atomic write + interruption-safe fallback — output is only written to the final path after validation passes (#162, 02d5dd9)

### Changed

- **deps**: Migrate from `pip` + `requirements.lock` to `uv` with `pyproject.toml` extras (#164)

### Fixed

- **embed**: Place `.tmp` before the file extension so ffmpeg picks the correct output muxer (b153202)
- **validator**: Parse real SRT timestamps in speed calculation instead of assuming a fixed frame rate (c1d89a1)
- **ui**: Drop unused json import and narrow job types for mypy (f97fe57)
- **ci**: Restore green baseline for lint, types, and tests (57808c7)

### Documentation

- Document `dji-embed ui` and the `[ui]` extra (61b253e)
- Fold FAQ and metadata-checker into existing docs; add UI to installation and decision table (b220007)
- Replace `agents.md` with Claude Code-specific `CLAUDE.md` (999bc67)
- Add PR description template for housekeeping changes (a9fb2a8)
- Comprehensive repository housekeeping analysis + cleanup scripts (62d48ec)

### Maintenance

- Remove unnecessary development scripts from root directory (871d9bf)

## [1.1.2] - 2025-08-14

### Fixed

- **build**: Remove invalid syntax line from `build_exe.py` that was blocking the Windows EXE build (1862e06)

## [1.1.1] - 2025-08-14

### Added

- **ci**: Auto-changelog generation from conventional commits (6e84081)
- **winget**: Manifest sync from `pyproject.toml` via `sync_version.py` (296f3f8)
- Public tiny sample MP4 / SRT fixtures for testing (3c1604d)
- Manual trigger to the Windows EXE build workflow (a2885dd)

### Fixed

- **build**: Simplify `build_exe.py` output and resolve Windows EXE encoding (2833e54, 6094088, 0465663)
- **bootstrap**: Update ExifTool URL and replace deprecated wizard command (4f13d31)
- **winget**: Submission-workflow chain — correct secret name, `wingetcreate` install method, manifest preparation, manual triggers, and README exclusion (30fe79d, 5597f79, d484ed1, fd2c713, 4778204)

### Documentation

- Decision table for user guidance (#144)
- End-to-end recipes for common workflows (#145)
- Enhanced troubleshooting guide with comprehensive solutions (3af8471)
- Update root documents to reflect production-ready status (eae30c6)

## [1.1.0] - 2025-01-13

### Added - M3 Parser Hardening & CLI UX
- Golden fixtures for comprehensive testing across 4 DJI model families (Issue #137)
  - Mini 3/4 Pro square bracket format
  - Air 3 HTML-formatted SRT with extended telemetry
  - Avata 2 legacy GPS format with BAROMETER data
  - Mavic 3 Enterprise format with RTK and extended data
- Lenient parser mode with structured warnings for malformed SRT files (Issue #138)
- Unit normalization and sanity checks for altitude/speed validation (Issue #139)
- CLI time-offset and resample strategy options for SRT↔MP4 alignment (Issue #140)
- CLI validate command with comprehensive drift analysis reports (Issue #141)
- Professional CLI structure with subcommands (embed, validate, export, probe, doctor) (Issue #142)
- Consistent exit codes across all CLI commands for automation (Issue #142)
- JSON logging option (--log-json) for machine-readable warnings/errors (Issue #143)

### Added - M2 CI/Build Reliability
- CI test matrix for Windows + Linux across Python 3.10-3.12 (Issue #133)
- Comprehensive smoke tests for CLI commands after package build (Issue #134)
- Enhanced --version command showing FFmpeg/ExifTool versions (Issue #135)
- requirements.lock file for reproducible builds across environments (Issue #136)
- Documentation for requirements lock policy and external tool versions

### Fixed
- YAML formatting in CI workflows and pre-commit configuration
- Updated CLI documentation to reflect current command structure
- Cross-platform pip caching in GitHub Actions workflows
- Ruff validation errors including unused imports and boolean comparisons
- Duplicate function definitions and naming conflicts

### Changed  
- Restructured CLI from flat commands to professional subcommand hierarchy
- Standardized quote usage in YAML files for consistency
- Enhanced pre-commit hooks with proper arguments and dependencies
- Improved README with comprehensive CLI reference and troubleshooting
- Updated all examples to use correct subcommand syntax
- CI now uses exact locked dependency versions for consistency
- Updated agents.md to align with GitHub Issues and Milestones

### Documentation
- Added complete CLI reference section with all commands and options
- Enhanced troubleshooting guide with common issues and solutions
- Updated installation instructions and command examples
- Fixed outdated command syntax throughout documentation
- Added external tool version specifications and compatibility matrix

## [1.0.7] - 2025-07-24

### Removed
- Winget packaging workflow and manifests

## [1.0.6] - 2025-07-23

### Fixed
- ExifTool extraction now copies bundled libraries correctly
- `dji-embed embed` processes all videos instead of stopping early

## [1.0.5] - 2025-07-22

### Fixed
- Bootstrap script now handles pre-release versions properly
- Pre-release tags (like `1.0.4-test1`) install from GitHub instead of PyPI
- Better error messages when version format issues occur
- Fallback to stable version if pre-release installation fails

### Added
- Support for installing directly from GitHub tags in bootstrap script
- Improved version detection and handling in Windows installer

## [1.0.4] - 2025-07-20

### Changed
- Tools and diagnostic scripts moved to the `tools` directory for clarity
- Build and packaging steps cleaned up to produce reproducible releases
- Documentation now notes the project is unstable while testing continues

### Added
- First signed package published to PyPI

### Removed
- Winget packaging postponed until the build is confirmed stable

## [1.0.3] - 2025-07-18

### Fixed
- Release workflow repaired for PyPI publishing
- Updated bootstrap installer fallback version

## [1.0.2] - 2025-07-17

### Added
- PowerShell bootstrap script for one-click setup on Windows
- Winget package `CallMarcus.DJI-Embed` with bundled dependencies
- Release workflow builds a signed `dji-embed.exe` via PyInstaller
- CI smoke test validates the bootstrap installer

### Changed
- README and docs reorganised for novice Windows users

### Fixed
- Reliable winget publish workflow

## [1.0.1] - 2025-07-16

### Fixed
- Packaging now includes the `src` package so the CLI works when installed from a wheel

## [1.0.0] - 2025-07-16

### Added
- Initial release
- Support for DJI Mini 3 Pro SRT format
- Batch processing of MP4/SRT file pairs
- GPS metadata embedding using FFmpeg
- Optional ExifTool support for additional metadata
- Telemetry export to JSON format
- GPX track export functionality
- CSV telemetry export
- Automatic dependency checking
- Cross-platform support (Windows, macOS, Linux)
- Batch CSV conversion via `telemetry_converter.py csv --batch`
- Metadata presence checker via `metadata_check.py`
- Support for HTML-based SRT logs with extended camera info
- Pytest test suite for parsing and FFmpeg command generation
- Optional DAT flight log merging and parser
- GitHub Action to publish signed wheels to PyPI on semver tags
- Release documentation in `docs/RELEASE.md`
- Dockerfile providing FFmpeg and ExifTool for container use

### Changed
- Improved metadata checker output with clearer status icons
- Improved MP4 deduplication when scanning directories
- Clarified Windows `PATH` instructions
- Documented using `py` when `python` is unavailable
- Minor documentation improvements
- Switched to Rich-based logging with verbose/quiet modes

### Supported Formats
- DJI Mini 3 Pro: `[latitude: xx.xxx] [longitude: xx.xxx]` format
- Legacy format: `GPS(lat,lon,alt)` format
- Camera settings extraction (ISO, shutter speed, f-number)
- Altitude data (relative and absolute)

### Features
- No video re-encoding (fast processing)
- Preserves original video quality
- Embeds SRT as subtitle track
- Creates JSON summaries with flight statistics
- Handles case-insensitive file extensions
- Progress feedback during batch processing

