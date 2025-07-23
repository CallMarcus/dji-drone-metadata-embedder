# Update the SHA256 in the winget manifest
param(
    [Parameter(Mandatory=$true)]
    [string]$SHA256
)

$manifestPath = ".github\winget-manifests\CallMarcus.DJIMetadataEmbedder.installer.yaml"

if (Test-Path $manifestPath) {
    $content = Get-Content $manifestPath -Raw
    $content = $content -replace 'PLACEHOLDER_SHA256', $SHA256.ToUpper()
    $content | Set-Content $manifestPath
    Write-Host "✅ Updated manifest with SHA256: $SHA256" -ForegroundColor Green
} else {
    Write-Host "❌ Manifest not found at: $manifestPath" -ForegroundColor Red
}
