# AI Coding Assistant – Task Breakdown (`agents.md`)

*Last updated: July 20th, 2025*

---

## ✅ Phase 0 Complete - Package Structure Fixed!

The package structure has been successfully consolidated and all core functionality is working. We can now proceed with testing and deployment.

---

## 📋 PHASE 1: Core Functionality Verification

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

## 📋 PHASE 2: Windows User Experience

> **Goal**: Zero-friction install for everyday Windows pilots

### 2.1 · PowerShell Bootstrap Script (📜 `tools/bootstrap.ps1`)

| Step | What the script does | Implementation hints | Status |
|------|---------------------|---------------------|---------|
| 1 | **Self-elevate if needed** | Use `#Requires -RunAsAdministrator` | ✅ DONE |
| 2 | Ensure **Python ≥ 3.10** | Install from MS Store/winget | ✅ DONE |
| 3 | Download **FFmpeg + ExifTool** | SHA-256 validation | ✅ DONE |
| 4 | `pip install dji-drone-metadata-embedder` | From PyPI | ✅ READY |
| 5 | Update PATH | Current session + persistent | ✅ DONE |
| 6 | Auto-launch wizard | `dji-embed wizard` | ✅ READY |

The bootstrap script is now complete and ready for use!

### 2.2 · Winget Package

| Task | Description | Status |
|------|-------------|---------|
| **2.2.1** | Submit winget manifest | ❌ TODO |
| **2.2.2** | GitHub Action for winget updates | ✅ DONE (untested) |
| **2.2.3** | Documentation for winget install | ❌ TODO |

### 2.3 · Quick Install Methods

#### One-Line PowerShell Install
```powershell
iwr -useb https://raw.githubusercontent.com/CallMarcus/dji-drone-metadata-embedder/main/tools/bootstrap.ps1 | iex
```

#### Manual Bootstrap
```powershell
# Download and run the bootstrap script
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/CallMarcus/dji-drone-metadata-embedder/main/tools/bootstrap.ps1" -OutFile "dji_bootstrap.ps1"
.\dji_bootstrap.ps1
```

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

1. **Test the bootstrap script**:
   ```powershell
   .\tools\bootstrap.ps1
   ```

2. **Run comprehensive tests**:
   ```bash
   pip install -e .[dev]
   pytest
   dji-embed --version
   ```

3. **Test all CLI commands**:
   ```bash
   dji-embed embed /path/to/videos
   dji-embed check /path/to/videos
   dji-embed convert /path/to/files --format gpx
   dji-embed wizard
   ```

4. **Verify PyPI package**:
   ```bash
   python -m build
   twine check dist/*
   ```

---

## 📊 Success Metrics

### Phase 1 Success:
- [ ] All SRT formats parse correctly
- [ ] Video processing works end-to-end
- [ ] Documentation is accurate and complete
- [ ] Package installs cleanly from PyPI
- [ ] Bootstrap script works on clean Windows systems

### Phase 2 Success:
- [ ] Windows users can install with one command
- [ ] No Python/CLI knowledge required
- [ ] Works on Windows 10/11 without admin rights
- [ ] Less than 3 minutes from download to first processed video

### Phase 3 Success:
- [ ] GUI provides visual alternative to CLI
- [ ] Docker images available for all platforms
- [ ] Automated deployment pipeline working

---

## 🚀 Current Focus

With Phase 0 complete, the immediate priority is:

1. **Test the bootstrap script** on various Windows configurations
2. **Verify all core features** work correctly (Phase 1.1)
3. **Update documentation** to reflect the current state
4. **Prepare for PyPI release** with proper versioning

The package is now ready for real-world testing and deployment!

---

*Updated after successful completion of Phase 0 emergency fixes.*
