# DJI Metadata Embedder - Fix Summary (v1.0.5)

## Issue Fixed
The bootstrap script was failing because it tried to install version `1.0.4-test1` which is not a valid Python package version format (PEP 440 doesn't allow hyphens).

## Solution Implemented
1. **Updated bootstrap.ps1** to detect pre-release versions (containing hyphens)
2. For pre-releases, it now installs from GitHub using the tag
3. If GitHub install fails, it falls back to the latest stable version from PyPI
4. Better error messages for troubleshooting

## Next Steps

### 1. Push the Fix
```powershell
git push origin master
```

### 2. Create a Proper Release
Run the release script:
```powershell
.\create_release.ps1
```

This will:
- Delete the problematic v1.0.4-test1 tag
- Create a proper v1.0.5 tag
- Push it to GitHub to trigger release workflows

### 3. Monitor GitHub Actions
After pushing the tag, check:
- PyPI release workflow
- Windows executable build
- Winget package update

### 4. Test the Fixed Bootstrap
Once the release is created, test the bootstrap script:
```powershell
iwr -useb https://raw.githubusercontent.com/CallMarcus/dji-drone-metadata-embedder/master/tools/bootstrap.ps1 | iex
```

## Alternative Solutions

If you need to keep using pre-release tags in the future:
1. Use PEP 440 compliant versions: `1.0.4a1`, `1.0.4b1`, `1.0.4rc1`
2. Or use the updated bootstrap script which handles non-compliant versions

## Bootstrap Script Improvements

The updated script now:
- ✅ Handles pre-release versions from GitHub
- ✅ Falls back to stable versions if needed
- ✅ Provides better error messages
- ✅ Works with both standard and pre-release versions

## Testing Checklist

After creating the release:
- [ ] Bootstrap script installs successfully
- [ ] `dji-embed --version` shows 1.0.5
- [ ] FFmpeg and ExifTool are downloaded
- [ ] Basic video processing works
- [ ] Winget package updates (may take 24-48 hours)
