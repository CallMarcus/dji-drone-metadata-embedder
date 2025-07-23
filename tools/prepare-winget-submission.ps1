# Manual Winget Submission Script
# Run this after uploading dji-embed.exe to the v1.0.6 release

param(
    [string]$Version = "1.0.6",
    [string]$SHA256
)

Write-Host "=== DJI Metadata Embedder - Winget Submission Helper ===" -ForegroundColor Cyan

# Step 1: Calculate SHA256 if not provided
if (-not $SHA256) {
    if (Test-Path "dist\dji-embed.exe") {
        $hash = Get-FileHash -Path "dist\dji-embed.exe" -Algorithm SHA256
        $SHA256 = $hash.Hash
        Write-Host "✓ Calculated SHA256: $SHA256" -ForegroundColor Green
    } else {
        Write-Host "❌ dist\dji-embed.exe not found. Build it first with: python tools\build_exe.py" -ForegroundColor Red
        exit 1
    }
}

# Step 2: Update the installer manifest
$installerManifest = ".github\winget-manifests\CallMarcus.DJIMetadataEmbedder.installer.yaml"
if (Test-Path $installerManifest) {
    $content = Get-Content $installerManifest -Raw
    $content = $content -replace 'PLACEHOLDER_SHA256', $SHA256
    $content | Set-Content $installerManifest
    Write-Host "✓ Updated installer manifest with SHA256" -ForegroundColor Green
}

# Step 3: Create submission directory structure
$submitDir = "winget-submission"
$packageDir = "$submitDir\manifests\c\CallMarcus\DJIMetadataEmbedder\$Version"
New-Item -ItemType Directory -Force -Path $packageDir | Out-Null

# Copy manifests
Copy-Item ".github\winget-manifests\CallMarcus.DJIMetadataEmbedder.yaml" "$packageDir\"
Copy-Item ".github\winget-manifests\CallMarcus.DJIMetadataEmbedder.installer.yaml" "$packageDir\"
Copy-Item ".github\winget-manifests\CallMarcus.DJIMetadataEmbedder.locale.en-US.yaml" "$packageDir\"

Write-Host "✓ Created submission directory structure" -ForegroundColor Green

# Step 4: Instructions
Write-Host "`n📋 Next Steps:" -ForegroundColor Yellow
Write-Host "1. Upload dist\dji-embed.exe to: https://github.com/CallMarcus/dji-drone-metadata-embedder/releases/tag/v$Version"
Write-Host "2. Fork https://github.com/microsoft/winget-pkgs"
Write-Host "3. Copy the contents of $submitDir\manifests to your fork"
Write-Host "4. Create a PR with title: 'New package: CallMarcus.DJIMetadataEmbedder version $Version'"
Write-Host "`nManifests are ready in: $submitDir" -ForegroundColor Green

# Optional: Validate with wingetcreate
if (Get-Command wingetcreate -ErrorAction SilentlyContinue) {
    Write-Host "`nValidating manifests..." -ForegroundColor Cyan
    wingetcreate validate $packageDir
} else {
    Write-Host "`nTip: Install wingetcreate for validation: winget install wingetcreate" -ForegroundColor Gray
}
