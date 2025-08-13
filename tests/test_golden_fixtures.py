"""Test suite using golden SRT fixtures across all DJI model families.

This test validates parser robustness across different DJI drone formats
and edge cases, implementing M3 milestone requirement #137.
"""

import pytest
from pathlib import Path
import tempfile

from src.dji_metadata_embedder.utilities import parse_telemetry_points
from src.dji_metadata_embedder.core.validator import (
    validate_srt_format, 
    normalize_telemetry_units
)
from tests.fixtures.golden_srt_samples import (
    GOLDEN_SAMPLES, 
    EDGE_CASE_SAMPLES,
    create_golden_fixtures
)


class TestGoldenFixtures:
    """Test parser against golden fixture samples."""
    
    def test_mini_3_4_pro_format(self):
        """Test Mini 3/4 Pro square bracket format parsing."""
        sample = GOLDEN_SAMPLES["mini_3_4_pro"]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.SRT', delete=False) as f:
            f.write(sample["srt_content"])
            temp_path = Path(f.name)
        
        try:
            # Test basic parsing
            points = parse_telemetry_points(temp_path)
            assert len(points) == sample["expected_points"]
            
            # Verify coordinate extraction
            for i, expected_coord in enumerate(sample["expected_coordinates"]):
                lat, lon, alt = points[i][:3]
                exp_lat, exp_lon, exp_alt = expected_coord
                assert abs(lat - exp_lat) < 0.0001
                assert abs(lon - exp_lon) < 0.0001
                assert abs(alt - exp_alt) < 0.1
            
            # Test format validation
            validation = validate_srt_format(temp_path, lenient=True)
            assert validation["valid"]
            assert validation["format_detected"] == "mini3_4pro"
            assert validation["telemetry_points"] == sample["expected_points"]
            
        finally:
            temp_path.unlink()
    
    def test_air3_html_extended_format(self):
        """Test Air 3 HTML-formatted SRT with extended telemetry."""
        sample = GOLDEN_SAMPLES["air3_html_extended"]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.SRT', delete=False) as f:
            f.write(sample["srt_content"])
            temp_path = Path(f.name)
        
        try:
            # Test parsing handles HTML tags
            points = parse_telemetry_points(temp_path)
            assert len(points) == sample["expected_points"]
            
            # Verify coordinates are extracted despite HTML formatting
            for i, expected_coord in enumerate(sample["expected_coordinates"]):
                lat, lon, alt = points[i][:3]
                exp_lat, exp_lon, exp_alt = expected_coord
                assert abs(lat - exp_lat) < 0.0001
                assert abs(lon - exp_lon) < 0.0001
                assert abs(alt - exp_alt) < 0.1
            
            # Test format detection
            validation = validate_srt_format(temp_path, lenient=True)
            assert validation["format_detected"] == "html_extended"
            
        finally:
            temp_path.unlink()
    
    def test_avata2_legacy_gps_format(self):
        """Test Avata 2 legacy GPS format with BAROMETER data."""
        sample = GOLDEN_SAMPLES["avata2_legacy_gps"]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.SRT', delete=False) as f:
            f.write(sample["srt_content"])
            temp_path = Path(f.name)
        
        try:
            # Test legacy GPS parsing
            points = parse_telemetry_points(temp_path)
            assert len(points) == sample["expected_points"]
            
            # Verify coordinate extraction from GPS() format
            for i, expected_coord in enumerate(sample["expected_coordinates"]):
                lat, lon, alt = points[i][:3]
                exp_lat, exp_lon, exp_alt = expected_coord
                assert abs(lat - exp_lat) < 0.0001
                assert abs(lon - exp_lon) < 0.0001
                assert abs(alt - exp_alt) < 0.1
            
            # Test format detection
            validation = validate_srt_format(temp_path, lenient=True)
            assert validation["format_detected"] == "legacy_gps"
            
        finally:
            temp_path.unlink()
    
    def test_mavic3_enterprise_format(self):
        """Test Mavic 3 Enterprise format with RTK and extended data."""
        sample = GOLDEN_SAMPLES["mavic3_enterprise"]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.SRT', delete=False) as f:
            f.write(sample["srt_content"])
            temp_path = Path(f.name)
        
        try:
            # Test advanced format parsing
            points = parse_telemetry_points(temp_path)
            assert len(points) == sample["expected_points"]
            
            # Verify coordinate extraction
            for i, expected_coord in enumerate(sample["expected_coordinates"]):
                lat, lon, alt = points[i][:3]
                exp_lat, exp_lon, exp_alt = expected_coord
                assert abs(lat - exp_lat) < 0.0001
                assert abs(lon - exp_lon) < 0.0001
                assert abs(alt - exp_alt) < 0.1
            
            # Test format validation recognizes extended features
            validation = validate_srt_format(temp_path, lenient=True)
            assert validation["valid"]
            
        finally:
            temp_path.unlink()


