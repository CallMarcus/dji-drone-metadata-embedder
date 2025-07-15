# Contributing to DJI Drone Metadata Embedder

Thank you for your interest in contributing to this project! We welcome contributions from the DJI drone community.

## Ways to Contribute

### 1. Report Issues
- Use the GitHub issue tracker to report bugs
- Include your DJI drone model and firmware version
- Attach sample SRT files (remove sensitive location data if needed)
- Describe the expected vs actual behavior

### 2. Add Support for New Models
If your DJI drone uses a different SRT format:
1. Open an issue with "New Model Support: [Model Name]"
2. Attach a sample SRT file (5-10 subtitle entries)
3. Include the video filename format used by your model

### 3. Submit Code Changes
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-format-support`)
3. Make your changes
4. Test thoroughly with your drone footage
5. Submit a pull request

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/dji-drone-metadata-embedder.git
   cd dji-drone-metadata-embedder
   ```

2. Install development tools:
   ```bash
   pip install pytest black flake8
   ```

3. Run tests (when available):
   ```bash
   pytest tests/
   ```

## Code Style

- Follow PEP 8 Python style guide
- Use meaningful variable names
- Add comments for complex regex patterns
- Include docstrings for new functions

### Example Code Style

```python
def parse_new_format(telemetry_line: str) -> Dict[str, Any]:
    """
    Parse NewModel SRT format.
    
    Format: |LAT:59.302335|LON:18.203059|ALT:132.86|
    
    Args:
        telemetry_line: Single line of telemetry data
        
    Returns:
        Dictionary with extracted values
    """
    pattern = r'\|LAT:([+-]?\d+\.?\d*)\|LON:([+-]?\d+\.?\d*)\|ALT:([+-]?\d+\.?\d*)\|'
    match = re.search(pattern, telemetry_line)
    
    if match:
        return {
            'latitude': float(match.group(1)),
            'longitude': float(match.group(2)),
            'altitude': float(match.group(3))
        }
    return {}
```

## Testing New Formats

Before submitting:
1. Test with multiple SRT/MP4 files from your drone
2. Verify GPS metadata is correctly embedded
3. Check that subtitle tracks are preserved
4. Ensure JSON output contains expected data

## Documentation

When adding new features:
1. Update README.md with new options/features
2. Add format details to docs/SRT_FORMATS.md
3. Update CHANGELOG.md with your changes

## Pull Request Guidelines

Your PR should:
- Have a clear, descriptive title
- Reference any related issues
- Include a description of changes
- Add your drone model to the supported list
- Include sample output showing it works

## Questions?

Feel free to open an issue for:
- Clarification on code structure
- Help with regex patterns
- Testing procedures
- Feature discussions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
