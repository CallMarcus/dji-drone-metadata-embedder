#!/usr/bin/env python3
"""
Generate changelog entries from conventional commit messages.

This script parses git commit messages following the Conventional Commits specification
and generates changelog entries in Keep a Changelog format.

Conventional Commit format: type(scope): description
Examples:
- feat(cli): add new validate command
- fix(parser): handle malformed SRT timestamps  
- docs: update troubleshooting guide
- ci: add Windows build matrix
"""

import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional


# Conventional commit type mappings to changelog sections
COMMIT_TYPE_MAPPING = {
    "feat": "Added",
    "feature": "Added", 
    "add": "Added",
    "fix": "Fixed",
    "bugfix": "Fixed",
    "docs": "Documentation", 
    "doc": "Documentation",
    "ci": "CI/CD",
    "build": "Build",
    "chore": "Maintenance",
    "refactor": "Changed",
    "perf": "Performance",
    "test": "Testing",
    "style": "Style",
    "revert": "Reverted",
}

# Breaking change indicators
BREAKING_INDICATORS = [
    "BREAKING CHANGE", "breaking change",
    "BREAKING", "breaking",
    "!:" # conventional commit breaking change indicator
]


def run_git_command(args: List[str]) -> str:
    """Run a git command and return output."""
    try:
        result = subprocess.run(
            ["git"] + args, 
            capture_output=True, 
            text=True, 
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Git command failed: {e}")
        sys.exit(1)


def parse_conventional_commit(commit_line: str) -> Optional[Dict]:
    """Parse a conventional commit message."""
    # Split hash and message
    parts = commit_line.split(" ", 1)
    if len(parts) != 2:
        return None
    
    commit_hash, message = parts
    
    # Parse conventional commit format: type(scope): description
    conventional_pattern = r'^(?P<type>\w+)(?:\((?P<scope>[^)]+)\))?(?P<breaking>!)?\s*:\s*(?P<description>.+)$'
    match = re.match(conventional_pattern, message)
    
    if not match:
        # Try simple format: type: description
        simple_pattern = r'^(?P<type>\w+)\s*:\s*(?P<description>.+)$'
        match = re.match(simple_pattern, message)
        if not match:
            return None
    
    groups = match.groupdict()
    
    # Check for breaking changes
    is_breaking = groups.get("breaking") == "!" or any(
        indicator in message.upper() for indicator in BREAKING_INDICATORS
    )
    
    return {
        "hash": commit_hash,
        "type": groups["type"].lower(),
        "scope": groups.get("scope", "").lower() if groups.get("scope") else None,
        "description": groups["description"].strip(),
        "breaking": is_breaking,
        "raw_message": message
    }


def get_commits_since_tag(since_tag: Optional[str] = None) -> List[Dict]:
    """Get commits since a specific tag or all if no tag provided."""
    if since_tag:
        # Get commits since the tag
        commit_range = f"{since_tag}..HEAD"
    else:
        # Get all commits (fallback)
        commit_range = "HEAD"
    
    try:
        output = run_git_command(["log", "--oneline", "--no-merges", commit_range])
    except:
        # If no commits found, try getting recent commits
        output = run_git_command(["log", "--oneline", "--no-merges", "-10"])
    
    if not output:
        return []
    
    commits = []
    for line in output.split('\n'):
        if line.strip():
            parsed = parse_conventional_commit(line.strip())
            if parsed:
                commits.append(parsed)
    
    return commits


def get_latest_release_tag() -> Optional[str]:
    """Get the latest release tag."""
    try:
        # Get all tags sorted by version
        output = run_git_command(["tag", "--list", "--sort=-version:refname"])
        tags = output.split('\n')
        
        # Find first tag that looks like a version (v1.2.3 or 1.2.3)
        version_pattern = r'^v?\d+\.\d+\.\d+'
        for tag in tags:
            if re.match(version_pattern, tag.strip()):
                return tag.strip()
                
    except:
        pass
    
    return None


def group_commits_by_type(commits: List[Dict]) -> Dict[str, List[Dict]]:
    """Group commits by their type (feat -> Added, fix -> Fixed, etc.)."""
    grouped = {}
    
    for commit in commits:
        commit_type = commit["type"]
        section = COMMIT_TYPE_MAPPING.get(commit_type, "Other")
        
        if section not in grouped:
            grouped[section] = []
        
        grouped[section].append(commit)
    
    return grouped


def format_changelog_entry(commit: Dict) -> str:
    """Format a single commit as a changelog entry."""
    description = commit["description"]
    
    # Capitalize first letter
    if description:
        description = description[0].upper() + description[1:]
    
    # Add scope if present
    if commit["scope"]:
        entry = f"- **{commit['scope']}**: {description}"
    else:
        entry = f"- {description}"
    
    # Add commit hash as reference
    entry += f" ({commit['hash']})"
    
    # Mark breaking changes
    if commit["breaking"]:
        entry = "🚨 " + entry + " **[BREAKING]**"
    
    return entry


def generate_changelog_section(commits: List[Dict], version: str = "Unreleased") -> str:
    """Generate a complete changelog section."""
    if not commits:
        return ""
    
    grouped = group_commits_by_type(commits)
    
    # Build section
    if version == "Unreleased":
        section = f"## [Unreleased]\n\n"
    else:
        date = datetime.now().strftime("%Y-%m-%d")
        section = f"## [{version}] - {date}\n\n"
    
    # Order sections by importance
    section_order = [
        "Added", "Changed", "Fixed", "Removed", "Deprecated", "Security",
        "Performance", "Documentation", "Testing", "CI/CD", "Build", "Maintenance", "Other"
    ]
    
    for section_name in section_order:
        if section_name in grouped:
            section += f"### {section_name}\n\n"
            
            # Sort commits by scope, then description
            section_commits = sorted(
                grouped[section_name],
                key=lambda c: (c["scope"] or "z", c["description"])
            )
            
            for commit in section_commits:
                entry = format_changelog_entry(commit)
                section += entry + "\n"
            
            section += "\n"
    
    return section


def update_changelog_file(
    changelog_path: Path, 
    new_section: str, 
    version: str = "Unreleased"
) -> None:
    """Update the existing CHANGELOG.md file with new entries."""
    if not changelog_path.exists():
        # Create new changelog file
        content = f"""# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

{new_section}
"""
        changelog_path.write_text(content, encoding="utf-8")
        print(f"✅ Created new changelog: {changelog_path}")
        return
    
    # Read existing changelog
    content = changelog_path.read_text(encoding="utf-8")
    
    if version == "Unreleased":
        # Update unreleased section
        if "## [Unreleased]" in content:
            # Replace existing unreleased section
            pattern = r'## \[Unreleased\].*?(?=## \[|\Z)'
            content = re.sub(pattern, new_section, content, flags=re.DOTALL)
        else:
            # Insert at the top after header
            header_end = content.find('\n## [')
            if header_end != -1:
                content = content[:header_end] + '\n' + new_section + content[header_end:]
            else:
                content += '\n' + new_section
    else:
        # Add new version section
        unreleased_end = content.find('\n## [')
        if unreleased_end != -1 and "Unreleased" in content[:unreleased_end + 20]:
            # Insert after unreleased section
            next_section = content.find('\n## [', unreleased_end + 1)
            if next_section != -1:
                content = content[:next_section] + '\n' + new_section + content[next_section:]
            else:
                content += '\n' + new_section
        else:
            # Insert at top of versions
            insert_pos = content.find('\n## [')
            if insert_pos != -1:
                content = content[:insert_pos] + '\n' + new_section + content[insert_pos:]
            else:
                content += '\n' + new_section
    
    changelog_path.write_text(content, encoding="utf-8")
    print(f"✅ Updated changelog: {changelog_path}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate changelog from conventional commits")
    parser.add_argument("--version", help="Version to generate (default: Unreleased)")
    parser.add_argument("--since", help="Generate since specific tag/version")  
    parser.add_argument("--dry-run", action="store_true", help="Print changelog but don't update file")
    parser.add_argument("--output", help="Output file (default: CHANGELOG.md)")
    
    args = parser.parse_args()
    
    # Determine version
    version = args.version or "Unreleased"
    
    # Determine commit range
    since_tag = args.since
    if not since_tag and version != "Unreleased":
        since_tag = get_latest_release_tag()
    
    print(f"🔍 Generating changelog for {version}...")
    if since_tag:
        print(f"📅 Commits since: {since_tag}")
    
    # Get commits
    commits = get_commits_since_tag(since_tag)
    
    if not commits:
        print("ℹ️ No conventional commits found")
        return 0
    
    print(f"📝 Found {len(commits)} conventional commits")
    
    # Generate changelog section
    changelog_section = generate_changelog_section(commits, version)
    
    if args.dry_run:
        print("\n" + "="*60)
        print("GENERATED CHANGELOG SECTION:")
        print("="*60)
        print(changelog_section)
        return 0
    
    # Update changelog file
    output_file = Path(args.output) if args.output else Path("CHANGELOG.md")
    update_changelog_file(output_file, changelog_section, version)
    
    print(f"🚀 Changelog updated with {len(commits)} commits")
    return 0


if __name__ == "__main__":
    sys.exit(main())