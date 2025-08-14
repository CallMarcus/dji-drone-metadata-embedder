# End-to-End Recipes

This guide provides complete, step-by-step workflows for the most common use cases with DJI Metadata Embedder.

## 📖 Recipe Index

1. [**Basic Processing**](#recipe-1-basic-processing) - Process DJI footage with embedded metadata
2. [**Privacy-Safe Sharing**](#recipe-2-privacy-safe-sharing) - Remove location data for public sharing  
3. [**GPS Track Analysis**](#recipe-3-gps-track-analysis) - Extract flight paths for mapping
4. [**Professional Workflow**](#recipe-4-professional-workflow) - Advanced processing with DAT logs

---

## Recipe 1: Basic Processing
**Goal**: Process DJI videos with embedded telemetry for personal archive

### What You Need
- DJI drone footage (MP4 files)
- Matching SRT subtitle files
- DJI Metadata Embedder installed

### Step-by-Step

#### 1. Check Your Files
```bash
# Verify you have matching pairs
dji-embed check /path/to/drone/footage/

# Example output:
# DJI_0001.MP4: ✅ GPS metadata found
# DJI_0001.SRT: ✅ Telemetry data available
```

#### 2. Run System Check
```bash
# Ensure all dependencies are working
dji-embed doctor

# Should show:
# ✅ FFmpeg: FOUND
# ✅ ExifTool: FOUND (if installed)
```

#### 3. Process Your Videos
```bash
# Basic processing - creates 'processed' folder
dji-embed embed /path/to/drone/footage/

# With custom output location
dji-embed embed /path/to/drone/footage/ -o /archive/processed/
```

#### 4. Verify Results
```bash
# Check the processed videos have metadata
dji-embed check /archive/processed/

# You should see files like:
# DJI_0001_metadata.MP4   (video with embedded telemetry)
# DJI_0001_telemetry.json (flight summary)
```

### Expected Results
- Videos play in any media player with subtitle telemetry track
- GPS metadata searchable in photo management apps
- JSON files contain flight statistics and camera settings
- Original videos remain unchanged

---

## Recipe 2: Privacy-Safe Sharing
**Goal**: Process videos for social media/YouTube while protecting location privacy

### What You Need
- DJI footage you want to share publicly
- Need to remove or fuzz GPS coordinates
- May want to keep altitude/camera data

### Step-by-Step

#### 1. Choose Privacy Level
```bash
# Option A: Remove ALL GPS data
dji-embed embed /drone/footage/ --redact drop -o /public/safe/

# Option B: Fuzz GPS to ~100m accuracy (city-level)
dji-embed embed /drone/footage/ --redact fuzz -o /public/safe/

# Option C: Keep telemetry overlay, remove GPS metadata
dji-embed embed /drone/footage/ --redact drop -o /public/safe/
```

#### 2. Verify Privacy Protection
```bash
# Check that GPS is removed/fuzzed
dji-embed check /public/safe/

# Should show:
# DJI_0001_metadata.MP4: ⚠️ No GPS metadata (if using --redact drop)
# or
# DJI_0001_metadata.MP4: ✅ GPS metadata found (if using --redact fuzz)
```

#### 3. Review JSON Summaries
```bash
# Check the telemetry JSON files
cat /public/safe/DJI_0001_telemetry.json

# Verify GPS coordinates are:
# - null (for --redact drop)
# - rounded (for --redact fuzz) 
```

#### 4. Upload Safely
Your processed videos now have:
- ✅ Telemetry subtitle tracks (safe to share)
- ✅ Camera settings and altitude data
- ❌ No precise GPS coordinates
- ❌ No identifying location information

### Privacy Comparison
| **Method** | **GPS Metadata** | **Subtitle Track** | **Best For** |
|------------|------------------|-------------------|--------------|
| `--redact none` | Full precision | Full telemetry | Private archive |
| `--redact fuzz` | ~100m accuracy | Full telemetry | Regional sharing |
| `--redact drop` | Completely removed | Telemetry without GPS | Public sharing |

---

## Recipe 3: GPS Track Analysis  
**Goal**: Extract flight paths for Google Earth, mapping software, or flight analysis

### What You Need
- DJI SRT files (MP4 files optional)
- Google Earth, QGIS, or other GPS software
- Interest in flight path analysis

### Step-by-Step

#### 1. Export Single Flight Path
```bash
# Create GPX file from one flight
dji-embed convert gpx /drone/footage/DJI_0001.SRT

# Creates: DJI_0001.gpx
```

#### 2. Export Multiple Flights
```bash
# Batch convert entire session
dji-embed convert gpx /drone/session/ --batch

# Creates GPX file for each SRT found
```

#### 3. Export as CSV for Analysis
```bash
# Get spreadsheet data with timestamps
dji-embed convert csv /drone/footage/DJI_0001.SRT -o flight_data.csv

# Batch export all flights
dji-embed convert csv /drone/session/ --batch
```

#### 4. Open in Analysis Software

**Google Earth:**
1. Open Google Earth
2. File → Open → Select `.gpx` file
3. View your flight path with elevation profile

**Excel/Sheets (CSV):**
1. Open the CSV file
2. Columns include: timestamp, latitude, longitude, altitude, speed
3. Create charts, calculate statistics, analyze patterns

**QGIS/Mapping Software:**
1. Add Layer → Vector → GPX file
2. Analyze flight patterns, elevation changes, speed profiles

### Data Formats Explained
- **GPX**: Standard GPS exchange format, works with most mapping software
- **CSV**: Spreadsheet format with raw telemetry data for analysis
- **JSON**: Flight summary with statistics and camera settings

---

## Recipe 4: Professional Workflow
**Goal**: Maximum data extraction with DAT flight logs and professional metadata

### What You Need
- DJI footage (MP4/SRT pairs)  
- DAT flight log files from drone
- ExifTool installed
- Professional video editing workflow

### Step-by-Step

#### 1. Install Full Dependencies
```bash
# Ensure you have ExifTool
dji-embed doctor

# Should show both:
# ✅ FFmpeg: FOUND  
# ✅ ExifTool: FOUND
```

#### 2. Organize Your Files
```
/flight-session/
├── DJI_0001.MP4
├── DJI_0001.SRT  
├── DJI_0002.MP4
├── DJI_0002.SRT
└── DJI_FLY_20240301_142355_001_log.DAT
```

#### 3. Process with Maximum Data
```bash
# Auto-detect DAT files + ExifTool metadata
dji-embed embed /flight-session/ \
  --dat-auto \
  --exiftool \
  -o /processed/professional/ \
  --verbose
```

#### 4. Validate Quality
```bash
# Check for timing drift issues
dji-embed validate /flight-session/ --format json

# Review validation report
```

#### 5. Review Enhanced Data
```bash
# Check all embedded metadata formats
dji-embed check /processed/professional/

# Review enhanced JSON telemetry
cat /processed/professional/DJI_0001_telemetry.json
```

### Professional Results Include:
- **Video Files**: Embedded GPS, altitude, camera settings via FFmpeg
- **EXIF Metadata**: Professional GPS metadata via ExifTool  
- **DAT Integration**: Enhanced flight log data from drone
- **JSON Summaries**: Complete flight statistics and analysis
- **Subtitle Tracks**: Frame-accurate telemetry overlays
- **Quality Reports**: Timing drift and sync validation

### Professional Applications:
- **Insurance Claims**: Comprehensive flight documentation
- **Surveying**: Accurate GPS coordinates and elevation data
- **Film Production**: Professional metadata workflow
- **Flight Training**: Detailed performance analysis
- **Compliance**: Complete audit trail with timing validation

---

## 🔧 Troubleshooting Recipes

### Recipe Failed? Try These Steps:

#### 1. **"No MP4/SRT pairs found"**
```bash
# Check file naming
ls /drone/footage/
# Ensure files like: DJI_0001.MP4 + DJI_0001.SRT

# Check file detection
dji-embed check /drone/footage/
```

#### 2. **"FFmpeg not found"**
```bash
# Install dependencies first
dji-embed doctor

# On Windows, try the bootstrap installer
# On macOS: brew install ffmpeg  
# On Linux: apt install ffmpeg
```

#### 3. **"Timing drift detected"**
```bash
# Validate your files
dji-embed validate /drone/footage/

# Review drift report for sync issues
```

#### 4. **"Processing very slow"**
```bash
# Use quiet mode to reduce output
dji-embed embed /drone/footage/ --quiet

# Process to faster storage location
dji-embed embed /drone/footage/ -o /local/ssd/output/
```

---

## 📊 Quick Reference

### File Naming Requirements
- Videos: `DJI_####.MP4` (case insensitive)
- Subtitles: `DJI_####.SRT` (case insensitive)  
- DAT logs: `DJI_FLY_*.DAT` (auto-detected)

### Output Files Created
- `*_metadata.MP4` - Processed video with embedded metadata
- `*_telemetry.json` - Flight summary and statistics
- `*.gpx` - GPS track (convert command only)
- `*.csv` - Raw telemetry data (convert command only)

### Storage Requirements
- Processing: ~2x original video size (temporary)
- Final output: ~Same size as original videos
- JSON files: ~1-50KB per flight
- GPX/CSV files: ~10-100KB per flight

---

*Need more specific help? Check the [decision table](decision-table.md) or [troubleshooting guide](troubleshooting.md).*