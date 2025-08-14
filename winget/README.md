# Winget Manifests

This directory contains Windows Package Manager (winget) manifest files for the DJI Metadata Embedder package.

## 📦 Manifest Files

- **`CallMarcus.DJIMetadataEmbedder.yaml`** - Version manifest (main entry point)
- **`CallMarcus.DJIMetadataEmbedder.installer.yaml`** - Installer configuration
- **`CallMarcus.DJIMetadataEmbedder.locale.en-US.yaml`** - Localized package information

## 🔄 Version Synchronization

These manifests are automatically kept in sync with the project version using the `sync_version.py` script:

```bash
# Update all manifests to version 1.2.0
python tools/sync_version.py 1.2.0

# Check that all files are in sync
python tools/sync_version.py --check
```

The sync script updates:
- `PackageVersion` fields in all manifest files
- Download URLs in the installer manifest (GitHub release links)

## 🧪 Local Testing

### Validate Manifests

Use the official winget tools to validate manifest structure:

```powershell
# Install winget manifest validation tool
dotnet tool install --global wingetcreate

# Validate manifests
winget validate --manifest ./winget/
```

### Test Installation

Test local installation using the manifest files:

```powershell
# Install from local manifests (for testing)
winget install --manifest ./winget/

# Uninstall for testing
winget uninstall CallMarcus.DJIMetadataEmbedder
```

## 🚀 Release Process

### Automatic Submission

The project uses GitHub Actions for automatic winget submissions:

1. **Release Creation**: When a new release tag (e.g., `v1.2.0`) is pushed
2. **EXE Build**: The `release-exe.yml` workflow builds `dji-embed.exe`  
3. **Winget Submission**: The `release-winget.yml` workflow automatically:
   - Validates version sync using `sync_version.py --check`
   - Submits to the winget community repository using `wingetcreate`
   - Creates a pull request to [microsoft/winget-pkgs](https://github.com/microsoft/winget-pkgs)

### Manual Submission

If needed, you can manually submit to winget:

```powershell
# Set GitHub token for winget submissions
$env:WINGET_GITHUB_TOKEN = "your_token_here"

# Submit updated manifest
wingetcreate update CallMarcus.DJIMetadataEmbedder --version 1.2.0 --submit --token $env:WINGET_GITHUB_TOKEN
```

## 📋 Manifest Structure

### Package Identifier
- **ID**: `CallMarcus.DJIMetadataEmbedder`
- **Moniker**: `dji-embed` (short alias for installation)

### Installation
- **Type**: Portable executable
- **Scope**: User-level installation
- **Commands**: `dji-embed` (available in PATH)
- **File Extensions**: `.mp4`, `.srt`, `.dat`

### Download URL
- **Source**: GitHub Releases (`/releases/download/v{version}/dji-embed.exe`)
- **Architecture**: x64 Windows
- **Signature**: SHA256 hash (updated automatically by wingetcreate)

## 🔍 User Experience

Once published, users can install via:

```powershell
# Install by package ID
winget install CallMarcus.DJIMetadataEmbedder

# Install by moniker (short name)
winget install dji-embed

# Show package information
winget show dji-embed

# Upgrade to latest version
winget upgrade dji-embed
```

## 🛠️ Development Notes

### Updating Manifests

When making changes to the package description, features, or metadata:

1. **Edit the manifests** in this directory
2. **Test locally** with `winget validate --manifest ./winget/`
3. **Update version** using `python tools/sync_version.py <version>`
4. **Commit changes** - they'll be used in the next release

### Release Notes

The `locale.en-US.yaml` file includes:
- **ReleaseNotes**: Brief changelog for the version
- **ReleaseNotesUrl**: Link to full GitHub release notes
- **InstallationNotes**: Post-install instructions and requirements

### Dependencies

The manifests reference the portable EXE version which includes:
- ✅ Python runtime (bundled via PyInstaller)
- ⚠️ FFmpeg (user must install separately)
- ⚠️ ExifTool (optional, user must install)

Users are directed to use the bootstrap installer for automatic dependency setup.

---

*These manifests enable one-click installation on Windows via `winget install dji-embed` while maintaining proper version synchronization with the project release process.*