# DJI Metadata Embedder - Validation Tests

This directory contains comprehensive validation tests to verify that your DJI Metadata Embedder installation is working correctly on Windows 11.

## Quick Start

Run all validation tests with one command:

```bash
cd C:\Claude\dji-drone-metadata-embedder
py validation_tests\run_all_tests.py
```

## Test Categories

### 1. Installation & Dependencies (`test_installation_and_dependencies.py`)
- ✅ Python version compatibility (3.8+)
- ✅ Package imports work correctly
- ✅ Python dependencies (rich, ffmpeg-python, piexif)
- ✅ External tools (FFmpeg, ExifTool)
- ✅ CLI command availability
- ✅ Sample data detection

### 2. SRT Parsing (`test_srt_parsing.py`)
- ✅ Parse repo sample SRT files
- ✅ Parse real drone footage SRT files
- ✅ Handle different DJI SRT formats (Mini 3/4 Pro, legacy GPS)
- ✅ Calculate telemetry statistics correctly
- ✅ Extract GPS coordinates, altitude, camera settings

### 3. Video Processing (`test_video_processing.py`)
- ✅ Dependency checker functionality
- ✅ Embedder initialization
- ✅ Video file detection and pairing
- ✅ Metadata embedding simulation
- ✅ JSON output format validation

### 4. Advanced Features (`test_advanced_features.py`)
- ✅ GPX conversion from SRT files
- ✅ CSV export functionality
- ✅ Metadata checker tools
- ✅ CLI command structure
- ✅ Module imports and function availability

### 5. End-to-End Integration (`test_integration.py`)
- ✅ Complete processing workflow
- ✅ Telemetry export workflow
- ✅ CLI integration with real files
- ✅ Error handling with invalid inputs
- ✅ Performance validation

## Running Individual Tests

You can run specific test categories:

```bash
# Test installation only
py validation_tests\test_installation_and_dependencies.py

# Test SRT parsing only
py validation_tests\test_srt_parsing.py

# Test video processing
py validation_tests\test_video_processing.py

# Test advanced features
py validation_tests\test_advanced_features.py

# Test end-to-end integration
py validation_tests\test_integration.py
```

## Test Data Requirements

### Optimal Testing (Real Drone Footage)
Place your DJI drone footage in `C:\Claude\DroneFootage\`:
- `DJI_0001.MP4` + `DJI_0001.SRT` pairs
- Tests will use these for real-world validation

### Fallback Testing (Samples)
If no real footage is available, tests use samples from:
- `samples/mini4pro/clip.SRT`
- `samples/avata2/clip.SRT`
- `samples/air3/clip.SRT`

## What Each Test Validates

### ✅ Core Functionality
- SRT telemetry parsing from multiple DJI models
- GPS coordinate extraction and validation
- Altitude and camera setting extraction
- JSON summary generation

### ✅ Video Processing
- FFmpeg integration for metadata embedding
- Subtitle track embedding (preserves all telemetry)
- Output file generation
- No quality loss (stream copy)

### ✅ Advanced Features
- GPX track export for mapping software
- CSV data export for analysis
- Metadata presence checking
- CLI command availability

### ✅ Error Handling
- Invalid SRT file handling
- Missing dependency detection
- Empty directory processing
- Graceful failure modes

## Expected Results

### ✅ Perfect Installation (All Tests Pass)
```
📊 COMPREHENSIVE VALIDATION SUMMARY
=======================================
   ✅ PASS Installation & Dependencies
   ✅ PASS SRT Parsing Functionality
   ✅ PASS Video Processing Pipeline
   ✅ PASS Advanced Features
   ✅ PASS End-to-End Integration

🎯 Overall Results: 5/5 test categories passed
```

### ⚠️ Partial Installation (Missing FFmpeg)
```
📊 COMPREHENSIVE VALIDATION SUMMARY
=======================================
   ✅ PASS Installation & Dependencies
   ✅ PASS SRT Parsing Functionality
   ⚠️  PARTIAL Video Processing Pipeline
   ✅ PASS Advanced Features
   ✅ PASS End-to-End Integration

🎯 Overall Results: 4/5 test categories passed
```

### ❌ Installation Issues
```
📊 COMPREHENSIVE VALIDATION SUMMARY
=======================================
   ❌ FAIL Installation & Dependencies
   
📝 Install missing dependencies with:
   pip install rich ffmpeg-python piexif
```

## Troubleshooting

### Common Issues

**"Python was not found"**
```bash
# Use py instead of python
py validation_tests\run_all_tests.py
```

**"dji-embed command not found"**
```bash
# Install in development mode
pip install -e .
```

**"FFmpeg not found"**
```bash
# Download FFmpeg and add to PATH
# See main README.md for detailed instructions
```

**"No test data found"**
```bash
# Place DJI MP4+SRT files in C:\Claude\DroneFootage\
# Or tests will use limited sample data
```

### Debug Mode

For detailed output during testing:

```bash
# Run tests with Python's verbose mode
py -v validation_tests\run_all_tests.py
```

## Integration with Main Tests

These validation tests complement the existing test suite:

```bash
# Run existing unit tests
pytest tests/

# Run validation tests (this directory)
py validation_tests\run_all_tests.py
```

## CI/CD Integration

These tests can be integrated into CI/CD pipelines:

```yaml
# GitHub Actions example
- name: Run validation tests
  run: python validation_tests/run_all_tests.py
```

## Performance Benchmarks

The validation tests also provide performance insights:
- SRT parsing speed
- Video processing time
- Export generation speed
- Memory usage patterns

Typical performance on Windows 11:
- SRT parsing: ~100ms for 30-second clip
- Video processing: ~2-5 seconds (no re-encoding)
- GPX export: ~50ms
- CSV export: ~30ms

## Support

If validation tests fail:

1. **Check the detailed output** for specific error messages
2. **Review individual test results** to isolate issues
3. **Verify dependencies** using the installation test
4. **Check README.md** for installation instructions
5. **Submit an issue** with test output if problems persist

The validation tests are designed to give you confidence that your DJI Metadata Embedder installation is production-ready and will handle your drone footage correctly.
