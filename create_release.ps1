# Quick script to create a proper 1.0.6 release

Write-Host "Creating proper 1.0.6 release..." -ForegroundColor Green

# Delete the test tag locally and remotely
Write-Host "Cleaning up test tag..." -ForegroundColor Cyan
git tag -d v1.0.4-test1 2>$null
git push origin :refs/tags/v1.0.4-test1 2>$null

# Create a proper v1.0.6 tag
Write-Host "Creating v1.0.6 tag..." -ForegroundColor Cyan
$message = @"
Release v1.0.6

- ExifTool extraction copies bundled libraries correctly
- Embed command processes all videos
"@

git tag -a v1.0.6 -m $message

# Push the new tag
Write-Host "Pushing v1.0.6 tag..." -ForegroundColor Cyan
git push origin v1.0.6

Write-Host "Done! Release v1.0.6 created." -ForegroundColor Green
