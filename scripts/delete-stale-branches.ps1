# Delete stale remote branches - REVIEW BEFORE EXECUTING!
# This script deletes merged feature branches from remote repository

param(
    [switch]$Execute = $false,
    [switch]$Help = $false
)

if ($Help) {
    Write-Host @"
DJI Metadata Embedder - Stale Branch Cleanup
============================================

Usage:
    .\delete-stale-branches.ps1           # Dry run (preview only)
    .\delete-stale-branches.ps1 -Execute  # Actually delete branches

This script removes merged feature branches matching these patterns:
- codex/*
- 3l1c1y-codex/*
- feat/issue-*
- fix/issue-*
- ci-*
- docs-*
- milestone-*

Protected branches (master, main, active development) are NOT deleted.
"@
    exit 0
}

$ErrorActionPreference = "Continue"

Write-Host "🧹 DJI Metadata Embedder - Stale Branch Cleanup" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Fetch latest refs
Write-Host "📡 Fetching latest refs..." -ForegroundColor Yellow
git fetch --all --prune 2>&1 | Out-Null

# Count branches before
$totalBranches = (git branch -r | Measure-Object).Count
Write-Host "📊 Total remote branches: $totalBranches" -ForegroundColor White
Write-Host ""

# Function to count branches matching pattern
function Get-BranchCount {
    param([string]$Pattern)
    $count = (git branch -r | Select-String $Pattern | Measure-Object).Count
    Write-Host "  - $Pattern $count branches" -ForegroundColor Gray
}

Write-Host "🔍 Branch breakdown:" -ForegroundColor Yellow
Get-BranchCount "origin/codex/"
Get-BranchCount "origin/3l1c1y-codex/"
Get-BranchCount "origin/feat/"
Get-BranchCount "origin/fix/"
Get-BranchCount "origin/ci"
Get-BranchCount "origin/docs"
Get-BranchCount "origin/milestone-"
Write-Host ""

if (-not $Execute) {
    Write-Host "🔎 DRY RUN MODE - No branches will be deleted" -ForegroundColor Yellow
    Write-Host "   Run with -Execute flag to actually delete branches" -ForegroundColor Yellow
    Write-Host ""
}

# Function to delete branches matching pattern
function Remove-StaleBranches {
    param(
        [string]$Pattern,
        [string]$Description
    )

    Write-Host "🎯 Processing: $Description" -ForegroundColor Cyan

    # Get list of branches
    $branches = git branch -r |
        Where-Object { $_ -match $Pattern } |
        ForEach-Object { $_.Trim() -replace '^\s*origin/', '' } |
        Where-Object { $_ -and $_ -notmatch '^HEAD' }

    if (-not $branches) {
        Write-Host "   ✓ No branches found" -ForegroundColor Green
        return 0
    }

    $count = ($branches | Measure-Object).Count
    Write-Host "   Found $count branches" -ForegroundColor White

    if (-not $Execute) {
        Write-Host "   Would delete:" -ForegroundColor Gray
        $branches | Select-Object -First 5 | ForEach-Object {
            Write-Host "     - $_" -ForegroundColor Gray
        }
        if ($count -gt 5) {
            Write-Host "     ... and $($count - 5) more" -ForegroundColor Gray
        }
    } else {
        Write-Host "   Deleting..." -ForegroundColor Yellow
        $deleted = 0
        foreach ($branch in $branches) {
            if ($branch) {
                try {
                    Write-Host "     Deleting: $branch" -ForegroundColor Gray
                    git push origin --delete $branch 2>&1 | Out-Null
                    $deleted++
                } catch {
                    Write-Host "     ⚠️  Failed to delete: $branch" -ForegroundColor Red
                }
            }
        }
        Write-Host "   ✓ Deleted $deleted branches" -ForegroundColor Green
    }
    Write-Host ""
    return $count
}

# Track total
$totalToDelete = 0

# Delete branches by category
$totalToDelete += Remove-StaleBranches "origin/codex/add-" "Codex 'add' feature branches"
$totalToDelete += Remove-StaleBranches "origin/codex/fix-" "Codex 'fix' branches"
$totalToDelete += Remove-StaleBranches "origin/codex/update-" "Codex 'update' branches"
$totalToDelete += Remove-StaleBranches "origin/codex/clean-" "Codex 'clean' branches"
$totalToDelete += Remove-StaleBranches "origin/codex/create-" "Codex 'create' branches"
$totalToDelete += Remove-StaleBranches "origin/codex/enhance-" "Codex 'enhance' branches"
$totalToDelete += Remove-StaleBranches "origin/codex/implement-" "Codex 'implement' branches"
$totalToDelete += Remove-StaleBranches "origin/codex/refactor-" "Codex 'refactor' branches"
$totalToDelete += Remove-StaleBranches "origin/codex/remove-" "Codex 'remove' branches"
$totalToDelete += Remove-StaleBranches "origin/codex/analyze-" "Codex 'analyze' branches"
$totalToDelete += Remove-StaleBranches "origin/codex/check-" "Codex 'check' branches"
$totalToDelete += Remove-StaleBranches "origin/codex/compare-" "Codex 'compare' branches"
$totalToDelete += Remove-StaleBranches "origin/codex/" "Remaining codex branches"
$totalToDelete += Remove-StaleBranches "origin/3l1c1y-codex/" "3l1c1y-codex branches"
$totalToDelete += Remove-StaleBranches "origin/feat/issue-" "Feature branches with issue numbers"
$totalToDelete += Remove-StaleBranches "origin/fix/issue-" "Fix branches with issue numbers"
$totalToDelete += Remove-StaleBranches "origin/ci-" "CI improvement branches"
$totalToDelete += Remove-StaleBranches "origin/docs-" "Documentation branches"
$totalToDelete += Remove-StaleBranches "origin/milestone-" "Milestone branches"

Write-Host "✨ Cleanup complete!" -ForegroundColor Green
Write-Host ""

if (-not $Execute) {
    Write-Host "💡 To actually delete branches, run:" -ForegroundColor Yellow
    Write-Host "   .\scripts\delete-stale-branches.ps1 -Execute" -ForegroundColor White
    Write-Host ""
    Write-Host "📊 Summary:" -ForegroundColor Cyan
    Write-Host "   - Would delete: ~$totalToDelete branches" -ForegroundColor White
} else {
    $remainingBranches = (git branch -r | Measure-Object).Count
    $deleted = $totalBranches - $remainingBranches
    Write-Host "📊 Results:" -ForegroundColor Cyan
    Write-Host "   - Deleted: $deleted branches" -ForegroundColor Green
    Write-Host "   - Remaining: $remainingBranches branches" -ForegroundColor White
    Write-Host ""
    Write-Host "🔄 Running final prune..." -ForegroundColor Yellow
    git fetch --prune 2>&1 | Out-Null
    Write-Host "✓ Done!" -ForegroundColor Green
}
