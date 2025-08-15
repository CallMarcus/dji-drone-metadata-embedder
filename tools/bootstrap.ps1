#requires -version 5.1
param(
    [switch]$Silent,
    [switch]$NoLaunch,
    [string]$Version
)

$ErrorActionPreference = 'Stop'
$VerbosePreference = if($Silent){'SilentlyContinue'} else{'Continue'}

function Log($Msg){ if(-not $Silent){ Write-Host "[+] $Msg" -ForegroundColor Green } }
function LogError($Msg){ Write-Host "[!] ERROR: $Msg" -ForegroundColor Red }
function LogWarn($Msg){ Write-Host "[!] WARNING: $Msg" -ForegroundColor Yellow }
function LogInfo($Msg){ if(-not $Silent){ Write-Host "[i] $Msg" -ForegroundColor Cyan } }

# Test if a Python executable actually works (not just a Microsoft Store alias)
function Test-PythonExecutable($PythonPath) {
    try {
        # Test with a timeout to avoid hanging on Store aliases
        $job = Start-Job -ScriptBlock {
            param($path)
            try {
                $result = & $path -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
                if ($LASTEXITCODE -eq 0) { return $result }
            } catch {}
            return $null
        } -ArgumentList $PythonPath
        
        $result = $job | Wait-Job -Timeout 10 | Receive-Job
        $job | Remove-Job -Force
        
        if ($result -and $result -match '^\d+\.\d+$') {
            $version = [version]$result
            if ($version -ge [version]'3.10') {
                return @{ 'working' = $true; 'version' = $result; 'path' = $PythonPath }
            } else {
                LogWarn "Python $result found but version too old (need 3.10+)"
            }
        }
    } catch {
        # Silently fail - this is expected for Store aliases
    }
    return @{ 'working' = $false }
}

# Find working Python installation
function Find-WorkingPython {
    LogInfo "Searching for Python installation..."
    
    # Priority order: specific versions, then generic commands
    $pythonCandidates = @(
        # Specific Python versions in common locations
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe", 
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "C:\Program Files\Python312\python.exe",
        "C:\Program Files\Python311\python.exe",
        "C:\Program Files\Python310\python.exe",
        "C:\Python312\python.exe",
        "C:\Python311\python.exe", 
        "C:\Python310\python.exe",
        # Generic commands (might be Store aliases)
        "py",
        "python3", 
        "python"
    )
    
    foreach ($candidate in $pythonCandidates) {
        if ($candidate -like "*python.exe" -and -not (Test-Path $candidate)) {
            continue  # Skip missing specific paths
        }
        
        try {
            # For command names, resolve to full path first
            if ($candidate -notlike "*\*") {
                $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
                if (-not $cmd) { continue }
                $fullPath = $cmd.Source
            } else {
                $fullPath = $candidate
            }
            
            # Skip obvious Microsoft Store aliases
            if ($fullPath -like "*WindowsApps*" -and $fullPath -like "*python.exe") {
                LogInfo "Skipping Microsoft Store alias: $fullPath"
                continue
            }
            
            $test = Test-PythonExecutable $fullPath
            if ($test.working) {
                LogInfo "Found working Python $($test.version) at: $fullPath"
                return $fullPath
            }
        } catch {
            # Continue searching
        }
    }
    
    return $null
}

