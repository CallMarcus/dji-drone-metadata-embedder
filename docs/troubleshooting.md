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

### "Telemetry stream present but no GPS decoded" / ExifTool too old

Your ExifTool predates the decoder for that model (e.g. Ubuntu 24.04 ships
12.76; Air 3S needs ≥ 13.39, Mini 5 Pro ≥ 13.52). Fix:

    dji-embed doctor --install exiftool

This downloads the pinned, checksum-verified release into a per-user tools
directory and `dji-embed` uses it automatically. `dji-embed doctor` shows the
resolved version and a `timed-metadata decode:` verdict. Use `--force` to
reinstall; `DJIEMBED_EXIFTOOL_PATH` overrides everything.

### "python was not found"

**Windows:**
```cmd
# Use 'py' instead of 'python'
py -m pip install dji-drone-metadata-embedder
dji-embed --help

# Or install Python from python.org
```

### I updated, but `dji-embed --version` still shows the old version

Almost always two different Pythons on the same machine (python.org,
Microsoft Store, winget, Homebrew...): the `dji-embed` on your PATH belongs
to one interpreter, while plain `pip` belongs to another. `pip install
dji-drone-metadata-embedder` then reports "requirement already satisfied"
in the wrong environment — and without `--upgrade` it never updates anyway.

**Shortcut:** `dji-embed doctor --online` checks PyPI for the latest release
and prints the exact upgrade command for the interpreter that owns *your*
`dji-embed` (the literal `python.exe -m pip ...` path, `pipx upgrade`, or
the winget/EXE route) — no PATH archaeology needed. The check is opt-in and
only ever runs from `doctor`; see the README for details and the
`DJIEMBED_NO_UPDATE_CHECK=1` opt-out.

**Diagnose** — find which interpreter owns the `dji-embed` that runs:

```powershell
# Windows (PowerShell)
Get-Command dji-embed | Format-List Source
# e.g. C:\...\Python313\Scripts\dji-embed.exe
#      → owned by C:\...\Python313\python.exe
```

```bash
# macOS/Linux
command -v dji-embed
# e.g. ~/.local/bin/dji-embed — its first line names the owning python
head -1 "$(command -v dji-embed)"
```

**Fix** — upgrade with that interpreter, not with bare `pip`:

```powershell
# Windows: use the python.exe next to the Scripts folder found above
& "C:\...\Python313\python.exe" -m pip install --upgrade dji-drone-metadata-embedder
dji-embed --version
```

```bash
# macOS/Linux
/path/to/that/python -m pip install --upgrade dji-drone-metadata-embedder

# pipx installs avoid this whole problem — one isolated env per app:
pipx upgrade dji-drone-metadata-embedder
```

The standalone Windows EXE and winget installs are separate from pip:
update those by downloading the new EXE from the GitHub release, or with
`winget upgrade CallMarcus.DJIMetadataEmbedder`.

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

### My antivirus blocked the EXE

Some security tools may flag downloaded executables. Releases from
v1.23.0 onwards are Authenticode code-signed (publisher: "Open Source
Developer, Marcus Westermark" — check the file's **Properties → Digital
Signatures** tab), which reduces these warnings over time as the
certificate accrues reputation. Verify the download source and allow
the file if you trust it, or contact your administrator. Releases
before v1.23.0 are unsigned.

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

### Avata 360 `.OSV` / `.LRF` Files

DJI Avata 360 footage is delivered as `.OSV` (the 360 video) plus a matching
`.LRF` low-res proxy instead of `.MP4`. Both are MP4-family containers, so the
embedder discovers and processes them like any `.mp4`, pairing each with the
shared `DJI_..._D.SRT`.

- Both the `.OSV` and the `.LRF` are processed, producing
  `..._metadata.OSV` and `..._metadata.LRF`. If you only want the full-quality
  360 output, keep the `_metadata.OSV` file and discard the `.LRF` outputs.
- The 360 projection metadata inside the `.OSV` is preserved by the stream-copy
  mux but is not parsed by this tool; only the SRT telemetry is read.

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

### Preserving DJI Data Streams (`djmd` / `dbgi`)

Newer DJI models (Air 3S, Neo, etc.) embed proprietary timed-metadata streams
— `djmd` (gyro/IMU/orientation) and `dbgi` (debug info) — inside the source
MP4. The MP4 muxer cannot tag these streams, so the default embed **drops
them** (otherwise ffmpeg fails with `Could not find tag for codec none`). The
video, audio, and telemetry subtitle are unaffected.

To keep those streams byte-for-byte, embed into a Matroska container instead:

```bash
dji-embed embed /path/to/footage --container mkv
```

This produces `<name>_metadata.mkv` with every source stream preserved (and an
`srt` telemetry track). Use the default `mp4` unless a downstream tool needs
the raw `djmd`/`dbgi` data.

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

# There is no built-in timing offset. For severe drift, normalise the
# frame rate with ffmpeg first, then re-run the embed:
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

2. **Process each segment separately:**
   ```bash
   # Embed each split part on its own; shorter clips accumulate less drift
   dji-embed embed part1/
   dji-embed embed part2/
   ```

### Wrong or Missing UTC Times in GPX/CSV Exports

**Problem:** `convert` warns "Timezone auto-detection failed", or exported UTC
times are hours off

**Background:** DJI SRT timestamps are local wall-clock time with no timezone.
With the default `--tz-offset auto`, the local→UTC offset is recovered from the
SRT file's modification time, which only works when the mtime still marks the
recording time.

**Causes:**
- Extracting a zip usually resets the mtime to the extraction time. The
  detected offset then lands outside the real UTC−12..UTC+14 range, detection
  refuses (falling back to raw cue timestamps), and a warning is printed.
- Cloud transfers (Drive, Dropbox, messaging apps) often rewrite mtimes too.

**Solution:** pass the offset explicitly:
```bash
# Footage recorded at UTC+2 (e.g. central Europe in summer)
dji-embed convert gpx clip.SRT --tz-offset +2
```

**Known limitation — footage from another timezone:** zip timestamps are
timezone-naive local times. A zip created in UTC−5 and extracted in UTC+2 with
timestamps preserved yields a *plausible-looking* wrong offset that no sanity
check can catch. For footage received from someone in another timezone, always
pass `--tz-offset` with the **pilot's** offset.

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

## 🗺️ Map & Panorama Issues

### 360° Panoramas Open as Flat Images

**Problem:** Clicking a panorama on a `photomap` map shows a stretched flat
photo instead of the interactive 360° viewer

**Cause:** The map was opened by double-clicking the HTML file. Browsers
block the viewer's image access on `file://` pages, so it silently falls
back to a plain image. The map needs to come from a local web server.

**Solutions:**
```bash
# Build and serve in one step (opens your browser)
dji-embed photomap /path/to/photos --link-originals --serve

# Or serve an already-built map folder later
dji-embed serve /path/to/photos
```

The server binds to a private local address on your machine only — nothing
is uploaded. The desktop app's *Make a map* task does this automatically.

Panoramas need their GPano metadata intact to be detected — see
[Maps & Panoramas](geospatial.md) before resizing or re-exporting them, as
most editors silently strip it.

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
