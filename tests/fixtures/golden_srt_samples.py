"""Golden SRT fixture samples for comprehensive testing across DJI model families.

This module contains reference SRT samples that serve as 'golden files' for
testing parser robustness across different DJI drone models and formats.
"""

from typing import Dict, List, Any
from pathlib import Path

# Golden SRT samples for different DJI model families
GOLDEN_SAMPLES = {
    "mini_3_4_pro": {
        "description": "DJI Mini 3/4 Pro format with square bracket notation",
        "format_type": "mini3_4pro",
        "srt_content": """1
00:00:00,000 --> 00:00:00,033
[latitude: 59.0000] [longitude: 18.0000] [rel_alt: 1.0 abs_alt: 100.0] [iso : 100] [shutter : 1/30] [fnum : 170]

2
00:00:00,033 --> 00:00:00,066
[latitude: 59.0001] [longitude: 18.0001] [rel_alt: 2.0 abs_alt: 101.0] [iso : 100] [shutter : 1/30] [fnum : 170]

3
00:00:00,066 --> 00:00:00,100
[latitude: 59.0002] [longitude: 18.0002] [rel_alt: 3.0 abs_alt: 102.0] [iso : 200] [shutter : 1/60] [fnum : 170]
""",
        "expected_points": 3,
        "expected_coordinates": [
            (59.0000, 18.0000, 100.0),
            (59.0001, 18.0001, 101.0),
            (59.0002, 18.0002, 102.0)
        ],
        "expected_metadata": {
            "total_duration": 0.1,
            "frame_rate": 30,
            "has_camera_settings": True,
            "altitude_range": (100.0, 102.0)
        }
    },
    
    "air3_html_extended": {
        "description": "DJI Air 3 HTML-formatted SRT with extended telemetry",
        "format_type": "html_extended",
        "srt_content": """1
00:00:00,000 --> 00:00:00,033
<font size='36'>SrtCnt : 1, DiffTime : 33ms
2024-01-01 12:00:00,000
[iso : 100] [shutter : 1/1000] [fnum : 280] [latitude: 59.1111] [longitude: 18.2222] [rel_alt: 5.0 abs_alt: 105.0]</font>

2
00:00:00,033 --> 00:00:00,066
<font size='36'>SrtCnt : 2, DiffTime : 33ms
2024-01-01 12:00:00,033
[iso : 100] [shutter : 1/1000] [fnum : 280] [latitude: 59.1112] [longitude: 18.2223] [rel_alt: 5.1 abs_alt: 105.1]</font>

3
00:00:00,066 --> 00:00:00,100
<font size='36'>SrtCnt : 3, DiffTime : 34ms
2024-01-01 12:00:00,066
[iso : 200] [shutter : 1/2000] [fnum : 320] [latitude: 59.1113] [longitude: 18.2224] [rel_alt: 5.2 abs_alt: 105.2]</font>
""",
        "expected_points": 3,
        "expected_coordinates": [
            (59.1111, 18.2222, 105.0),
            (59.1112, 18.2223, 105.1),
            (59.1113, 18.2224, 105.2)
        ],
        "expected_metadata": {
            "total_duration": 0.1,
            "frame_rate": 30,
            "has_timestamps": True,
            "has_counter": True,
            "altitude_range": (105.0, 105.2)
        }
    },
    
    "avata2_legacy_gps": {
        "description": "DJI Avata 2 legacy GPS format with BAROMETER data",
        "format_type": "legacy_gps",
        "srt_content": """1
00:00:00,000 --> 00:00:00,033
GPS(39.906217,116.391305,69.800) BAROMETER(91.2) HOME(39.906206,116.391400)

2
00:00:00,033 --> 00:00:00,066
GPS(39.906218,116.391306,69.900) BAROMETER(91.1) HOME(39.906206,116.391400)

3
00:00:00,066 --> 00:00:00,100
GPS(39.906219,116.391307,70.000) BAROMETER(91.0) HOME(39.906206,116.391400)

4
00:00:00,100 --> 00:00:00,133
GPS(39.906220,116.391308,70.100) BAROMETER(90.9) HOME(39.906206,116.391400)
""",
        "expected_points": 4,
        "expected_coordinates": [
            (39.906217, 116.391305, 69.800),
            (39.906218, 116.391306, 69.900),
            (39.906219, 116.391307, 70.000),
            (39.906220, 116.391308, 70.100)
        ],
        "expected_metadata": {
            "total_duration": 0.133,
            "frame_rate": 30,
            "has_barometer": True,
            "has_home_point": True,
            "altitude_range": (69.8, 70.1)
        }
    },
    
    "mavic3_enterprise": {
        "description": "DJI Mavic 3 Enterprise format with RTK and extended data",
        "format_type": "mavic3_enterprise",
        "srt_content": """1
00:00:00,000 --> 00:00:00,033
<font size='36'>FrameCnt: 1, DiffTime : 33ms
[latitude: 40.7589] [longitude: -73.9851] [rel_alt: 120.0 abs_alt: 150.5] 
[iso : 100] [shutter : 1/500] [fnum : 280] [focal_len : 24.0] [rtk_flag: 50] 
[gb_yaw : 45.2] [gb_pitch : -15.0] [gb_roll : 0.5]</font>

2
00:00:00,033 --> 00:00:00,066
<font size='36'>FrameCnt: 2, DiffTime : 33ms
[latitude: 40.7590] [longitude: -73.9850] [rel_alt: 121.0 abs_alt: 151.5] 
[iso : 100] [shutter : 1/500] [fnum : 280] [focal_len : 24.0] [rtk_flag: 50] 
[gb_yaw : 46.1] [gb_pitch : -14.8] [gb_roll : 0.3]</font>

3
00:00:00,066 --> 00:00:00,100
<font size='36'>FrameCnt: 3, DiffTime : 34ms
[latitude: 40.7591] [longitude: -73.9849] [rel_alt: 122.0 abs_alt: 152.5] 
[iso : 200] [shutter : 1/1000] [fnum : 320] [focal_len : 35.0] [rtk_flag: 50] 
[gb_yaw : 47.0] [gb_pitch : -14.5] [gb_roll : 0.1]</font>
""",
        "expected_points": 3,
        "expected_coordinates": [
            (40.7589, -73.9851, 150.5),
            (40.7590, -73.9850, 151.5),
            (40.7591, -73.9849, 152.5)
        ],
        "expected_metadata": {
            "total_duration": 0.1,
            "frame_rate": 30,
            "has_rtk": True,
            "has_gimbal_data": True,
            "has_focal_length": True,
            "altitude_range": (150.5, 152.5)
        }
    }
}

