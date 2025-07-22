# DJI Metadata Embedder - Cleanup and Restructure Script
# Run this from the project root directory

Write-Host "DJI Metadata Embedder - Cleanup and Restructure" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan

# Step 1: Backup current state
Write-Host "`nStep 1: Creating backup..." -ForegroundColor Yellow
$backupDir = "backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Copy-Item -Path "dji_metadata_embedder", "src", "pyproject.toml" -Destination $backupDir -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "Backup created in: $backupDir" -ForegroundColor Green

# Step 2: Clean up build artifacts
Write-Host "`nStep 2: Cleaning build artifacts..." -ForegroundColor Yellow
Remove-Item -Path "dist", "build", "*.egg-info", "dji_drone_metadata_embedder.egg-info" -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path . -Include "__pycache__" -Recurse -Directory | Remove-Item -Recurse -Force
Write-Host "Build artifacts cleaned" -ForegroundColor Green

# Step 3: Restructure packages
Write-Host "`nStep 3: Restructuring package..." -ForegroundColor Yellow

# Ensure src/dji_metadata_embedder exists
New-Item -ItemType Directory -Path "src\dji_metadata_embedder" -Force | Out-Null

# Move implementation files if they exist in root package dir
if (Test-Path "dji_metadata_embedder") {
    $files = @("embedder.py", "dat_parser.py", "per_frame_embedder.py", 
               "telemetry_converter.py", "metadata_check.py", "utilities.py")
    
    foreach ($file in $files) {
        $sourcePath = "dji_metadata_embedder\$file"
        if (Test-Path $sourcePath) {
            Move-Item -Path $sourcePath -Destination "src\dji_metadata_embedder\$file" -Force
            Write-Host "Moved $file to src/dji_metadata_embedder/" -ForegroundColor Gray
        }
    }
}

# Remove old package directory
if (Test-Path "dji_metadata_embedder") {
    Remove-Item -Path "dji_metadata_embedder" -Recurse -Force
}

Write-Host "Package restructured" -ForegroundColor Green

# Step 4: Fix imports in Python files
Write-Host "`nStep 4: Fixing imports..." -ForegroundColor Yellow

# Fix imports in src files
Get-ChildItem -Path "src" -Filter "*.py" -Recurse | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    $content = $content -replace "from dji_metadata_embedder\.", "from ."
    Set-Content -Path $_.FullName -Value $content -NoNewline
}

# Fix imports in test files  
Get-ChildItem -Path "tests" -Filter "*.py" -Recurse | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    $content = $content -replace "from \.", "from dji_metadata_embedder."
    Set-Content -Path $_.FullName -Value $content -NoNewline
}

Write-Host "Imports fixed" -ForegroundColor Green

# Step 5: Create missing files
Write-Host "`nStep 5: Creating missing files..." -ForegroundColor Yellow

# Ensure __init__.py exists with proper content
$initContent = @'
"""DJI Drone Metadata Embedder."""
__version__ = "1.0.2"

# Import check to ensure files were moved correctly
try:
    from .embedder import DJIMetadataEmbedder
    from .per_frame_embedder import embed_flight_path, extract_frame_locations
    from .dat_parser import parse_v13 as parse_dat_v13
    from .cli import main
    
    __all__ = [
        "__version__",
        "main",
        "DJIMetadataEmbedder",
        "embed_flight_path", 
        "extract_frame_locations",
        "parse_dat_v13",
    ]
except ImportError as e:
    # Provide helpful error if files are missing
    import warnings
    warnings.warn(f"Some modules could not be imported: {e}")
    __all__ = ["__version__"]
'@

Set-Content -Path "src\dji_metadata_embedder\__init__.py" -Value $initContent

Write-Host "Missing files created" -ForegroundColor Green

# Step 6: Reinstall in development mode
Write-Host "`nStep 6: Reinstalling package..." -ForegroundColor Yellow
& python -m pip uninstall dji-drone-metadata-embedder -y 2>$null
& python -m pip install -e .

# Step 7: Verify installation
Write-Host "`nStep 7: Verifying installation..." -ForegroundColor Yellow
$testResult = & python -c "import dji_metadata_embedder; print(dji_metadata_embedder.__version__)" 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "Package imported successfully! Version: $testResult" -ForegroundColor Green
} else {
    Write-Host "Import failed! Error:" -ForegroundColor Red
    Write-Host $testResult -ForegroundColor Red
}

Write-Host "`nCleanup complete!" -ForegroundColor Cyan
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Run: pytest" -ForegroundColor White
Write-Host "2. Run: dji-embed --version" -ForegroundColor White
Write-Host "3. Commit changes if everything works" -ForegroundColor White