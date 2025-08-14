#!/usr/bin/env python3
"""
Create minimal valid MP4 files for testing purposes.

This script creates tiny, valid MP4 files that can be used for testing
the DJI metadata embedder without requiring external dependencies.
"""

import struct
from pathlib import Path


def create_minimal_mp4(output_path: Path, duration_ms: int = 100) -> None:
    """
    Create a minimal valid MP4 file.
    
    This creates a bare-bones MP4 structure with:
    - ftyp box (file type)
    - moov box (movie header)  
    - mdat box (media data - empty)
    
    The file will be recognized as valid MP4 by most tools but contain no actual video.
    """
    with open(output_path, 'wb') as f:
        # Write ftyp box (file type)
        f.write(b'\x00\x00\x00\x20')  # box size (32 bytes)
        f.write(b'ftyp')              # box type
        f.write(b'isom')              # major brand
        f.write(b'\x00\x00\x02\x00')  # minor version
        f.write(b'isom')              # compatible brand 1
        f.write(b'iso2')              # compatible brand 2
        f.write(b'avc1')              # compatible brand 3 (AVC/H.264)
        f.write(b'mp41')              # compatible brand 4
        
        # Write moov box (movie header)
        moov_size = 108
        f.write(struct.pack('>I', moov_size))  # box size
        f.write(b'moov')                       # box type
        
        # mvhd box (movie header)
        f.write(b'\x00\x00\x00\x6C')  # mvhd box size (108 bytes)
        f.write(b'mvhd')              # box type
        f.write(b'\x00')              # version
        f.write(b'\x00\x00\x00')      # flags
        f.write(b'\x00\x00\x00\x00')  # creation time
        f.write(b'\x00\x00\x00\x00')  # modification time
        f.write(struct.pack('>I', 1000))       # timescale (1000 = 1ms resolution)
        f.write(struct.pack('>I', duration_ms))  # duration
        f.write(b'\x00\x01\x00\x00')  # rate (1.0)
        f.write(b'\x01\x00')          # volume (1.0)
        f.write(b'\x00\x00')          # reserved
        f.write(b'\x00\x00\x00\x00\x00\x00\x00\x00')  # reserved
        
        # Unity matrix
        f.write(b'\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
        f.write(b'\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00')
        f.write(b'\x00\x00\x00\x00\x00\x00\x00\x00\x40\x00\x00\x00')
        
        f.write(b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')  # pre_defined
        f.write(b'\x00\x00\x00\x00\x00\x00')  # pre_defined
        f.write(b'\x00\x00\x00\x02')          # next_track_ID
        
        # Write mdat box (media data - empty)
        f.write(b'\x00\x00\x00\x08')  # box size (8 bytes = header only)
        f.write(b'mdat')              # box type
        # No actual media data
    
    print(f"✅ Created minimal MP4: {output_path} ({output_path.stat().st_size} bytes)")


def create_all_sample_mp4s(samples_dir: Path) -> int:
    """Create MP4 files for all sample directories."""
    count = 0
    
    models = {
        "air3": 66,      # 66ms to match SRT duration  
        "avata2": 133,   # 133ms to match SRT duration
        "mini4pro": 100, # 100ms to match SRT duration
    }
    
    for model, duration in models.items():
        model_dir = samples_dir / model
        if model_dir.exists():
            mp4_path = model_dir / "clip.mp4"
            create_minimal_mp4(mp4_path, duration)
            count += 1
    
    return count


def main():
    """Main entry point."""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    samples_dir = project_root / "samples"
    
    print("🎬 Creating minimal MP4 sample files...")
    print(f"📍 Working in: {samples_dir}")
    
    if not samples_dir.exists():
        print(f"❌ Samples directory not found: {samples_dir}")
        return 1
    
    count = create_all_sample_mp4s(samples_dir)
    
    print(f"\n✅ Created {count} minimal MP4 files")
    
    # Verify sample completeness
    print("\n📋 Sample verification:")
    for model_dir in samples_dir.iterdir():
        if not model_dir.is_dir():
            continue
            
        mp4_path = model_dir / "clip.mp4"
        srt_path = model_dir / "clip.SRT"
        dat_path = model_dir / "clip.DAT"
        
        has_mp4 = mp4_path.exists()
        has_srt = srt_path.exists()
        has_dat = dat_path.exists()
        
        files = []
        if has_mp4: 
            files.append(f"MP4 ({mp4_path.stat().st_size}b)")
        if has_srt: 
            files.append("SRT")
        if has_dat: 
            files.append("DAT")
        
        status = "✅" if has_mp4 and has_srt else "⚠️"
        print(f"  {status} {model_dir.name}: {', '.join(files)}")
    
    print("\n🚀 Sample fixtures ready for public testing!")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())