# True gimbal attitude from a flight log

Mini-series drones (Mini 3 Pro, Mini 4 Pro without an embedded telemetry
track, and similar) record **no gimbal attitude anywhere on the SD card**.
Their SRT sidecars carry position but not where the camera pointed, so the
3D map draws the camera footprint as a labelled *estimate*.

The attitude does exist — inside the flight record your DJI app or RC
keeps. `--flight-log` merges it into the map:

```bash
dji-embed flightmap ./flights --3d --flight-log my-flight.csv
```

Where a log matches a flight, the camera footprint becomes a measurement
and the "estimated" badge disappears on its own. Where it doesn't, nothing
changes — the estimate stays, honestly labelled. Repeat the flag for
several flights.

## Getting the CSV

DJI encrypts flight records and holds the decryption keys, so **decrypting
a flight log requires an internet connection whichever tool you use** —
the key comes from DJI. There is no offline decoder; that is a property of
DJI's design, not of any particular product.

1. Copy the record from your device. On a DJI RC the files sit at the root
   of *Internal shared storage* (plug in USB, open in your file manager):
   `DJIFlightRecord_2026-07-27_[17-28-49].txt` and similar. On a phone,
   use the DJI app's flight-record export.
2. Feed it to any decoder that exports CSV — Airdata, Flight Reader,
   PhantomHelp Log Viewer, and others all work. This tool is deliberately
   vendor-neutral: it recognises the *content* of the export, not one
   product's schema.
3. In the decoder's export settings, make sure these are included:
    - **gimbal pitch and yaw** (in Flight Reader: `GIMBAL.pitch` and
      `GIMBAL.yaw`),
    - **a UTC timestamp** (in Flight Reader: the UTC option under
      Logs/Reports; Airdata's `datetime(utc)` is there by default),
    - the aircraft's **latitude/longitude** if available — the merge uses
      them to verify the log really belongs to the flight.

## How the merge behaves

- **With a UTC column** the join is exact: each track point takes the
  nearest log sample within one second.
- **Without one** the UTC offset is inferred from the start times (snapped
  to 15-minute steps) and the output says so — inference assumes the
  recording started within a few minutes of the log, so prefer the UTC
  export option.
- A log whose GPS track sits far from the flight is refused even when the
  clocks line up.
- Gimbal data already present in the SRT always wins; a log fills gaps,
  it never overwrites.
- Numbers in the export follow the decimal separator of the machine that
  produced it (comma or dot) — both parse. A value that parses as neither
  stops the run with the column and line named, rather than being silently
  dropped.
