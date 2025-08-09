# AI Coding Assistant – GitHub Issues Tracking (`agents.md`)

*Last updated: August 9th, 2025*

This document tracks the GitHub Issues and Milestones for the DJI Drone Metadata Embedder project. All development work should align with the actual GitHub project management system.

***

## Current Milestone: M2 – CI/Build Reliability (Week 2–3)

**Due Date**: August 29, 2025  
**Status**: ✅ **COMPLETED** - All 4 issues resolved

### ✅ Completed Issues

| Issue | Priority | Description | Status |
|-------|----------|-------------|---------|
| **#136** | MED | deps: introduce requirements.lock for reproducible builds | ✅ DONE |
| **#135** | MED | build: pin FFmpeg/ExifTool versions and expose via --version | ✅ DONE |
| **#134** | HIGH | ci: smoke test wheel & EXE using tiny fixtures | ✅ DONE |
| **#133** | MED | ci: test matrix (Windows + Linux; py310–py312) | ✅ DONE |

### 🎯 M2 Achievements

- ✅ **Enhanced CI Pipeline**: Added Windows + Linux matrix testing across Python 3.10-3.12
- ✅ **Smoke Testing**: Added comprehensive smoke tests for version, doctor, check, and convert commands  
- ✅ **Reproducible Builds**: Implemented requirements.lock with exact dependency versions
- ✅ **Tool Version Tracking**: Enhanced --version command to show FFmpeg/ExifTool versions
- ✅ **Documentation**: Added requirements lock policy and external tool version specs

***

## Next Milestone: M3 – Parser Hardening & CLI UX (Week 3–5)

**Due Date**: September 12, 2025  
**Status**: 🔄 **IN PROGRESS** - 7 open issues

### 🔄 M3 Open Issues

| Issue | Priority | Type | Description |
|-------|----------|------|-------------|
| **#143** | MED | cli | optional --log-json (machine-readable warnings/errors) |
| **#142** | HIGH | cli | subcommands (embed, validate, export, probe) + consistent exit codes |
| **#141** | HIGH | cli | implement validate command (drift report) |
| **#140** | MED | cli/parser | add --time-offset and resample strategy for SRT↔MP4 alignment |
| **#139** | MED | parser | unit normalisation & sanity checks (altitude/speed) |
| **#138** | HIGH | parser | lenient mode with structured warnings |
| **#137** | HIGH | ci/parser | add golden fixtures for SRT & HTML-SRT across 4 DJI model families |

***

## Future Milestone: M4 – Docs, Samples & Release Hygiene (Week 5–6)

**Due Date**: September 19, 2025  
**Status**: 📋 **PLANNED** - 6 open issues

### 📋 M4 Planned Issues

| Issue | Priority | Type | Description |
|-------|----------|------|-------------|
| **#149** | MED | release | winget manifest sync from pyproject via sync_version.py |
| **#148** | MED | release | auto-changelog from conventional commits |
| **#147** | MED | ci/docs | add public tiny sample MP4/SRT fixtures |
| **#146** | MED | docs | troubleshooting guide (model quirks, VFR drift, codecs) |
| **#145** | MED | docs | end-to-end recipes (4 common flows) |
| **#144** | MED | docs | decision table — which path do I take? |

***

## 📊 Project Status Summary

### ✅ Recently Completed
- **M2 - CI/Build Reliability**: Full CI matrix, smoke testing, reproducible builds, tool version tracking
- **Documentation Updates**: README, CLI reference, troubleshooting, CHANGELOG.md  
- **Core Functionality Verification**: All SRT formats, telemetry export, DAT parsing tested

### 🔄 Current Work
- **M3 - Parser Hardening & CLI UX**: 7 issues focusing on robust parsing and better user experience

### 📋 Upcoming Work  
- **M4 - Docs & Release Hygiene**: Documentation improvements, samples, release automation

***

## 🚀 Development Guidelines

### GitHub-First Approach
All work should be tracked via **GitHub Issues and Milestones** rather than arbitrary phases. This ensures:
- ✅ Clear acceptance criteria for each task
- ✅ Proper issue tracking and assignment
- ✅ Milestone-based progress tracking  
- ✅ Integration with GitHub project management

### Issue Management
1. **Create Issues** for new features or bugs
2. **Assign to Milestones** with appropriate due dates
3. **Use Priority Labels** (priority:high, priority:med) for planning
4. **Update agents.md** when milestone status changes
5. **Close Issues** when acceptance criteria are met

### Milestone Workflow
1. **M2**: ✅ **COMPLETED** - CI/Build Reliability
2. **M3**: 🔄 **IN PROGRESS** - Parser Hardening & CLI UX  
3. **M4**: 📋 **PLANNED** - Docs, Samples & Release Hygiene

***

*Updated: August 9th, 2025 - Aligned with GitHub Issues and Milestones*
