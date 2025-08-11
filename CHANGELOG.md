# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Stability Notice**
>
> While the core features work for embedding DJI telemetry, the project is still
> being stabilised. Expect ongoing changes and potential breakage as bugs are
> fixed and the build process is improved.

## [Unreleased]

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

### Changed  
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

