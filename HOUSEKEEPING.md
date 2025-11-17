# Repository Housekeeping Recommendations

**Generated:** 2025-08-15
**Current State:** 132 remote branches, production-ready codebase

---

## 🎯 Executive Summary

This repository is production-ready but has accumulated **132 stale remote branches** and several development-only scripts in the root directory. Recommended cleanup will:

- **Reduce clutter** by removing 125+ merged feature branches
- **Improve clarity** by moving development scripts to appropriate locations
- **Maintain functionality** by preserving all user-facing scripts and both test suites

---

## 📊 Current Status Analysis

### Branch Inventory
- **Total remote branches:** 132
- **Current working branch:** `claude/review-repo-docs-015rE98NQRiYfUYiwJuxgCpG`
- **Stale branch patterns:**
  - `codex/*` - 80+ branches from AI agent development
  - `feat/*`, `fix/*`, `ci/*`, `docs/*` - Feature branches (merged)
  - `3l1c1y-codex/*` - Additional AI agent work
  - Various one-off development branches

### File Organization
```
Root Directory Issues:
✅ KEEP: process_drone_footage.bat/sh (user convenience)
✅ KEEP: run_diagnostic.bat (user convenience)
⚠️ MOVE/REMOVE: create-issues.ps1 (dev helper)
⚠️ MOVE/REMOVE: create_github_release.ps1 (ad-hoc v1.0.7 release)
⚠️ MOVE/REMOVE: create_release.ps1/sh (ad-hoc release scripts)
⚠️ MOVE/REMOVE: get-exe-info.ps1 (dev/testing)
⚠️ DUPLICATE: test-exe.ps1 (exists in tools/)
```