# Install Python using the most reliable method
function Install-Python {
    LogInfo "No working Python found. Installing Python 3.11..."
    
    # Method 1: Try winget (most reliable on Windows 11)
    try {
        Log "Installing Python via winget..."
        $result = & winget install -e --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements --silent 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            LogInfo "Winget installation completed. Waiting for installation to finalize..."
            Start-Sleep 10
            
            # Refresh environment variables
            $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH","User")
            
            # Look for newly installed Python
            $python = Find-WorkingPython
            if ($python) {
                Log "Python successfully installed via winget"
                return $python
            }
        }
    } catch {
        LogWarn "Winget installation failed: $($_.Exception.Message)"
    }
    
    # Method 2: Try Chocolatey if available
    try {
        if (Get-Command choco -ErrorAction SilentlyContinue) {
            Log "Trying Chocolatey installation..."
            & choco install python311 -y
            Start-Sleep 5
            $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH","User")
            $python = Find-WorkingPython
            if ($python) {
                Log "Python successfully installed via Chocolatey"
                return $python
            }
        }
    } catch {
        LogWarn "Chocolatey installation failed"
    }
    
    # Method 3: Direct download and install
    try {
        Log "Downloading Python installer..."
        $pythonUrl = "https://www.python.org/ftp/python/3.11.8/python-3.11.8-amd64.exe"
        $installerPath = Join-Path $env:TEMP "python-installer.exe"
        
        Invoke-WebRequest -Uri $pythonUrl -OutFile $installerPath -UseBasicParsing
        
        Log "Installing Python (this may take a few minutes)..."
        $installArgs = "/quiet InstallAllUsers=0 PrependPath=1 Include_test=0"
        $process = Start-Process -FilePath $installerPath -ArgumentList $installArgs -Wait -PassThru
        
        if ($process.ExitCode -eq 0) {
            Start-Sleep 10
            $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH","User")
            $python = Find-WorkingPython
            if ($python) {
                Log "Python successfully installed via direct download"
                Remove-Item $installerPath -Force -ErrorAction SilentlyContinue
                return $python
            }
        }
        
        Remove-Item $installerPath -Force -ErrorAction SilentlyContinue
    } catch {
        LogWarn "Direct download installation failed: $($_.Exception.Message)"
    }
    
    throw "All Python installation methods failed. Please install Python 3.10+ manually from python.org"
}

# Ensure we have a working Python
function Ensure-Python {
    $python = Find-WorkingPython
    if ($python) {
        return $python
    }
    
    # No working Python found, try to install
    return Install-Python
}

# IMPROVED: Get latest version with robust fallback handling
if(-not $Version){
    # Default fallback version that we know works
    $fallbackVersion = "v1.1.2"
    
    try{
        LogInfo "Checking for latest version..."
        $headers = @{ 'User-Agent' = 'DJI-Embed-Installer/1.0' }
        $release = Invoke-RestMethod -Uri "https://api.github.com/repos/CallMarcus/dji-drone-metadata-embedder/releases/latest" -Headers $headers -TimeoutSec 15
        $Version = $release.tag_name.TrimStart('v')
        LogInfo "Latest GitHub release: $Version"
    }catch{
        LogWarn "GitHub API unavailable, trying PyPI..."
        try{
            $pypi = Invoke-RestMethod -Uri "https://pypi.org/pypi/dji-drone-metadata-embedder/json" -TimeoutSec 15
            $Version = $pypi.info.version
            LogInfo "Latest PyPI version: $Version"
        }catch{
            $Version = $fallbackVersion
            LogWarn "APIs unavailable, using fallback version: $Version"
            LogWarn "This is normal if you're offline or APIs are rate-limited"
        }
    }
}

Log "Installing DJI Metadata Embedder $Version"

