# DJI SRT Telemetry Formats

This document describes the various SRT telemetry formats used by different DJI drone models.

## Format Types

### Format 1: Bracketed Key-Value Pairs

Used by: DJI Mini 3 Pro, DJI Mini 4 Pro, some newer models

```
[latitude: 59.302335] [longitude: 18.203059] [rel_alt: 1.300 abs_alt: 132.860] [iso : 2700] [shutter : 1/30.0] [fnum : 170]
```

**Fields:**
- `latitude`: GPS latitude in decimal degrees
- `longitude`: GPS longitude in decimal degrees
- `rel_alt`: Relative altitude from takeoff point (meters)
- `abs_alt`: Absolute altitude above sea level (meters)
- `iso`: Camera ISO value
- `shutter`: Shutter speed (e.g., 1/30.0)
- `fnum`: F-number × 100 (170 = f/1.7)

### Format 2: GPS Function Format

Used by: DJI Mavic Pro, DJI Phantom 4, older models

```
GPS(39.906217,116.391305,69.800) BAROMETER(91.2) 
HOME(39.906206,116.391400) D=5.2m H=1.5m
```

**Fields:**
- `GPS(lat,lon,alt)`: GPS coordinates and altitude
- `BAROMETER(value)`: Barometric pressure reading
- `HOME(lat,lon)`: Home point coordinates
- `D`: Distance from home point
- `H`: Height above home point

### Format 3: Comprehensive Format

Used by: DJI Mavic 3, DJI Air 2S

```
<font size="36">SrtCnt : 1, DiffTime : 33ms
2024-01-15 14:30:22,123
[iso : 100] [shutter : 1/1000] [fnum : 280] [ev : 0] [ct : 5500] [color_md : default] [focal_len : 240] [latitude: 59.302335] [longitude: 18.203059] [rel_alt: 10.200 abs_alt: 142.760]</font>
```

**Additional Fields:**
- `SrtCnt`: Frame counter
- `DiffTime`: Time difference from previous frame
- `ev`: Exposure compensation
- `ct`: Color temperature
- `color_md`: Color mode
- `focal_len`: Focal length × 10 (240 = 24mm)

## Camera Settings Interpretation

### ISO Values
- Direct value (e.g., 100, 200, 400, 800, 1600, 3200)

### Shutter Speed
- Fractional format: `1/1000`, `1/500`, `1/250`
- Decimal format: `1/1000.0`
- Long exposure: `2.0` (2 seconds)

### F-Number (Aperture)
- Stored as integer × 100
- Examples:
  - 170 = f/1.7
  - 280 = f/2.8
  - 400 = f/4.0

### Focal Length
- Stored as integer × 10
- Examples:
  - 240 = 24mm
  - 350 = 35mm
  - 500 = 50mm

## GPS Coordinate Formats

### Decimal Degrees
- Standard format: `59.302335`
- Range: -90 to 90 for latitude, -180 to 180 for longitude
- Precision: Usually 6-7 decimal places

### Altitude
- Relative altitude: Height from takeoff point
- Absolute altitude: Height above sea level
- Units: Meters
- Can be negative (below takeoff point or sea level)

## Timestamp Formats

### SRT Standard
```
00:00:00,000 --> 00:00:00,033
```
- Hours:Minutes:Seconds,Milliseconds
- Arrow indicates duration of subtitle display

### Extended Format
```
2024-01-15 14:30:22,123
```
- Full date and time for precise temporal reference

## Adding Support for New Formats

To add support for a new DJI model's SRT format:

1. **Identify the Pattern**: Open SRT files and identify the telemetry pattern
2. **Create Regex Patterns**: Design regex to extract each field
3. **Update Parser**: Add new parsing logic to `parse_dji_srt()` method
4. **Test**: Ensure backward compatibility with existing formats

### Example Parser Addition

```python
# New format: |LAT:59.302335|LON:18.203059|ALT:132.86|
new_format_match = re.search(r'\|LAT:([+-]?\d+\.?\d*)\|LON:([+-]?\d+\.?\d*)\|ALT:([+-]?\d+\.?\d*)\|', telemetry_line)
if new_format_match:
    lat = float(new_format_match.group(1))
    lon = float(new_format_match.group(2))
    alt = float(new_format_match.group(3))
    telemetry_data['gps_coords'].append((lat, lon))
    telemetry_data['altitudes'].append(alt)
```

## Known Model-Format Mappings

| Model | Format Type | Notes |
|-------|------------|-------|
| DJI Mini 3 Pro | Format 1 | Bracketed key-value pairs |
| DJI Mini 4 Pro | Format 1 | Bracketed key-value pairs |
| DJI Mavic 3 | Format 3 | Comprehensive with HTML tags |
| DJI Air 2S | Format 3 | Comprehensive with HTML tags |
| DJI Mavic Pro | Format 2 | GPS function format |
| DJI Phantom 4 | Format 2 | GPS function format |
| DJI Mavic Air 2 | Format 1 | Bracketed key-value pairs |
| DJI FPV | Format 1 | May include additional flight data |

## Special Considerations

### Frame Rate
- SRT timestamps typically match video frame rate
- Common rates: 23.976, 24, 25, 29.97, 30, 50, 59.94, 60 fps

### Coordinate Systems
- Most DJI drones use WGS84 datum
- Coordinates are typically in decimal degrees
- Altitude reference may vary (MSL vs AGL)

### Missing Data
- GPS may not be available immediately after takeoff
- Indoor flights won't have GPS data
- Some fields may be empty or zero
