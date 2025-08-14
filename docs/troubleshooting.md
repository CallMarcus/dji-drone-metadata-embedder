# Troubleshooting

Comprehensive solutions to issues encountered when running `dji-embed`, organized by category.

---

## 🚀 Quick Diagnostics

**Start here if you're having issues:**

```bash
# Run system diagnostics
dji-embed doctor

# Check your files  
dji-embed check /path/to/your/files

# Validate video/subtitle sync
dji-embed validate /path/to/your/files
```

---

## 📦 Installation Issues

### "ffmpeg is not recognized"

The program requires FFmpeg to be installed and available on your `PATH`.

**Verify Installation:**
```bash
ffmpeg -version  # Single dash - correct
ffmpeg --version # Double dash - will show error
```

**Solutions by Platform:**

**Windows:**
```powershell
# Use the bootstrap installer (recommended)
iwr -useb https://raw.githubusercontent.com/CallMarcus/dji-drone-metadata-embedder/master/tools/bootstrap.ps1 | iex

# Or manual install from gyan.dev
# Download from https://www.gyan.dev/ffmpeg/builds/
# Add the 'bin' folder to your PATH
```

**macOS:**
```bash
# Using Homebrew
brew install ffmpeg

# Using MacPorts  
sudo port install ffmpeg
```

**Linux:**
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# RHEL/CentOS/Fedora
sudo dnf install ffmpeg
```

### "exiftool is not recognized"

ExifTool is optional but needed for the `--exiftool` flag.

**Windows:**
```powershell
# Bootstrap installer includes ExifTool
iwr -useb https://raw.githubusercontent.com/CallMarcus/dji-drone-metadata-embedder/master/tools/bootstrap.ps1 | iex
```

**Manual Install:**
- Download from [exiftool.org](https://exiftool.org/)
- Rename executable to `exiftool.exe` 
- Add to your `PATH`

### "Could not find ...exiftool_files/perl5*.dll"

The `exiftool_files` directory wasn't copied alongside `exiftool.exe`.

**Fix:**
```bash
# Delete incomplete installation
rm -rf ~/AppData/Local/dji-embed/bin  # Windows
rm -rf ~/.local/bin/dji-embed         # Linux/macOS

# Re-run bootstrap installer
iwr -useb https://raw.githubusercontent.com/CallMarcus/dji-drone-metadata-embedder/master/tools/bootstrap.ps1 | iex
```

### "python was not found"

**Windows:**
```cmd
# Use 'py' instead of 'python'
py -m pip install dji-drone-metadata-embedder
dji-embed --help

# Or install Python from python.org
```

### Permission Errors

**Solutions:**
```bash
# Use different output directory
dji-embed embed /drone/footage -o ~/Desktop/processed

# Run with elevated privileges (Windows)
# Right-click PowerShell → "Run as Administrator"

# Fix permissions (Linux/macOS)
sudo chmod -R 755 /path/to/output/directory
```

---

## 🎥 File Format Issues

### No MP4/SRT Pairs Found

**Check File Naming:**
```bash
# Correct naming patterns:
DJI_0001.MP4 + DJI_0001.SRT
DJI_0001.mp4 + DJI_0001.srt  
DJI_20240301_142355_001.MP4 + DJI_20240301_142355_001.SRT

# Verify your files
ls /drone/footage/
dji-embed check /drone/footage/
```

**Common Naming Issues:**
- Missing leading zeros: `DJI_1.MP4` → `DJI_0001.MP4`
- Case mismatch: `DJI_0001.mp4` + `DJI_0001.SRT` ✅ (works)
- Wrong extensions: `.mov`, `.mkv` → Convert to `.mp4`
- Spaces in names: `DJI 0001.MP4` → `DJI_0001.MP4`

### Codec Compatibility Issues

**Problem:** "Unsupported video codec" or encoding failures

**Check Video Codec:**
```bash
ffprobe -v quiet -show_streams /path/to/video.mp4

# Look for:
# codec_name=h264    # ✅ Supported
# codec_name=h265    # ⚠️ May have issues  
# codec_name=prores  # ❌ Unsupported for embedding
```

**Solutions:**
```bash
# Convert to H.264 if needed
ffmpeg -i input.mp4 -c:v libx264 -c:a aac -crf 18 output.mp4

