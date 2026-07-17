# Release Process

This project publishes packages to PyPI and Windows Package Manager (winget) via GitHub Actions. Pushing a git tag that follows the pattern `vX.Y.Z` triggers the automated release workflow.

## Release Workflow

The release process is mostly automated. Pushing the tag runs the PyPI, EXE,
and changelog workflows; the winget submission is a separate manual step.

### 1. PyPI Release (`release-pypi.yml`)
1. Build the wheel and source distribution using `python -m build`
2. Import a GPG key from the `GPG_PRIVATE_KEY` repository secret
3. Sign all files in `dist/` with `gpg --detach-sign`
4. Upload the package to PyPI via the Trusted Publishers flow (OIDC)
5. Attach the artefacts and their signatures to the GitHub release page
6. Generate `SHA256SUMS.txt` for verification

### 2. Windows EXE Build (`release-exe.yml`)
Three jobs: `build` → `sign` → `publish`.
1. Build a standalone `dji-embed.exe` using PyInstaller and download the
   just-published wheel from PyPI (windows runner)
2. Authenticode-sign the exe via the reusable `certum-sign.yml` workflow
   (see "Code signing" below)
3. Generate `SHA256SUMS.txt`, attest build provenance (Sigstore), and attach
   everything to the GitHub release — both happen **after** signing because
   signing changes the file hashes

### 2b. Windows Installer (`release-installer.yml`)
Five jobs: `build` → `sign-app` → `assemble` → `sign-installer` → `publish`.
1. Build `dji-embed.exe`, publish the Avalonia GUI, stage pinned
   FFmpeg/ExifTool + licenses (windows runner)
2. Sign `dji-embed.exe` and `DjiEmbed.Gui.exe`
3. Compile the Inno Setup installer over the signed binaries and smoke-test
   a silent install (also asserts both signatures are valid); the
   Inno-generated uninstaller is knowingly unsigned (compile-time-only)
4. Sign the setup EXE
5. Checksums + attestation + release upload

### Code signing (Certum SimplySign)
Signing runs headlessly on Linux inside the pinned
`ghcr.io/callmarcus/dji-drone-metadata-embedder/certum-signer` container
(built by `signer-image.yml`, sources in `docker/certum-signer/`), driven by
the `.github/actions/certum-sign` composite action through the reusable
`certum-sign.yml` workflow. Repository secrets: `CERTUM_USER_ID`,
`CERTUM_OTP_URI`, and optionally `CERTUM_CERT_FINGERPRINT` (SHA-256 pin).
After changing any signing piece or bumping the pinned SimplySign version,
run the manual **Sign test** workflow (`sign-test.yml`) — it signs an
existing release exe end-to-end without cutting a release.

### 3. Winget Submission (`release-winget.yml`) — manual
This workflow is **not** triggered by the release tag. It only runs via
`workflow_dispatch` and must be started by a maintainer once the PyPI/EXE
release has completed:

```bash
gh workflow run release-winget.yml -f version=X.Y.Z
```

When run it will:
1. Verify version sync using `python tools/sync_version.py --check`
2. Install `wingetcreate` tool for manifest submission
3. Submit the updated manifest to [microsoft/winget-pkgs](https://github.com/microsoft/winget-pkgs)
4. Create a pull request for community review

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
2. ✅ **Windows EXE** - Standalone executable built and attached (triggered by the PyPI workflow completing)
3. ✅ **Auto-Changelog** - Changelog updated from commits

**Winget Submission is a separate manual step** — see [Winget Integration](#winget-integration) below.

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
- **Submission**: Manual via `gh workflow run release-winget.yml -f version=X.Y.Z` (not auto-triggered by the release tag)
- **Community review**: PRs created in microsoft/winget-pkgs

Users can install via:
```powershell
winget install CallMarcus.DJIMetadataEmbedder
```
