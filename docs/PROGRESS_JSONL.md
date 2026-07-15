# `--progress jsonl` — machine-readable progress events

`photomap`, `flightmap`, `embed`, and `check` accept `--progress jsonl`. In
this mode a command writes **one JSON object per line to stdout** and nothing
else — human/informational output is suppressed, and warnings and log
messages go to stderr. A non-zero exit code always means the run failed;
for success, read the `result` event's `ok` field (see the `embed` nuance
under the terminal rule below). Lines are pure ASCII (non-ASCII text is
JSON-escaped and round-trips intact through any JSON parser), so the stream
is safe to read under any pipe encoding. This is the interface for frontends
and scripts:

```bash
dji-embed flightmap D:\Drone\trip --progress jsonl
```

```json
{"v":1,"event":"start","command":"flightmap"}
{"v":1,"event":"progress","current":1,"total":3,"item":"DJI_0001"}
{"v":1,"event":"progress","current":2,"total":3,"item":"DJI_0002"}
{"v":1,"event":"progress","current":3,"total":3,"item":"movie"}
{"v":1,"event":"warning","message":"No GPS telemetry","item":"movie"}
{"v":1,"event":"result","ok":true,"outputs":["D:/Drone/trip/flightmap.html"],"summary":{"flights":2,"skipped":1,"joined_files":0}}
```

## Stability

- Every event carries `"v": 1`. Additive changes (new fields, new event
  types) do **not** bump `v`; consumers must ignore fields and event types
  they do not recognise. Breaking changes bump `v`.
- The machine-checkable contract lives in
  [`progress_jsonl.schema.json`](progress_jsonl.schema.json) (JSON Schema,
  draft 2020-12, validates any single event line). The test suite validates
  every emitted line against it.

## Events

| event | fields | meaning |
|---|---|---|
| `start` | `command` (required), `total` (optional) | First event of every run. `total` is omitted when the item count is not known up front (render an indeterminate progress bar). |
| `progress` | `current`, `total` (required), `item` (optional) | One item finished being picked up for processing. `current` counts from 1 to `total`. |
| `warning` | `message` (required), `item` (optional) | Non-fatal problem; the run continues. |
| `result` | `ok`, `outputs`, `summary` (all required) | Terminal event of a run that completed. `outputs` = absolute paths of files written (may be empty). `summary` is command-specific (below). |
| `error` | `message` (required), `item` (optional) | Terminal event of a run that failed; the process exits non-zero. No `result` follows. |

**Terminal rule:** a stream starts with `start` and ends with exactly one of
`result` or `error` — including on unexpected internal failures, which
surface as an `error` event before the non-zero exit. With one documented
nuance: `embed` processes files independently and keeps its existing
exit-code behaviour, so a run where some files failed still **exits 0** and
ends in `result` with `"ok": false` (per-file problems are `warning` events;
the counts are in `summary`). For `embed`, therefore, treat `result.ok` —
not the exit code — as the success signal. For every other command `result`
implies `"ok": true`.

**Warnings are not live:** `warning` events for skipped items are typically
emitted after the scan completes (once the skipped set is known), not
interleaved with the `progress` events. Attribute them by their `item`
field, never by arrival order.

## Per-command notes

### `flightmap`
- One `progress` event per `.SRT` file scanned; `start` carries no `total`
  (the file count is discovered during the scan — take `total` from the
  first `progress` event).
- One `warning` per SRT without GPS telemetry (`message` is `"No GPS
  telemetry"`, the file name is in `item`), emitted after the scan.
- `summary`: `{"flights": N, "skipped": N, "joined_files": N}` —
  `joined_files` counts source files that were chained into multi-segment
  flights.

### `photomap`
- No `progress` events in v1 (the photo scan is a single batch ExifTool
  call); `start` has no `total`. Expect `start` → warnings → `result`.
- `summary`: `{"photos": N, "skipped": N}` (mapped vs no-GPS).
- `--serve` cannot be combined with `--progress jsonl` (serving blocks
  forever; frontends open the written HTML themselves).

### `embed`
- One `progress` event per video file.
- `summary`: `{"processed": N, "total": N, "warnings": N, "errors": N,
  "output_directory": "..."}`; `outputs` = `[output_directory]`.
- `ok` is `false` when any file errored (see terminal rule above).

### `check`
- One `progress` event per path argument.
- `outputs` is empty. `summary`: `{"checked": N, "files": {"<path>":
  {<metadata flags>}}}` — the per-file object is `check`'s existing
  detection result: `{"gps": bool, "altitude": bool, "creation_time":
  bool}`. A path that does not exist or cannot be read yields `{}` and a
  `warning` event (`"Not found or unreadable"`) — the run still ends in
  `result` with `"ok": true`.

## Relation to `--log-json`

`--log-json` (env `DJIEMBED_LOG_JSON`) is an older, separate feature: it
formats *log lines* as JSON for the commands that read it (e.g. `doctor`)
and is independent of this event stream. The four progress-wired commands
do not change their logging format based on it; under `--progress jsonl`
their logs are human-readable text on stderr. Parse stdout events, treat
stderr as free-form diagnostics.
