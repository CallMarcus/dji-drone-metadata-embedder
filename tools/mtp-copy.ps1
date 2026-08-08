<#
.SYNOPSIS
Copy DJI flight records off a remote controller over USB (MTP).

.DESCRIPTION
DJI RCs expose flight records over MTP, which has no drive letter -
plain Copy-Item cannot see it. This script walks the Shell.Application
COM namespace instead, so it works on a stock Windows PowerShell 5.1
with the RC plugged in, powered on, and unlocked.

Where the records live depends on the controller generation: older RCs
keep DJIFlightRecord_*.txt at the root of "Internal shared storage",
while the DJI RC 2 (current DJI Fly) keeps FlightRecord_*.txt - no DJI
prefix - under Android\data\dji.go.v5\files\FlightRecord. Both
locations and both name shapes are probed.

.EXAMPLE
powershell -ExecutionPolicy Bypass -File tools\mtp-copy.ps1
.EXAMPLE
powershell -ExecutionPolicy Bypass -File tools\mtp-copy.ps1 -Filter '*FlightRecord_2026-07-*' -Destination D:\FlightRecords
#>
param(
  [string]$Destination = (Join-Path $env:USERPROFILE 'Documents\FlightRecords'),
  # Matches both namings: DJIFlightRecord_*.txt (older RCs) and
  # FlightRecord_*.txt (DJI RC 2 / current DJI Fly).
  [string]$Filter = '*FlightRecord_*.txt',
  [int]$TimeoutSeconds = 120
)

$ErrorActionPreference = 'Stop'
$shell = New-Object -ComObject Shell.Application
$pc = $shell.NameSpace(17)  # "This PC", where portable devices appear

# The DJI Fly app folder on Android-based controllers (DJI RC 2): records
# live here rather than at the storage root.
$djiFlySubPath = @('Android', 'data', 'dji.go.v5', 'files', 'FlightRecord')

function Get-ChildFolderItem($folderItem, [string]$name) {
  if ($null -eq $folderItem) { return $null }
  try {
    return ($folderItem.GetFolder.Items() |
      Where-Object { $_.IsFolder -and $_.Name -eq $name } |
      Select-Object -First 1)
  } catch { return $null }
}

# Find the portable device exposing flight records: any device where the
# storage root (older RCs) or the DJI Fly app folder (DJI RC 2) contains
# a matching file. Name-matching ("*MTP*") is not reliable across RC
# models, so probe contents instead.
$records = @()
$deviceName = $null
$skipped = @()
foreach ($dev in $pc.Items()) {
  if (-not $dev.IsFolder) { continue }
  # A locked or half-attached device can still throw or return null from
  # its COM calls - skip anything that will not enumerate cleanly.
  try {
    # Only portable (WPD) devices carry a shell-namespace path ("::{...");
    # fixed drives (C:\) and network locations (\\server\share) have real
    # paths. Skipping them keeps a local folder that happens to hold
    # matching files - like a previous run's destination - from being
    # mistaken for the RC and silently re-copied from.
    if ($dev.Path -notlike '::{*') {
      $skipped += ('{0} ({1})' -f $dev.Name, $dev.Path)
      continue
    }
    $devFolder = $dev.GetFolder
    if ($null -eq $devFolder) { continue }
    $storages = @($devFolder.Items())
  } catch { continue }
  foreach ($storage in $storages) {
    if (-not $storage.IsFolder) { continue }
    # Candidate folders, probed in order: the storage root, then the
    # DJI Fly app folder. Walking the subpath just returns $null at the
    # first missing hop on controllers that lack it.
    $candidates = @($storage)
    $deep = $storage
    foreach ($name in $djiFlySubPath) { $deep = Get-ChildFolderItem $deep $name }
    if ($null -ne $deep) { $candidates += $deep }
    foreach ($candidate in $candidates) {
      try {
        $candidateFolder = $candidate.GetFolder
        if ($null -eq $candidateFolder) { continue }
        $found = @($candidateFolder.Items() | Where-Object { $_.Name -like $Filter })
      } catch { continue }
      if ($found.Count -gt 0) {
        $records = $found
        $deviceName = $dev.Name
        break
      }
    }
    if ($deviceName) { break }
  }
  if ($deviceName) { break }
}

if (-not $deviceName) {
  Write-Output "No flight records matching '$Filter' found on any portable device."
  Write-Output 'Is the RC plugged in over USB, powered on, and unlocked?'
  Write-Output '(Records sit at the root of "Internal shared storage" on older RCs,'
  Write-Output ' or under Android\data\dji.go.v5\files\FlightRecord on the DJI RC 2.)'
  # Say what was ruled out, so "the filter skipped the RC" and "the RC
  # was never there" do not produce the same silence.
  if ($skipped.Count -gt 0) {
    Write-Output ("Ignored {0} non-portable item(s): {1}" -f $skipped.Count, ($skipped -join ', '))
  }
  exit 1
}

Write-Output ("Found {0} record(s) on '{1}'." -f $records.Count, $deviceName)

if (-not (Test-Path $Destination)) {
  New-Item -ItemType Directory -Path $Destination | Out-Null
}
$destFolder = $shell.NameSpace((Resolve-Path $Destination).Path)

$existing = @(Get-ChildItem -Path $Destination -Filter $Filter -ErrorAction SilentlyContinue |
              ForEach-Object { $_.Name })
$want = @($records | Where-Object { $existing -notcontains $_.Name })
Write-Output ("Copying {0} new record(s) to {1} ({2} already there)." -f
              $want.Count, $Destination, ($records.Count - $want.Count))

foreach ($r in $want) {
  Write-Output ("  -> {0}" -f $r.Name)
  $destFolder.CopyHere($r, 16)  # 16 = answer "yes to all" to dialogs
}

# CopyHere is asynchronous over MTP; wait for the files to land.
$target = $existing.Count + $want.Count
if ($want.Count -gt 0) {
  for ($t = 0; $t -lt $TimeoutSeconds; $t++) {
    Start-Sleep -Seconds 1
    $have = @(Get-ChildItem -Path $Destination -Filter $Filter -ErrorAction SilentlyContinue)
    if ($have.Count -ge $target) { break }
  }
  $have = @(Get-ChildItem -Path $Destination -Filter $Filter -ErrorAction SilentlyContinue)
  if ($have.Count -lt $target) {
    Write-Output ("WARNING: timed out after {0}s with {1} of {2} files landed - MTP copies may still be in flight." -f $TimeoutSeconds, $have.Count, $target)
  }
}

$landed = @(Get-ChildItem -Path $Destination -Filter $Filter)
Write-Output ''
Write-Output ("{0} record(s) now in {1}:" -f $landed.Count, $Destination)
$landed | Sort-Object Name | ForEach-Object {
  Write-Output ("  {0}  {1} bytes" -f $_.Name, $_.Length)
}
