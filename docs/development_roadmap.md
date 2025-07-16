# Development Roadmap

This roadmap tracks the planned evolution of **DJI Drone Metadata Embedder** from a command-line tool into a fully packaged Windows application. The phases and tasks are summarised below. Refer to `agents.md` for the detailed instructions used by automated coding assistants.

## Phase 1 – Foundation & Setup
- **Project structure setup** – create GUI, core and utils packages with placeholder modules.
- **Dependency download manager** – manage FFmpeg and ExifTool downloads.
- **System information utility** – detect Windows version, Python installation and system details.

## Phase 2 – GUI Development
- **Main window framework** using `tkinter`.
- **File selection, progress bar and status logger components**.

## Phase 3 – Core Processing
- **Video processing core** that integrates the existing embedding logic.
- **Input validation utilities**.

## Phase 4 – Build System
- **PyInstaller build script** for producing a standalone executable.
- **Windows installer** scripted via NSIS.

## Phase 5 – Testing & Quality
- **Automated test suite** covering core functions and GUI behaviour.
- **Sample data generator** for development and testing.

## Phase 6 – Distribution
- **GitHub Actions CI/CD** workflow for releases.
- **User documentation** including installation and troubleshooting guides.

## Current Progress
- The repository currently contains the original CLI implementation.
- A basic `dependency_manager.py` exists but other Phase 1 modules are missing.
- No GUI, build scripts or installer have been created yet.

The project aims to deliver a one-click Windows application with comprehensive documentation and automated builds.
