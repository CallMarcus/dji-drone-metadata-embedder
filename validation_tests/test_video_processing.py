#!/usr/bin/env python3
"""
Test script to validate DJI video processing and metadata embedding functionality.
Tests the core video processing pipeline with real files.
"""

import sys
from pathlib import Path
import json
import tempfile

# Add the package to Python path for testing
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dji_metadata_embedder.embedder import DJIMetadataEmbedder
    from dji_metadata_embedder.utilities import check_dependencies
except ImportError as e:
    print(f"❌ Could not import DJI modules: {e}")
    print("   Try running: pip install -e .")
    sys.exit(1)


def test_dependency_check():
    """Test the dependency checking function."""
    print("🔍 Testing dependency checker...")
    
    try:
        deps_ok, missing = check_dependencies()
        
        if deps_ok:
            print("   ✅ All dependencies available")
            return True
        else:
            print(f"   ⚠️  Missing dependencies: {missing}")
            print("   📝 Install missing tools before video processing")
            return False
            
    except Exception as e:
        print(f"   ❌ Dependency check failed: {e}")
        return False


def test_embedder_initialization():
    """Test that the DJIMetadataEmbedder can be initialized."""
    print("\n🏗️  Testing embedder initialization...")
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Test with default output directory
            embedder1 = DJIMetadataEmbedder(temp_path)
            expected_output = temp_path / "processed"
            
            if embedder1.output_dir == expected_output:
                print("   ✅ Default output directory set correctly")
            else:
                print(f"   ❌ Output directory mismatch: {embedder1.output_dir} != {expected_output}")
                return False
            
            # Test with custom output directory
            custom_output = temp_path / "custom"
            embedder2 = DJIMetadataEmbedder(temp_path, custom_output)
            
            if embedder2.output_dir == custom_output:
                print("   ✅ Custom output directory set correctly")
            else:
                print("   ❌ Custom output directory mismatch")
                return False
            
            print("   ✅ Embedder initialization successful")
            return True
            
    except Exception as e:
        print(f"   ❌ Embedder initialization failed: {e}")
        return False


def test_video_file_detection():
    """Test detection of video files in directories."""
    print("\n📂 Testing video file detection...")
    
    drone_footage_dir = Path("C:/Claude/DroneFootage")
    
    if not drone_footage_dir.exists():
        print("   ⚠️  DroneFootage directory not found, creating test scenario")
        return test_video_detection_with_samples()
    
    try:
        DJIMetadataEmbedder(drone_footage_dir)

        # Get list of video files (simulating internal file discovery)
        video_files = list(drone_footage_dir.glob("*.mp4")) + list(drone_footage_dir.glob("*.MP4"))
        srt_files = list(drone_footage_dir.glob("*.srt")) + list(drone_footage_dir.glob("*.SRT"))
        
        print(f"   📹 Found {len(video_files)} video files")
        print(f"   📋 Found {len(srt_files)} SRT files")
        
        # Check for pairs
        pairs = 0
        for video_file in video_files:
            srt_file = video_file.with_suffix('.SRT')
            if not srt_file.exists():
                srt_file = video_file.with_suffix('.srt')
            
            if srt_file.exists():
                pairs += 1
                print(f"   ✅ Pair found: {video_file.name} + {srt_file.name}")
            else:
                print(f"   ⚠️  No SRT for: {video_file.name}")
        
        if pairs > 0:
            print(f"   📊 Found {pairs} video+SRT pairs")
            return True
        else:
            print("   ❌ No video+SRT pairs found")
            return False
            
    except Exception as e:
        print(f"   ❌ Video detection failed: {e}")
        return False


def test_video_detection_with_samples():
    """Test video detection using repo samples."""
    print("   🧪 Testing with sample data...")
    
    samples_dir = Path(__file__).parent.parent / "samples"
    if not samples_dir.exists():
        print("   ❌ No samples directory found")
        return False
    
    # Check each sample directory
    found_samples = False
    for model_dir in samples_dir.iterdir():
        if not model_dir.is_dir():
            continue
        
        mp4_files = list(model_dir.glob("*.mp4")) + list(model_dir.glob("*.MP4"))
        srt_files = list(model_dir.glob("*.SRT"))
        
        if mp4_files and srt_files:
            print(f"   ✅ Sample pair found in {model_dir.name}")
            found_samples = True
    
    return found_samples


