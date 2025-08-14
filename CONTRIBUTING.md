# Contributing to DJI Drone Metadata Embedder

Thank you for your interest in contributing! This project has matured into a production-ready tool with comprehensive documentation and automated processes. We welcome contributions from the DJI drone community.

## 🎯 **Project Status: Production Ready**

All major milestones (M1-M4) have been completed. The project now features professional documentation, comprehensive testing, and automated release processes. Future contributions should focus on maintenance, new model support, and community enhancements.

## 🤝 **Ways to Contribute**

### 1. Report Issues & Bugs
- **Use the GitHub issue tracker** to report bugs or unexpected behavior
- **Include diagnostic information**: Run `dji-embed doctor` and include the output
- **Provide drone details**: DJI model, firmware version, and DJI Fly app version  
- **Attach sample files**: Include sample SRT files (remove sensitive GPS data with `--redact drop`)
- **Expected vs actual behavior**: Clear description of what should happen vs what does happen

### 2. Add Support for New DJI Models
The project supports major DJI models (Mini 3/4 Pro, Air 3, Avata 2, Mavic 3 Enterprise), but new models are released regularly:

1. **Create an issue** with title "New Model Support: [Model Name]"
2. **Provide sample files**: Attach a small sample SRT file (5-10 subtitle entries with GPS redacted)
3. **Include format details**: Video filename patterns and any unique characteristics
4. **Test with existing tool**: Try processing with current version and note any issues

### 3. Submit Code Changes
1. **Fork the repository** and create a feature branch
2. **Follow conventional commits**: Use `feat:`, `fix:`, `docs:` prefixes (see [CHANGELOG_AUTOMATION.md](docs/CHANGELOG_AUTOMATION.md))
3. **Test thoroughly**: Use the sample fixtures in `/samples` directory for testing
4. **Update documentation**: Add your changes to troubleshooting guide or decision table if relevant
5. **Submit a pull request** with clear description of changes

## 🛠️ **Development Setup**

### Quick Start
1. **Clone the repository**:
   ```bash
   git clone https://github.com/CallMarcus/dji-drone-metadata-embedder.git
   cd dji-drone-metadata-embedder
   ```

2. **Set up development environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
   pip install -U pip
   pip install -e ".[dev]"
   ```

3. **Verify setup**:
   ```bash
   # Run tests
   pytest -q
   
   # Test CLI
   dji-embed --help
   dji-embed doctor
   
   # Test with sample fixtures
   dji-embed check samples/air3/
   ```

## 📝 **Code Style & Standards**

### Coding Guidelines
- **Follow PEP 8**: Use `ruff` for linting (automatically enforced in CI)
- **Conventional commits**: Use `feat:`, `fix:`, `docs:`, `ci:` prefixes for automatic changelog generation
- **Type hints**: Include type annotations for new functions
- **Meaningful names**: Use descriptive variable and function names
- **Document regex**: Add comments for complex regex patterns

### Testing Requirements
- **All changes must be tested**: Add tests for new functionality
- **Use sample fixtures**: Test with provided samples in `/samples` directory
- **Cross-platform**: Tests must pass on Windows and Linux (Python 3.10-3.12)
- **CLI smoke tests**: Include basic CLI tests for new commands or options

### Example: Adding New DJI Format Support

```python
def parse_new_model_format(telemetry_line: str) -> Dict[str, Any]:
    """
    Parse DJI NewModel SRT format.
    
    Expected format: |LAT:59.302335|LON:18.203059|ALT:132.86|
    
    Args:
        telemetry_line: Single line of telemetry data from SRT
        
    Returns:
        Dictionary with extracted GPS and altitude values
        
    Raises:
        ValueError: If line format is not recognized
    """
    # Pattern explanation: |KEY:value| format with decimal numbers
    pattern = r'\|LAT:([+-]?\d+\.?\d*)\|LON:([+-]?\d+\.?\d*)\|ALT:([+-]?\d+\.?\d*)\|'
    match = re.search(pattern, telemetry_line)
    
    if match:
        return {
            'latitude': float(match.group(1)),
            'longitude': float(match.group(2)),
            'altitude': float(match.group(3)),
            'format_detected': 'newmodel_pipe'
        }
    
    return {}
```

## 🧪 **Testing Your Changes**

### Before Submitting
1. **Test with sample fixtures**: Use `/samples` directory for initial testing
2. **Test with real footage**: Verify with multiple SRT/MP4 files from your specific drone model
3. **Validate output**: Check that GPS metadata is correctly embedded and JSON output is accurate
4. **Cross-format compatibility**: Ensure existing formats still work correctly
5. **Run full test suite**: Execute `pytest` to ensure no regressions

### Testing Commands
```bash
# Test your changes with sample fixtures
dji-embed embed samples/air3/ --verbose

# Test validation and drift analysis  
dji-embed validate samples/ --format json

# Check that CLI works as expected
dji-embed doctor
dji-embed --help
dji-embed check samples/mini4pro/
```

## 📚 **Documentation Updates**

When adding new features or model support:

1. **Update core documentation**:
   - Add to [decision table](docs/decision-table.md) if it affects user workflows
   - Include in [troubleshooting guide](docs/troubleshooting.md) if there are common issues
   - Add to [SRT_FORMATS.md](docs/SRT_FORMATS.md) for new format specifications

2. **Update README**: Include new CLI options, supported models, or significant features

3. **Changelog**: Conventional commits automatically generate changelog entries

## 🔄 **Pull Request Guidelines**

### PR Requirements
- **Conventional commit title**: Use `feat:`, `fix:`, `docs:` prefixes
- **Reference issues**: Link to related GitHub issues  
- **Clear description**: Explain what changes and why
- **Test evidence**: Include sample output showing the feature works
- **Documentation**: Update relevant docs for user-facing changes

### PR Template Checklist
- [ ] Tests added/updated for new functionality
- [ ] Documentation updated (if applicable)  
- [ ] Sample fixtures tested
- [ ] Cross-platform compatibility verified
- [ ] No breaking changes to existing functionality
- [ ] Conventional commit format used

## 🆘 **Getting Help**

### Community Support
- **GitHub Issues**: Best place for technical questions and bug reports
- **Discussions**: General questions about usage and workflows
- **Sample fixtures**: Use provided `/samples` for testing and examples

### What to Include When Asking for Help
- Output of `dji-embed doctor`
- Your operating system and Python version
- DJI drone model and firmware version
- Sample SRT file (with GPS redacted using `--redact drop`)
- Complete error messages and expected behavior

## 📄 **License**

By contributing, you agree that your contributions will be licensed under the MIT License.

---

*Thank you for helping make DJI Metadata Embedder better for the entire drone community!* 🚁