class TestLenientParserMode:
    """Test lenient parser mode with malformed inputs."""
    
    def test_missing_timestamps_lenient(self):
        """Test parser handles missing timestamps in lenient mode."""
        sample = EDGE_CASE_SAMPLES["missing_timestamps"]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.SRT', delete=False) as f:
            f.write(sample["srt_content"])
            temp_path = Path(f.name)
        
        try:
            # Lenient mode should handle gracefully
            validation = validate_srt_format(temp_path, lenient=True)
            assert validation["valid"] == sample["lenient_should_pass"]
            assert len(validation["warnings"]) > 0
            
            # Strict mode should fail
            validation_strict = validate_srt_format(temp_path, lenient=False)
            assert validation_strict["valid"] == sample["strict_should_pass"]
            
        finally:
            temp_path.unlink()
    
    def test_mixed_formats_lenient(self):
        """Test parser handles mixed telemetry formats."""
        sample = EDGE_CASE_SAMPLES["mixed_formats"]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.SRT', delete=False) as f:
            f.write(sample["srt_content"])
            temp_path = Path(f.name)
        
        try:
            # Should extract what it can in lenient mode
            points = parse_telemetry_points(temp_path)
            assert len(points) > 0  # Should get at least some points
            
            validation = validate_srt_format(temp_path, lenient=True)
            assert validation["valid"]
            assert validation["telemetry_points"] > 0
            
        finally:
            temp_path.unlink()
    
    def test_extreme_coordinates(self):
        """Test parser handles extreme coordinate values."""
        sample = EDGE_CASE_SAMPLES["extreme_coordinates"]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.SRT', delete=False) as f:
            f.write(sample["srt_content"])
            temp_path = Path(f.name)
        
        try:
            # Parse extreme coordinates
            points = parse_telemetry_points(temp_path)
            assert len(points) == sample["expected_points"]
            
            # Test unit normalization catches extreme values
            normalization = normalize_telemetry_units(points, strict=False)
            assert len(normalization["warnings"]) > 0
            assert "altitude" in str(normalization["warnings"])
            
        finally:
            temp_path.unlink()
    
    def test_unicode_content(self):
        """Test parser handles unicode characters properly."""
        sample = EDGE_CASE_SAMPLES["unicode_content"]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.SRT', delete=False, encoding='utf-8') as f:
            f.write(sample["srt_content"])
            temp_path = Path(f.name)
        
        try:
            # Should handle unicode gracefully
            points = parse_telemetry_points(temp_path)
            assert len(points) == sample["expected_points"]
            
            # Validation should work with unicode
            validation = validate_srt_format(temp_path, lenient=True)
            assert validation["valid"]
            
        finally:
            temp_path.unlink()


