# Test the built executable
Write-Host "=== Testing dji-embed.exe ===" -ForegroundColor Cyan

$exePath = "dist\dji-embed.exe"

if (Test-Path $exePath) {
    Write-Host "`nTesting --version:" -ForegroundColor Yellow
    & $exePath --version
    
    Write-Host "`nTesting --help:" -ForegroundColor Yellow
    & $exePath --help
    
    Write-Host "`n✅ If you see the help text above, the executable is working!" -ForegroundColor Green
    Write-Host "⚠️  Note: The build had warnings about missing 'parsers' and 'wizard' modules" -ForegroundColor Yellow
    Write-Host "   These features might not work in the standalone exe" -ForegroundColor Yellow
} else {
    Write-Host "❌ Executable not found at: $exePath" -ForegroundColor Red
}
