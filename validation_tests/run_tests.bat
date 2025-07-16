@echo off
REM Windows batch file to run DJI Metadata Embedder validation tests
REM This script provides an easy way to test your installation on Windows 11

echo.
echo ==========================================
echo DJI Metadata Embedder - Validation Tests
echo Windows 11 Installation Verification
echo ==========================================
echo.

REM Check if we're in the right directory
if not exist "pyproject.toml" (
    echo ERROR: Please run this script from the dji-drone-metadata-embedder directory
    echo Current directory: %CD%
    echo.
    echo Usage:
    echo   cd C:\Claude\dji-drone-metadata-embedder
    echo   validation_tests\run_tests.bat
    echo.
    pause
    exit /b 1
)

REM Check Python availability
echo Checking Python availability...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python command not found, trying 'py'...
    py --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo ERROR: Python not found in PATH
        echo Please install Python 3.8+ and add to PATH
        pause
        exit /b 1
    ) else (
        set PYTHON_CMD=py
        echo Found Python using 'py' command
    )
) else (
    set PYTHON_CMD=python
    echo Found Python using 'python' command
)

echo.
echo ==========================================
echo Running Comprehensive Validation Tests
echo ==========================================
echo.
echo This will test:
echo   1. Installation and Dependencies
echo   2. SRT Parsing Functionality  
echo   3. Video Processing Pipeline
echo   4. Advanced Features
echo   5. End-to-End Integration
echo.
echo Estimated time: 2-5 minutes
echo.

pause

REM Run the master test script
%PYTHON_CMD% validation_tests\run_all_tests.py

REM Check result and provide feedback
if %errorlevel% equ 0 (
    echo.
    echo ==========================================
    echo SUCCESS: All validation tests passed!
    echo ==========================================
    echo.
    echo Your DJI Metadata Embedder is ready to use.
    echo.
    echo Quick usage examples:
    echo   dji-embed "C:\Path\To\Your\DroneFootage"
    echo   dji-embed "D:\DCIM\100MEDIA" --exiftool
    echo.
    echo For help: dji-embed --help
    echo.
) else if %errorlevel% equ 1 (
    echo.
    echo ==========================================
    echo PARTIAL: Some tests failed
    echo ==========================================
    echo.
    echo Review the output above to see what failed.
    echo Core functionality may still work.
    echo.
) else if %errorlevel% equ 2 (
    echo.
    echo ==========================================
    echo INTERRUPTED: Testing was cancelled
    echo ==========================================
    echo.
) else (
    echo.
    echo ==========================================
    echo ERROR: Testing failed
    echo ==========================================
    echo.
    echo Common solutions:
    echo   1. pip install -e .
    echo   2. Install FFmpeg and add to PATH
    echo   3. Restart command prompt
    echo.
    echo See README.md for detailed instructions.
    echo.
)

echo.
echo Press any key to exit...
pause >nul
