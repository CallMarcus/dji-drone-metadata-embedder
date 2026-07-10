# External Tool Versions

This document specifies the recommended and tested versions of external tools used by dji-embed.

## FFmpeg

### Recommended Version: 6.1.1

**Why this version:**
- Stable release with good H.264/H.265 codec support
- Reliable subtitle stream handling
- Cross-platform availability
- Well-tested metadata embedding

**Download sources:**
- **Windows**: https://www.gyan.dev/ffmpeg/builds/ (Static builds)
- **macOS**: `brew install ffmpeg` 
- **Linux**: `apt install ffmpeg` or equivalent

**Minimum supported:** 4.4.0+  
**Latest tested:** 7.0.2

### Version Detection

```bash
# Check your FFmpeg version
ffmpeg -version

# Via dji-embed (shows detected version)
dji-embed --version
```

## ExifTool  

### Recommended Version: 13.59

**Why this version:**
- Current production release
- Decodes DJI `djmd`/`dbgi` MP4 timed metadata for all supported models
  (Air 3S ≥ 13.39, Mini 5 Pro ≥ 13.52)
- Matches the `dji-embed doctor --install exiftool` pin

**Note:** 12.76 (Ubuntu 24.04's package) recognises DJI MP4 telemetry streams
but decodes **no GPS** — run `dji-embed doctor --install exiftool` on such
systems.

**Download sources:**
- **Any OS (recommended):** `dji-embed doctor --install exiftool` — pinned, checksum-verified, per-user install
- **Windows**: https://exiftool.org/install.html#Windows (Standalone executable)
- **macOS**: `brew install exiftool`
- **Linux**: `apt install exiftool` or equivalent

**Minimum supported:** 11.00+ (SRT workflows); 13.05+ (MP4 timed metadata)  
**Latest tested:** 13.59

### Version Detection

```bash  
# Check your ExifTool version
exiftool -ver

# Via dji-embed (shows detected version)
dji-embed --version
```

## Docker/Container Versions

The Dockerfile pins these exact versions:

```dockerfile
ARG FFMPEG_VERSION=6.1.1

# Usage in Dockerfile
RUN curl -L "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz" \
    | tar -xJ --strip-components=1 -C /usr/local/bin/
```

The image installs ExifTool from apt with no version pin (`apt-get install ffmpeg exiftool`).

## Compatibility Matrix

| dji-embed | FFmpeg | ExifTool | Status |
|-----------|---------|----------|--------|
| 1.16.0    | 6.1.1   | 13.59    | ✅ Recommended |
| 1.16.0    | 6.0.x   | 12.70+   | ✅ Supported |
| 1.16.0    | 5.1.x   | 12.50+   | ⚠️ Limited testing |
| 1.16.0    | 4.4.x   | 11.00+   | ⚠️ Minimum support |

## Known Issues

### FFmpeg
- **Versions < 4.4.0**: May have subtitle embedding issues
- **Development builds**: Can have unstable behavior

### ExifTool  
- **Versions < 11.00**: Limited GPS coordinate format support
- **Very old versions (< 10.x)**: May not handle MP4 metadata correctly

## Version Verification

The `dji-embed --version` command now shows detected tool versions:

```
dji-embed 1.16.0
  python: python
  ffmpeg: 6.1.1
  exiftool: 13.59
```

If tools show "not available", they need to be installed or added to PATH.