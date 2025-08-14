#!/usr/bin/env python3
"""
Simple verification that sample fixtures are complete and properly formatted.
"""

import re
from pathlib import Path


def verify_srt_content(srt_path: Path) -> dict:
    """Verify SRT file has expected structure."""
    try:
        content = srt_path.read_text(encoding='utf-8')
        
        # Count SRT blocks (numbered entries)
        blocks = re.findall(r'^\d+$', content, re.MULTILINE)
        
        # Check for GPS coordinates
        gps_patterns = [
            r'latitude[:\s]*[-+]?\d+\.?\d*',  # [latitude: 59.0000] 
            r'longitude[:\s]*[-+]?\d+\.?\d*', # [longitude: 18.0000]
            r'GPS\([-+]?\d+\.?\d*,[-+]?\d+\.?\d*', # GPS(39.906217,116.391305,69.800)
        ]
        
        has_gps = any(re.search(pattern, content, re.IGNORECASE) for pattern in gps_patterns)
        
        # Check for timestamps
        timestamps = re.findall(r'\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}', content)
        
        return {
            "success": True,
            "blocks": len(blocks),
            "has_gps": has_gps,
            "timestamps": len(timestamps),
            "size_bytes": len(content)
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def verify_mp4_structure(mp4_path: Path) -> dict:
    """Verify MP4 file has basic structure."""
    try:
        with open(mp4_path, 'rb') as f:
            header = f.read(32)
        
        # Check for MP4 signatures
        has_ftyp = b'ftyp' in header
        has_isom = b'isom' in header
        
        size = mp4_path.stat().st_size
        
        return {
            "success": True,
            "has_ftyp": has_ftyp,
            "has_isom": has_isom,
            "size_bytes": size,
            "valid": has_ftyp and size > 100
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def verify_sample_directory(sample_dir: Path) -> dict:
    """Verify complete sample directory."""
    result = {"directory": sample_dir.name}
    
    # Check MP4
    mp4_path = sample_dir / "clip.mp4"
    result["mp4"] = verify_mp4_structure(mp4_path) if mp4_path.exists() else {"success": False, "error": "Missing"}
    
    # Check SRT
    srt_path = sample_dir / "clip.SRT" 
    result["srt"] = verify_srt_content(srt_path) if srt_path.exists() else {"success": False, "error": "Missing"}
    
    # Check DAT
    dat_path = sample_dir / "clip.DAT"
    result["has_dat"] = dat_path.exists()
    result["dat_size"] = dat_path.stat().st_size if dat_path.exists() else 0
    
    # Overall completeness
    result["complete"] = (
        result["mp4"]["success"] and result["mp4"].get("valid", False) and
        result["srt"]["success"] and result["srt"].get("has_gps", False)
    )
    
    return result


def main():
    """Main verification function."""
    print("✅ Verifying sample fixtures...")
    
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    samples_dir = project_root / "samples"
    
    if not samples_dir.exists():
        print(f"❌ Samples directory not found: {samples_dir}")
        return 1
    
    results = []
    expected_models = ["air3", "avata2", "mini4pro"]
    
    for model in expected_models:
        model_dir = samples_dir / model
        if model_dir.exists():
            results.append(verify_sample_directory(model_dir))
    
    # Print detailed results
    print(f"\n📊 Verified {len(results)} sample directories:\n")
    
    for result in results:
        name = result["directory"]
        status = "✅" if result["complete"] else "❌"
        print(f"{status} {name}/")
        
        # MP4 details
        mp4 = result["mp4"]
        if mp4["success"]:
            size = mp4.get("size_bytes", 0)
            valid = "✅" if mp4.get("valid", False) else "⚠️"
            ftyp = "✅" if mp4.get("has_ftyp", False) else "❌"
            print(f"  📹 MP4: {size} bytes, ftyp:{ftyp}, valid:{valid}")
        else:
            print(f"  ❌ MP4: {mp4.get('error', 'Failed')}")
        
        # SRT details
        srt = result["srt"] 
        if srt["success"]:
            blocks = srt.get("blocks", 0)
            gps = "✅" if srt.get("has_gps", False) else "❌" 
            timestamps = srt.get("timestamps", 0)
            print(f"  📝 SRT: {blocks} blocks, {timestamps} timestamps, GPS:{gps}")
        else:
            print(f"  ❌ SRT: {srt.get('error', 'Failed')}")
        
        # DAT details
        dat_size = result.get("dat_size", 0)
        dat_status = "✅" if result.get("has_dat", False) else "⚠️"
        print(f"  📁 DAT: {dat_status} ({dat_size} bytes)")
        
        print()
    
    # Summary
    complete_count = sum(1 for r in results if r["complete"])
    total_count = len(results)
    
    print(f"🎯 Summary: {complete_count}/{total_count} samples ready")
    
    if complete_count == total_count:
        print("🚀 All sample fixtures are complete and properly formatted!")
        return 0
    else:
        print("⚠️ Some samples need fixes")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())