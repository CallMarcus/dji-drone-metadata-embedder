<#
.SYNOPSIS
  Assemble + smoke-test the Windows installer LOCALLY over binaries you have
  already Authenticode-signed. Fallback for when the CI SimplySign path is
  unavailable (see the v1.23.0 release notes / signing saga).

.DESCRIPTION
  The CI installer workflow does: build -> sign-app -> assemble -> sign-installer.
  When SimplySign can't be driven headlessly, the two signing rounds move to
  your machine. This script owns the deterministic middle (assemble + verify);
  you own the two signings with your normal SimplySign signtool command.

  Full local flow:
    1. Download the `staging` and `to-sign` artifacts from the failed/attempted
       "Build Windows Installer" run (build job succeeds even when signing fails).
         gh run download <run-id> -n staging -D staging\app
         gh run download <run-id> -n to-sign -D to-sign
    2. Sign BOTH exes in to-sign\ with SimplySign, e.g.:
         signtool sign /n "Open Source Developer Marcus..." /tr http://time.certum.pl `
           /td sha256 /fd sha256 to-sign\dji-embed.exe to-sign\DjiEmbed.Gui.exe
    3. Compile the installer over the signed binaries:
         tools\build_installer_local.ps1 -StagingDir staging\app `
           -SignedExeDir to-sign -AppVersion 1.23.0
    4. Sign the produced setup exe (path printed at the end) with SimplySign.
    5. Verify + checksum:
         tools\build_installer_local.ps1 -VerifySetup dist-installer\dji-metadata-embedder-setup-1.23.0.exe

  Note: a locally built installer does NOT carry the Sigstore build-provenance
  attestation (that is CI-only). The Authenticode signature is intact; the
  attestation gap is acceptable for a one-off and closes next release.

.PARAMETER StagingDir
  The extracted `staging` artifact (contains the {app} tree minus the two exes).

.PARAMETER SignedExeDir
  Directory holding your already-signed dji-embed.exe and DjiEmbed.Gui.exe.

.PARAMETER AppVersion
  X.Y.Z. Drives the ISCC AppVersion and the output filename.

.PARAMETER OutputDir
  Where the setup exe lands (default: dist-installer).

.PARAMETER SkipSmokeTest
  Skip the silent install + PATH/signature assertions (they modify the machine).

.PARAMETER VerifySetup
  Verify a signed setup exe and emit its SHA256SUMS file, then exit. Use after
  you have signed the setup exe.
#>
[CmdletBinding(DefaultParameterSetName = 'Build')]
param(
    [Parameter(ParameterSetName = 'Build', Mandatory)] [string] $StagingDir,
    [Parameter(ParameterSetName = 'Build', Mandatory)] [string] $SignedExeDir,
    [Parameter(ParameterSetName = 'Build', Mandatory)] [string] $AppVersion,
    [Parameter(ParameterSetName = 'Build')] [string] $OutputDir = 'dist-installer',
    [Parameter(ParameterSetName = 'Build')] [string] $IsccPath,
    [Parameter(ParameterSetName = 'Build')] [switch] $SkipSmokeTest,
    [Parameter(ParameterSetName = 'Verify', Mandatory)] [string] $VerifySetup,
    [Parameter(ParameterSetName = 'Verify')] [string] $VerifyAppVersion
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$exes = @('dji-embed.exe', 'DjiEmbed.Gui.exe')

function Assert-Signed([string] $path) {
    $sig = Get-AuthenticodeSignature $path
    if ($sig.Status -ne 'Valid') {
        throw "$([IO.Path]::GetFileName($path)) signature is '$($sig.Status)', expected 'Valid'. Sign it before continuing."
    }
    Write-Host "  signed OK: $([IO.Path]::GetFileName($path))  [$($sig.SignerCertificate.Subject)]"
}

if ($PSCmdlet.ParameterSetName -eq 'Verify') {
    if (-not (Test-Path $VerifySetup)) { throw "not found: $VerifySetup" }
    Write-Host "Verifying setup signature..."
    Assert-Signed $VerifySetup
    $dir = Split-Path -Parent (Resolve-Path $VerifySetup)
    $name = Split-Path -Leaf $VerifySetup
    $hash = (Get-FileHash $VerifySetup -Algorithm SHA256).Hash.ToLower()
    $sumsPath = Join-Path $dir 'SHA256SUMS-installer.txt'
    "$hash  $name" | Set-Content -Encoding ascii $sumsPath
    Write-Host "Wrote $sumsPath :"
    Get-Content $sumsPath
    $tag = if ($VerifyAppVersion) { "v$VerifyAppVersion" } else { '<tag>' }
    Write-Host "`nReady to attach to the release:"
    Write-Host "  gh release upload $tag `"$VerifySetup`" `"$sumsPath`""
    return
}

