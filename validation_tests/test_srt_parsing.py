"""
Test script to validate DJI SRT parsing functionality.
Tests parsing of different SRT formats and data extraction.
"""

import sys
import tempfile
from pathlib import Path

# Add the package to Python path for testing
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dji_metadata_embedder.utilities import parse_dji_srt
except ImportError as e:
    print(f"❌ Could not import DJI modules: {e}")
    print("   Try running: pip install -e .")
    sys.exit(1)


def test_sample_srt_parsing():
    """Test parsing of repo sample SRT files."""
    print("📋 Testing sample SRT parsing...")
    
    samples_dir = Path(__file__).parent.parent / "samples"
    
    if not samples_dir.exists():
        print("   ⚠️  Samples directory not found")
        return False
    
    success_count = 0
    total_count = 0
    
    for model_dir in samples_dir.iterdir():
        if not model_dir.is_dir():
            continue
            
        srt_files = list(model_dir.glob("*.SRT"))
        for srt_file in srt_files:
            total_count += 1
            print(f"   📄 Testing {model_dir.name}/{srt_file.name}")
            
            try:
                telemetry = parse_dji_srt(srt_file)
                
                # Check that we got some data
                if telemetry['gps_coords']:
                    print(f"      ✅ Found {len(telemetry['gps_coords'])} GPS points")
                    lat, lon = telemetry['gps_coords'][0]
                    print(f"      📍 First GPS: {lat:.6f}, {lon:.6f}")
                    success_count += 1
                else:
                    print("      ❌ No GPS data extracted")
                    
                if telemetry['altitudes']:
                    print(f"      🏔️  Max altitude: {max(telemetry['altitudes']):.1f}m")
                
                if telemetry['camera_info']:
                    cam = telemetry['camera_info'][0]
                    print(f"      📷 Camera: ISO {cam.get('iso', 'N/A')}, {cam.get('shutter', 'N/A')}")
                    
            except Exception as e:
                print(f"      ❌ Parsing failed: {e}")
    
    print(f"   📊 Results: {success_count}/{total_count} SRT files parsed successfully")
    return success_count > 0


