# Quick script to create a proper 1.0.7 release

Write-Host "Creating proper 1.0.7 release..." -ForegroundColor Green

# Delete the test tag locally and remotely
Write-Host "Cleaning up test tag..." -ForegroundColor Cyan
git tag -d v1.0.4-test1 2>$null
git push origin :refs/tags/v1.0.4-test1 2>$null

# Create a proper v1.0.7 tag
Write-Host "Creating v1.0.7 tag..." -ForegroundColor Cyan
$message = @"
Release v1.0.7

- Removed winget packaging files and workflow
"@

git tag -a v1.0.7 -m $message

# Push the new tag
Write-Host "Pushing v1.0.7 tag..." -ForegroundColor Cyan
git push origin v1.0.7

Write-Host "Done! Release v1.0.7 created." -ForegroundColor Green
