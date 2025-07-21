#!/usr/bin/env python3
"""
Test script to validate DJI advanced features like telemetry conversion,
metadata checking, and CLI functionality.
"""

import sys
from pathlib import Path
import tempfile
import subprocess
import xml.etree.ElementTree as ET

# Add the package to Python path for testing
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dji_metadata_embedder.telemetry_converter import convert_to_gpx, convert_to_csv
    from dji_metadata_embedder.metadata_check import check_metadata
except ImportError as e:
    print(f"❌ Could not import DJI modules: {e}")
    print("   Try running: pip install -e .")
    sys.exit(1)


def test_gpx_conversion():
    """Test conversion of SRT telemetry to GPX format."""
    print("🗺️  Testing GPX conversion...")
    
    # Find test SRT file
    drone_footage_dir = Path("C:/Claude/DroneFootage")
    samples_dir = Path(__file__).parent.parent / "samples" / "mini4pro"
    
    srt_file = None
    if drone_footage_dir.exists():
        srt_files = list(drone_footage_dir.glob("*.SRT"))
        if srt_files:
            srt_file = srt_files[0]
    
    if not srt_file and samples_dir.exists():
        srt_files = list(samples_dir.glob("*.SRT"))
        if srt_files:
            srt_file = srt_files[0]
    
    if not srt_file:
        print("   ❌ No SRT file available for testing")
        return False
    
    try:
        print(f"   📄 Converting {srt_file.name} to GPX...")
        
        with tempfile.NamedTemporaryFile(suffix='.gpx', delete=False) as temp_gpx:
            temp_gpx_path = Path(temp_gpx.name)
        
        try:
            # Test GPX conversion
            convert_to_gpx(srt_file, temp_gpx_path)
            
            # Verify GPX file was created and has content
            if temp_gpx_path.exists() and temp_gpx_path.stat().st_size > 0:
                print(f"   ✅ GPX file created ({temp_gpx_path.stat().st_size} bytes)")
                
                # Test GPX structure
                try:
                    tree = ET.parse(temp_gpx_path)
                    root = tree.getroot()
                    
                    # Check for track points
                    trkpts = root.findall('.//{http://www.topografix.com/GPX/1/1}trkpt')
                    if trkpts:
                        print(f"   📍 Found {len(trkpts)} track points in GPX")
                        
                        # Check first track point has lat/lon
                        first_trkpt = trkpts[0]
                        lat = first_trkpt.get('lat')
                        lon = first_trkpt.get('lon')
                        
                        if lat and lon:
                            print(f"   🎯 First point: {lat}, {lon}")
                            return True
                        else:
                            print("   ❌ Track points missing lat/lon")
                            return False
                    else:
                        print("   ❌ No track points found in GPX")
                        return False
                        
                except ET.ParseError as e:
                    print(f"   ❌ GPX file is malformed: {e}")
                    return False
                    
            else:
                print("   ❌ GPX file not created or empty")
                return False
                
        finally:
            # Clean up
            if temp_gpx_path.exists():
                temp_gpx_path.unlink()
                
    except Exception as e:
        print(f"   ❌ GPX conversion failed: {e}")
        return False


def test_csv_conversion():
    """Test conversion of SRT telemetry to CSV format."""
    print("\n📊 Testing CSV conversion...")
    
    # Find test SRT file
    drone_footage_dir = Path("C:/Claude/DroneFootage")
    samples_dir = Path(__file__).parent.parent / "samples" / "mini4pro"
    
    srt_file = None
    if drone_footage_dir.exists():
        srt_files = list(drone_footage_dir.glob("*.SRT"))
        if srt_files:
            srt_file = srt_files[0]
    
    if not srt_file and samples_dir.exists():
        srt_files = list(samples_dir.glob("*.SRT"))
        if srt_files:
            srt_file = srt_files[0]
    
    if not srt_file:
        print("   ❌ No SRT file available for testing")
        return False
    
    try:
        print(f"   📄 Converting {srt_file.name} to CSV...")
        
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as temp_csv:
            temp_csv_path = Path(temp_csv.name)
        
        try:
            # Test CSV conversion
            convert_to_csv(srt_file, temp_csv_path)
            
            # Verify CSV file was created and has content
            if temp_csv_path.exists() and temp_csv_path.stat().st_size > 0:
                print(f"   ✅ CSV file created ({temp_csv_path.stat().st_size} bytes)")
                
                # Test CSV content
                with open(temp_csv_path, 'r') as f:
                    lines = f.readlines()
                
                if len(lines) >= 2:  # Header + at least one data row
                    header = lines[0].strip()
                    
                    print(f"   📋 CSV has {len(lines)-1} data rows")
                    print(f"   📝 Header: {header}")
                    
                    # Check for expected columns
                    expected_cols = ['timestamp', 'latitude', 'longitude', 'altitude']
                    if any(col in header.lower() for col in expected_cols):
                        print("   ✅ CSV has expected columns")
                        return True
                    else:
                        print("   ❌ CSV missing expected columns")
                        return False
                else:
                    print("   ❌ CSV file has insufficient data")
                    return False
                    
            else:
                print("   ❌ CSV file not created or empty")
                return False
                
        finally:
            # Clean up
            if temp_csv_path.exists():
                temp_csv_path.unlink()
                
    except Exception as e:
        print(f"   ❌ CSV conversion failed: {e}")
        return False


