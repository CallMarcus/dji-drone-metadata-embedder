# Requirements Lock Policy

This project uses `requirements.lock` to ensure reproducible builds across different environments and CI runs.

## Overview

- **`requirements.lock`** - Contains exact pinned versions of all dependencies
- **`pyproject.toml`** - Contains flexible version ranges for end users
- **CI builds** use exact locked versions for consistency
- **End users** get flexible ranges for compatibility

## Updating the Lock File

### When to Update

Update `requirements.lock` when:
- Adding new dependencies to `pyproject.toml`
- Security vulnerabilities in pinned versions
- Bug fixes in dependencies that affect our functionality
- Monthly maintenance updates

### How to Update

1. **Install current dependencies:**
   ```bash
   pip install -e .[dev]
   ```

2. **Generate new lock file:**
   ```bash
   pip freeze > requirements.lock.tmp
   ```

3. **Clean up the lock file:**
   - Remove `-e .` lines (our package)
   - Remove unnecessary transitive dependencies
   - Keep only production + dev dependencies
   - Sort alphabetically by package name

4. **Test the new lock:**
   ```bash
   pip install -r requirements.lock.tmp
   pytest
   ```

5. **Replace the old lock:**
   ```bash
   mv requirements.lock.tmp requirements.lock
   ```

### Lock File Format

```
# Production dependencies
click==8.1.6
rich==13.7.1

# Development dependencies  
pytest==8.3.2
black==24.4.2
ruff==0.4.6
mypy==1.8.0

# Build dependencies
build==1.2.1
hatchling==1.25.0
```

## CI Integration

The CI pipeline uses locked versions to ensure:
- ✅ Consistent behavior across all builds
- ✅ Early detection of dependency-related regressions  
- ✅ Reproducible release artifacts

Cache keys include `requirements.lock` hash to invalidate when dependencies change.

## Troubleshooting

### Lock file conflicts
If `requirements.lock` causes installation issues:
1. Check if your Python version is supported (3.10+)
2. Try updating pip: `pip install --upgrade pip`
3. Check for platform-specific dependency issues

### Outdated dependencies
If dependencies become severely outdated:
1. Follow the update process above
2. Test thoroughly with the new versions
3. Update any compatibility code if needed