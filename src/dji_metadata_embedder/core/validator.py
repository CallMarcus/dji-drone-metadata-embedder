"""Validation module for SRT/MP4 pairs and drift analysis."""

import logging
from pathlib import Path
from typing import Dict, List, Any, Tuple
import re
from datetime import datetime


logger = logging.getLogger(__name__)


class Validator:
    """Enhanced validator for files and telemetry data."""

    def is_valid(self, file_path: Path) -> bool:
        """Return True if the given path exists."""
        return Path(file_path).exists()


def parse_srt_timestamps(srt_path: Path) -> List[Tuple[float, str]]:
    """Extract timestamps from SRT file.
    
    Returns list of (timestamp_seconds, timecode_string) tuples.
    """
    content = srt_path.read_text(encoding="utf-8")
    blocks = content.strip().split("\n\n")
    timestamps = []
    
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 2:
            continue
            
        # Parse SRT timestamp line "00:00:01,000 --> 00:00:02,000"
        ts_line = lines[1]
        ts_match = re.search(r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})", ts_line)
        if ts_match:
            start_time = ts_match.group(1)
            # Convert to seconds
            h, m, s_ms = start_time.split(":")
            s, ms = s_ms.split(",")
            total_seconds = int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
            timestamps.append((total_seconds, start_time))
    
    return timestamps