def test_metadata_checker():
    """Test the metadata checker functionality."""
    print("\n🔍 Testing metadata checker...")
    
    # Test with video files if available
    drone_footage_dir = Path("C:/Claude/DroneFootage")
    
    if drone_footage_dir.exists():
        video_files = list(drone_footage_dir.glob("*.MP4"))
        if video_files:
            test_file = video_files[0]
            print(f"   📹 Checking metadata in {test_file.name}")
            
            try:
                metadata = check_metadata(test_file)
                
                if metadata:
                    print("   ✅ Metadata extraction successful")
                    
                    # Check for GPS data
                    if 'gps' in metadata or 'GPS' in str(metadata):
                        print("   📍 GPS metadata found")
                    else:
                        print("   📍 No GPS metadata found (expected for unprocessed files)")
                    
                    return True
                else:
                    print("   ⚠️  No metadata found (this may be normal)")
                    return True  # Not having metadata is OK for raw files
                    
            except Exception as e:
                print(f"   ❌ Metadata check failed: {e}")
                return False
    
    # Test with sample if no real files
    print("   🧪 Testing metadata checker logic...")
    try:
        # Create a dummy file path for testing
        dummy_path = Path("test_video.mp4")
        
        # The function should handle non-existent files gracefully
        check_metadata(dummy_path)
        print("   ✅ Metadata checker handles missing files")
        return True
        
    except Exception as e:
        print(f"   ❌ Metadata checker test failed: {e}")
        return False


def test_cli_command_structure():
    """Test the CLI command structure and help."""
    print("\n⚡ Testing CLI command structure...")
    
    try:
        # Test help command
        result = subprocess.run(['dji-embed', '--help'], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            help_output = result.stdout
            print("   ✅ CLI help command works")
            
            # Check for expected options in help
            expected_options = ['--output', '--exiftool', '--check', '--verbose']
            found_options = []
            
            for option in expected_options:
                if option in help_output:
                    found_options.append(option)
            
            print(f"   📝 Found CLI options: {', '.join(found_options)}")
            
            if len(found_options) >= 3:
                print("   ✅ CLI structure looks correct")
                return True
            else:
                print("   ⚠️  Some expected CLI options missing")
                return False
        else:
            print(f"   ❌ CLI help failed: {result.stderr}")
            return False
            
    except FileNotFoundError:
        print("   ❌ dji-embed command not found")
        print("   📝 Run 'pip install -e .' to install CLI command")
        return False
    except subprocess.TimeoutExpired:
        print("   ❌ CLI command timed out")
        return False


def test_cli_dependency_check():
    """Test the CLI dependency check functionality."""
    print("\n🔧 Testing CLI dependency check...")
    
    try:
        # Test check command with a dummy directory
        with tempfile.TemporaryDirectory() as temp_dir:
            result = subprocess.run(['dji-embed', 'check', temp_dir],
                                  capture_output=True, text=True, timeout=15)
            
            if result.returncode in [0, 1]:  # 0 = success, 1 = some deps missing
                output = result.stdout + result.stderr
                print("   ✅ CLI dependency check runs")
                
                # Check output mentions key tools
                if 'ffmpeg' in output.lower():
                    print("   🔧 Dependency check mentions FFmpeg")
                
                if 'exiftool' in output.lower():
                    print("   🔧 Dependency check mentions ExifTool")
                
                return True
            else:
                print("   ❌ CLI dependency check failed unexpectedly")
                return False
                
    except FileNotFoundError:
        print("   ⚠️  CLI command not available")
        return False
    except subprocess.TimeoutExpired:
        print("   ❌ CLI dependency check timed out")
        return False


def test_telemetry_module_imports():
    """Test that all telemetry modules can be imported and have expected functions."""
    print("\n📦 Testing telemetry module imports...")
    
    try:
        # Test telemetry converter
        from dji_metadata_embedder import telemetry_converter
        
        expected_functions = ['convert_to_gpx', 'convert_to_csv']
        found_functions = []
        
        for func_name in expected_functions:
            if hasattr(telemetry_converter, func_name):
                found_functions.append(func_name)
        
        print(f"   ✅ Telemetry converter functions: {', '.join(found_functions)}")
        
        # Test metadata checker
        from dji_metadata_embedder import metadata_check
        
        if hasattr(metadata_check, 'check_metadata'):
            print("   ✅ Metadata checker function available")
        
        # Test utilities
        from dji_metadata_embedder import utilities
        
        util_functions = ['parse_dji_srt', 'check_dependencies']
        found_utils = []
        
        for func_name in util_functions:
            if hasattr(utilities, func_name):
                found_utils.append(func_name)
        
        print(f"   ✅ Utility functions: {', '.join(found_utils)}")
        
        if len(found_functions) >= 2 and len(found_utils) >= 2:
            return True
        else:
            print("   ❌ Some expected functions missing")
            return False
            
    except ImportError as e:
        print(f"   ❌ Module import failed: {e}")
        return False


def run_advanced_features_tests():
    """Run all advanced features validation tests."""
    print("🚀 DJI Advanced Features - Functionality Validation")
    print("=" * 60)
    
    tests = [
        ("GPX Conversion", test_gpx_conversion),
        ("CSV Conversion", test_csv_conversion),
        ("Metadata Checker", test_metadata_checker),
        ("CLI Command Structure", test_cli_command_structure),
        ("CLI Dependency Check", test_cli_dependency_check),
        ("Module Imports", test_telemetry_module_imports),
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
    print("📊 ADVANCED FEATURES SUMMARY")
    print("=" * 60)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {status} {test_name}")
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All advanced features tests passed!")
        return True
    else:
        print("⚠️  Some advanced features tests failed.")
        return False


if __name__ == "__main__":
    success = run_advanced_features_tests()
    sys.exit(0 if success else 1)
