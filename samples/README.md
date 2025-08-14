# Sample Test Fixtures

This directory contains tiny sample MP4/SRT/DAT files for testing `dji-embed` functionality without needing your own drone footage.

## 📁 Available Samples

Each directory contains a complete set of test files:

### `air3/` - DJI Air 3 Format
- **Format**: HTML-style SRT with extended telemetry
- **Features**: Timestamps, counters, rich camera metadata  
- **Duration**: ~66ms (2 frames at 30fps)
- **GPS**: Stockholm, Sweden area (redacted coordinates)

### `avata2/` - DJI Avata 2 Format  
- **Format**: Legacy GPS format with BAROMETER data
- **Features**: GPS coordinates, barometer readings, home point
- **Duration**: ~133ms (4 frames at 30fps)
- **GPS**: Beijing, China area (redacted coordinates)

### `mini4pro/` - DJI Mini 3/4 Pro Format
- **Format**: Square bracket notation (most common)
- **Features**: GPS, altitude, camera settings (ISO, shutter, f-number)
- **Duration**: ~100ms (3 frames at 30fps)  
- **GPS**: Stockholm, Sweden area (redacted coordinates)

## 🧪 Testing Commands

### Basic Processing
```bash
# Process Air 3 samples
dji-embed embed samples/air3/

# Process all samples
dji-embed embed samples/ -o test_output/
```

### Validate Samples
```bash  
# Check what metadata is detected
dji-embed check samples/air3/

# Validate timing and file structure
dji-embed validate samples/
```

### Export GPS Tracks
```bash
# Create GPX files
dji-embed convert gpx samples/air3/clip.SRT
dji-embed convert gpx samples/ --batch

# Create CSV files  
dji-embed convert csv samples/mini4pro/clip.SRT -o flight_data.csv
```

### System Diagnostics
```bash
# Verify your installation works
dji-embed doctor

# Test with sample files
dji-embed embed samples/mini4pro/ --verbose
```

## 🗂️ File Structure

Each sample directory contains:
- `clip.mp4` - Minimal valid MP4 file (150 bytes)
- `clip.SRT` - Real DJI telemetry subtitle file  
- `clip.DAT` - Minimal DAT flight log file (45 bytes)
- `processed/` - Output directory (created after processing)

## 🔒 Privacy & Redaction Testing

These samples use redacted GPS coordinates that are safe for public distribution:
- **Stockholm area**: `59.xxxx, 18.xxxx`  
- **Beijing area**: `39.xxxx, 116.xxxx`

Test privacy features:
```bash
# Remove GPS data completely
dji-embed embed samples/ --redact drop -o safe_output/

# Fuzzy GPS coordinates  
dji-embed embed samples/ --redact fuzz -o fuzzy_output/
```

## 📊 Expected Results

After processing, you should see:
- `*_metadata.mp4` - Original video with embedded telemetry
- `*_telemetry.json` - Flight summary with GPS track and statistics
- Subtitle tracks embedded for compatible players

**Air 3 JSON example:**
```json
{
  "total_duration": 0.066,
  "total_distance": 0.0,
  "max_altitude": 105.1,
  "min_altitude": 105.0,
  "telemetry_points": 2,
  "has_camera_settings": true,
  "format_detected": "html_extended"
}
```

## 🐛 Troubleshooting

If processing fails:
1. Run `dji-embed doctor` to check dependencies
2. Verify file permissions: `ls -la samples/air3/`  
3. Check for detailed errors: `dji-embed embed samples/air3/ --verbose`

**Common Issues:**
- "FFmpeg not found" → Install FFmpeg first
- "No MP4/SRT pairs found" → Check file naming matches `clip.mp4` + `clip.SRT`
- "Permission denied" → Ensure write access to output directory

## 🎯 Integration Testing

These samples are perfect for:
- **CI/CD pipelines** - Automated testing without large files
- **Installation verification** - Quick smoke tests
- **Development** - Test parser changes across formats  
- **Documentation examples** - Show expected behavior
- **Bug reproduction** - Minimal test cases

## 📝 Creating Your Own

Want to create similar samples from your footage?

```bash
# Extract first 3 seconds and redact GPS
dji-embed embed /your/footage/ --redact fuzz -o samples/custom/

# Trim SRT to match
head -20 your_flight.SRT > samples/custom/clip.SRT

# Trim MP4 to match  
ffmpeg -i your_video.mp4 -t 3 -c copy samples/custom/clip.mp4
```

---

*These samples demonstrate all major DJI telemetry formats while remaining tiny and privacy-safe for public distribution.*