# Edge cases and malformed samples for robustness testing
EDGE_CASE_SAMPLES = {
    "missing_timestamps": {
        "description": "SRT with malformed timestamp lines",
        "srt_content": """1

[latitude: 59.0000] [longitude: 18.0000] [rel_alt: 1.0 abs_alt: 100.0]

2
INVALID_TIMESTAMP
[latitude: 59.0001] [longitude: 18.0001] [rel_alt: 2.0 abs_alt: 101.0]
""",
        "expected_warnings": ["Invalid timestamp format", "Incomplete block"],
        "lenient_should_pass": True,
        "strict_should_pass": False
    },
    
    "mixed_formats": {
        "description": "SRT mixing different telemetry formats",
        "srt_content": """1
00:00:00,000 --> 00:00:00,033
[latitude: 59.0000] [longitude: 18.0000] [rel_alt: 1.0 abs_alt: 100.0]

2
00:00:00,033 --> 00:00:00,066
GPS(39.906217,116.391305,69.800) BAROMETER(91.2)

3
00:00:00,066 --> 00:00:00,100
<font>SrtCnt : 3 [latitude: 60.0000] [longitude: 19.0000]</font>
""",
        "expected_warnings": ["Mixed telemetry formats detected"],
        "expected_points": 3,
        "lenient_should_pass": True
    },
    
    "extreme_coordinates": {
        "description": "SRT with coordinates at extreme ranges",
        "srt_content": """1
00:00:00,000 --> 00:00:00,033
[latitude: 89.9999] [longitude: 179.9999] [rel_alt: 8848.0 abs_alt: 8848.0]

2
00:00:00,033 --> 00:00:00,066
[latitude: -89.9999] [longitude: -179.9999] [rel_alt: -400.0 abs_alt: -400.0]
""",
        "expected_warnings": ["Extreme coordinate values", "Large altitude changes"],
        "expected_points": 2,
        "lenient_should_pass": True
    },
    
    "unicode_content": {
        "description": "SRT with unicode characters and special formatting",
        "srt_content": """1
00:00:00,000 --> 00:00:00,033
🚁 [latitude: 59.0000] [longitude: 18.0000] [rel_alt: 1.0 abs_alt: 100.0] ✈️

2
00:00:00,033 --> 00:00:00,066
ПИЛОТ: [latitude: 59.0001] [longitude: 18.0001] [rel_alt: 2.0 abs_alt: 101.0]
""",
        "expected_points": 2,
        "expected_warnings": ["Non-ASCII characters in telemetry"],
        "lenient_should_pass": True
    }
}


