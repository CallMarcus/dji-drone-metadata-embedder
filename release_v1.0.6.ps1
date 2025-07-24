# Complete release process for v1.0.6
Write-Host "DJI Metadata Embedder v1.0.6 Release Process" -ForegroundColor Green
Write-Host "===========================================" -ForegroundColor Green

# Step 1: Commit the fix summary update
Write-Host "`nStep 1: Committing final updates..." -ForegroundColor Cyan
git add FIX_SUMMARY.md
git commit -m "docs: update fix summary for v1.0.6"

# Step 2: Push all commits
Write-Host "`nStep 2: Pushing commits to master..." -ForegroundColor Cyan
git push origin master

# Step 3: Run the release script
Write-Host "`nStep 3: Creating v1.0.6 release..." -ForegroundColor Cyan
.\create_release.ps1

Write-Host "`n✅ Release process complete!" -ForegroundColor Green
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "1. Monitor GitHub Actions at: https://github.com/CallMarcus/dji-drone-metadata-embedder/actions"
Write-Host "2. Wait for PyPI release to complete"
Write-Host "3. Test the bootstrap script after release is published"
