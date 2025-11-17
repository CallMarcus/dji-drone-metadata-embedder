#!/bin/bash
# Delete stale remote branches - REVIEW BEFORE EXECUTING!
# This script deletes merged feature branches from remote repository

set -e

echo "🧹 DJI Metadata Embedder - Stale Branch Cleanup"
echo "================================================"
echo ""

# Fetch latest refs
echo "📡 Fetching latest refs..."
git fetch --all --prune

# Count branches before
TOTAL_BRANCHES=$(git branch -r | wc -l)
echo "📊 Total remote branches: $TOTAL_BRANCHES"
echo ""

# Function to list branches matching pattern
list_branches() {
    local pattern=$1
    local count=$(git branch -r | grep "$pattern" | wc -l)
    echo "  - $pattern: $count branches"
}

echo "🔍 Branch breakdown:"
list_branches "origin/codex/"
list_branches "origin/3l1c1y-codex/"
list_branches "origin/feat/"
list_branches "origin/fix/"
list_branches "origin/ci/"
list_branches "origin/docs/"
list_branches "origin/milestone-"
echo ""

# Dry run mode by default
DRY_RUN=${DRY_RUN:-true}

if [ "$DRY_RUN" = "true" ]; then
    echo "🔎 DRY RUN MODE - No branches will be deleted"
    echo "   Set DRY_RUN=false to actually delete branches"
    echo ""
fi

# Function to delete branches matching pattern
delete_branches() {
    local pattern=$1
    local description=$2

    echo "🎯 Processing: $description"

    # Get list of branches
    branches=$(git branch -r | grep "$pattern" | sed 's/^\s*origin\///' | grep -v HEAD || true)

    if [ -z "$branches" ]; then
        echo "   ✓ No branches found"
        return
    fi

    count=$(echo "$branches" | wc -l)
    echo "   Found $count branches"

    if [ "$DRY_RUN" = "true" ]; then
        echo "   Would delete:"
        echo "$branches" | head -5 | sed 's/^/     - /'
        if [ $count -gt 5 ]; then
            echo "     ... and $((count - 5)) more"
        fi
    else
        echo "   Deleting..."
        echo "$branches" | while read -r branch; do
            if [ -n "$branch" ]; then
                echo "     Deleting: $branch"
                git push origin --delete "$branch" 2>&1 | grep -v "^remote:" || true
            fi
        done
        echo "   ✓ Deleted $count branches"
    fi
    echo ""
}

# Delete branches by category
delete_branches "origin/codex/add-" "Codex 'add' feature branches"
delete_branches "origin/codex/fix-" "Codex 'fix' branches"
delete_branches "origin/codex/update-" "Codex 'update' branches"
delete_branches "origin/codex/clean-" "Codex 'clean' branches"
delete_branches "origin/codex/create-" "Codex 'create' branches"
delete_branches "origin/codex/enhance-" "Codex 'enhance' branches"
delete_branches "origin/codex/implement-" "Codex 'implement' branches"
delete_branches "origin/codex/refactor-" "Codex 'refactor' branches"
delete_branches "origin/codex/remove-" "Codex 'remove' branches"
delete_branches "origin/codex/" "Remaining codex branches"
delete_branches "origin/3l1c1y-codex/" "3l1c1y-codex branches"
delete_branches "origin/feat/issue-" "Feature branches with issue numbers"
delete_branches "origin/fix/issue-" "Fix branches with issue numbers"
delete_branches "origin/ci-" "CI improvement branches"
delete_branches "origin/docs-" "Documentation branches"
delete_branches "origin/milestone-" "Milestone branches"

echo "✨ Cleanup complete!"
echo ""

if [ "$DRY_RUN" = "true" ]; then
    echo "💡 To actually delete branches, run:"
    echo "   DRY_RUN=false bash scripts/delete-stale-branches.sh"
else
    REMAINING_BRANCHES=$(git branch -r | wc -l)
    DELETED=$((TOTAL_BRANCHES - REMAINING_BRANCHES))
    echo "📊 Results:"
    echo "   - Deleted: $DELETED branches"
    echo "   - Remaining: $REMAINING_BRANCHES branches"
    echo ""
    echo "🔄 Running final prune..."
    git fetch --prune
    echo "✓ Done!"
fi