if (-not (Test-Path $StagingDir)) { throw "staging dir not found: $StagingDir" }

Write-Host "== Verifying your signed app binaries =="
foreach ($e in $exes) {
    $src = Join-Path $SignedExeDir $e
    if (-not (Test-Path $src)) { throw "missing signed exe: $src" }
    Assert-Signed $src
}

Write-Host "== Injecting signed binaries into the staging tree =="
foreach ($e in $exes) {
    Copy-Item -Force (Join-Path $SignedExeDir $e) (Join-Path $StagingDir $e)
}

Write-Host "== Locating Inno Setup (ISCC) =="
# Probe machine-wide AND per-user (winget installs per-user when it can't
# elevate) roots, with a version-folder wildcard, plus PATH and an explicit
# override.
$isccCandidates = @()
if ($IsccPath) { $isccCandidates += $IsccPath }
$isccCandidates += (Get-Command ISCC.exe -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty Source)
$isccCandidates += Get-ChildItem -ErrorAction SilentlyContinue -Path `
    "${env:ProgramFiles(x86)}\Inno Setup*\ISCC.exe", `
    "${env:ProgramFiles}\Inno Setup*\ISCC.exe", `
    "$env:LOCALAPPDATA\Programs\Inno Setup*\ISCC.exe" |
    Select-Object -ExpandProperty FullName
$iscc = $isccCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $iscc) {
    throw "Inno Setup not found. Install it (winget install --id JRSoftware.InnoSetup -e) " +
          "or pass -IsccPath <path to ISCC.exe>."
}
Write-Host "  using: $iscc"

$absOut = Join-Path (Get-Location) $OutputDir
New-Item -ItemType Directory -Force -Path $absOut | Out-Null
$absStaging = (Resolve-Path $StagingDir).Path

Write-Host "== Compiling installer (v$AppVersion) =="
& $iscc "/DAppVersion=$AppVersion" "/DStagingDir=$absStaging" "/O$absOut" `
    (Join-Path $repoRoot 'installer\DjiMetadataEmbedder.iss')
if ($LASTEXITCODE -ne 0) { throw "ISCC failed ($LASTEXITCODE)" }

$setup = Join-Path $absOut "dji-metadata-embedder-setup-$AppVersion.exe"
if (-not (Test-Path $setup)) { throw "expected output not produced: $setup" }
Write-Host "  produced: $setup"

if (-not $SkipSmokeTest) {
    Write-Host "== Smoke test: silent install =="
    & $setup /VERYSILENT /SUPPRESSMSGBOXES /NORESTART | Out-Null
    $app = "$env:LOCALAPPDATA\Programs\DJI Metadata Embedder"
    foreach ($f in @('DjiEmbed.Gui.exe', 'dji-embed.exe', 'tools\ffmpeg.exe', 'tools\exiftool.exe')) {
        if (-not (Test-Path "$app\$f")) { throw "installed tree missing $f" }
    }
    foreach ($e in $exes) {
        $sig = Get-AuthenticodeSignature "$app\$e"
        if ($sig.Status -ne 'Valid') { throw "installed ${e} signature: $($sig.Status)" }
    }
    & "$app\dji-embed.exe" --version
    if ($LASTEXITCODE -ne 0) { throw "bundled CLI failed" }
    Write-Host "  smoke test passed"
}

Write-Host "`n== Next =="
Write-Host "1. Sign the setup exe with SimplySign:"
Write-Host "     signtool sign /n `"<your cert>`" /tr http://time.certum.pl /td sha256 /fd sha256 `"$setup`""
Write-Host "2. Verify + checksum:"
Write-Host "     tools\build_installer_local.ps1 -VerifySetup `"$setup`" -VerifyAppVersion $AppVersion"
