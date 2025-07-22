# Create GitHub Release for v1.0.6
Write-Host "Creating GitHub Release for v1.0.6..." -ForegroundColor Green

# Check if GitHub CLI is installed
$ghInstalled = Get-Command gh -ErrorAction SilentlyContinue
if (-not $ghInstalled) {
    Write-Host "GitHub CLI not found. Installing via winget..." -ForegroundColor Yellow
    winget install GitHub.cli
    Write-Host "Please restart PowerShell after installation and run this script again." -ForegroundColor Yellow
    exit 1
}

# Create the release
Write-Host "Creating release..." -ForegroundColor Cyan

$releaseNotes = @"
## What's Changed

### 🐛 Bug Fixes
- Fixed bootstrap script to handle pre-release versions properly
- Pre-release tags (like `1.0.4-test1`) now install from GitHub instead of PyPI
- Better error messages when version format issues occur
- Fallback to stable version if pre-release installation fails

### 🚀 Improvements
- Support for installing directly from GitHub tags in bootstrap script
- Improved version detection and handling in Windows installer
- Updated ExifTool URL to latest version (13.32)

### 📦 Installation

**Windows (Easy Install):**
``````powershell
iwr -useb https://raw.githubusercontent.com/CallMarcus/dji-drone-metadata-embedder/master/tools/bootstrap.ps1 | iex
``````

**PyPI:**
``````bash
pip install dji-drone-metadata-embedder==1.0.6
``````

**Docker:**
``````bash
docker pull callmarcus/dji-embed:latest
``````

### 📚 Documentation
- [Installation Guide](https://github.com/CallMarcus/dji-drone-metadata-embedder/blob/master/docs/installation.md)
- [User Guide](https://github.com/CallMarcus/dji-drone-metadata-embedder/blob/master/docs/user_guide.md)
- [Troubleshooting](https://github.com/CallMarcus/dji-drone-metadata-embedder/blob/master/docs/troubleshooting.md)

**Full Changelog**: https://github.com/CallMarcus/dji-drone-metadata-embedder/compare/v1.0.5...v1.0.6
"@

# Create the release using GitHub CLI
try {
    gh release create v1.0.6 `
        --title "v1.0.6 - Bug Fix Release" `
        --notes $releaseNotes `
        --latest
    
    Write-Host "✅ GitHub Release created successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "View the release at: https://github.com/CallMarcus/dji-drone-metadata-embedder/releases/tag/v1.0.6" -ForegroundColor Cyan
} catch {
    Write-Host "❌ Failed to create release: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "You can create it manually at: https://github.com/CallMarcus/dji-drone-metadata-embedder/releases/new" -ForegroundColor Yellow
}
