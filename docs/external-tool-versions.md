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

### Recommended Version: 12.76

**Why this version:**
- Mature GPS metadata support
- Extensive video format compatibility  
- Active maintenance and security updates
- Proven stability with MP4 files

**Download sources:**
- **Windows**: https://exiftool.org/install.html#Windows (Standalone executable)
- **macOS**: `brew install exiftool`
- **Linux**: `apt install exiftool` or equivalent

**Minimum supported:** 11.00+  
**Latest tested:** 13.25

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
ARG EXIFTOOL_VERSION=12.76

# Usage in Dockerfile
RUN curl -L "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz" \
    | tar -xJ --strip-components=1 -C /usr/local/bin/
```

## Compatibility Matrix

| dji-embed | FFmpeg | ExifTool | Status |
|-----------|---------|----------|--------|
| 1.0.4     | 6.1.1   | 12.76    | ✅ Recommended |
| 1.0.4     | 6.0.x   | 12.70+   | ✅ Supported |  
| 1.0.4     | 5.1.x   | 12.50+   | ⚠️ Limited testing |
| 1.0.4     | 4.4.x   | 11.00+   | ⚠️ Minimum support |

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
dji-embed 1.0.4
  python: python
  ffmpeg: 6.1.1
  exiftool: 12.76
```

If tools show "not available", they need to be installed or added to PATH.