class TestUnitNormalization:
    """Test unit normalization and sanity checks."""
    
    def test_coordinate_sanity_checks(self):
        """Test coordinate range validation."""
        # Valid coordinates
        valid_points = [(40.7589, -73.9851, 150.5, "00:00:00")]
        result = normalize_telemetry_units(valid_points)
        assert result["issues"] == []
        assert result["normalized_count"] == 1
        
        # Invalid coordinates
        invalid_points = [(91.0, -181.0, -2000.0, "00:00:00")]  # Outside valid ranges
        result = normalize_telemetry_units(invalid_points, strict=True)
        assert len(result["issues"]) > 0
        assert "Invalid latitudes" in str(result["issues"])
        assert "Invalid longitudes" in str(result["issues"])
        assert "Invalid altitudes" in str(result["issues"])
    
    def test_altitude_change_detection(self):
        """Test detection of unrealistic altitude changes."""
        # Large altitude jump
        points = [
            (40.0, -74.0, 100.0, "00:00:00"),
            (40.0, -74.0, 300.0, "00:00:01")  # 200m jump
        ]
        result = normalize_telemetry_units(points)
        assert any("altitude changes" in str(w) for w in result["warnings"])
    
    def test_speed_calculation(self):
        """Test speed calculation and unrealistic speed detection."""
        # Realistic movement
        points = [
            (40.0000, -74.0000, 100.0, "00:00:00"),
            (40.0001, -74.0001, 100.0, "00:00:01")  # Small movement
        ]
        result = normalize_telemetry_units(points)
        assert "speed" in result["statistics"]
        assert result["statistics"]["speed"]["max_kmh"] < 100  # Reasonable speed
    
    def test_statistics_calculation(self):
        """Test that statistics are calculated correctly."""
        points = [
            (40.0, -74.0, 100.0, "00:00:00"),
            (40.1, -74.1, 200.0, "00:00:01"),
            (40.2, -74.2, 150.0, "00:00:02")
        ]
        result = normalize_telemetry_units(points)
        
        stats = result["statistics"]
        assert "latitude" in stats
        assert "longitude" in stats
        assert "altitude" in stats
        
        # Check ranges
        assert stats["latitude"]["min"] == 40.0
        assert stats["latitude"]["max"] == 40.2
        assert stats["altitude"]["range"] == 100.0  # 200 - 100


class TestComprehensiveValidation:
    """Integration tests across all formats and features."""
    
    def test_all_golden_samples(self):
        """Test all golden samples can be parsed without errors."""
        for sample_name, sample in GOLDEN_SAMPLES.items():
            with tempfile.NamedTemporaryFile(mode='w', suffix='.SRT', delete=False) as f:
                f.write(sample["srt_content"])
                temp_path = Path(f.name)
            
            try:
                # Each sample should parse successfully
                points = parse_telemetry_points(temp_path)
                assert len(points) == sample["expected_points"], f"Failed for {sample_name}"
                
                # Validation should pass
                validation = validate_srt_format(temp_path, lenient=True)
                assert validation["valid"], f"Validation failed for {sample_name}"
                
                # Unit normalization should work
                normalization = normalize_telemetry_units(points)
                assert normalization["normalized_count"] > 0, f"Normalization failed for {sample_name}"
                
            finally:
                temp_path.unlink()
    
    def test_fixture_creation(self):
        """Test that fixture creation works properly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "fixtures"
            create_golden_fixtures(output_dir)
            
            # Check that all expected directories were created
            for sample_name in GOLDEN_SAMPLES.keys():
                sample_dir = output_dir / sample_name
                assert sample_dir.exists()
                assert (sample_dir / "clip.SRT").exists()
                assert (sample_dir / "expected.json").exists()
            
            # Check edge cases directory
            edge_cases_dir = output_dir / "edge_cases"
            assert edge_cases_dir.exists()
            
            for case_name in EDGE_CASE_SAMPLES.keys():
                case_dir = edge_cases_dir / case_name
                assert case_dir.exists()
                assert (case_dir / "clip.SRT").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])