# Then process with dji-embed
dji-embed embed /path/to/converted/
```

**Supported Codecs:**
- ✅ **H.264/AVC**: Primary support, all features
- ⚠️ **H.265/HEVC**: Basic support, may have embedding issues
- ❌ **ProRes/DNxHD**: Not supported for metadata embedding
- ❌ **VP9/AV1**: Not supported

---

## 📊 DJI Model-Specific Issues

### Mini 3/4 Pro Issues

**Format:** `[latitude: 59.123456] [longitude: 18.123456]`

**Common Problems:**
```bash
# Missing GPS data in newer firmware
# Check SRT content:
head -20 DJI_0001.SRT

# Should contain GPS coordinates, not just camera settings
```

**Solutions:**
- Enable "Subtitle" in DJI Fly app settings
- Update to latest DJI Fly app version
- Check that GPS was acquired before takeoff

### Air 3 Issues  

**Format:** HTML-style with extended data

**Common Problems:**
- HTML tags interfering with parsing
- Extended telemetry causing slow processing

**Solutions:**
```bash
# Use lenient parsing mode (default in v1.1.0+)
dji-embed embed /footage --verbose

# Check format detection
dji-embed validate /footage --format json
```

### Avata 2 Issues

**Format:** `GPS(lat,lon,alt)` with BAROMETER data

**Common Problems:**
- Legacy format not recognized
- Mixed GPS and barometer altitude readings

**Solutions:**
```bash
# Verify format detection
dji-embed check DJI_0001.SRT

# Should show: "✅ Legacy GPS format detected"
```

### Mavic 3 Enterprise Issues

**Format:** Extended format with RTK data

**Common Problems:**
- RTK precision causing coordinate overflow
- Professional features not recognized

**Solutions:**
```bash
# Use professional workflow
dji-embed embed /footage --exiftool --dat-auto

# Check for extended features
dji-embed validate /footage --drift-threshold 0.1
```

---

## ⏰ Timing & Synchronization Issues

### VFR (Variable Frame Rate) Drift

**Problem:** Video and subtitle timing gets progressively out of sync

**Symptoms:**
```bash
# Run validation to detect drift
dji-embed validate /footage

# Look for warnings like:
# "Duration mismatch: SRT=180.5s, MP4=181.2s (diff=0.7s)"
# "Inconsistent frame intervals detected"
```

**Causes:**
- DJI drones record VFR video (variable frame rate)
- SRT assumes constant 30fps
- Long flights accumulate timing drift

**Solutions:**
```bash
# Check video frame rate pattern
ffprobe -v quiet -show_streams video.mp4 | grep -E "(r_frame_rate|avg_frame_rate)"

# For severe drift, try manual time offset
dji-embed embed /footage --time-offset 0.5  # Adjust timing by 0.5s

# Alternative: Use ffmpeg to fix frame rate first
ffmpeg -i input.mp4 -r 30 -c:v libx264 -crf 18 output.mp4
```

### Frame Rate Mismatches

**Common Frame Rates:**
- ✅ **30fps**: Standard, best compatibility
- ⚠️ **24fps**: Cinema mode, may cause drift
- ⚠️ **60fps**: High frame rate, subtitle timing issues
- ❌ **Variable**: Causes progressive drift

**Fix Frame Rate Issues:**
```bash
# Check current frame rate
ffprobe -v quiet -show_streams video.mp4 | grep r_frame_rate

# Convert to constant 30fps
ffmpeg -i input.mp4 -r 30 -c:v libx264 -preset medium -crf 20 output.mp4
```

### Long Flight Drift

**Problem:** Timing drift increases over long flights (>10 minutes)

**Solutions:**
1. **Split long flights:**
   ```bash
   # Split video at 10-minute intervals
   ffmpeg -i long_flight.mp4 -c copy -t 600 part1.mp4
   ffmpeg -i long_flight.mp4 -c copy -ss 600 -t 600 part2.mp4
   
   # Split corresponding SRT files manually
   # Process each part separately
   ```

2. **Use time offset compensation:**
   ```bash
   # For each segment, adjust timing
   dji-embed embed part1/ --time-offset 0.0
   dji-embed embed part2/ --time-offset -0.5
   ```

---

## 📈 Performance Issues

### Slow Processing

**Symptoms:** Processing takes much longer than expected

**Diagnosis:**
```bash
# Enable verbose logging
dji-embed embed /footage --verbose

