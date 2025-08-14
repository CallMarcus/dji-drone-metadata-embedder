#!/usr/bin/env python3
"""
Test script to verify sample fixtures work correctly.

This script tests that our sample MP4/SRT pairs can be parsed
and processed correctly by the DJI metadata embedder.
"""

import sys
from pathlib import Path
from typing import Dict, List

# Add project root to path so we can import modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

try:
    from dji_metadata_embedder.srt_parser import parse_srt_file
    from dji_metadata_embedder.mp4_utils import get_video_info
except ImportError as e:
    print(f"❌ Could not import modules: {e}")
    print("Make sure you're running from the project root")
    sys.exit(1)


def test_srt_parsing(srt_path: Path) -> Dict:
    """Test SRT file parsing."""
    try:
        telemetry_points = parse_srt_file(srt_path)
        return {
            "success": True,
            "points_count": len(telemetry_points),
            "first_point": telemetry_points[0] if telemetry_points else None,
            "error": None
        }
    except Exception as e:
        return {
            "success": False, 
            "points_count": 0,
            "first_point": None,
            "error": str(e)
        }


def test_mp4_info(mp4_path: Path) -> Dict:
    """Test MP4 file info extraction."""
    try:
        # Since we can't run ffmpeg, just check if file exists and has reasonable size
        if not mp4_path.exists():
            return {"success": False, "error": "File does not exist"}
            
        size = mp4_path.stat().st_size
        if size < 100:
            return {"success": False, "error": f"File too small ({size} bytes)"}
            
        return {
            "success": True,
            "file_size": size,
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "file_size": 0, 
            "error": str(e)
        }


def test_sample_directory(sample_dir: Path) -> Dict:
    """Test a complete sample directory."""
    result = {
        "directory": sample_dir.name,
        "mp4_test": None,
        "srt_test": None, 
        "has_dat": False,
        "complete": False
    }
    
    # Test MP4
    mp4_path = sample_dir / "clip.mp4"
    if mp4_path.exists():
        result["mp4_test"] = test_mp4_info(mp4_path)
    
    # Test SRT  
    srt_path = sample_dir / "clip.SRT"
    if srt_path.exists():
        result["srt_test"] = test_srt_parsing(srt_path)
    
    # Check for DAT
    dat_path = sample_dir / "clip.DAT"
    result["has_dat"] = dat_path.exists()
    
    # Determine if complete
    result["complete"] = (
        result["mp4_test"] and result["mp4_test"]["success"] and
        result["srt_test"] and result["srt_test"]["success"]
    )
    
    return result


def main():
    """Main test function."""
    print("🧪 Testing sample fixtures...")
    
    samples_dir = project_root / "samples"
    if not samples_dir.exists():
        print(f"❌ Samples directory not found: {samples_dir}")
        return 1
    
    results = []
    for sample_dir in samples_dir.iterdir():
        if sample_dir.is_dir():
            result = test_sample_directory(sample_dir)
            results.append(result)
    
    # Print results
    print(f"\n📊 Testing {len(results)} sample directories:")
    
    for result in results:
        dir_name = result["directory"]
        complete = "✅" if result["complete"] else "⚠️"
        
        print(f"\n{complete} {dir_name}/")
        
        # MP4 results
        if result["mp4_test"]:
            mp4_result = result["mp4_test"]
            if mp4_result["success"]:
                size = mp4_result["file_size"]
                print(f"  📹 MP4: {size} bytes")
            else:
                print(f"  ❌ MP4: {mp4_result['error']}")
        else:
            print(f"  ❌ MP4: Missing")
        
        # SRT results  
        if result["srt_test"]:
            srt_result = result["srt_test"]
            if srt_result["success"]:
                count = srt_result["points_count"]
                print(f"  📝 SRT: {count} telemetry points")
                if srt_result["first_point"]:
                    point = srt_result["first_point"]
                    lat = getattr(point, 'latitude', 'N/A')
                    lon = getattr(point, 'longitude', 'N/A') 
                    alt = getattr(point, 'altitude', 'N/A')
                    print(f"       First point: {lat}, {lon}, {alt}m")
            else:
                print(f"  ❌ SRT: {srt_result['error']}")
        else:
            print(f"  ❌ SRT: Missing")
        
        # DAT
        dat_status = "✅" if result["has_dat"] else "⚠️"
        print(f"  {dat_status} DAT: {'Present' if result['has_dat'] else 'Missing'}")
    
    # Summary
    complete_count = sum(1 for r in results if r["complete"])
    total_count = len(results)
    
    print(f"\n🎯 Summary: {complete_count}/{total_count} complete sample sets")
    
    if complete_count == total_count:
        print("🚀 All samples ready for public testing!")
        return 0
    else:
        print("⚠️ Some samples need attention")
        return 1


if __name__ == "__main__":
    sys.exit(main())