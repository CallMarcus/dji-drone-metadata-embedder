# Claude Code Instructions

_Last updated: 2025-08-15_

## Purpose
This file provides context and guidelines for Claude Code when contributing to the **dji-drone-metadata-embedder** repository. It ensures consistent, high-quality contributions aligned with the project's production-ready status.

---

## 1. Repository Context

- **Repository:** [CallMarcus/dji-drone-metadata-embedder](https://github.com/CallMarcus/dji-drone-metadata-embedder)
- **Default branch:** `master`
- **Language:** Python 3.10–3.12
- **Status:** Production-ready (All M1-M4 milestones completed)
- **CI/CD:** GitHub Actions
- **Testing:** `pytest` for unit tests, `validation_tests/` for E2E tests
- **Package management:** `pip` with `pyproject.toml` and `requirements.lock`
- **CLI entry point:** `dji-embed`

---

## 2. Project Architecture

### Core Components
```
src/dji_metadata_embedder/
├── cli.py                    # Main CLI with Click commands
├── embedder.py               # Core SRT→MP4 metadata embedding
├── telemetry_converter.py    # GPX/CSV export functionality
├── metadata_check.py         # Metadata verification tool
├── dat_parser.py            # DAT flight log parsing
├── per_frame_embedder.py    # Frame-by-frame processing
├── utilities.py             # Shared utility functions
├── core/
│   ├── processor.py         # Processing pipeline
│   └── validator.py         # SRT validation & drift detection
└── utils/
    ├── dependency_manager.py # FFmpeg/ExifTool management
    └── system_info.py       # System diagnostics
```

### Key Features
- **Batch processing** of DJI drone footage (MP4 + SRT pairs)
- **GPS metadata embedding** via FFmpeg (no re-encoding)
- **Multiple DJI formats**: Mini 3/4 Pro, Air 3, Avata 2, Mavic 3 Enterprise
- **Export formats**: JSON, GPX, CSV
- **Privacy controls**: GPS redaction (drop/fuzz)
- **Cross-platform**: Windows, macOS, Linux

---

## 3. Development Guidelines

### Code Style & Standards
- **PEP 8 compliance** enforced via `ruff`
- **Type hints** for all new functions
- **Descriptive names** for variables and functions
- **Document regex patterns** with inline comments
- **No breaking changes** to existing API without major version bump

### Testing Requirements
- **All changes must have tests** in `tests/` directory
- **Use golden fixtures** in `samples/` for integration tests
- **Cross-platform validation** on Windows & Linux (Python 3.10-3.12)
- **CLI smoke tests** for new commands/options
- **Run locally before committing:** `pytest -q`

### Commit Message Format
Use [Conventional Commits](https://www.conventionalcommits.org/) for automatic changelog generation:

```
feat(cli): add new validate command
fix(parser): handle malformed SRT timestamps
docs: update troubleshooting guide
ci: improve test matrix coverage
chore: remove deprecated scripts
```

**Types:**
- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation only
- `ci:` - CI/CD changes
- `test:` - Test changes
- `chore:` - Maintenance tasks
- `refactor:` - Code refactoring

---

## 4. Branch Naming Convention

```
feat/issue-<NUMBER>-<short-description>     # New features
fix/issue-<NUMBER>-<short-description>      # Bug fixes
docs/<description>                           # Documentation
ci/<description>                             # CI/CD improvements
claude/<session-id>                          # Claude Code sessions
```

**Important:** Feature branches are deleted after merge to keep the repository clean. See `HOUSEKEEPING.md` for maintenance guidelines.

---

## 5. Working with GitHub Issues

When implementing GitHub issues:

1. **Read the entire issue** including acceptance criteria
2. **Create a feature branch** following naming convention above
3. **Make minimal changes** to satisfy requirements
4. **Add/update tests** and documentation
5. **Run tests locally:** `pytest -q`
6. **Open a PR** with conventional commit format in title
7. **Reference the issue** in PR description: `Closes #123`

### PR Template Checklist
- [ ] Tests added/updated for new functionality
- [ ] Documentation updated (if user-facing changes)
- [ ] Sample fixtures tested (if parser changes)
- [ ] Cross-platform compatibility verified
- [ ] No breaking changes to existing functionality
- [ ] Conventional commit format used in PR title

---

## 6. Common Tasks

### Setup Development Environment
```bash
# Clone and setup
git clone https://github.com/CallMarcus/dji-drone-metadata-embedder.git
cd dji-drone-metadata-embedder

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1

# Install dependencies
pip install -U pip
pip install -e ".[dev]"

# Verify setup
pytest -q
dji-embed --help
dji-embed doctor
```

### Running Tests
```bash
# Unit tests (fast)
pytest -q

# Specific test file
pytest tests/test_parsing.py -v

# Integration tests with samples
pytest tests/test_golden_fixtures.py -v

# E2E validation tests
python validation_tests/run_all_tests.py
```

### Testing with Sample Fixtures
```bash
# Check sample files
dji-embed check samples/

# Test embedding with Air 3 samples
dji-embed embed samples/air3/ --verbose

# Validate SRT/MP4 sync
dji-embed validate samples/
```

### Building and Testing Package
```bash
# Build wheel
python -m build

# Install locally
pip install dist/*.whl

# Test CLI
dji-embed --version
dji-embed doctor
```

---

## 7. Adding Support for New DJI Models

When adding support for a new DJI drone model:

1. **Obtain sample files** (SRT, MP4, DAT if available)
2. **Analyze the format** - identify GPS, altitude, camera settings patterns
3. **Create regex patterns** in `embedder.py`
4. **Add test fixtures** to `samples/<model>/`
5. **Update documentation:**
   - `README.md` - Add to "Supported DJI Models" section
   - `docs/SRT_FORMATS.md` - Document the format specification
   - `docs/troubleshooting.md` - Add model-specific issues if any
6. **Test thoroughly** with real footage from that model

### Example Parser Pattern
```python
# In embedder.py, add to parse_dji_srt() method

# New Model Format: [GPS: lat,lon,alt] [CAMERA: iso,shutter,fnum]
new_model = re.search(
    r'\[GPS:\s*([+-]?\d+\.?\d*),([+-]?\d+\.?\d*),([+-]?\d+\.?\d*)\]'
    r'\s*\[CAMERA:\s*(\d+),([^,]+),(\d+)\]',
    telemetry_line
)
if new_model:
    return {
        'latitude': float(new_model.group(1)),
        'longitude': float(new_model.group(2)),
        'altitude': float(new_model.group(3)),
        'iso': new_model.group(4),
        'shutter': new_model.group(5),
        'fnum': new_model.group(6),
        'format_detected': 'new_model_v1'
    }
```

---

## 8. Release Process

The project uses automated releases via GitHub Actions. **Do not manually bump version numbers** unless explicitly working on a release.

### Version Synchronization
All version numbers are kept in sync via `tools/sync_version.py`:
- `src/dji_metadata_embedder/__init__.py` (source of truth)
- `README.md` (version badge)
- `tools/bootstrap.ps1` (fallback version)
- `dji-embed.spec` (PyInstaller spec)
- `winget/*.yaml` (Windows Package Manager manifests)

### Automated Release Workflows
When a tag `vX.Y.Z` is pushed:
1. **PyPI Release** - Package built and published
2. **Windows EXE** - Standalone executable created
3. **Winget Submission** - Windows Package Manager updated
4. **Auto-Changelog** - CHANGELOG.md updated from commits

See `docs/RELEASE.md` for detailed release procedures (maintainers only).

---

## 9. Documentation Standards

### When to Update Documentation

**Always update when:**
- Adding new CLI commands or options → Update `README.md` and `docs/user_guide.md`
- Adding new DJI model support → Update `docs/SRT_FORMATS.md`
- Fixing common issues → Update `docs/troubleshooting.md`
- Changing workflow → Update `docs/decision-table.md` or `docs/recipes.md`

**Documentation Files:**
- `README.md` - Main entry point, feature overview, quick start
- `CONTRIBUTING.md` - How to contribute, testing, PR guidelines
- `docs/installation.md` - Installation instructions for all platforms
- `docs/user_guide.md` - Basic usage examples
- `docs/troubleshooting.md` - Common issues and solutions (529 lines!)
- `docs/SRT_FORMATS.md` - Technical format specifications
- `docs/decision-table.md` - "Which command should I use?" guide
- `docs/recipes.md` - End-to-end workflow examples
- `docs/faq.md` - Frequently asked questions

---

## 10. Key Files & Their Purpose

### Configuration Files
- `pyproject.toml` - Package metadata, dependencies, build config
- `requirements.txt` - User dependencies (runtime)
- `requirements.lock` - Locked dependency versions (CI)
- `requirements-build.txt` - Build-time dependencies
- `pytest.ini` - pytest configuration
- `.pre-commit-config.yaml` - Pre-commit hooks (ruff, etc.)
- `dji-embed.spec` - PyInstaller spec for Windows EXE

### CI/CD Workflows (`.github/workflows/`)
- `ci.yml` - Test matrix (Windows/Linux, Python 3.10-3.12)
- `release-pypi.yml` - PyPI package publishing
- `release-exe.yml` - Windows executable build
- `release-winget.yml` - Winget manifest submission
- `auto-changelog.yml` - Changelog generation from commits
- `docs.yml` - MkDocs documentation deployment

### Tools & Scripts
- `tools/sync_version.py` - Synchronize version across files
- `tools/bootstrap.ps1` - Windows one-click installer
- `tools/build_exe.py` - PyInstaller build script
- `tools/diagnostic_script.py` - System diagnostics
- `scripts/generate_changelog.py` - Manual changelog generation
- `scripts/delete-stale-branches.sh/ps1` - Branch cleanup utilities

---

## 11. Known Limitations & Design Decisions

### FFmpeg Dependency
- **Why:** No Python library reliably embeds metadata without re-encoding
- **Impact:** Users must install FFmpeg separately
- **Mitigation:** bootstrap.ps1 auto-installs on Windows

### No Re-encoding
- **Why:** Preserve video quality, fast processing
- **Impact:** Some players may not show embedded metadata
- **Mitigation:** Subtitle track preserves all telemetry

### Subtitle Track Approach
- **Why:** Guaranteed compatibility, preserves all data
- **Impact:** SRT file embedded as subtitle track
- **Benefit:** Overlays work in video players, full telemetry preserved

### Two Test Directories
- **`tests/`:** Unit tests (fast, focused, 14 files)
- **`validation_tests/`:** E2E tests (comprehensive, 6 modules)
- **Why:** Different purposes - unit vs integration testing
- **Keep both:** They serve complementary roles

---

## 12. Project Status & Milestones

### ✅ Completed (August 2025)
- **M1 - Stabilise & Version Cohesion** - Single-source versioning, tag-driven releases
- **M2 - CI/Build Reliability** - Test matrix, smoke tests, locked dependencies
- **M3 - Parser Hardening & CLI UX** - Golden fixtures, professional CLI, validation
- **M4 - Docs, Samples & Release Hygiene** - Decision table, troubleshooting, auto-changelog

### 🚀 Future Development
- **GUI Application** - See `docs/development_roadmap.md`
- **New DJI Models** - Community contributions welcome
- **Performance Optimizations** - Based on user feedback

---

## 13. Getting Help & Resources

### Documentation
- **User Docs:** `docs/user_guide.md`, `docs/faq.md`
- **Developer Docs:** `CONTRIBUTING.md`, this file (`CLAUDE.md`)
- **Troubleshooting:** `docs/troubleshooting.md` (comprehensive!)
- **API Reference:** `docs/api.md`

### Sample Files
- `samples/air3/` - DJI Air 3 format
- `samples/avata2/` - DJI Avata 2 format
- `samples/mini4pro/` - DJI Mini 4 Pro format
- `examples/DJI_sample.SRT` - Generic example

### Community
- **Issues:** GitHub Issues for bug reports and feature requests
- **Discussions:** GitHub Discussions for questions
- **Contributing:** See `CONTRIBUTING.md`

---

## 14. Quick Reference

### Most Common Commands
```bash
# Development
pytest -q                           # Run tests
dji-embed doctor                    # System diagnostics
dji-embed check samples/            # Verify samples

# User operations
dji-embed embed /path/to/footage    # Process videos
dji-embed convert gpx file.SRT      # Export to GPX
dji-embed validate /path/to/files   # Check sync

# Building
python -m build                     # Build package
pip install dist/*.whl              # Install locally
```

### Important Reminders
- ✅ Always run `pytest -q` before committing
- ✅ Use conventional commits for automatic changelog
- ✅ Test on sample fixtures in `samples/` directory
- ✅ Update documentation for user-facing changes
- ✅ Keep PRs focused on single issue/feature
- ❌ Don't manually bump version numbers
- ❌ Don't commit large media files (use samples/)
- ❌ Don't make breaking changes without discussion

---

## 15. Differences from agents.md

This file (`CLAUDE.md`) is specifically for Claude Code, providing:
- **Claude-specific context** about the project state
- **Practical examples** and code snippets
- **Comprehensive quick reference** for common operations
- **Integration with Claude's workflow** (reading files, running tests, etc.)

The previous `agents.md` was more generic for multiple AI assistants and focused heavily on milestone tracking. `CLAUDE.md` assumes the project is production-ready and focuses on maintenance and enhancement.

---

**Last Updated:** 2025-08-15
**Project Version:** v1.1.2
**Status:** Production Ready ✅
