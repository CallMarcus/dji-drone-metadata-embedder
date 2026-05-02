# DJI SRT Telemetry Formats

This document describes the different SRT telemetry formats used by different DJI drone models.

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

### Format 2b: Legacy-with-Unit (Matrice 300 lineage)

Used by: DJI Matrice 300 RTK and adjacent enterprise models.

```
GPS(36.6146,-6.1120,0.0M) BAROMETER:0.3M
```

Identical to Format 2 except the altitude inside the GPS tuple carries a
unit suffix (`M`) and BAROMETER uses a colon notation rather than
parentheses. The parser tolerates the suffix via an optional
`[A-Za-z]*` group on the altitude capture; latitude and longitude are
extracted as for Format 2.

### Format 2c: P4 RTK Compact Single-Line

Used by: DJI Phantom 4 RTK, Phantom 4 Pro, and likely the Matrice
350 RTK / Matrice 30 enterprise lineage.

```
F/5.6, SS 400, ISO 100, EV 0, GPS (-58.851745, -34.237922, 15),
HOME (-58.847509, -34.232707, -57.98m), D 698.70m, H 85.80m,
H.S 0.00m/s, V.S 0.00m/s, F.PRY (2.7°, -7.0°, 110.1°),
G.PRY (-24.4°, 0.0°, 110.4°)
```

**Fields parsed today:**
- `GPS (lat, lon, alt)` — note the space before `(` and integer altitude
- `F/N` → camera fnum (free-standing, not `[fnum:…]`)
- `SS N` → camera shutter
- `ISO N` → camera iso
- `EV N` → camera ev

**Fields recognised but not yet decoded** (open follow-up):
`HOME (…)`, `D Nm`, `H Nm`, `H.S Nm/s`, `V.S Nm/s`, `F.PRY (p, r, y)`,
`G.PRY (p, r, y)`. These tokens are documented for future work; the
parser currently extracts GPS + camera and ignores the rest.

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
| DJI Matrice 300 RTK | Format 2b | Legacy-with-unit (`0.0M` altitude) |
| DJI Phantom 4 RTK / P4P | Format 2c | P4 RTK compact single-line |
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
