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

## Getting the TXT off your controller

Flight records are small `.txt` files your DJI app or RC writes per
flight — named like `DJIFlightRecord_2026-07-27_[17-28-49].txt`. Despite
the extension they are encrypted binary, not text.

**DJI RC (RC 2, RC Pro, ...):**

1. Plug the RC into your computer over USB, with the RC **powered on and
   unlocked**. It appears in Explorer as a portable (MTP) device — no
   drive letter, which is why some copy tools cannot see it.
2. Open the device › *Internal shared storage*. The flight records sit
   at the **root** of that storage, not in a folder.
3. Copy the `DJIFlightRecord_*.txt` files anywhere on your computer.

Or let the [helper script from the
repository](https://github.com/CallMarcus/dji-drone-metadata-embedder/blob/master/tools/mtp-copy.ps1)
do it (Windows; copies only records you do not already have) — it is not
shipped in the installed package, so grab it from the repo first:

    powershell -ExecutionPolicy Bypass -File tools\mtp-copy.ps1

If the device does not appear: unlock the RC's screen, try another
cable/port (some cables are charge-only), and accept any "allow access"
prompt on the RC.

**Phone as the controller:** use the DJI app itself — Profile › More ›
Flight Data (wording varies by app version) offers a flight-record
export/upload; the files it produces are the same `DJIFlightRecord_*.txt`.

## Getting the CSV

DJI encrypts flight records and holds the decryption keys, so **decrypting
a flight log requires an internet connection whichever tool you use** —
the key comes from DJI. There is no offline decoder; that is a property of
DJI's design, not of any particular product.

1. Get the record onto your computer (see [Getting the TXT off your
   controller](#getting-the-txt-off-your-controller) above).
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

### Fetching the CSV via the API (optional)

If you have a [Flight Reader API](https://www.flightreader.com/api/) key,
`fetch-log` does the decode step for you:

    $env:FLIGHTREADER_API_KEY = "sk_..."   # PowerShell; use  export FLIGHTREADER_API_KEY=sk_...  on macOS/Linux
    dji-embed fetch-log DJIFlightRecord_2026-07-27_[17-28-49].txt
    dji-embed flightmap D:\Flights --3d --flight-log DJIFlightRecord_2026-07-27_[17-28-49].flightreader.csv

Know what this does before you run it: **your entire flight log is
uploaded to flightreader.com to decrypt it** — your exact coordinates,
and everything else the log records, leave your computer (Flight Reader
states uploads are deleted immediately after processing). The command
asks for confirmation once per invocation before uploading new records,
and each record's CSV is written beside it and reused on every later run
— the same record is never uploaded twice. Delete the `.flightreader.csv`
to refetch. You supply your own key; this tool never embeds or brokers one.

The fetcher asks the API for exactly the columns the merge needs,
including an epoch timestamp — so API-fetched CSVs always get the exact
join. The UTC export advice above is for hand-made exports.

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