# Monitor system resources while processing
```

**Common Causes & Solutions:**

1. **Large video files:**
   ```bash
   # Process to faster storage
   dji-embed embed /footage -o /tmp/fast_output
   
   # Reduce console output
   dji-embed embed /footage --quiet
   ```

2. **Network storage:**
   ```bash
   # Copy files locally first
   cp -r /network/footage /local/temp/
   dji-embed embed /local/temp/ -o /local/output/
   ```

3. **Insufficient RAM:**
   ```bash
   # Process files individually instead of batch
   for file in *.mp4; do
     dji-embed embed "$file" --quiet
   done
   ```

### Memory Issues

**Error:** "Memory error" or system freezing

**Solutions:**
```bash
# Check available memory
free -h  # Linux
Get-ComputerInfo | Select TotalPhysicalMemory, AvailablePhysicalMemory  # Windows

# Process smaller batches
find /footage -name "*.mp4" | head -5 | xargs -I {} dji-embed embed {}
```

---

## 🔍 Data Quality Issues

### Missing GPS Data

**Problem:** No GPS coordinates in output JSON files

**Diagnosis:**
```bash
# Check SRT content
head -50 DJI_0001.SRT

# Should contain GPS coordinates like:
# [latitude: 59.123456] [longitude: 18.123456]
# or GPS(59.123456,18.123456,150.5)
```

**Solutions:**
1. **Enable GPS logging in DJI Fly:**
   - Settings → Camera → Subtitles → Enable
   - Ensure GPS lock before takeoff
   - Wait for "GPS Ready" status

2. **Check SRT format:**
   ```bash
   # Validate SRT format
   dji-embed validate /footage --format json
   
   # Look for format_detected field
   ```

### Altitude Discrepancies  

**Problem:** Altitude readings don't match expectations

**Understanding DJI Altitudes:**
- **Relative Altitude (`rel_alt`)**: Height above takeoff point
- **Absolute Altitude (`abs_alt`)**: Height above sea level
- **Barometric**: Based on air pressure (can drift)
- **GPS**: Based on GPS elevation (less accurate)

**Check Altitude Sources:**
```bash
# Review JSON output
cat processed/DJI_0001_telemetry.json | jq '.max_altitude'

# Compare with SRT data
grep -E "(rel_alt|abs_alt)" DJI_0001.SRT | head -5
```

### Camera Settings Missing

**Problem:** No camera metadata (ISO, shutter speed, f-number)

**Solutions:**
```bash
# Ensure extended metadata extraction
dji-embed embed /footage --exiftool

# Check SRT format supports camera data
grep -E "(iso|shutter|fnum)" DJI_0001.SRT | head -3
```

---

## 🐛 Advanced Troubleshooting

### Debug Mode

**Enable maximum logging:**
```bash
# Full debug output
dji-embed embed /footage --verbose --log-json > debug.log 2>&1

# Review debug log
less debug.log
```

### File Corruption

**Check file integrity:**
```bash
# Test video file
ffmpeg -v error -i video.mp4 -f null - 2>error.log
cat error.log

# Test SRT encoding
file -bi DJI_0001.SRT
# Should show: text/plain; charset=utf-8
```

### Edge Cases

**Very old DJI models:**
```bash
# Try legacy format detection
dji-embed validate /footage --format json | jq '.format_detected'

# Manual format verification
head -100 DJI_0001.SRT | grep -E "(GPS|latitude|longitude)"
```

**Mixed recording sessions:**
```bash
# Process different formats separately  
find /footage -name "*Mini*" -exec dji-embed embed {} \;
find /footage -name "*Mavic*" -exec dji-embed embed {} \;
```

---

## 📞 Getting More Help

### Before Asking for Help

1. **Run diagnostics:**
   ```bash
   dji-embed doctor > diagnostics.txt
   dji-embed validate /footage --format json > validation.txt
   ```

2. **Check versions:**
   ```bash
   dji-embed --version
   ffmpeg -version | head -1
   exiftool -ver 2>/dev/null || echo "ExifTool not found"
   ```

3. **Provide sample files** (with GPS redacted if needed):
   ```bash
   # Redact GPS from sample SRT
   dji-embed embed sample/ --redact drop -o safe_sample/
   ```

### Support Channels

- **GitHub Issues**: [Report bugs and feature requests](https://github.com/CallMarcus/dji-drone-metadata-embedder/issues)
- **Documentation**: Check [decision table](decision-table.md) and [recipes](recipes.md)
- **Community**: Share experiences and solutions with other users

### Information to Include

When reporting issues, include:
- Output of `dji-embed doctor`
- Your operating system and version  
- DJI drone model and firmware version
- Sample SRT file (with GPS redacted if needed)
- Complete error messages
- What you expected vs. what happened

---

*Still having issues? Check the [decision table](decision-table.md) for guidance on which path to take, or review the [recipes](recipes.md) for complete workflows.*
