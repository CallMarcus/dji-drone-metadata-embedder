# Decision Table: Which Path Do I Take?

This guide helps you choose the right command and approach for your specific use case with DJI Metadata Embedder.

## Quick Decision Tree

### 🎯 **What do you want to do?**

| **Goal** | **Command** | **When to Use** |
|----------|-------------|-----------------|
| **Process videos with telemetry** | `dji-embed embed` | You have MP4/SRT pairs and want embedded metadata |
| **Just export GPS tracks** | `dji-embed convert` | You only need GPX/CSV files, not embedded videos |
| **Check what's already there** | `dji-embed check` | Verify if videos already have metadata |
| **Validate file quality** | `dji-embed validate` | Check for timing drift or file issues |
| **System diagnostics** | `dji-embed doctor` | Troubleshoot installation or dependencies |

---

## 📋 Detailed Decision Matrix

### For Video Processing (`dji-embed embed`)

| **If you have...** | **And you want...** | **Use this command** |
|--------------------|---------------------|----------------------|
| MP4 + SRT files | Basic embedded metadata | `dji-embed embed /path/to/videos` |
| MP4 + SRT files | Custom output location | `dji-embed embed /path/to/videos -o /output/dir` |
| MP4 + SRT + DAT files | Enhanced telemetry data | `dji-embed embed /path/to/videos --dat /path/to/flight.DAT` |
| Multiple videos with DAT files | Auto-detect DAT files | `dji-embed embed /path/to/videos --dat-auto` |
| Privacy concerns | Remove GPS coordinates | `dji-embed embed /path/to/videos --redact drop` |
| Privacy concerns | Fuzzy GPS coordinates | `dji-embed embed /path/to/videos --redact fuzz` |
| ExifTool installed | Maximum metadata compatibility | `dji-embed embed /path/to/videos --exiftool` |

### For Data Export (`dji-embed convert`)

| **Input** | **Output Format** | **Command** |
|-----------|------------------|-------------|
| Single SRT file | GPX track | `dji-embed convert gpx /path/to/file.SRT` |
| Single SRT file | CSV data | `dji-embed convert csv /path/to/file.SRT` |
| Directory of SRT files | Multiple GPX files | `dji-embed convert gpx /path/to/srt/dir --batch` |
| Directory of SRT files | Multiple CSV files | `dji-embed convert csv /path/to/srt/dir --batch` |
| Custom output filename | Specific output file | `dji-embed convert gpx input.SRT -o custom.gpx` |

### For Analysis and Validation

| **Purpose** | **Command** | **Use Case** |
|-------------|-------------|--------------|
| Check existing metadata | `dji-embed check /path/to/files` | See what's already embedded |
| Validate SRT/MP4 sync | `dji-embed validate /path/to/videos` | Check for timing drift issues |
| System diagnostics | `dji-embed doctor` | Troubleshoot installation problems |
| Version information | `dji-embed --version` | Check tool and dependency versions |

---

## 🎛️ Common Options Explained

### Output Control
- `-o, --output DIR` - Specify where processed files go (default: `./processed/`)
- `-q, --quiet` - Reduce console output (good for scripting)
- `-v, --verbose` - Show detailed processing information

### Privacy & Redaction
- `--redact none` - Keep all GPS data (default)
- `--redact fuzz` - Round GPS coordinates to ~100m precision
- `--redact drop` - Remove all GPS data completely

### Advanced Options
- `--exiftool` - Use ExifTool for additional metadata formats
- `--dat FILE` - Include specific DAT flight log data
- `--dat-auto` - Automatically find matching DAT files
- `--log-json` - Machine-readable JSON output for automation

---

## 🗺️ Workflow Examples

### **Scenario 1: Basic Processing**
```bash
# I have DJI_0001.MP4 and DJI_0001.SRT, want embedded video
dji-embed embed /drone/footage/
```

### **Scenario 2: Privacy-Conscious Processing**
```bash
# Process videos but remove GPS for public sharing
dji-embed embed /drone/footage/ --redact drop -o /safe/outputs/
```

### **Scenario 3: GPS Track Only**
```bash
# I just want a GPX file for Google Earth
dji-embed convert gpx /drone/footage/DJI_0001.SRT
```

### **Scenario 4: Batch Processing with DAT**
```bash
# Process multiple videos with flight logs
dji-embed embed /drone/session/ --dat-auto --exiftool -o /processed/
```

### **Scenario 5: Quality Check**
```bash
# Check if my videos already have metadata
dji-embed check /drone/footage/
# Validate timing sync between video and telemetry
dji-embed validate /drone/footage/
```

### **Scenario 6: Troubleshooting**
```bash
# Installation not working?
dji-embed doctor
# Check versions
dji-embed --version
```

---

## 📱 DJI Model Compatibility

| **DJI Model** | **SRT Format** | **Compatibility** | **Notes** |
|---------------|----------------|-------------------|-----------|
| **Mini 3/4 Pro** | `[latitude: X] [longitude: Y]` | ✅ Fully supported | Most common format |
| **Air 3** | HTML-style with extended data | ✅ Fully supported | Rich telemetry data |
| **Avata 2** | `GPS(lat,lon,alt)` legacy format | ✅ Fully supported | BAROMETER data included |
| **Mavic 3 Enterprise** | Extended format with RTK | ✅ Fully supported | Professional features |
| **Other models** | Various formats | ⚠️ May work | Use `validate` command first |

---

## ❓ Still Not Sure?

### Quick Questions:
1. **Do you have video files?** 
   - Yes → Use `embed` or `check`
   - No, just SRT → Use `convert`

2. **Is this your first time?**
   - Yes → Run `dji-embed doctor` first
   - No → Continue with your workflow

3. **Having problems?**
   - Installation issues → `dji-embed doctor`
   - File issues → `dji-embed validate`
   - Unknown metadata → `dji-embed check`

4. **Need automation?**
   - Add `--log-json` to any command
   - Use `--quiet` for scripting
   - Check exit codes for success/failure

### Get More Help:
- **Full CLI reference**: See README.md
- **Troubleshooting**: See docs/troubleshooting.md  
- **How-to guides**: See docs/how-to/
- **File formats**: See docs/SRT_FORMATS.md

---

*Still confused? Run `dji-embed doctor` to verify your setup, then try `dji-embed check` on a sample file to see what you're working with.*