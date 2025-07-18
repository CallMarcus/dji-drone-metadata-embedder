#requires -version 5.1
param(
    [switch]$Silent,
    [switch]$NoLaunch,
    [string]$Version
)


$ErrorActionPreference = 'Stop'
$VerbosePreference = if($Silent){'SilentlyContinue'} else{'Continue'}

function Log($Msg){ if(-not $Silent){ Write-Host "[+] $Msg" } }

$DefaultVersion = '1.0.2'

if(-not $Version){
    try{
        $Version = (Invoke-RestMethod https://api.github.com/repos/CallMarcus/dji-drone-metadata-embedder/releases/latest -Headers @{ 'User-Agent' = 'bootstrap' }).tag_name.TrimStart('v')
    }catch{
        try{
            $Version = (Invoke-RestMethod https://pypi.org/pypi/dji-drone-metadata-embedder/json -UseBasicParsing).info.version
        }catch{
            $Version = $DefaultVersion
            Log "Falling back to bundled version $DefaultVersion"
        }
    }
}

Log "Installing dji-drone-metadata-embedder $Version"

# Elevate if not admin
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if(-not $isAdmin){
    try{
        $args='-ExecutionPolicy Bypass -File "'+$PSCommandPath+'"'
        if($Silent){$args+=' -Silent'}
        if($NoLaunch){$args+=' -NoLaunch'}
        Start-Process powershell -Verb RunAs -ArgumentList $args -Wait
        exit
    }catch{ Log 'Admin elevation failed; continuing in user mode.' }
}

# Ensure Python >=3.10
function Ensure-Python{
    $py=Get-Command python -ErrorAction SilentlyContinue
    if($py){$v=&$py.Path -c "import sys;print(f'{sys.version_info.major}.{sys.version_info.minor}')";if([version]$v -ge [version]'3.10'){return $py.Path}}
    $store="$env:SystemRoot\System32\storecli.exe"
    if(Test-Path $store){ try{ & $store install --productid 9NRWMJP3717T --silent }catch{} }
    $py=Get-Command python -ErrorAction SilentlyContinue
    if(-not $py){ & winget install -e --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements --silent }
    return (Get-Command python).Path
}

$python=Ensure-Python
Log "Using Python: $python"
& $python -m pip install --upgrade pip | Out-Null

# Try installing from PyPI first
$package='dji-drone-metadata-embedder'
$pkgArg = if($Version){"$package==$Version"}else{$package}
& $python -m pip install --upgrade $pkgArg | Out-Null
if($LASTEXITCODE -ne 0){
    Log "PyPI install failed; attempting local install"
    $repo=Join-Path $PSScriptRoot '..'
    if(Test-Path (Join-Path $repo 'pyproject.toml')){
        & $python -m pip install $repo | Out-Null
        if($LASTEXITCODE -ne 0){ throw "Failed to install $package" }
    }else{
        throw "Failed to install $package and local project not found"
    }
}

$binDir=Join-Path $env:LOCALAPPDATA 'dji-embed\\bin'
New-Item -Force -ItemType Directory $binDir | Out-Null

function Get-Asset($url){
    $tmp=Join-Path $env:TEMP ([IO.Path]::GetFileName($url))
    $sha=(Invoke-WebRequest "$url.sha256" -UseBasicParsing).Content.Split()[0]
    for($i=0;$i -lt 3;$i++){
        Invoke-WebRequest $url -OutFile $tmp -UseBasicParsing
        $hash=(Get-FileHash $tmp -Algorithm SHA256).Hash
        if($hash -eq $sha){return $tmp}
        Log "Checksum mismatch for $url; retrying"
    }
    throw "Failed to verify $url"
}

# FFmpeg
$ffUrl='https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-win64-gpl.zip'
$ffZip=Get-Asset $ffUrl
$tmp=Join-Path $env:TEMP 'ffmpeg'
Expand-Archive $ffZip $tmp -Force
$ffBin=Get-ChildItem $tmp -Directory | Select-Object -First 1 | ForEach-Object {Join-Path $_ 'bin'}
Copy-Item "$ffBin\*" $binDir -Recurse -Force
Remove-Item $tmp -Recurse -Force

# ExifTool
$exUrl='https://github.com/exiftool/exiftool/releases/latest/download/Image-ExifTool.zip'
$exZip=Get-Asset $exUrl
$tmp=Join-Path $env:TEMP 'exiftool'
Expand-Archive $exZip $tmp -Force
Copy-Item (Get-ChildItem $tmp -Recurse -Filter exiftool*.exe | Select-Object -First 1).FullName $binDir -Force
Remove-Item $tmp -Recurse -Force

$pyScripts=Join-Path $env:APPDATA 'Python\Scripts'
foreach($p in @($binDir,$pyScripts)){ if(-not ($env:PATH -split ';' | Where-Object { $_ -eq $p })){ $env:PATH="$p;$env:PATH" } }
try{ [Environment]::SetEnvironmentVariable('PATH',$env:PATH,'User') }catch{}
if($isAdmin){
    try{ [Environment]::SetEnvironmentVariable('PATH',$env:PATH,'Machine') }catch{ Log 'HKLM PATH update failed' }}

if(-not $NoLaunch){ & dji-embed wizard }
Log 'Done.'
