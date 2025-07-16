# DJI Metadata Embedder - Development Roadmap
## AI Coding Assistant Instructions

This document breaks down the development of the DJI Metadata Embedder into specific, actionable tasks for AI coding assistants (Claude Code, ChatGPT Codex, etc.).

---

## 📋 Project Overview

**Goal**: Transform the current command-line Python package into a user-friendly Windows application with zero-setup installation.

**Current State**: Working Python package with CLI interface, requires manual dependency installation
**Target State**: Standalone Windows executable with GUI, includes all dependencies

---

## 🎯 Phase 1: Foundation & Setup (Priority: HIGH)

### Task 1.1: Project Structure Setup
**Objective**: Create professional project structure for GUI application
**Files to Create**:
```
dji-metadata-embedder/
├── src/
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py
│   │   ├── components/
│   │   │   ├── __init__.py
│   │   │   ├── file_selector.py
│   │   │   ├── progress_bar.py
│   │   │   └── status_logger.py
│   │   └── resources/
│   │       ├── icons/
│   │       └── styles/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── processor.py
│   │   └── validator.py
│   └── utils/
│       ├── __init__.py
│       ├── dependency_manager.py
│       └── system_info.py
├── tools/
│   ├── download_dependencies.py
│   └── build_executable.py
├── installer/
│   ├── setup.nsi
│   └── assets/
├── tests/
└── docs/
```

**Requirements**:
- Use pathlib for all path operations
- Include proper __init__.py files
- Add basic docstrings to all modules
- Create empty placeholder files if needed

**Output**: Complete directory structure with placeholder files

---

### Task 1.2: Dependency Download Manager
**Objective**: Automatically download and manage FFmpeg and ExifTool
**File**: `src/utils/dependency_manager.py`

**Specifications**:
- Download FFmpeg from https://www.gyan.dev/ffmpeg/builds/ffmpeg-git-essentials.zip
- Download ExifTool from https://exiftool.org/exiftool-12.76.zip
- Extract to `tools/` directory
- Verify executables work correctly
- Handle network errors gracefully
- Show download progress

**Functions to Implement**:
```python
class DependencyManager:
    def __init__(self, tools_dir: Path)
    def download_ffmpeg(self) -> bool
    def download_exiftool(self) -> bool
    def verify_dependencies(self) -> dict
    def get_dependency_info(self) -> dict
```

**Testing Requirements**:
- Test on clean Windows machine
- Test network failure scenarios
- Test corrupted download handling

---

### Task 1.3: System Information Utility
**Objective**: Detect Windows version, Python installation, and system capabilities
**File**: `src/utils/system_info.py`

**Specifications**:
- Detect Windows version (7, 10, 11)
- Check Python installation and version
- Detect available disk space
- Check for admin privileges
- Identify system architecture (32/64-bit)

**Functions to Implement**:
```python
def get_windows_version() -> str
def get_python_info() -> dict
def get_disk_space(path: Path) -> int
def has_admin_privileges() -> bool
def get_system_architecture() -> str
def get_system_summary() -> dict
```

---

## 🖥️ Phase 2: GUI Development (Priority: HIGH)

### Task 2.1: Main Window Framework
**Objective**: Create the main application window using tkinter
**File**: `src/gui/main_window.py`

**Specifications**:
- Window size: 800x600, resizable
- Professional appearance with modern styling
- Title: "DJI Metadata Embedder v2.0"
- Icon support (when icon file available)
- Proper window centering
- Minimum size constraints

**Components to Include**:
- Menu bar with File, Tools, Help
- Status bar at bottom
- Main content area for components
- Proper error handling for GUI errors

**Class Structure**:
```python
class MainWindow:
    def __init__(self)
    def setup_ui(self)
    def setup_menu(self)
    def setup_status_bar(self)
    def center_window(self)
    def on_closing(self)
```

---

### Task 2.2: File Selection Component
**Objective**: Create drag-and-drop file/folder selection widget
**File**: `src/gui/components/file_selector.py`

**Specifications**:
- Support folder selection via browse button
- Drag-and-drop functionality for folders
- Input validation (check for MP4/SRT files)
- Visual feedback for valid/invalid selections
- Remember last selected folder

