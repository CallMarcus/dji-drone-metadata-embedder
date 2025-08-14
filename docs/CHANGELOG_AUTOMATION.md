# Changelog Automation

This project automatically generates changelog entries from [Conventional Commits](https://www.conventionalcommits.org/) using GitHub Actions and custom scripts.

## 📝 How It Works

### Conventional Commits Format

Commit messages should follow this format:
```
type(scope): description

[optional body]

[optional footer]
```

**Examples:**
```bash
git commit -m "feat(cli): add new validate command with drift analysis"
git commit -m "fix(parser): handle malformed SRT timestamps gracefully"  
git commit -m "docs: update troubleshooting guide with VFR drift solutions"
git commit -m "ci: add Windows build matrix for Python 3.10-3.12"
git commit -m "feat!: redesign CLI with breaking subcommand structure"
```

### Supported Types

| **Type** | **Changelog Section** | **Description** |
|----------|----------------------|------------------|
| `feat` | **Added** | New features |
| `fix` | **Fixed** | Bug fixes |
| `docs` | **Documentation** | Documentation changes |
| `style` | **Style** | Code style changes |
| `refactor` | **Changed** | Code refactoring |
| `perf` | **Performance** | Performance improvements |
| `test` | **Testing** | Test changes |
| `ci` | **CI/CD** | CI/CD changes |
| `build` | **Build** | Build system changes |
| `chore` | **Maintenance** | Maintenance tasks |

### Breaking Changes

Mark breaking changes with `!` or include `BREAKING CHANGE:` in the commit message:
```bash
git commit -m "feat!: redesign CLI structure"
git commit -m "refactor: change API format

BREAKING CHANGE: The API response format has changed from array to object"
```

## 🤖 Automatic Generation

### On Release Tags

When you push a version tag (e.g., `v1.2.0`), GitHub Actions automatically:

1. ✅ Generates changelog entries from commits since the last release
2. ✅ Updates `CHANGELOG.md` with the new version section  
3. ✅ Commits changes back to the `master` branch
4. ✅ Organizes entries by type (Added, Fixed, Documentation, etc.)

**Trigger a release:**
```bash
git tag v1.2.0
git push origin v1.2.0
```

### Manual Generation

You can manually trigger changelog generation via GitHub Actions:

1. Go to **Actions** → **Auto-generate Changelog** 
2. Click **Run workflow**
3. Enter the version number (e.g., `1.2.0`)
4. Optionally specify a "since" tag
5. Creates a pull request with the updated changelog

## 🛠️ Development Scripts

### Update Unreleased Section

During development, update the "Unreleased" section with recent commits:

```bash
# Update with commits since last release tag
python3 scripts/update-unreleased.py

# Check what was added
git diff CHANGELOG.md
```

### Manual Generation

Generate changelog for a specific version:

```bash
# Generate for version 1.2.0 since last tag
python3 scripts/generate_changelog.py --version 1.2.0

# Generate since specific tag
python3 scripts/generate_changelog.py --version 1.2.0 --since v1.1.0

# Preview without updating file
python3 scripts/generate_changelog.py --version 1.2.0 --dry-run
```

### Test Before Committing

Preview what will be generated:

```bash
# Show recent conventional commits
git log --oneline --no-merges -10 | grep -E '^[a-f0-9]+ (feat|fix|docs|ci|build|chore|refactor|perf|test|style):'

# Generate changelog preview
python3 scripts/generate_changelog.py --dry-run --since v1.1.0
```

## 📋 Best Practices

### Writing Good Commit Messages

**✅ Good Examples:**
```bash
feat(cli): add validate command with drift analysis
fix(parser): handle missing GPS coordinates gracefully
docs(readme): add installation troubleshooting section
ci(windows): add Python 3.12 to test matrix
perf(srt): optimize large file parsing by 40%
```

**❌ Avoid:**
```bash
Update stuff
Fix bug
WIP
asdf
Merge branch 'feature'
```

### Commit Scope Guidelines

Use consistent scopes across the project:

- **`cli`** - Command line interface changes
- **`parser`** - SRT/telemetry parsing logic
- **`embedder`** - Video metadata embedding
- **`converter`** - GPX/CSV export functionality 
- **`validator`** - File validation and drift analysis
- **`docs`** - Documentation updates
- **`ci`** - CI/CD workflow changes
- **`build`** - Build system and packaging
- **`tests`** - Test suite changes

### Release Workflow

1. **During Development:**
   ```bash
   # Make changes with conventional commits
   git commit -m "feat(cli): add new export format"
   git commit -m "fix(parser): handle edge case in timestamps"
   
   # Update unreleased section periodically
   python3 scripts/update-unreleased.py
   ```

2. **Before Release:**
   ```bash
   # Review unreleased changes
   git diff CHANGELOG.md
   
   # Update version in pyproject.toml
   python3 tools/sync_version.py 1.2.0
   ```

3. **Create Release:**
   ```bash
   # Tag and push
   git tag v1.2.0
   git push origin v1.2.0
   
   # GitHub Actions will automatically update changelog
   ```

## 🔧 Customization

### Adding New Commit Types

Edit `scripts/generate_changelog.py` to add new commit types:

```python
COMMIT_TYPE_MAPPING = {
    "feat": "Added",
    "fix": "Fixed",
    "security": "Security",  # Add new type
    "deprecate": "Deprecated",
    # ... existing types
}
```

### Custom Formatting

The changelog format can be customized in the `format_changelog_entry()` function:

```python
def format_changelog_entry(commit: Dict) -> str:
    """Customize how commits appear in changelog."""
    description = commit["description"]
    
    # Your custom formatting logic here
    if commit["scope"]:
        entry = f"- **{commit['scope']}**: {description}"
    else:
        entry = f"- {description}"
    
    return entry
```

## 📊 GitHub Integration

### Workflow Permissions

The auto-changelog workflow needs these permissions:
- `contents: write` - Update changelog file
- `pull-requests: write` - Create PRs for manual triggers

### Branch Protection

Consider protecting the `master` branch and allowing the changelog workflow as an exception:

```yaml
# .github/branch_protection.yml
branch_protection:
  master:
    required_status_checks: true
    restrictions:
      users: []
      teams: []
      apps: ["github-actions"]  # Allow Actions to push
```

## 🐛 Troubleshooting

### Commits Not Appearing

**Check commit format:**
```bash
# Must start with type:
git log --oneline -5 | grep -v -E '^[a-f0-9]+ (feat|fix|docs|ci|build|chore|refactor|perf|test|style):'
```

**Fix non-conventional commits:**
```bash
# Rewrite commit messages (use with caution)
git rebase -i HEAD~3
```

### Missing Release Tags

**List existing tags:**
```bash
git tag --list --sort=-version:refname
```

**Create missing tag:**
```bash
git tag v1.1.0 <commit-hash>
git push origin v1.1.0
```

### Workflow Failures

**Check Actions logs:**
1. Go to GitHub → Actions tab
2. Click on failed run
3. Review step outputs

**Common issues:**
- Missing Python dependencies
- Git authentication problems  
- Branch protection conflicts
- Invalid version formats

---

*This automation saves time and ensures consistent, comprehensive changelogs for every release while maintaining the high-quality documentation standards expected by users.*