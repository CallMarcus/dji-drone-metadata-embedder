# Release Process

This project publishes packages to PyPI and Windows Package Manager (winget) via GitHub Actions. Pushing a git tag that follows the pattern `vX.Y.Z` triggers the automated release workflow.

## Release Workflow

The release process consists of multiple automated workflows:

### 1. PyPI Release (`release-pypi.yml`)
1. Build the wheel and source distribution using `python -m build`
2. Import a GPG key from the `GPG_PRIVATE_KEY` repository secret
3. Sign all files in `dist/` with `gpg --detach-sign`
4. Upload the package to PyPI via the Trusted Publishers flow (OIDC)
5. Attach the artefacts and their signatures to the GitHub release page
6. Generate `SHA256SUMS.txt` for verification

### 2. Windows EXE Build (`release-exe.yml`)
1. Build a standalone `dji-embed.exe` using PyInstaller
2. Sign the executable and upload to GitHub Releases
3. Update release assets with the Windows executable

### 3. Winget Submission (`release-winget.yml`) 
1. Verify version sync using `python tools/sync_version.py --check`
2. Install `wingetcreate` tool for manifest submission
3. Automatically submit updated manifest to [microsoft/winget-pkgs](https://github.com/microsoft/winget-pkgs)
4. Create pull request for community review

### 4. Auto-Changelog (`auto-changelog.yml`)
1. Generate changelog entries from conventional commits
2. Update `CHANGELOG.md` with new version section
3. Commit changes back to the repository

## Creating a Release

### 1. Prepare the Release

```bash
# Update to new version across all files
python tools/sync_version.py 1.2.0

# Update unreleased changelog section (optional)
python scripts/update-unreleased.py

# Review all changes
git diff
```

### 2. Create and Push Tag

```bash
# Commit version updates
git add .
git commit -m "release: prepare version 1.2.0"

# Create and push tag
git tag v1.2.0  
git push origin v1.2.0
```

### 3. Monitor Workflows

The following workflows will run automatically:

1. ✅ **PyPI Release** - Package uploaded to PyPI
2. ✅ **Windows EXE** - Standalone executable built and attached
3. ✅ **Winget Submission** - Manifest submitted to winget community
4. ✅ **Auto-Changelog** - Changelog updated from commits

## Version Synchronization

The `tools/sync_version.py` script keeps version numbers consistent across:

- `src/dji_metadata_embedder/__init__.py` (source of truth)
- `README.md` (version badge)
- `tools/bootstrap.ps1` (fallback version)
- `dji-embed.spec` (PyInstaller spec)
- `winget/*.yaml` (Windows Package Manager manifests)

## Winget Integration

The project maintains local winget manifests in the `/winget` directory:

- **Package ID**: `CallMarcus.DJIMetadataEmbedder`
- **Moniker**: `dji-embed`
- **Auto-submission**: Triggered after successful EXE build
- **Community review**: PRs created in microsoft/winget-pkgs

Users can install via:
```powershell
winget install dji-embed
```