# Elevate if not admin (helps with winget reliability)
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if(-not $isAdmin){
    try{
        LogInfo "Requesting administrator privileges for optimal installation..."
        $scriptPath = $PSCommandPath
        if (-not $scriptPath) {
            # Handle case where script is piped from web
            $scriptContent = $MyInvocation.MyCommand.ScriptBlock.ToString()
            $scriptPath = Join-Path $env:TEMP "dji_bootstrap.ps1"
            $scriptContent | Out-File -FilePath $scriptPath -Encoding UTF8
        }
        
        $args = @(
            '-ExecutionPolicy', 'Bypass',
            '-File', "`"$scriptPath`""
        )
        if($Silent) { $args += '-Silent' }
        if($NoLaunch) { $args += '-NoLaunch' }
        if($Version) { $args += '-Version'; $args += $Version }
        
        $process = Start-Process -FilePath 'powershell' -Verb 'RunAs' -ArgumentList $args -Wait -PassThru
        
        if ($process.ExitCode -eq 0) {
            Log "Installation completed successfully"
            exit 0
        } else {
            LogWarn "Elevated installation had issues, continuing in user mode..."
        }
    }catch{ 
        LogWarn 'Admin elevation failed, continuing in user mode' 
    }
}

# Get working Python
try {
    $python = Ensure-Python
    Log "Using Python: $python"
} catch {
    LogError $_.Exception.Message
    LogError ""
    LogError "MANUAL INSTALLATION REQUIRED:"
    LogError "1. Download Python from: https://python.org/downloads/"
    LogError "2. During installation, check 'Add Python to PATH'"
    LogError "3. Run this installer again"
    LogError ""
    if (-not $Silent) {
        Read-Host "Press Enter to exit"
    }
    exit 1
}

# Upgrade pip with better error handling
try {
    LogInfo "Updating pip..."
    $pipOutput = & $python -m pip install --upgrade pip 2>&1
    if ($LASTEXITCODE -ne 0) {
        LogWarn "Pip upgrade failed, continuing anyway..."
    }
} catch {
    LogWarn "Pip upgrade encountered issues, continuing..."
}

# Install the main package (use correct name for Windows/macOS)
$package = 'dji-drone-metadata-embedder'

# Check if version contains pre-release identifiers (hyphen)
if ($Version -and $Version -match '-') {
    LogWarn "Detected pre-release version: $Version"
    LogWarn "Pre-release versions must be installed from GitHub"
    
    # Install from GitHub for pre-releases
    $gitUrl = "git+https://github.com/CallMarcus/dji-drone-metadata-embedder.git@v$Version"
    $pkgArg = $gitUrl
    Log "Installing from GitHub: v$Version"
} else {
    $pkgArg = if($Version) { "$package==$Version" } else { $package }
}

try {
    Log "Installing $package..."
    $installOutput = & $python -m pip install --upgrade $pkgArg 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Log "Package installed successfully"
    } else {
        # If GitHub install fails, try without version specification
        if ($Version -and $Version -match '-') {
            LogWarn "GitHub installation failed, trying latest stable version..."
            $installOutput = & $python -m pip install --upgrade $package 2>&1
            if ($LASTEXITCODE -eq 0) {
                Log "Latest stable version installed successfully"
            } else {
                throw "Installation failed with exit code $LASTEXITCODE"
            }
        } else {
            throw "Installation failed with exit code $LASTEXITCODE"
        }
    }
} catch {
    LogError "Package installation failed: $($_.Exception.Message)"
    LogError ""
    LogError "TROUBLESHOOTING:"
    LogError "1. Check internet connection"
    LogError "2. Try manually: pip install dji-drone-metadata-embedder"
    LogError "3. For pre-release: pip install git+https://github.com/CallMarcus/dji-drone-metadata-embedder.git@v$Version"
    LogError "4. If issues persist, visit: https://github.com/CallMarcus/dji-drone-metadata-embedder"
    LogError ""
    if (-not $Silent) {
        Read-Host "Press Enter to exit"
    }
    exit 1
}

# Install tools (FFmpeg and ExifTool)
$binDir = Join-Path $env:LOCALAPPDATA 'dji-embed\bin'
$FFmpegUrl = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'
$ExifToolUrl = 'https://sourceforge.net/projects/exiftool/files/exiftool-13.33_64.zip/download'
New-Item -Force -ItemType Directory $binDir | Out-Null

# Function to download and extract tools safely
function Install-Tool($Name, $Url, $ExtractLogic) {
    try {
        LogInfo "Installing $Name..."
        $fileName = Split-Path $Url -Leaf
        $tempFile = Join-Path $env:TEMP $fileName
        $tempDir = Join-Path $env:TEMP "$Name-extract"
        
        # Download with .NET WebClient for better handling of large files
        try {
            $wc = New-Object System.Net.WebClient
            $wc.Headers.Add("User-Agent", "DJI-Embed-Installer")
            $wc.DownloadFile($Url, $tempFile)
        } catch {
            # Fallback to Invoke-WebRequest if WebClient fails
            LogWarn "WebClient failed, trying Invoke-WebRequest..."
            Invoke-WebRequest -Uri $Url -OutFile $tempFile -UseBasicParsing
        }
        
        # Check if file was downloaded
        if (-not (Test-Path $tempFile)) {
            throw "Download failed - file not found"
        }
        
        $fileSize = (Get-Item $tempFile).Length
        LogInfo "Downloaded $Name ($([Math]::Round($fileSize/1MB, 1)) MB)"
        
        # Extract and install
        & $ExtractLogic $tempFile $tempDir
        
        # Cleanup
        Remove-Item $tempFile -Force -ErrorAction SilentlyContinue
        Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue
        
        Log "$Name installed successfully"
        return $true
    } catch {
        LogWarn "$Name installation failed: $($_.Exception.Message)"
        
        # Additional help for common issues
        if ($Name -eq "FFmpeg" -and $_.Exception.Message -like "*Central Directory*") {
            LogWarn "The FFmpeg download may have been corrupted. Please download manually from:"
            LogWarn "https://www.gyan.dev/ffmpeg/builds/"
        }
        
        return $false
    }
}

# Install FFmpeg
$ffmpegSuccess = Install-Tool "FFmpeg" $FFmpegUrl {
    param($zipFile, $tempDir)
    
    # Use .NET for extraction of large files
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($zipFile, $tempDir)
    
    # Find the ffmpeg executable
    $ffmpegExe = Get-ChildItem -Path $tempDir -Filter "ffmpeg.exe" -Recurse | Select-Object -First 1
    if ($ffmpegExe) {
        Copy-Item $ffmpegExe.FullName (Join-Path $binDir "ffmpeg.exe") -Force
        
        # Also copy ffprobe if found
        $ffprobeExe = Get-ChildItem -Path $tempDir -Filter "ffprobe.exe" -Recurse | Select-Object -First 1
        if ($ffprobeExe) {
            Copy-Item $ffprobeExe.FullName (Join-Path $binDir "ffprobe.exe") -Force
        }
    } else {
        throw "FFmpeg executable not found in archive"
    }
}

# Install ExifTool with correct version
$exifSuccess = Install-Tool "ExifTool" $ExifToolUrl {
    param($zipFile, $tempDir)
    # Use .NET ZipFile extraction to avoid verbose output
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    if (Test-Path $tempDir) {
        Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
    [System.IO.Compression.ZipFile]::ExtractToDirectory($zipFile, $tempDir)
    $exeTool = Get-ChildItem $tempDir -Recurse -Filter "exiftool*.exe" | Select-Object -First 1
    if ($exeTool) {
        Copy-Item $exeTool.FullName (Join-Path $binDir "exiftool.exe") -Force

        # Copy the bundled Perl library directory if present
        $libDir = Join-Path $exeTool.DirectoryName "exiftool_files"
        if (Test-Path $libDir) {
            Copy-Item $libDir (Join-Path $binDir "exiftool_files") -Recurse -Force
        }
    } else {
        throw "ExifTool executable not found in archive"
    }
}

# Update PATH
$pathsToAdd = @($binDir)
$currentPath = $env:PATH
$pathChanged = $false

foreach($p in $pathsToAdd) { 
    if(-not ($currentPath -split ';' | Where-Object { $_ -eq $p })) { 
        $env:PATH = "$p;$env:PATH"
        $pathChanged = $true
        LogInfo "Added to PATH: $p"
    } 
}

if ($pathChanged) {
    try { 
        [Environment]::SetEnvironmentVariable('PATH', $env:PATH, 'User')
        LogInfo "Updated PATH for current user"
    } catch {
        LogWarn "Could not update PATH permanently"
    }
}

# Verify tools are actually installed
LogInfo "Verifying tool installation..."
$ffmpegPath = Join-Path $binDir "ffmpeg.exe"
$exiftoolPath = Join-Path $binDir "exiftool.exe"

if (Test-Path $ffmpegPath) {
    LogInfo "FFmpeg found at: $ffmpegPath"
    try {
        $version = & $ffmpegPath -version 2>&1 | Select-Object -First 1
        LogInfo "FFmpeg version: $version"
    } catch {
        LogWarn "FFmpeg exists but failed to run"
    }
} else {
    LogError "FFmpeg not found at: $ffmpegPath"
}

if (Test-Path $exiftoolPath) {
    LogInfo "ExifTool found at: $exiftoolPath"
    try {
        # ExifTool might need to be run with full path
        $version = & "$exiftoolPath" -ver 2>&1
        if ($LASTEXITCODE -eq 0) {
            LogInfo "ExifTool version: $version"
        } else {
            LogWarn "ExifTool exists but returned error code: $LASTEXITCODE"
            LogWarn "Error output: $version"
        }
    } catch {
        LogWarn "ExifTool exists but failed to run: $($_.Exception.Message)"
    }
} else {
    LogError "ExifTool not found at: $exiftoolPath"
}

# Verify installation
LogInfo "Verifying installation..."
$djiEmbedWorking = $false
try {
    $result = & dji-embed --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        $djiEmbedWorking = $true
        Log "[OK] dji-embed command is working"
    }
} catch {}

if (-not $djiEmbedWorking) {
    try {
        # Try with Python module syntax
        $result = & $python -m dji_metadata_embedder --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            $djiEmbedWorking = $true
            Log "[OK] dji-embed working via Python module"
        }
    } catch {}
}

# Final status report
Log ""
Log "=== INSTALLATION SUMMARY ==="
Log "Python: [OK] Working"
Log "DJI Metadata Embedder: $(if($djiEmbedWorking){'[OK] Working'}else{'[WARN] May need PATH refresh'})"
Log "FFmpeg: $(if($ffmpegSuccess){'[OK] Installed'}else{'[WARN] Install manually'})"
Log "ExifTool: $(if($exifSuccess){'[OK] Installed'}else{'[WARN] Install manually'})"
Log ""

if ($djiEmbedWorking) {
    Log "Installation completed successfully!"
    Log ""
    Log "USAGE:"
    Log "  dji-embed /path/to/drone/videos"
    Log ""
    Log "For help: dji-embed --help"
} else {
    LogWarn "Installation completed but command may not be in PATH"
    LogWarn "Try opening a new Command Prompt/PowerShell window"
    LogWarn "Or use: python -m dji_metadata_embedder"
}

# If tools failed, provide manual download links
if (-not $ffmpegSuccess -or -not $exifSuccess) {
    Log ""
    Log "=== MANUAL DOWNLOAD LINKS ==="
    if (-not $ffmpegSuccess) {
        Log "FFmpeg: https://www.gyan.dev/ffmpeg/builds/"
        Log "  1. Download 'release essentials' build"
        Log "  2. Extract and copy ffmpeg.exe to: $binDir"
    }
    if (-not $exifSuccess) {
        Log "ExifTool: https://exiftool.org/"
        Log "  1. Download Windows Executable"
        Log "  2. Rename to exiftool.exe and copy to: $binDir"
    }
}

# Launch wizard if requested  
if(-not $NoLaunch -and $djiEmbedWorking) { 
    try {
        LogInfo "Launching system check..."
        # Set environment variables for the tools location
        $env:DJIEMBED_FFMPEG_PATH = Join-Path $binDir "ffmpeg.exe"
        $env:DJIEMBED_EXIFTOOL_PATH = Join-Path $binDir "exiftool.exe"
        
        # Launch doctor command to verify installation
        & dji-embed doctor
    } catch {
        LogInfo "You can run 'dji-embed doctor' to verify your installation later"
    }
}

if (-not $Silent) {
    Log ""
    Read-Host "Press Enter to close this window"
}
