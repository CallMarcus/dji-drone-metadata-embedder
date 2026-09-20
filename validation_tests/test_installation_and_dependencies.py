#!/usr/bin/env python3
"""
Test script to validate DJI Metadata Embedder installation and dependencies on Windows 11.
Run this first to ensure everything is properly set up.
"""

import importlib
import subprocess
import sys
from importlib import util
from pathlib import Path


def test_python_version():
    """Test that Python version is adequate."""
    print("🐍 Testing Python version...")
    version = sys.version_info
    print(f"   Python {version.major}.{version.minor}.{version.micro}")
    
    if version < (3, 10):
        raise RuntimeError("❌ Python 3.10+ required")
    
    print("   ✅ Python version OK")
    return True


def test_package_importable():
    """Test that the main package can be imported."""
    print("\n📦 Testing package imports...")

    try:
        if util.find_spec("dji_metadata_embedder") is None:
            raise ImportError("dji_metadata_embedder not found")

        from dji_metadata_embedder import DJIMetadataEmbedder
        from dji_metadata_embedder.metadata_check import check_metadata
        from dji_metadata_embedder.telemetry_converter import convert_to_gpx

        _ = (DJIMetadataEmbedder, convert_to_gpx, check_metadata)

        print("   ✅ Main package imported")
        print("   ✅ DJIMetadataEmbedder imported")
        print("   ✅ Telemetry converter imported")
        print("   ✅ Metadata checker imported")

        return True

    except ImportError as e:
        print(f"   ❌ Import failed: {e}")
        return False


def test_dependencies():
    """Test that required dependencies are installed."""
    print("\n📚 Testing Python dependencies...")
    
    dependencies = {
        'rich': '✅ Rich (progress bars/UI)',
        'ffmpeg': '✅ FFmpeg-python (video processing)',
        'piexif': '✅ Piexif (EXIF metadata)'
    }
    
    missing = []
    for dep_name, success_msg in dependencies.items():
        try:
            importlib.import_module(dep_name.replace('-', '_'))
            print(f"   {success_msg}")
        except ImportError:
            missing.append(dep_name)
            print(f"   ❌ {dep_name} not found")
    
    if missing:
        print("\n   📝 Install missing dependencies with:")
        print(f"   pip install {' '.join(missing)}")
        return False
    
    return True


def test_external_tools():
    """Test that external tools (FFmpeg, ExifTool) are available."""
    print("\n🔧 Testing external tools...")
    
    tools = {
        'ffmpeg': 'FFmpeg (required for video processing)',
        'exiftool': 'ExifTool (optional, for additional metadata)'
    }
    
    available = {}
    for tool, description in tools.items():
        try:
            result = subprocess.run([tool, '-version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                version_line = result.stdout.split('\n')[0]
                print(f"   ✅ {description}")
                print(f"      {version_line}")
                available[tool] = True
            else:
                print(f"   ❌ {tool} failed to run")
                available[tool] = False
        except (FileNotFoundError, subprocess.TimeoutExpired):
            print(f"   ❌ {tool} not found in PATH")
            available[tool] = False
    
    if not available.get('ffmpeg'):
        print("\n   ⚠️  FFmpeg is required! Install instructions:")
        print("      1. Download from https://www.gyan.dev/ffmpeg/builds/")
        print("      2. Extract to C:\\ffmpeg")
        print("      3. Add C:\\ffmpeg\\bin to PATH")
        print("      4. Restart command prompt")
    
    return available.get('ffmpeg', False)


def test_cli_command():
    """Test that the CLI command is available."""
    print("\n⚡ Testing CLI command...")
    
    try:
        result = subprocess.run(['dji-embed', '--help'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("   ✅ dji-embed command available")
            return True
        else:
            print("   ❌ dji-embed command failed")
            print(f"      Error: {result.stderr}")
            return False
    except FileNotFoundError:
        print("   ❌ dji-embed command not found")
        print("   📝 Try installing in development mode:")
        print("      pip install -e .")
        return False


def test_sample_data():
    """Test that sample data is available."""
    print("\n📂 Testing sample data...")
    
    samples_dir = Path(__file__).parent.parent / "samples"
    drone_footage_dir = Path("C:/Claude/DroneFootage")
    
    sample_found = False
    
    # Check repo samples
    if samples_dir.exists():
        for model_dir in samples_dir.iterdir():
            if model_dir.is_dir():
                srt_files = list(model_dir.glob("*.SRT"))
                if srt_files:
                    print(f"   ✅ Sample data found: {model_dir.name}")
                    sample_found = True
    
    # Check DroneFootage directory
    if drone_footage_dir.exists():
        srt_files = list(drone_footage_dir.glob("*.SRT"))
        mp4_files = list(drone_footage_dir.glob("*.MP4"))
        if srt_files and mp4_files:
            print(f"   ✅ Real drone footage found: {len(mp4_files)} videos, {len(srt_files)} SRT files")
            sample_found = True
    
    if not sample_found:
        print("   ⚠️  No sample data found")
        print("      Place DJI MP4 + SRT files in C:/Claude/DroneFootage for testing")
    
    return sample_found


def run_all_tests():
    """Run all validation tests."""
    print("🚁 DJI Metadata Embedder - Installation Validation")
    print("=" * 60)
    
    tests = [
        ("Python Version", test_python_version),
        ("Package Import", test_package_importable),
        ("Dependencies", test_dependencies),
        ("External Tools", test_external_tools),
        ("CLI Command", test_cli_command),
        ("Sample Data", test_sample_data),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"   ❌ {test_name} failed: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 VALIDATION SUMMARY")
    print("=" * 60)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {status} {test_name}")
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All validations passed! Your installation is ready.")
        return True
    else:
        print("⚠️  Some validations failed. Check the errors above.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