**Features**:
- Browse button with folder dialog
- Drag-and-drop zone with visual feedback
- File count display (X MP4 files, Y SRT files found)
- Error messages for invalid selections

**Class Structure**:
```python
class FileSelector(tk.Frame):
    def __init__(self, parent, title: str, callback: callable)
    def setup_ui(self)
    def on_browse_click(self)
    def on_drop(self, event)
    def validate_folder(self, folder_path: Path) -> bool
    def update_file_count(self, folder_path: Path)
```

---

### Task 2.3: Progress Bar Component
**Objective**: Create advanced progress bar with file-level tracking
**File**: `src/gui/components/progress_bar.py`

**Specifications**:
- Overall progress bar (0-100%)
- Current file progress bar
- File counter (Processing file X of Y)
- Current operation display
- Estimated time remaining
- Cancel button functionality

**Features**:
- Smooth progress animations
- Multi-level progress tracking
- Time estimation based on file sizes
- Pause/resume capability
- Error state visualization

**Class Structure**:
```python
class ProgressBar(tk.Frame):
    def __init__(self, parent)
    def setup_ui(self)
    def update_overall_progress(self, percent: float)
    def update_file_progress(self, percent: float)
    def set_current_file(self, filename: str, index: int, total: int)
    def set_operation(self, operation: str)
    def show_error(self, message: str)
    def reset(self)
```

---

### Task 2.4: Status Logger Component
**Objective**: Create scrollable log window with filtering and export
**File**: `src/gui/components/status_logger.py`

**Specifications**:
- Scrollable text area with monospace font
- Log levels: INFO, WARNING, ERROR
- Color-coded messages
- Timestamp for each entry
- Export to file functionality
- Clear log button

**Features**:
- Auto-scroll to bottom
- Filter by log level
- Search functionality
- Copy to clipboard
- Save log to file

**Class Structure**:
```python
class StatusLogger(tk.Frame):
    def __init__(self, parent)
    def setup_ui(self)
    def log_info(self, message: str)
    def log_warning(self, message: str)
    def log_error(self, message: str)
    def clear_log(self)
    def export_log(self, filename: str)
    def filter_by_level(self, level: str)
```

---

## ⚙️ Phase 3: Core Processing (Priority: MEDIUM)

### Task 3.1: Video Processing Core
**Objective**: Refactor existing processing logic for GUI integration
**File**: `src/core/processor.py`

**Specifications**:
- Integrate with existing dji_metadata_embedder package
- Add progress callback support
- Thread-safe processing
- Error handling and recovery
- Batch processing capabilities

**Features**:
- Progress callbacks for GUI updates
- Cancellation support
- Detailed error reporting
- File validation before processing
- Backup creation option

**Class Structure**:
```python
class VideoProcessor:
    def __init__(self, progress_callback: callable = None)
    def process_folder(self, input_folder: Path, output_folder: Path, options: dict)
    def process_single_file(self, video_path: Path, srt_path: Path, output_path: Path)
    def validate_files(self, folder_path: Path) -> dict
    def cancel_processing(self)
    def get_processing_stats(self) -> dict
```

---

### Task 3.2: Input Validation
**Objective**: Comprehensive validation of user inputs and files
**File**: `src/core/validator.py`

**Specifications**:
- Validate folder paths and permissions
- Check MP4/SRT file pairing
- Verify sufficient disk space
- Check for valid SRT format
- Validate output folder permissions

**Functions to Implement**:
```python
def validate_input_folder(folder_path: Path) -> dict
def validate_output_folder(folder_path: Path) -> dict
def validate_file_pairs(folder_path: Path) -> list
def validate_srt_format(srt_path: Path) -> bool
def calculate_required_space(input_folder: Path) -> int
def validate_dependencies() -> dict
```

---

## 🔧 Phase 4: Build System (Priority: MEDIUM)

### Task 4.1: PyInstaller Build Script
**Objective**: Create automated build script for standalone executable
**File**: `tools/build_executable.py`

**Specifications**:
- Bundle Python runtime
- Include all dependencies (FFmpeg, ExifTool)
- Create single executable file
- Handle hidden imports
- Include resource files (icons, etc.)

