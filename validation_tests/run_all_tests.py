#!/usr/bin/env python3
"""
Master validation script for DJI Metadata Embedder on Windows 11.
Runs all validation tests and provides comprehensive system validation.
"""

import sys
import subprocess
import time
from pathlib import Path


def run_test_script(script_name, description):
    """Run a single test script and return results."""
    print(f"\n{'='*80}")
    print(f"🧪 RUNNING: {description}")
    print(f"📄 Script: {script_name}")
    print(f"{'='*80}")
    
    script_path = Path(__file__).parent / script_name
    
    if not script_path.exists():
        print(f"❌ Test script not found: {script_name}")
        return False, 0
    
    try:
        start_time = time.time()
        
        # Run the test script
        result = subprocess.run([sys.executable, str(script_path)], 
                              capture_output=True, text=True, timeout=300)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Print the output
        if result.stdout:
            print(result.stdout)
        
        if result.stderr:
            print("STDERR:", result.stderr)
        
        success = result.returncode == 0
        
        if success:
            print(f"\n✅ {description} - PASSED ({duration:.1f}s)")
        else:
            print(f"\n❌ {description} - FAILED ({duration:.1f}s)")
        
        return success, duration
        
    except subprocess.TimeoutExpired:
        print(f"\n⏰ {description} - TIMED OUT (>300s)")
        return False, 300
        
    except Exception as e:
        print(f"\n💥 {description} - ERROR: {e}")
        return False, 0


def print_system_info():
    """Print system information."""
    print("🖥️  SYSTEM INFORMATION")
    print("=" * 50)
    
    try:
        import platform
        print(f"   OS: {platform.system()} {platform.release()}")
        print(f"   Architecture: {platform.machine()}")
        print(f"   Python: {platform.python_version()}")
        print(f"   Python Executable: {sys.executable}")
        
        # Check Python path
        current_dir = Path(__file__).parent.parent
        print(f"   Working Directory: {current_dir}")
        
    except Exception as e:
        print(f"   ⚠️  Could not get system info: {e}")


def check_prerequisites():
    """Check basic prerequisites before running tests."""
    print("\n🔧 CHECKING PREREQUISITES")
    print("=" * 50)
    
    prerequisites_ok = True
    
    # Check Python version
    version = sys.version_info
    if version >= (3, 8):
        print(f"   ✅ Python {version.major}.{version.minor}.{version.micro}")
    else:
        print(f"   ❌ Python {version.major}.{version.minor}.{version.micro} (need 3.8+)")
        prerequisites_ok = False
    
    # Check if we're in the right directory
    current_dir = Path(__file__).parent.parent
    pyproject_file = current_dir / "pyproject.toml"
    
    if pyproject_file.exists():
        print(f"   ✅ Found pyproject.toml in {current_dir}")
    else:
        print(f"   ❌ pyproject.toml not found in {current_dir}")
        print("   📝 Make sure you're running from the dji-drone-metadata-embedder directory")
        prerequisites_ok = False
    
    # Check for test files
    drone_footage_dir = Path("C:/Claude/DroneFootage")
    samples_dir = current_dir / "samples"
    
    test_data_available = False
    
    if drone_footage_dir.exists():
        mp4_files = list(drone_footage_dir.glob("*.MP4"))
        srt_files = list(drone_footage_dir.glob("*.SRT"))
        if mp4_files and srt_files:
            print(f"   ✅ Real drone footage available ({len(mp4_files)} videos)")
            test_data_available = True
    
    if samples_dir.exists():
        for model_dir in samples_dir.iterdir():
            if model_dir.is_dir():
                srt_files = list(model_dir.glob("*.SRT"))
                if srt_files:
                    print(f"   ✅ Sample data available ({model_dir.name})")
                    test_data_available = True
                    break
    
    if not test_data_available:
        print("   ⚠️  No test data found (tests will use limited simulation)")
    
    return prerequisites_ok


def run_all_validation_tests():
    """Run all validation tests in order."""
    print("🚁 DJI METADATA EMBEDDER - COMPREHENSIVE VALIDATION")
    print("🖥️  Windows 11 - Production Readiness Test")
    print("=" * 80)
    
    # Print system info
    print_system_info()
    
    # Check prerequisites
    if not check_prerequisites():
        print("\n❌ Prerequisites check failed. Please fix issues before continuing.")
        return False
    
    # Define test suite
    test_suite = [
        ("test_installation_and_dependencies.py", "Installation & Dependencies"),
        ("test_srt_parsing.py", "SRT Parsing Functionality"),
        ("test_video_processing.py", "Video Processing Pipeline"),
        ("test_advanced_features.py", "Advanced Features"),
        ("test_integration.py", "End-to-End Integration"),
    ]
    
    print(f"\n🎯 STARTING TEST SUITE ({len(test_suite)} test categories)")
    print("=" * 80)
    
    results = {}
    total_duration = 0
    
    # Run each test
    for script_name, description in test_suite:
        success, duration = run_test_script(script_name, description)
        results[description] = success
        total_duration += duration
    
    # Print comprehensive summary
    print("\n" + "=" * 80)
    print("📊 COMPREHENSIVE VALIDATION SUMMARY")
    print("=" * 80)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {status} {test_name}")
    
    print(f"\n🎯 Overall Results: {passed}/{total} test categories passed")
    print(f"⏱️  Total Duration: {total_duration:.1f} seconds")
    
    # Final assessment
    if passed == total:
        print("\n🎉 VALIDATION COMPLETE - ALL TESTS PASSED!")
        print("✨ Your DJI Metadata Embedder installation is ready for production use.")
        print("\n📋 What's validated:")
        print("   ✅ All dependencies are properly installed")
        print("   ✅ SRT parsing works with multiple DJI formats")
        print("   ✅ Video processing pipeline is functional")
        print("   ✅ Advanced features (GPX/CSV export) work")
        print("   ✅ CLI commands are available and working")
        print("   ✅ End-to-end workflow completes successfully")
        
        print("\n🚀 Ready to use! Try processing your drone footage:")
        print("   dji-embed \"C:\\Path\\To\\Your\\DroneFootage\"")
        
        return True
        
    elif passed >= total * 0.8:  # 80% pass rate
        print("\n⚠️  VALIDATION MOSTLY SUCCESSFUL")
        print("🔧 Most functionality works, but some issues were detected.")
        print("📝 Review the failed tests above for specific issues.")
        
        if not any("Installation" in name for name, success in results.items() if not success):
            print("✅ Core functionality appears to work.")
            print("🚀 You can likely use the tool, but some advanced features may be limited.")
        
        return False
        
    else:
        print("\n❌ VALIDATION FAILED")
        print("🔧 Significant issues detected. Please address the following:")
        
        failed_tests = [name for name, success in results.items() if not success]
        for failed_test in failed_tests:
            print(f"   🔴 {failed_test}")
        
        if "Installation" in failed_tests[0]:
            print("\n📝 Start by fixing installation issues:")
            print("   1. pip install -e .")
            print("   2. Install FFmpeg (see README.md)")
            print("   3. Restart command prompt")
        
        return False


def main():
    """Main function."""
    try:
        success = run_all_validation_tests()
        
        if success:
            print("\n🏁 Testing completed successfully!")
            sys.exit(0)
        else:
            print("\n🏁 Testing completed with issues.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Testing interrupted by user.")
        sys.exit(2)
        
    except Exception as e:
        print(f"\n💥 Testing failed due to unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(3)


if __name__ == "__main__":
    main()
