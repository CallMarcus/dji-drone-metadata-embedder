@echo off
echo DJI Drone Metadata Embedder
echo ==========================
echo.

REM Check if directory argument is provided
if "%~1"=="" (
    echo Usage: process_drone_footage.bat [directory_path]
    echo Example: process_drone_footage.bat "D:\DroneFootage\Flight1"
    echo.
    pause
    exit /b 1
)

REM Check if Python is available
where py >nul 2>nul
if %errorlevel% neq 0 (
    where python >nul 2>nul
    if %errorlevel% neq 0 (
        echo Error: Python is not installed or not in PATH
        echo Please install Python from https://www.python.org/
        pause
        exit /b 1
    )
    set PYTHON_CMD=python
) else (
    set PYTHON_CMD=py
)

REM Get the directory where this batch file is located
set SCRIPT_DIR=%~dp0

REM Run the Python script
echo Processing drone footage in: %~1
echo.
dji-embed %*

echo.
echo Processing complete!
pause