**Features**:
- One-click build process
- Automatic dependency detection
- Build validation
- Size optimization
- Debug/release modes

**Script Structure**:
```python
def download_dependencies()
def create_spec_file()
def build_executable()
def validate_build()
def cleanup_build_files()
def main()
```

---

### Task 4.2: Windows Installer Script
**Objective**: Create professional Windows installer using NSIS
**File**: `installer/setup.nsi`

**Specifications**:
- Professional installer interface
- Start menu shortcuts
- Desktop shortcut option
- Context menu integration
- Uninstaller creation
- Registry entries

**Features**:
- Modern UI with progress bars
- License agreement display
- Custom installation path
- Component selection
- Automatic updates check

**Components**:
- Main executable
- Documentation files
- Context menu integration
- Uninstall support

---

## 🧪 Phase 5: Testing & Quality (Priority: LOW)

### Task 5.1: Automated Testing Suite
**Objective**: Create comprehensive test suite for GUI and core functionality
**File**: `tests/test_gui.py`, `tests/test_core.py`

**Specifications**:
- Unit tests for all core functions
- GUI component testing
- Integration tests
- File processing tests
- Error handling tests

**Test Categories**:
- Dependency download tests
- File validation tests
- Processing pipeline tests
- GUI interaction tests
- Error recovery tests

---

### Task 5.2: Sample Data Generator
**Objective**: Create test data for development and testing
**File**: `tests/generate_test_data.py`

**Specifications**:
- Generate sample MP4 files
- Create corresponding SRT files
- Various SRT formats (Mini 3, Mini 4, Avata 2)
- Edge cases and error conditions
- Performance testing data

---

## 📦 Phase 6: Distribution (Priority: LOW)

### Task 6.1: GitHub Actions CI/CD
**Objective**: Automate build and release process
**File**: `.github/workflows/build-release.yml`

**Specifications**:
- Automated testing on push
- Build executable on tag creation
- Create GitHub releases
- Upload artifacts
- Cross-platform testing

---

### Task 6.2: User Documentation
**Objective**: Create comprehensive user documentation
**Files**: `docs/user_guide.md`, `docs/installation.md`, `docs/troubleshooting.md`

**Specifications**:
- Step-by-step installation guide
- User interface walkthrough
- Common troubleshooting scenarios
- Video tutorials scripts
- FAQ section

---

## 🎯 Task Execution Guidelines

### For AI Coding Assistants:

**Before Starting Each Task**:
1. Read the current project structure
2. Understand the existing codebase
3. Check for existing implementations
4. Identify dependencies between tasks

**During Development**:
1. Follow Python best practices (PEP 8, type hints)
2. Add comprehensive docstrings
3. Include error handling
4. Add logging where appropriate
5. Create meaningful variable names

**After Completing Each Task**:
1. Test the implementation
2. Update documentation
3. Create simple usage examples
4. Note any issues or improvements needed

**Code Quality Requirements**:
- All functions must have type hints
- All classes must have docstrings
- Error handling for all external operations
- Logging for debugging purposes
- Follow existing code style in the project

### Testing Each Task:
```python
# Example test structure for each task
def test_task_basic_functionality():
    # Test normal operation
    pass

def test_task_error_handling():
    # Test error conditions
    pass

def test_task_edge_cases():
    # Test boundary conditions
    pass
```

---

## 📊 Success Criteria

**Phase 1 Complete**: All foundation files created, dependencies downloadable
**Phase 2 Complete**: GUI runs without errors, all components functional
**Phase 3 Complete**: Video processing works through GUI
**Phase 4 Complete**: Standalone executable builds successfully
**Phase 5 Complete**: All tests pass, quality metrics met
**Phase 6 Complete**: Automated releases working, documentation complete

**Final Success**: Average DJI pilot can download one file, double-click, and successfully process their videos within 5 minutes.

---

## 🔄 Iteration Process

1. **Implement Task** → **Test Locally** → **Document Issues** → **Refine**
2. **Integrate with Existing Code** → **Test Integration** → **Fix Conflicts**
3. **User Testing** → **Gather Feedback** → **Iterate Based on Feedback**

Each task should be treated as a complete, testable unit that can be developed independently while maintaining integration with the overall system.