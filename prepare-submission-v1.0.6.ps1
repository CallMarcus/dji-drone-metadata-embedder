# Prepare Winget Submission for v1.0.6
$version = "1.0.6"
$sha256 = "D2B4E91A6C776AD710EB3D9ED8B6F4CC006FF7E2DBC2A45A8054BBBD804E90D3"

Write-Host "=== Preparing Winget Submission for DJI Metadata Embedder v$version ===" -ForegroundColor Cyan

# Create submission directory structure
$submitDir = "winget-submission"
$packageDir = "$submitDir\manifests\c\CallMarcus\DJIMetadataEmbedder\$version"

Write-Host "Creating directory structure..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $packageDir | Out-Null

# Copy manifests from .github\winget-manifests
$sourceDir = ".github\winget-manifests"
if (Test-Path $sourceDir) {
    Copy-Item "$sourceDir\CallMarcus.DJIMetadataEmbedder.yaml" "$packageDir\" -Force
    Copy-Item "$sourceDir\CallMarcus.DJIMetadataEmbedder.installer.yaml" "$packageDir\" -Force
    Copy-Item "$sourceDir\CallMarcus.DJIMetadataEmbedder.locale.en-US.yaml" "$packageDir\" -Force
    
    Write-Host "✅ Manifests copied to submission directory" -ForegroundColor Green
} else {
    Write-Host "❌ Source manifests not found!" -ForegroundColor Red
    exit 1
}

# Validate with winget if available
if (Get-Command winget -ErrorAction SilentlyContinue) {
    Write-Host "`nValidating manifests..." -ForegroundColor Yellow
    winget validate $packageDir
} else {
    Write-Host "`n⚠️  Install winget for validation: https://aka.ms/getwinget" -ForegroundColor Yellow
}

Write-Host "`n✅ Submission files ready in: $submitDir" -ForegroundColor Green
Write-Host "`n📋 Manual Submission Steps:" -ForegroundColor Cyan
Write-Host "1. Fork: https://github.com/microsoft/winget-pkgs"
Write-Host "2. Clone your fork locally"
Write-Host "3. Create branch: CallMarcus.DJIMetadataEmbedder-$version"
Write-Host "4. Copy contents of $submitDir\manifests to your fork's manifests folder"
Write-Host "5. Commit: 'New package: CallMarcus.DJIMetadataEmbedder version $version'"
Write-Host "6. Push and create PR"

Write-Host "`n📝 PR Title: New package: CallMarcus.DJIMetadataEmbedder version $version" -ForegroundColor Yellow
