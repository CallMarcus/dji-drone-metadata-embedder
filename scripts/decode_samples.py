#!/usr/bin/env python3
"""
Decode base64-encoded sample files to create usable public fixtures for testing.

This script converts the base64-encoded sample MP4/DAT files into actual binary 
files that users can use for testing dji-embed functionality.
"""

import base64
import sys
from pathlib import Path


def decode_base64_file(input_path: Path, output_path: Path) -> bool:
    """Decode a base64 file to binary."""
    try:
        with open(input_path, 'r') as f:
            b64_content = f.read().strip()
        
        binary_content = base64.b64decode(b64_content)
        
        with open(output_path, 'wb') as f:
            f.write(binary_content)
        
        print(f"✅ Decoded {input_path.name} -> {output_path.name} ({len(binary_content)} bytes)")
        return True
        
    except Exception as e:
        print(f"❌ Failed to decode {input_path}: {e}")
        return False


def process_samples_directory(samples_dir: Path) -> int:
    """Process all sample directories and decode base64 files."""
    success_count = 0
    
    for model_dir in samples_dir.iterdir():
        if not model_dir.is_dir():
            continue
            
        print(f"\n📁 Processing {model_dir.name}/")
        
        # Look for base64 encoded files
        for b64_file in model_dir.glob("*.b64"):
            # Determine output filename (remove .b64 extension)
            output_name = b64_file.stem
            output_path = model_dir / output_name
            
            if decode_base64_file(b64_file, output_path):
                success_count += 1
    
    return success_count


def main():
    """Main entry point."""
    # Find samples directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    samples_dir = project_root / "samples"
    
    if not samples_dir.exists():
        print(f"❌ Samples directory not found: {samples_dir}")
        sys.exit(1)
    
    print("🔧 Decoding sample fixture files...")
    print(f"📍 Working in: {samples_dir}")
    
    success_count = process_samples_directory(samples_dir)
    
    print(f"\n✅ Successfully decoded {success_count} files")
    
    # Verify we have complete sample sets
    expected_models = ["air3", "avata2", "mini4pro"]
    complete_sets = 0
    
    for model in expected_models:
        model_dir = samples_dir / model
        if not model_dir.exists():
            continue
            
        has_mp4 = (model_dir / "clip.mp4").exists()
        has_srt = (model_dir / "clip.SRT").exists()
        has_dat = (model_dir / "clip.DAT").exists()
        
        if has_mp4 and has_srt:
            complete_sets += 1
            status = "✅"
            files = f"MP4 + SRT" + (" + DAT" if has_dat else "")
        else:
            status = "⚠️"
            missing = []
            if not has_mp4: missing.append("MP4")
            if not has_srt: missing.append("SRT")
            files = f"Missing: {', '.join(missing)}"
        
        print(f"{status} {model}: {files}")
    
    print(f"\n🎯 {complete_sets}/{len(expected_models)} complete sample sets ready for testing")
    
    if complete_sets == len(expected_models):
        print("🚀 All sample fixtures are ready for public use!")
        return 0
    else:
        print("⚠️  Some sample sets are incomplete")
        return 1


if __name__ == "__main__":
    sys.exit(main())