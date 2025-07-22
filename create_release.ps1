# Quick script to create a proper 1.0.5 release

Write-Host "Creating proper 1.0.5 release..." -ForegroundColor Green

# Delete the test tag locally and remotely
Write-Host "Cleaning up test tag..." -ForegroundColor Cyan
git tag -d v1.0.4-test1 2>$null
git push origin :refs/tags/v1.0.4-test1 2>$null

# Create a proper v1.0.5 tag
Write-Host "Creating v1.0.5 tag..." -ForegroundColor Cyan
$message = @"
Release v1.0.5

- Fixed bootstrap script to handle pre-release versions
- Pre-release tags now install from GitHub instead of PyPI
- Better error messages for version format issues
- Fallback to stable version if pre-release installation fails
- Support for installing directly from GitHub tags
"@

git tag -a v1.0.5 -m $message

# Push the new tag
Write-Host "Pushing v1.0.5 tag..." -ForegroundColor Cyan
git push origin v1.0.5

Write-Host "Done! Release v1.0.5 created." -ForegroundColor Green