### Test Directories (Both Legitimate)
- **tests/** - Unit tests (pytest suite) - 14 test files
- **validation_tests/** - Integration/E2E tests - 6 comprehensive test modules
- **scripts/** - Development utilities (sample generation, changelog, etc.)

---

## 🧹 Cleanup Plan

### Phase 1: Branch Cleanup (High Impact)

#### Recommended Actions:

**1.1 Identify Protected Branches**
```bash
# Keep these branches:
- master (default)
- Any active development branches
- Any branches with open PRs
```

**1.2 Delete Merged Feature Branches**
Most branches with these prefixes are safe to delete:
- `codex/*` - Merged AI agent work
- `feat/*` - Merged features
- `fix/*` - Merged bug fixes
- `ci/*` - Merged CI improvements
- `docs/*` - Merged documentation
- `3l1c1y-codex/*` - Merged AI work

**Automated Scripts Available:**
We've created comprehensive cleanup scripts in `scripts/`:
- `scripts/delete-stale-branches.sh` (Bash)
- `scripts/delete-stale-branches.ps1` (PowerShell)

Both scripts support dry-run mode and detailed progress reporting.

**Important Note - GitHub UI Required:**
Due to repository permissions, branch deletion must be done through GitHub's web interface:

1. Go to: `https://github.com/CallMarcus/dji-drone-metadata-embedder/branches/stale`
2. Review stale branches (filtered by last commit date)
3. Delete branches matching these patterns:
   - `codex/*` (~117 branches)
   - `3l1c1y-codex/*` (1 branch)
   - `ci-*`, `docs-*` (merged CI/docs branches)
   - Other merged feature branches

**Alternative - GitHub CLI:**
```bash
# If you have admin access
gh api repos/CallMarcus/dji-drone-metadata-embedder/git/refs/heads/codex/add-* --method DELETE

# Or use the scripts for local testing:
bash scripts/delete-stale-branches.sh  # Dry-run
```

---

### Phase 2: Root Directory Cleanup (Medium Impact)

#### 2.1 Scripts to Remove
These are one-off development helpers no longer needed:

```bash
# Remove ad-hoc release scripts (replaced by CI workflows)
rm create_github_release.ps1
rm create_release.ps1
rm create_release.sh

# Remove development helpers
rm get-exe-info.ps1
```

#### 2.2 Scripts to Relocate
Move to `scripts/` or `tools/` directory:

```bash
# Move to scripts/ (if keeping for reference)
mv create-issues.ps1 scripts/create-issues.ps1

# Or remove if CI handles this now
rm create-issues.ps1
```

#### 2.3 Duplicate Files
```bash
# test-exe.ps1 exists in root AND tools/
# Keep tools/test_exe.py (Python version)
rm test-exe.ps1  # Remove root version
```

---

### Phase 3: Documentation Updates (Low Impact)

#### 3.1 Update .gitignore
Already comprehensive! Minor addition:

```gitignore
# At end of file, add:
# Development scripts (kept for reference but gitignored in future)
scripts/create-issues.ps1
scripts/adhoc-*.ps1
```

#### 3.2 Update CONTRIBUTING.md
Add branch naming guidance:

```markdown
### Branch Naming Convention
- Feature: `feat/issue-123-description`
- Bug fix: `fix/issue-123-description`
- CI: `ci/improvement-description`
- Docs: `docs/improvement-description`
- AI agents: `claude/session-id` or `codex/description`

**Note:** Feature branches are deleted after merge to keep repository clean.
```

---

## 📋 Execution Checklist

### Before Starting
- [ ] Backup current branch state
- [ ] Verify no open PRs on branches to be deleted
- [ ] Notify collaborators of cleanup

### Branch Cleanup
- [ ] Create and test deletion script with dry-run
- [ ] Delete `codex/*` branches (80+ branches)
- [ ] Delete `3l1c1y-codex/*` branches
- [ ] Delete merged `feat/*`, `fix/*`, `ci/*`, `docs/*` branches
- [ ] Verify protected branches remain intact
- [ ] Run `git fetch --prune` to clean local refs

### File Cleanup
- [ ] Remove ad-hoc release scripts (3 files)
- [ ] Remove development helpers (2 files)
- [ ] Remove duplicate test-exe.ps1
- [ ] Verify user convenience scripts still work

### Documentation
- [ ] Update .gitignore if needed
- [ ] Update CONTRIBUTING.md with branch policy
- [ ] Add note to README about clean branch policy
- [ ] Commit and push changes

### Verification
- [ ] Run test suite: `pytest -q`
- [ ] Run validation tests: `py validation_tests/run_all_tests.py`
- [ ] Verify CI workflows still function
- [ ] Check that user scripts still work

---

## 🎯 Expected Results

### Before Cleanup
- **Remote branches:** 132
- **Root scripts:** 9 files (.ps1, .sh, .bat)
- **Git repo size:** 13MB

### After Cleanup
- **Remote branches:** ~5-7 (master + active work)
- **Root scripts:** 2-3 (user-facing only)
- **Git repo size:** 12-13MB (branches are refs, minimal space savings)
- **Clarity:** Significantly improved
- **Maintenance:** Easier to navigate

---

## ⚠️ Risks & Mitigation

### Risk: Deleting Active Branches
- **Mitigation:** Check for open PRs first
- **Recovery:** Branches can be restored from reflog within ~90 days

### Risk: Breaking User Workflows
- **Mitigation:** Only remove development scripts, keep user-facing ones
- **Recovery:** Scripts are in git history

### Risk: CI Pipeline Issues
- **Mitigation:** Test CI after file removals
- **Recovery:** Revert commit if issues found

---

## 🚀 Quick Start Commands

### Safe Dry-Run Analysis
```bash
# See what would be deleted (codex branches)
git branch -r | grep 'origin/codex/' | wc -l
git branch -r | grep 'origin/codex/' | head -20

# Check for open PRs
gh pr list --state open --json headRefName
```

### Conservative Cleanup (Recommended First Step)
```bash
# Delete only obviously stale AI agent branches
git fetch --all --prune
git push origin --delete $(git branch -r | grep 'origin/codex/add-' | sed 's/origin\///' | head -10)

# Verify no issues, then continue with more
```

---

## 📝 Notes

1. **Test directories are BOTH needed:**
   - `tests/` = Unit tests (fast, focused)
   - `validation_tests/` = Integration tests (comprehensive, E2E)

2. **Tools directory is well-organized:**
   - bootstrap.ps1 (user installer)
   - sync_version.py (release tooling)
   - build_exe.py (packaging)
   - All are actively used

3. **CI workflows are comprehensive:**
   - All in `.github/workflows/`
   - No need for root-level release scripts

4. **.gitignore is already excellent:**
   - Comprehensive coverage
   - Only minor additions suggested

---

## 🤝 Recommendations for Future

1. **Establish branch deletion policy:**
   - Delete feature branches within 1 week of merge
   - Use GitHub branch protection rules
   - Enable "Automatically delete head branches" in repo settings

2. **Use branch naming conventions:**
   - Follow conventional naming in agents.md
   - Include issue numbers in branch names
   - Use descriptive but concise names

3. **Keep root directory clean:**
   - User-facing scripts only in root
   - Development scripts in `scripts/` or `tools/`
   - Ad-hoc scripts should be temporary and removed after use

---

**End of Report**
