# Get SHA256 and size of the executable
$exePath = "dist\dji-embed.exe"

if (Test-Path $exePath) {
    $hash = Get-FileHash -Path $exePath -Algorithm SHA256
    $size = (Get-Item $exePath).Length / 1MB
    
    Write-Host "=== DJI-Embed.exe Information ===" -ForegroundColor Cyan
    Write-Host "SHA256: $($hash.Hash)" -ForegroundColor Green
    Write-Host "Size: $([math]::Round($size, 2)) MB" -ForegroundColor Green
    Write-Host ""
    Write-Host "Copy this SHA256 for the winget manifest:" -ForegroundColor Yellow
    Write-Host $hash.Hash
} else {
    Write-Host "ERROR: $exePath not found!" -ForegroundColor Red
}