def create_golden_fixtures(output_dir: Path) -> None:
    """Create all golden fixture files in the specified directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create standard samples
    for name, sample in GOLDEN_SAMPLES.items():
        sample_dir = output_dir / name
        sample_dir.mkdir(exist_ok=True)
        
        # Write SRT file
        srt_file = sample_dir / "clip.SRT"
        srt_file.write_text(sample["srt_content"], encoding="utf-8")
        
        # Write metadata JSON for testing
        metadata_file = sample_dir / "expected.json"
        import json
        metadata_file.write_text(json.dumps({
            "description": sample["description"],
            "format_type": sample["format_type"],
            "expected_points": sample["expected_points"],
            "expected_coordinates": sample["expected_coordinates"],
            "expected_metadata": sample["expected_metadata"]
        }, indent=2), encoding="utf-8")
    
    # Create edge case samples
    edge_cases_dir = output_dir / "edge_cases"
    edge_cases_dir.mkdir(exist_ok=True)
    
    for name, sample in EDGE_CASE_SAMPLES.items():
        case_dir = edge_cases_dir / name
        case_dir.mkdir(exist_ok=True)
        
        srt_file = case_dir / "clip.SRT"
        srt_file.write_text(sample["srt_content"], encoding="utf-8")
        
        metadata_file = case_dir / "expected.json"
        import json
        metadata_file.write_text(json.dumps({
            "description": sample["description"],
            "expected_warnings": sample.get("expected_warnings", []),
            "expected_points": sample.get("expected_points", 0),
            "lenient_should_pass": sample.get("lenient_should_pass", True),
            "strict_should_pass": sample.get("strict_should_pass", False)
        }, indent=2), encoding="utf-8")


def get_sample_by_name(sample_name: str) -> Dict[str, Any]:
    """Get a specific golden sample by name."""
    if sample_name in GOLDEN_SAMPLES:
        return GOLDEN_SAMPLES[sample_name]
    elif sample_name in EDGE_CASE_SAMPLES:
        return EDGE_CASE_SAMPLES[sample_name]
    else:
        raise ValueError(f"Unknown sample: {sample_name}")


def list_available_samples() -> List[str]:
    """List all available sample names."""
    return list(GOLDEN_SAMPLES.keys()) + list(EDGE_CASE_SAMPLES.keys())


def validate_sample_parsing(sample_name: str, parser_func) -> Dict[str, Any]:
    """Validate that a parser function correctly handles a golden sample."""
    sample = get_sample_by_name(sample_name)
    
    # Create temporary SRT file
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.SRT', delete=False) as f:
        f.write(sample["srt_content"])
        temp_path = Path(f.name)
    
    try:
        # Run parser
        result = parser_func(temp_path)
        
        # Validate results against expectations
        validation_result = {
            "sample_name": sample_name,
            "parser_result": result,
            "validation_passed": True,
            "validation_errors": []
        }
        
        # Check expected points count
        if "expected_points" in sample:
            expected_count = sample["expected_points"]
            if isinstance(result, list):
                actual_count = len(result)
            elif isinstance(result, dict) and "telemetry_points" in result:
                actual_count = result["telemetry_points"]
            else:
                actual_count = 0
            
            if actual_count != expected_count:
                validation_result["validation_passed"] = False
                validation_result["validation_errors"].append(
                    f"Point count mismatch: expected {expected_count}, got {actual_count}"
                )
        
        return validation_result
        
    finally:
        # Clean up temp file
        temp_path.unlink()