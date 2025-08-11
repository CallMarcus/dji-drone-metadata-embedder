#!/bin/bash
# Quick script to create a proper 1.0.4 release

echo "Creating proper 1.0.4 release..."

# First, push the bootstrap fix
echo "Pushing bootstrap fix..."
git push origin master

# Delete the test tag locally and remotely
echo "Cleaning up test tag..."
git tag -d v1.0.4-test1 2>/dev/null || true
git push origin :refs/tags/v1.0.4-test1 2>/dev/null || true

# Create a proper v1.0.4 tag
echo "Creating v1.0.4 tag..."
git tag -a v1.0.4 -m "Release v1.0.4

- Fixed package structure consolidation
- Working Windows executable build
- Improved bootstrap script for Windows
- Support for multiple DJI drone formats
- DAT file parsing support
- GPX/CSV export functionality"

# Push the new tag
echo "Pushing v1.0.4 tag..."
git push origin v1.0.4

echo "Done! Release v1.0.4 created."
