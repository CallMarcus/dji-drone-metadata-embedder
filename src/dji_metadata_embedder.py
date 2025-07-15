import os
import re
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
import json
from typing import Dict, List, Tuple, Optional

class DJIMetadataEmbedder:
    def __init__(self, directory: str, output_dir: str = None):
        self.directory = Path(directory)
        self.output_dir = Path(output_dir) if output_dir else self.directory / "processed"
        self.output_dir.mkdir(exist_ok=True)
        
    def parse_dji_srt(self, srt_path: Path) -> Dict:
        """Parse DJI SRT file and extract telemetry data."""
        telemetry_data = {
            'gps_coords': [],
            'altitudes': [],
            'rel_altitudes': [],
            'speeds': [],
            'timestamps': [],
            'camera_info': [],
            'first_gps': None,
            'avg_gps': None,
            'max_altitude': None,
            'flight_duration': None,
            'srt_counts': [],
            'diff_times': []
        }
        
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Split into subtitle blocks
            blocks = content.strip().split('\n\n')
            
            for block in blocks:
                lines = block.strip().split('\n')
                if len(lines) >= 3:
                    # Parse timestamp
                    timestamp_line = lines[1]
                    timestamp_match = re.search(r'(\d{2}:\d{2}:\d{2},\d{3})', timestamp_line)
                    if timestamp_match:
                        telemetry_data['timestamps'].append(timestamp_match.group(1))
                    
                    # Parse telemetry data (usually in the 3rd line onward)
                    telemetry_line = ' '.join(lines[2:])

                    # Remove HTML tags if present (newer DJI format)
                    if '<font' in telemetry_line:
                        telemetry_line = re.sub(r'<[^>]+>', '', telemetry_line)

                    # Detect comprehensive format with frame counters
                    srt_cnt_match = re.search(r'SrtCnt\s*:\s*(\d+)', telemetry_line)
                    diff_time_match = re.search(r'DiffTime\s*:\s*([^\s]+)', telemetry_line)
                    if srt_cnt_match or diff_time_match:
                        telemetry_data.setdefault('srt_counts', []).append(int(srt_cnt_match.group(1)) if srt_cnt_match else None)
                        telemetry_data.setdefault('diff_times', []).append(diff_time_match.group(1) if diff_time_match else None)
                    
                    # Extract GPS coordinates - Multiple format support
                    # Format 1: [latitude: xx.xxx] [longitude: xx.xxx]
                    lat_match = re.search(r'\[latitude:\s*([+-]?\d+\.?\d*)\]', telemetry_line)
                    lon_match = re.search(r'\[longitude:\s*([+-]?\d+\.?\d*)\]', telemetry_line)
                    
                    # Format 2: GPS(lat,lon,alt)
                    if not lat_match or not lon_match:
                        gps_match = re.search(r'GPS\(([+-]?\d+\.?\d*),\s*([+-]?\d+\.?\d*),\s*([+-]?\d+\.?\d*)\)', telemetry_line)
                        if gps_match:
                            lat_match = gps_match
                            lon_match = gps_match
                            lat = float(gps_match.group(1))
                            lon = float(gps_match.group(2))
                        else:
                            lat = None
                            lon = None
                    else:
                        lat = float(lat_match.group(1))
                        lon = float(lon_match.group(1))
                    
                    if lat is not None and lon is not None:
                        telemetry_data['gps_coords'].append((lat, lon))
                    
                    # Extract altitudes - [rel_alt: x.xxx abs_alt: xxx.xxx]
                    alt_match = re.search(r'\[rel_alt:\s*([+-]?\d+\.?\d*)\s*abs_alt:\s*([+-]?\d+\.?\d*)\]', telemetry_line)
                    if alt_match:
                        rel_alt = float(alt_match.group(1))
                        abs_alt = float(alt_match.group(2))
                        telemetry_data['rel_altitudes'].append(rel_alt)
                        telemetry_data['altitudes'].append(abs_alt)
                    
                    # Extract camera info including extended fields
                    iso_match = re.search(r'\[iso\s*:\s*(\d+)\]', telemetry_line)
                    shutter_match = re.search(r'\[shutter\s*:\s*([^\]]+)\]', telemetry_line)
                    fnum_match = re.search(r'\[fnum\s*:\s*(\d+)\]', telemetry_line)
                    ev_match = re.search(r'\[ev\s*:\s*([^\]]+)\]', telemetry_line)
                    ct_match = re.search(r'\[ct\s*:\s*([^\]]+)\]', telemetry_line)
                    color_md_match = re.search(r'\[color_md\s*:\s*([^\]]+)\]', telemetry_line)
                    focal_len_match = re.search(r'\[focal_len\s*:\s*([^\]]+)\]', telemetry_line)

                    if iso_match or shutter_match or fnum_match or ev_match or ct_match or color_md_match or focal_len_match:
                        camera_data = {}
                        if iso_match:
                            camera_data['iso'] = iso_match.group(1)
                        if shutter_match:
                            camera_data['shutter'] = shutter_match.group(1)
                        if fnum_match:
                            camera_data['fnum'] = fnum_match.group(1)
                        if ev_match:
                            camera_data['ev'] = ev_match.group(1)
                        if ct_match:
                            camera_data['ct'] = ct_match.group(1)
                        if color_md_match:
                            camera_data['color_md'] = color_md_match.group(1)
                        if focal_len_match:
                            camera_data['focal_len'] = focal_len_match.group(1)

                        telemetry_data['camera_info'].append(camera_data)
            
            # Calculate summary statistics
            if telemetry_data['gps_coords']:
                telemetry_data['first_gps'] = telemetry_data['gps_coords'][0]
                avg_lat = sum(coord[0] for coord in telemetry_data['gps_coords']) / len(telemetry_data['gps_coords'])
                avg_lon = sum(coord[1] for coord in telemetry_data['gps_coords']) / len(telemetry_data['gps_coords'])
                telemetry_data['avg_gps'] = (avg_lat, avg_lon)
            
            if telemetry_data['altitudes']:
                telemetry_data['max_altitude'] = max(telemetry_data['altitudes'])
            
            if telemetry_data['rel_altitudes']:
                telemetry_data['max_rel_altitude'] = max(telemetry_data['rel_altitudes'])
            
            if telemetry_data['timestamps'] and len(telemetry_data['timestamps']) > 1:
                # Calculate flight duration
                first_time = telemetry_data['timestamps'][0].split(',')[0]
                last_time = telemetry_data['timestamps'][-1].split(',')[0]
                telemetry_data['flight_duration'] = f"{first_time} - {last_time}"
                
            # Get camera settings from first frame
            if telemetry_data['camera_info']:
                telemetry_data['camera_settings'] = telemetry_data['camera_info'][0]
                
        except Exception as e:
            print(f"Error parsing SRT file {srt_path}: {e}")
            
        return telemetry_data
    
    def embed_metadata_ffmpeg(self, video_path: Path, srt_path: Path, telemetry: Dict, output_path: Path) -> bool:
        """Embed SRT as subtitle track and add metadata using ffmpeg."""
        try:
            # Build ffmpeg command
            cmd = [
                'ffmpeg',
                '-i', str(video_path),
                '-i', str(srt_path),
                '-c', 'copy',
                '-c:s', 'mov_text',
                '-metadata:s:s:0', 'language=eng',
                '-metadata:s:s:0', 'title=Telemetry Data'
            ]
            
            # Add GPS metadata if available
            if telemetry['first_gps']:
                lat, lon = telemetry['first_gps']
                cmd.extend([
                    '-metadata', f'location={lat:+.6f}{lon:+.6f}/',
                    '-metadata', f'location-eng={lat:+.6f}{lon:+.6f}/'
                ])
            
            # Add other metadata
            if telemetry['max_altitude']:
                cmd.extend(['-metadata', f'altitude={telemetry["max_altitude"]:.1f}'])
            
            # Add creation date from filename if it matches DJI pattern
            filename_date_match = re.search(r'DJI_(\d{8})_(\d{6})', video_path.stem)
            if filename_date_match:
                date_str = filename_date_match.group(1)
                time_str = filename_date_match.group(2)
                creation_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} {time_str[:2]}:{time_str[2:4]}:{time_str[4:6]}"
                cmd.extend(['-metadata', f'creation_time={creation_date}'])
            
            # Output file
            cmd.extend(['-y', str(output_path)])
            
            # Run ffmpeg
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✓ Successfully processed: {video_path.name}")
                return True
            else:
                print(f"✗ FFmpeg error for {video_path.name}: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"✗ Error processing {video_path.name}: {e}")
            return False
    
    def embed_metadata_exiftool(self, video_path: Path, telemetry: Dict) -> bool:
        """Use exiftool to embed GPS metadata (alternative/additional method)."""
        try:
            if not telemetry['first_gps']:
                return False
                
            lat, lon = telemetry['first_gps']
            
            cmd = [
                'exiftool',
                f'-GPSLatitude={abs(lat)}',
                f'-GPSLatitudeRef={"N" if lat >= 0 else "S"}',
                f'-GPSLongitude={abs(lon)}',
                f'-GPSLongitudeRef={"E" if lon >= 0 else "W"}',
                '-overwrite_original',
                str(video_path)
            ]
            
            if telemetry['max_altitude']:
                cmd.insert(-2, f'-GPSAltitude={telemetry["max_altitude"]}')
                cmd.insert(-2, '-GPSAltitudeRef=0')  # Above sea level
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0
            
        except Exception as e:
            print(f"ExifTool error: {e}")
            return False
    
    def process_directory(self, use_exiftool: bool = False):
        """Process all MP4/SRT pairs in the directory."""
        # Find all MP4 files
        video_files = list(self.directory.glob("*.mp4")) + list(self.directory.glob("*.MP4"))
        
        if not video_files:
            print(f"No MP4 files found in {self.directory}")
            return
        
        print(f"Found {len(video_files)} video files to process")
        print(f"Output directory: {self.output_dir}\n")
        
        success_count = 0
        
        for video_path in video_files:
            # Look for corresponding SRT file
            srt_path = video_path.with_suffix('.srt')
            if not srt_path.exists():
                srt_path = video_path.with_suffix('.SRT')
            
            if not srt_path.exists():
                print(f"⚠ No SRT file found for: {video_path.name}")
                continue
            
            print(f"Processing: {video_path.name}")
            
            # Parse SRT telemetry
            telemetry = self.parse_dji_srt(srt_path)
            
            # Generate output filename
            output_path = self.output_dir / f"{video_path.stem}_metadata{video_path.suffix}"
            
            # Embed metadata using ffmpeg
            if self.embed_metadata_ffmpeg(video_path, srt_path, telemetry, output_path):
                success_count += 1
                
                # Optionally use exiftool for additional metadata
                if use_exiftool:
                    self.embed_metadata_exiftool(output_path, telemetry)
                
                # Save telemetry summary as JSON
                json_path = self.output_dir / f"{video_path.stem}_telemetry.json"
                json_data = {
                    'filename': video_path.name,
                    'first_gps': telemetry['first_gps'],
                    'average_gps': telemetry['avg_gps'],
                    'max_altitude': telemetry['max_altitude'],
                    'max_relative_altitude': telemetry.get('max_rel_altitude'),
                    'flight_duration': telemetry['flight_duration'],
                    'num_gps_points': len(telemetry['gps_coords']),
                    'camera_settings': telemetry.get('camera_settings', {})
                }
                
                with open(json_path, 'w') as f:
                    json.dump(json_data, f, indent=2)
            
            print()  # Empty line between files
        
        print(f"\nProcessing complete! Successfully processed {success_count}/{len(video_files)} videos")
        print(f"Processed files saved to: {self.output_dir}")

def check_dependencies():
    """Check if required tools are installed."""
    dependencies = {
        'ffmpeg': ['ffmpeg', '-version'],
        'exiftool': ['exiftool', '-ver']
    }
    
    missing = []
    for tool, cmd in dependencies.items():
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            print(f"✓ {tool} is installed")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"✗ {tool} is NOT installed")
            missing.append(tool)
    
    if missing:
        print("\nMissing dependencies:")
        if 'ffmpeg' in missing:
            print("- FFmpeg: Download from https://ffmpeg.org/download.html")
            print("  For Windows: Use the full build from gyan.dev or BtbN")
        if 'exiftool' in missing:
            print("- ExifTool: Download from https://exiftool.org/")
            print("  For Windows: Download the Windows Executable and add to PATH")
        return False
    return True

def main():
    parser = argparse.ArgumentParser(description='Embed DJI drone telemetry from SRT files into MP4 videos')
    parser.add_argument('directory', help='Directory containing MP4 and SRT files')
    parser.add_argument('-o', '--output', help='Output directory (default: ./processed)')
    parser.add_argument('--exiftool', action='store_true', help='Also use exiftool for GPS metadata')
    parser.add_argument('--check', action='store_true', help='Only check dependencies')
    
    args = parser.parse_args()
    
    print("DJI Drone Media Metadata Embedder\n")
    
    if args.check or not check_dependencies():
        if args.check:
            return
        print("\nPlease install missing dependencies before continuing.")
        return
    
    print()  # Empty line after dependency check
    
    embedder = DJIMetadataEmbedder(args.directory, args.output)
    embedder.process_directory(use_exiftool=args.exiftool)

if __name__ == "__main__":
    main()
