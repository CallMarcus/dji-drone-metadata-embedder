#!/usr/bin/env python3
"""
Update the 'Unreleased' section of CHANGELOG.md with recent conventional commits.

This is a developer convenience script to update the changelog during development,
before creating an official release.
"""

import subprocess
import sys
from pathlib import Path

# Add the current directory to path so we can import generate_changelog
sys.path.append(str(Path(__file__).parent))

from generate_changelog import (
    get_commits_since_tag, 
    get_latest_release_tag,
    generate_changelog_section,
    update_changelog_file
)


def main():
    """Update unreleased section with recent commits."""
    print("🔄 Updating 'Unreleased' section in changelog...")
    
    # Get latest release tag
    latest_tag = get_latest_release_tag()
    if latest_tag:
        print(f"📅 Finding commits since: {latest_tag}")
    else:
        print("📅 No release tags found, using recent commits")
    
    # Get commits since last release
    commits = get_commits_since_tag(latest_tag)
    
    if not commits:
        print("ℹ️ No conventional commits found since last release")
        return 0
    
    print(f"📝 Found {len(commits)} conventional commits")
    
    # Generate changelog section for unreleased
    changelog_section = generate_changelog_section(commits, "Unreleased")
    
    # Update changelog file
    changelog_path = Path("CHANGELOG.md")
    update_changelog_file(changelog_path, changelog_section, "Unreleased")
    
    print("🚀 Unreleased section updated!")
    print("\n💡 Tip: Review the changes with 'git diff CHANGELOG.md'")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())