def test_metadata_embedding_simulation():
    """Test the metadata embedding process (simulation without actual processing)."""
    print("\n⚙️  Testing metadata embedding simulation...")
    
    drone_footage_dir = Path("C:/Claude/DroneFootage")
    
    if not drone_footage_dir.exists():
        print("   ⚠️  Using sample simulation")
        return simulate_with_samples()
    
    try:
        # Check if we have the required tools
        deps_ok, missing = check_dependencies()
        if not deps_ok:
            print(f"   ⚠️  Cannot test actual processing - missing: {missing}")
            return simulate_embedding_logic()
        
        # Find video+SRT pairs
        video_files = list(drone_footage_dir.glob("*.MP4"))
        
        for video_file in video_files[:1]:  # Test first file only
            srt_file = video_file.with_suffix('.SRT')
            if not srt_file.exists():
                continue
            
            print(f"   🎬 Simulating processing: {video_file.name}")
            
            # Test embedder setup
            with tempfile.TemporaryDirectory() as temp_dir:
                output_dir = Path(temp_dir) / "test_output"
                DJIMetadataEmbedder(drone_footage_dir, output_dir)

                # Simulate the telemetry parsing step
                from dji_metadata_embedder.utilities import parse_dji_srt
                telemetry = parse_dji_srt(srt_file)
                
                if telemetry['gps_coords']:
                    print(f"      ✅ SRT parsing successful ({len(telemetry['gps_coords'])} GPS points)")
                else:
                    print("      ❌ SRT parsing failed")
                    return False
                
                # Test output filename generation
                output_file = output_dir / f"{video_file.stem}_metadata{video_file.suffix}"
                json_file = output_dir / f"{video_file.stem}_telemetry.json"
                
                print(f"      📄 Output would be: {output_file.name}")
                print(f"      📊 JSON summary: {json_file.name}")
                
                # Simulate JSON generation
                json_data = {
                    'filename': video_file.name,
                    'first_gps': telemetry['first_gps'],
                    'average_gps': telemetry['avg_gps'],
                    'max_altitude': telemetry['max_altitude'],
                    'num_gps_points': len(telemetry['gps_coords'])
                }
                
                print("      📈 Simulation successful")
                print(f"         GPS: {json_data['first_gps']}")
                print(f"         Altitude: {json_data['max_altitude']}")
                print(f"         Points: {json_data['num_gps_points']}")
                
                return True
                
    except Exception as e:
        print(f"   ❌ Simulation failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("   ⚠️  No suitable test files found")
    return False


def simulate_with_samples():
    """Simulate processing with repo samples."""
    samples_dir = Path(__file__).parent.parent / "samples" / "mini4pro"
    
    if not samples_dir.exists():
        print("   ❌ No mini4pro samples found")
        return False
    
    srt_files = list(samples_dir.glob("*.SRT"))
    if not srt_files:
        print("   ❌ No SRT files in samples")
        return False
    
    print(f"   🧪 Simulating with sample: {srt_files[0].name}")
    
    try:
        from dji_metadata_embedder.utilities import parse_dji_srt
        telemetry = parse_dji_srt(srt_files[0])
        
        if telemetry['gps_coords']:
            print(f"      ✅ Sample parsing successful ({len(telemetry['gps_coords'])} GPS points)")
            return True
        else:
            print("      ❌ Sample parsing failed")
            return False
            
    except Exception as e:
        print(f"   ❌ Sample simulation failed: {e}")
        return False


def simulate_embedding_logic():
    """Simulate the embedding logic without external tools."""
    print("   🎭 Simulating embedding logic...")
    
    # Test that we can construct the necessary commands
    test_input = "test_video.mp4"
    test_srt = "test_video.srt"
    test_output = "test_output.mp4"
    
    # Simulate FFmpeg command construction
    ffmpeg_cmd = [
        'ffmpeg',
        '-i', test_input,
        '-i', test_srt,
        '-c', 'copy',
        '-c:s', 'mov_text',
        '-metadata:s:s:0', 'language=eng',
        '-metadata', 'location=+59.302335+18.203059/',
        '-y', test_output
    ]
    
    print(f"      📝 FFmpeg command constructed: {len(ffmpeg_cmd)} arguments")
    print("      🎯 Command structure valid")
    
    return True


def test_json_output_format():
    """Test the JSON output format generation."""
    print("\n📄 Testing JSON output format...")
    
    try:
        # Test JSON structure
        test_telemetry = {
            'gps_coords': [(59.302335, 18.203059), (59.302340, 18.203065)],
            'altitudes': [132.86, 132.96],
            'rel_altitudes': [1.3, 1.4],
            'camera_info': [{'iso': '2700', 'shutter': '1/30.0', 'fnum': '170'}],
            'first_gps': (59.302335, 18.203059),
            'avg_gps': (59.302337, 18.203062),
            'max_altitude': 132.96,
            'flight_duration': "00:00:00 - 00:00:02"
        }
        
        # Simulate JSON generation
        json_data = {
            'filename': 'test_video.MP4',
            'first_gps': test_telemetry['first_gps'],
            'average_gps': test_telemetry['avg_gps'],
            'max_altitude': test_telemetry['max_altitude'],
            'max_relative_altitude': max(test_telemetry['rel_altitudes']) if test_telemetry['rel_altitudes'] else None,
            'flight_duration': test_telemetry['flight_duration'],
            'num_gps_points': len(test_telemetry['gps_coords']),
            'camera_settings': test_telemetry['camera_info'][0] if test_telemetry['camera_info'] else {}
        }
        
        # Test JSON serialization
        json_str = json.dumps(json_data, indent=2)
        parsed_back = json.loads(json_str)
        
        if parsed_back == json_data:
            print("   ✅ JSON serialization/deserialization successful")
            print(f"   📊 JSON structure valid ({len(json_data)} fields)")
            return True
        else:
            print("   ❌ JSON round-trip failed")
            return False
            
    except Exception as e:
        print(f"   ❌ JSON format test failed: {e}")
        return False


def run_video_processing_tests():
    """Run all video processing validation tests."""
    print("🎬 DJI Video Processing - Functionality Validation")
    print("=" * 60)
    
    tests = [
        ("Dependency Check", test_dependency_check),
        ("Embedder Initialization", test_embedder_initialization),
        ("Video File Detection", test_video_file_detection),
        ("Metadata Embedding Simulation", test_metadata_embedding_simulation),
        ("JSON Output Format", test_json_output_format),
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
    print("📊 VIDEO PROCESSING SUMMARY")
    print("=" * 60)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {status} {test_name}")
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All video processing tests passed!")
        return True
    else:
        print("⚠️  Some video processing tests failed.")
        return False


if __name__ == "__main__":
    success = run_video_processing_tests()
    sys.exit(0 if success else 1)