def test_real_srt_parsing():
    """Test parsing of real DJI SRT files from DroneFootage directory."""
    print("\n🎬 Testing real drone footage SRT parsing...")
    
    drone_footage_dir = Path("C:/Claude/DroneFootage")
    
    if not drone_footage_dir.exists():
        print("   ⚠️  DroneFootage directory not found")
        return False
    
    srt_files = list(drone_footage_dir.glob("*.SRT"))
    
    if not srt_files:
        print("   ⚠️  No SRT files found in DroneFootage")
        return False
    
    success_count = 0
    
    for srt_file in srt_files:
        print(f"   📄 Testing {srt_file.name}")
        
        try:
            telemetry = parse_dji_srt(srt_file)
            
            # Display detailed results
            if telemetry['gps_coords']:
                print(f"      ✅ Found {len(telemetry['gps_coords'])} GPS points")
                lat, lon = telemetry['gps_coords'][0]
                print(f"      📍 First GPS: {lat:.6f}, {lon:.6f}")
                
                if telemetry['avg_gps']:
                    avg_lat, avg_lon = telemetry['avg_gps']
                    print(f"      🎯 Average GPS: {avg_lat:.6f}, {avg_lon:.6f}")
                
                success_count += 1
            else:
                print("      ❌ No GPS data extracted")
                
            if telemetry['altitudes']:
                print(f"      🏔️  Altitude range: {min(telemetry['altitudes']):.1f} - {max(telemetry['altitudes']):.1f}m")
            
            if telemetry['rel_altitudes']:
                print(f"      📏 Relative altitude: {min(telemetry['rel_altitudes']):.1f} - {max(telemetry['rel_altitudes']):.1f}m")
                
            if telemetry['camera_info']:
                cam = telemetry['camera_info'][0]
                print(f"      📷 Camera: ISO {cam.get('iso', 'N/A')}, shutter {cam.get('shutter', 'N/A')}, f/{cam.get('fnum', 'N/A')}")
            
            if telemetry['timestamps']:
                print(f"      ⏱️  Duration: {telemetry['timestamps'][0]} to {telemetry['timestamps'][-1]}")
                
        except Exception as e:
            print(f"      ❌ Parsing failed: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"   📊 Results: {success_count}/{len(srt_files)} real SRT files parsed successfully")
    return success_count > 0


def test_different_srt_formats():
    """Test parsing of different SRT format patterns."""
    print("\n🔍 Testing different SRT format patterns...")
    
    # Test Format 1: Mini 3/4 Pro format
    format1_srt = """1
00:00:00,000 --> 00:00:00,033
[latitude: 59.302335] [longitude: 18.203059] [rel_alt: 1.300 abs_alt: 132.860] [iso : 2700] [shutter : 1/30.0] [fnum : 170]

2
00:00:00,033 --> 00:00:00,066
[latitude: 59.302340] [longitude: 18.203065] [rel_alt: 1.400 abs_alt: 132.960] [iso : 2700] [shutter : 1/30.0] [fnum : 170]
"""

    # Test Format 2: Legacy GPS format
    format2_srt = """1
00:00:00,000 --> 00:00:00,033
GPS(59.302335,18.203059,132.860)

2
00:00:00,033 --> 00:00:00,066
GPS(59.302340,18.203065,132.960)
"""

    formats = [
        ("Mini 3/4 Pro Format", format1_srt),
        ("Legacy GPS Format", format2_srt),
    ]
    
    success_count = 0
    
    for format_name, srt_content in formats:
        print(f"   🧪 Testing {format_name}")
        
        try:
            # Create temporary SRT file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.SRT', delete=False) as f:
                f.write(srt_content)
                temp_srt = Path(f.name)
            
            try:
                telemetry = parse_dji_srt(temp_srt)
                
                if telemetry['gps_coords']:
                    print(f"      ✅ GPS points extracted: {len(telemetry['gps_coords'])}")
                    lat, lon = telemetry['gps_coords'][0]
                    print(f"      📍 First GPS: {lat:.6f}, {lon:.6f}")
                    success_count += 1
                else:
                    print("      ❌ No GPS data extracted")
                
                if telemetry['altitudes']:
                    print(f"      🏔️  Altitude: {telemetry['altitudes'][0]:.1f}m")
                
            finally:
                temp_srt.unlink()  # Clean up temp file
                
        except Exception as e:
            print(f"      ❌ Format test failed: {e}")
    
    print(f"   📊 Results: {success_count}/{len(formats)} formats parsed successfully")
    return success_count > 0


def test_telemetry_statistics():
    """Test calculation of telemetry statistics."""
    print("\n📈 Testing telemetry statistics calculation...")
    
    drone_footage_dir = Path("C:/Claude/DroneFootage")
    
    if not drone_footage_dir.exists():
        print("   ⚠️  Using sample data instead")
        samples_dir = Path(__file__).parent.parent / "samples" / "mini4pro"
        srt_files = list(samples_dir.glob("*.SRT")) if samples_dir.exists() else []
    else:
        srt_files = list(drone_footage_dir.glob("*.SRT"))
    
    if not srt_files:
        print("   ❌ No SRT files available for testing")
        return False
    
    for srt_file in srt_files[:1]:  # Test first file
        print(f"   📄 Analyzing {srt_file.name}")
        
        try:
            telemetry = parse_dji_srt(srt_file)
            
            # Test statistics calculation
            stats = {
                'total_gps_points': len(telemetry['gps_coords']),
                'first_gps': telemetry['first_gps'],
                'avg_gps': telemetry['avg_gps'],
                'max_altitude': telemetry['max_altitude'],
                'flight_duration': telemetry['flight_duration'],
            }
            
            print("      📊 Statistics calculated:")
            for key, value in stats.items():
                if value is not None:
                    print(f"         {key}: {value}")
            
            # Validate statistics
            if stats['total_gps_points'] > 0:
                print("      ✅ Statistics calculation successful")
                return True
            else:
                print("      ❌ No data for statistics")
                
        except Exception as e:
            print(f"      ❌ Statistics calculation failed: {e}")
    
    return False


def run_srt_parsing_tests():
    """Run all SRT parsing validation tests."""
    print("📋 DJI SRT Parsing - Functionality Validation")
    print("=" * 60)
    
    tests = [
        ("Sample SRT Parsing", test_sample_srt_parsing),
        ("Real SRT Parsing", test_real_srt_parsing),
        ("Format Compatibility", test_different_srt_formats),
        ("Statistics Calculation", test_telemetry_statistics),
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
    print("📊 SRT PARSING SUMMARY")
    print("=" * 60)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {status} {test_name}")
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All SRT parsing tests passed!")
        return True
    else:
        print("⚠️  Some SRT parsing tests failed.")
        return False


if __name__ == "__main__":
    success = run_srt_parsing_tests()
    sys.exit(0 if success else 1)