def get_video_duration(mp4_path: Path) -> float:
    """Get video duration in seconds using ffprobe."""
    import subprocess
    
    try:
        cmd = [
            "ffprobe", "-v", "quiet", 
            "-show_entries", "format=duration",
            "-of", "csv=p=0", str(mp4_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        pass
    return 0.0


def analyze_drift(srt_path: Path, mp4_path: Path, threshold: float = 1.0) -> Dict[str, Any]:
    """Analyze timing drift between SRT and MP4 files."""
    analysis = {
        "srt_file": str(srt_path),
        "mp4_file": str(mp4_path),
        "valid": True,
        "issues": [],
        "warnings": [],
        "statistics": {}
    }
    
    try:
        # Get SRT timestamps
        srt_timestamps = parse_srt_timestamps(srt_path)
        if not srt_timestamps:
            analysis["valid"] = False
            analysis["issues"].append("No valid timestamps found in SRT file")
            return analysis
        
        # Get video duration
        video_duration = get_video_duration(mp4_path)
        if video_duration == 0:
            analysis["warnings"].append("Could not determine video duration")
        
        # Calculate SRT duration
        srt_duration = max(ts[0] for ts in srt_timestamps) if srt_timestamps else 0
        
        # Check for drift
        if video_duration > 0:
            duration_diff = abs(srt_duration - video_duration)
            analysis["statistics"]["video_duration"] = video_duration
            analysis["statistics"]["srt_duration"] = srt_duration
            analysis["statistics"]["duration_difference"] = duration_diff
            
            if duration_diff > threshold:
                analysis["warnings"].append(
                    f"Duration mismatch: SRT={srt_duration:.2f}s, MP4={video_duration:.2f}s "
                    f"(diff={duration_diff:.2f}s)"
                )
        
        # Check timestamp continuity
        prev_timestamp = 0
        gaps = []
        for ts, _ in srt_timestamps:
            if ts < prev_timestamp:
                analysis["issues"].append(f"Timestamp regression at {ts:.2f}s")
            elif ts - prev_timestamp > 5.0:  # Gap > 5 seconds
                gaps.append((prev_timestamp, ts, ts - prev_timestamp))
            prev_timestamp = ts
        
        if gaps:
            analysis["warnings"].append(f"Found {len(gaps)} timing gaps > 5 seconds")
            analysis["statistics"]["timing_gaps"] = gaps[:3]  # Include first 3
        
        # Check frame rate consistency
        if len(srt_timestamps) > 1:
            intervals = []
            for i in range(1, len(srt_timestamps)):
                interval = srt_timestamps[i][0] - srt_timestamps[i-1][0]
                intervals.append(interval)
            
            if intervals:
                avg_interval = sum(intervals) / len(intervals)
                max_interval = max(intervals)
                min_interval = min(intervals)
                
                analysis["statistics"]["avg_frame_interval"] = avg_interval
                analysis["statistics"]["frame_rate_consistency"] = {
                    "min_interval": min_interval,
                    "max_interval": max_interval,
                    "std_dev": (max_interval - min_interval) / 2  # Rough estimate
                }
                
                # Warn if frame intervals vary significantly
                if max_interval / min_interval > 2.0:
                    analysis["warnings"].append("Inconsistent frame intervals detected")
        
        analysis["statistics"]["total_frames"] = len(srt_timestamps)
        
    except Exception as e:
        analysis["valid"] = False
        analysis["issues"].append(f"Analysis failed: {str(e)}")
    
    return analysis


def validate_directory(directory: Path, drift_threshold: float = 1.0) -> Dict[str, Any]:
    """Validate all SRT/MP4 pairs in a directory."""
    result = {
        "directory": str(directory),
        "timestamp": datetime.now().isoformat(),
        "total_files": 0,
        "valid_pairs": 0,
        "issues": [],
        "warnings": [],
        "file_analyses": []
    }
    
    try:
        # Find MP4 files
        mp4_files = list(directory.glob("*.mp4")) + list(directory.glob("*.MP4"))
        result["total_files"] = len(mp4_files)
        
        for mp4_file in mp4_files:
            # Look for corresponding SRT
            srt_candidates = [
                mp4_file.with_suffix(".SRT"),
                mp4_file.with_suffix(".srt")
            ]
            
            srt_file = None
            for candidate in srt_candidates:
                if candidate.exists():
                    srt_file = candidate
                    break
            
            if not srt_file:
                result["issues"].append(f"No SRT file found for {mp4_file.name}")
                continue
            
            # Analyze the pair
            analysis = analyze_drift(srt_file, mp4_file, drift_threshold)
            result["file_analyses"].append(analysis)
            
            if analysis["valid"]:
                result["valid_pairs"] += 1
            
            # Aggregate issues and warnings
            result["issues"].extend([f"{mp4_file.name}: {issue}" for issue in analysis["issues"]])
            result["warnings"].extend([f"{mp4_file.name}: {warning}" for warning in analysis["warnings"]])
    
    except Exception as e:
        result["issues"].append(f"Directory validation failed: {str(e)}")
    
    return result


def validate_srt_format(srt_path: Path, lenient: bool = True) -> Dict[str, Any]:
    """Validate SRT file format and extract telemetry with warnings.
    
    This implements the lenient parser mode for M3 milestone.
    """
    validation = {
        "file": str(srt_path),
        "valid": True,
        "format_detected": "unknown",
        "issues": [],
        "warnings": [],
        "telemetry_points": 0,
        "statistics": {}
    }
    
    try:
        content = srt_path.read_text(encoding="utf-8")
        blocks = content.strip().split("\n\n")
        
        if not blocks:
            validation["valid"] = False
            validation["issues"].append("Empty SRT file")
            return validation
        
        telemetry_points = []
        format_votes = {"mini3_4pro": 0, "html_extended": 0, "legacy_gps": 0}
        
        for i, block in enumerate(blocks):
            lines = block.strip().split("\n")
            if len(lines) < 3:
                if lenient:
                    validation["warnings"].append(f"Block {i+1}: Incomplete block (expected >= 3 lines)")
                    continue
                else:
                    validation["issues"].append(f"Block {i+1}: Invalid format - too few lines")
                    continue
            
            # Check timestamp format
            ts_line = lines[1]
            if not re.search(r"\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}", ts_line):
                if lenient:
                    validation["warnings"].append(f"Block {i+1}: Invalid timestamp format")
                    continue
                else:
                    validation["issues"].append(f"Block {i+1}: Invalid timestamp format")
                    continue
            
            # Analyze telemetry line(s)
            tele_line = " ".join(lines[2:])
            
            # Detect format
            if "[latitude:" in tele_line and "[longitude:" in tele_line:
                if "<font" in tele_line:
                    format_votes["html_extended"] += 1
                else:
                    format_votes["mini3_4pro"] += 1
            elif "GPS(" in tele_line:
                format_votes["legacy_gps"] += 1
            elif lenient:
                validation["warnings"].append(f"Block {i+1}: Unrecognized telemetry format")
            else:
                validation["issues"].append(f"Block {i+1}: Invalid telemetry format")
            
            telemetry_points.append(tele_line)
        
        # Determine primary format
        if format_votes:
            validation["format_detected"] = max(format_votes, key=format_votes.get)
            validation["statistics"]["format_confidence"] = format_votes
        
        validation["telemetry_points"] = len(telemetry_points)
        validation["statistics"]["total_blocks"] = len(blocks)
        
        # Additional validation checks
        if validation["telemetry_points"] == 0:
            validation["valid"] = False
            validation["issues"].append("No valid telemetry points found")
        elif validation["telemetry_points"] < len(blocks) * 0.5:  # Less than 50% valid
            if lenient:
                validation["warnings"].append(f"Low telemetry extraction rate: {validation['telemetry_points']}/{len(blocks)}")
            else:
                validation["valid"] = False
                validation["issues"].append("Too many invalid telemetry blocks")
        
    except UnicodeDecodeError:
        validation["valid"] = False
        validation["issues"].append("File encoding error - not valid UTF-8")
    except Exception as e:
        validation["valid"] = False
        validation["issues"].append(f"Validation failed: {str(e)}")
    
    return validation


def normalize_telemetry_units(telemetry_data: List[Tuple[float, float, float, str]], strict: bool = False) -> Dict[str, Any]:
    """Normalize and validate telemetry units with sanity checks.
    
    This implements unit normalization and sanity checks for M3 milestone (#139).
    """
    result = {
        "original_count": len(telemetry_data),
        "normalized_count": 0,
        "issues": [],
        "warnings": [],
        "statistics": {},
        "normalized_data": []
    }
    
    if not telemetry_data:
        result["issues"].append("No telemetry data provided")
        return result
    
    # Extract coordinate components
    latitudes = [point[0] for point in telemetry_data]
    longitudes = [point[1] for point in telemetry_data]
    altitudes = [point[2] for point in telemetry_data]
    
    # Sanity check ranges
    lat_issues = [lat for lat in latitudes if not (-90 <= lat <= 90)]
    lon_issues = [lon for lon in longitudes if not (-180 <= lon <= 180)]
    alt_issues = [alt for alt in altitudes if not (-1000 <= alt <= 20000)]  # Reasonable altitude range
    
    if lat_issues:
        if strict:
            result["issues"].append(f"Invalid latitudes found: {len(lat_issues)} points outside [-90, 90]")
        else:
            result["warnings"].append(f"Suspicious latitudes: {len(lat_issues)} points outside normal range")
    
    if lon_issues:
        if strict:
            result["issues"].append(f"Invalid longitudes found: {len(lon_issues)} points outside [-180, 180]")
        else:
            result["warnings"].append(f"Suspicious longitudes: {len(lon_issues)} points outside normal range")
    
    if alt_issues:
        if strict:
            result["issues"].append(f"Invalid altitudes found: {len(alt_issues)} points outside [-1000, 20000]m")
        else:
            result["warnings"].append(f"Suspicious altitudes: {len(alt_issues)} points outside normal range")
    
    # Calculate statistics
    if latitudes:
        result["statistics"]["latitude"] = {
            "min": min(latitudes),
            "max": max(latitudes),
            "avg": sum(latitudes) / len(latitudes),
            "range": max(latitudes) - min(latitudes)
        }
    
    if longitudes:
        result["statistics"]["longitude"] = {
            "min": min(longitudes),
            "max": max(longitudes),
            "avg": sum(longitudes) / len(longitudes),
            "range": max(longitudes) - min(longitudes)
        }
    
    if altitudes:
        result["statistics"]["altitude"] = {
            "min": min(altitudes),
            "max": max(altitudes),
            "avg": sum(altitudes) / len(altitudes),
            "range": max(altitudes) - min(altitudes)
        }
        
        # Check for reasonable altitude changes
        if len(altitudes) > 1:
            alt_changes = []
            for i in range(1, len(altitudes)):
                change = abs(altitudes[i] - altitudes[i-1])
                alt_changes.append(change)
            
            max_change = max(alt_changes) if alt_changes else 0
            if max_change > 100:  # More than 100m change between frames
                result["warnings"].append(f"Large altitude changes detected (max: {max_change:.1f}m)")
    
    # Speed calculations (if we have timestamps)
    timestamps = [point[3] for point in telemetry_data if len(point) > 3]
    if len(timestamps) > 1 and len(latitudes) > 1:
        try:
            speeds = []
            for i in range(1, len(telemetry_data)):
                lat1, lon1, _ = latitudes[i-1], longitudes[i-1], altitudes[i-1]
                lat2, lon2, _ = latitudes[i], longitudes[i], altitudes[i]
                
                # Simple distance calculation (not geodesic, but good enough for sanity check)
                dist = ((lat2-lat1)**2 + (lon2-lon1)**2)**0.5 * 111000  # Rough conversion to meters
                
                # Time difference (assuming 30fps for now)
                time_diff = 1/30.0  # seconds
                speed = dist / time_diff if time_diff > 0 else 0
                speeds.append(speed)
            
            if speeds:
                max_speed = max(speeds)
                avg_speed = sum(speeds) / len(speeds)
                
                result["statistics"]["speed"] = {
                    "max_mps": max_speed,
                    "avg_mps": avg_speed,
                    "max_kmh": max_speed * 3.6,
                    "avg_kmh": avg_speed * 3.6
                }
                
                # Sanity check for unrealistic speeds
                if max_speed > 200:  # More than 200 m/s (720 km/h) - clearly unrealistic for drone
                    result["warnings"].append(f"Unrealistic speed detected: {max_speed*3.6:.1f} km/h")
                
        except Exception as e:
            result["warnings"].append(f"Speed calculation failed: {str(e)}")
    
    # Normalize data (for now, just copy - could implement coordinate system conversions here)
    result["normalized_data"] = telemetry_data.copy()
    result["normalized_count"] = len(result["normalized_data"])
    
    return result