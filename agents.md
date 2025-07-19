# AI Coding Assistant – Task Breakdown (`agents.md`)

*Last updated: July 19th, 2025 - CRITICAL UPDATE*

---

## 🚨 CURRENT STATUS: Core Package Structure Broken

**Critical Issue**: The package has accumulated technical debt from mixed development approaches. We have duplicate package locations, broken imports, and failing CI/CD. **We must fix these foundational issues before any deployment work.**

---

## 📋 PHASE 0: Emergency Core Fixes (IMMEDIATE PRIORITY)

> **Goal**: Get the package working locally before attempting any deployment

### 0.1 · Fix Package Structure ⚡ CRITICAL

| Task | Description | Status | Files Affected |
|------|-------------|---------|----------------|
| **0.1.1** | Consolidate duplicate package locations (`/dji_metadata_embedder/` vs `/src/dji_metadata_embedder/`) | ✅ DONE | All Python files |
| **0.1.2** | Fix all import statements after consolidation | ✅ DONE | `src/**/*.py`, `tests/*.py` |
| **0.1.3** | Update pyproject.toml with correct paths and dependencies | ✅ DONE | `pyproject.toml` |
| **0.1.4** | Remove `pathlib` from dependencies (it's built-in) | ✅ DONE | `pyproject.toml`, `requirements.txt` |

**Implementation**:
```bash
# Run the cleanup script provided by Claude
.\cleanup_and_restructure.ps1
```

### 0.2 · Fix CLI Entry Point ⚡ CRITICAL  

| Task | Description | Status | Files Affected |
|------|-------------|---------|----------------|
| **0.2.1** | Replace stub `cli.py` with full implementation | ✅ DONE | `src/dji_metadata_embedder/cli.py` |
| **0.2.2** | Create `utilities.py` for dependency checking | ✅ DONE | `src/dji_metadata_embedder/utilities.py` |
| **0.2.3** | Ensure `dji-embed --version` works | ✅ DONE | Entry point configuration |
| **0.2.4** | Test all subcommands: embed, check, convert, wizard | ✅ DONE | CLI testing |

### 0.3 · Fix CI/CD Workflows

| Task | Description | Status | Files Affected |
|------|-------------|---------|----------------|
| **0.3.1** | Update CI workflow to reference correct package location | ✅ DONE | `.github/workflows/ci.yml` |
| **0.3.2** | Fix release workflow for PyPI publishing | ✅ DONE | `.github/workflows/release.yml` |
| **0.3.3** | Remove or fix broken workflows | ✅ DONE | `.github/workflows/*.yml` |
| **0.3.4** | Add proper dependency installation in CI | ✅ DONE | All workflow files |

### 0.4 · Clean Up Technical Debt

| Task | Description | Status | Files Affected |
|------|-------------|---------|----------------|
| **0.4.1** | Remove temp_setup.ps1 (temporary fix file) | ❌ TODO | `temp_setup.ps1` |
| **0.4.2** | Decide on GUI: remove or properly integrate | ❌ TODO | `/gui/` directory |
| **0.4.3** | Fix version management (remove sync_version.py complexity) | ❌ TODO | `tools/sync_version.py` |
| **0.4.4** | Update tests to work with new structure | ❌ TODO | `tests/*.py` |

---

## 📋 PHASE 1: Core Functionality Verification (AFTER Phase 0)

> **Goal**: Ensure all features work correctly before deployment

### 1.1 · Test Core Features

| Task | Description | Status |
|------|-------------|---------|
| **1.1.1** | Verify SRT parsing for all formats (Mini 3/4 Pro, Avata 2, legacy) | ❌ TODO |
| **1.1.2** | Test video metadata embedding with FFmpeg | ❌ TODO |
| **1.1.3** | Test ExifTool GPS metadata embedding | ❌ TODO |
| **1.1.4** | Verify DAT file parsing and integration | ❌ TODO |
| **1.1.5** | Test telemetry export (GPX, CSV) | ❌ TODO |

### 1.2 · Documentation Update

| Task | Description | Status |
|------|-------------|---------|
| **1.2.1** | Update README with correct installation instructions | ❌ TODO |
| **1.2.2** | Document all CLI commands and options | ❌ TODO |
| **1.2.3** | Add troubleshooting guide | ❌ TODO |
| **1.2.4** | Update CHANGELOG.md | ❌ TODO |

---

## 📋 PHASE 2: Windows User Experience (ONLY after Phase 0 & 1)

> **Goal**: Zero-friction install for everyday Windows pilots

*Note: The excellent work below from the previous agents.md should be implemented AFTER we fix the core package*

### 2.1 · PowerShell Bootstrap Script (📜 `tools/bootstrap.ps1`)

| Step | What the script does | Implementation hints | Status |
|------|---------------------|---------------------|---------|
| 1 | **Self-elevate if needed** | Use `#Requires -RunAsAdministrator` | ✅ DONE |
| 2 | Ensure **Python ≥ 3.10** | Install from MS Store/winget | ✅ DONE |
| 3 | Download **FFmpeg + ExifTool** | SHA-256 validation | ✅ DONE |
| 4 | `pip install dji-metadata-embedder` | From PyPI | ⚠️ BLOCKED |
| 5 | Update PATH | Current session + persistent | ✅ DONE |
| 6 | Auto-launch wizard | `dji-embed wizard` | ⚠️ BLOCKED |

**Blocker**: Package must be working and published to PyPI first!

### 2.2 · Winget Package

| Task | Description | Status |
|------|-------------|---------|
| **2.2.1** | Submit winget manifest | ⚠️ BLOCKED on working package |
| **2.2.2** | GitHub Action for winget updates | ✅ DONE (untested) |
| **2.2.3** | Documentation for winget install | ⚠️ BLOCKED |

---

## 📋 PHASE 3: Advanced Features (Future)

### 3.1 · GUI Development (Optional)

| Task | Description | Status |
|------|-------------|---------|
| **3.1.1** | Decide: Keep GUI or remove? | ❌ TODO |
| **3.1.2** | If keeping: Move to src/dji_metadata_embedder/gui | ❌ TODO |
| **3.1.3** | Create dji-embed-gui entry point | ❌ TODO |
| **3.1.4** | PyInstaller bundle with GUI | ❌ TODO |

### 3.2 · Docker Enhancement

| Task | Description | Status |
|------|-------------|---------|
| **3.2.1** | Update Dockerfile with new structure | ❌ TODO |
| **3.2.2** | Multi-arch builds (ARM64 support) | ❌ TODO |
| **3.2.3** | Docker Hub automated builds | ❌ TODO |

---

## 🎯 IMMEDIATE ACTION ITEMS

1. **Run diagnostic script** to assess current state:
   ```bash
   python diagnostic_script.py
   ```

2. **Execute cleanup script** to fix structure:
   ```powershell
   .\cleanup_and_restructure.ps1
   ```

3. **Replace core files** with Claude's fixed versions:
   - pyproject.toml
   - src/dji_metadata_embedder/cli.py
   - src/dji_metadata_embedder/utilities.py
   - .github/workflows/ci.yml
   - .github/workflows/release.yml

4. **Test locally**:
   ```bash
   pip install -e .[dev]
   pytest
   dji-embed --version
   ```

5. **Only after all tests pass**, proceed to Phase 1

---

## 📊 Success Metrics

### Phase 0 Success (Required before proceeding):
- [ ] Package imports without errors
- [ ] `dji-embed --version` returns correct version
- [ ] All tests pass locally
- [ ] CI/CD workflows pass on GitHub
- [ ] Can build package with `python -m build`

### Phase 1 Success:
- [ ] All SRT formats parse correctly
- [ ] Video processing works end-to-end
- [ ] Documentation is accurate and complete
- [ ] Package installs cleanly from test PyPI

### Phase 2 Success:
- [ ] Windows users can install with one command
- [ ] No Python/CLI knowledge required
- [ ] Works on Windows 10/11 without admin rights
- [ ] Less than 3 minutes from download to first processed video

---

## ⚠️ CRITICAL NOTE

**DO NOT proceed with deployment tasks (bootstrap script, winget, PyPI publishing) until Phase 0 is complete!** 

The current package structure is broken. Attempting to deploy it will only frustrate users and damage the project's reputation. Fix first, deploy second.

---

*Updated by Claude after thorough code analysis. Previous deployment-focused tasks moved to Phase 2.*
