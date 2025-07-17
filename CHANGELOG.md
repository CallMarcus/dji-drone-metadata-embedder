# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.2] - 2025-07-17

### Planned
- Support for more DJI models
- KML export format
- GUI interface
- Video thumbnail generation with GPS overlay
- Integration with mapping services
- Flight path visualization

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

