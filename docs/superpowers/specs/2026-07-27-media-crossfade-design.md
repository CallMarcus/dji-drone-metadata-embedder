# Media crossfade — design

**Date:** 2026-07-27
**Issue:** [#380](https://github.com/CallMarcus/dji-drone-metadata-embedder/issues/380)
**Status:** Approved

## Problem

The 3D map can put you at the drone's altitude (Ghost Camera, #372), show the
shape of the flight in the air (#375), sweep the camera's ground footprint
along it and tell you which seconds covered any spot you click (#378). All of
it is a reconstruction from telemetry. It cannot show the footage, and — more
importantly — it offers no way to check that the reconstruction and the footage
agree.

The **media crossfade** puts the real video frame over the cockpit view on a
blend slider. Held half-way, the terrain reconstruction and the recorded frame
are overlaid: if the telemetry is right, they line up. That is the payoff of
the arc and the most direct verification the tool offers — the map's claim
about where the camera pointed, checked against what the camera saw.

This is stage 4, the last of the 3D arc.

## Scope

- **Video only.** Photos are a separate source and would pull in the MapLibre
  half of #322.
- **Opt-in** via `--link-originals` / `--link-base` on `flightmap`, mirroring
  `photomap`'s existing flags.
- **Split recordings handled.** DJI closes the container at 4 GB; an Air 3 at
  4K/100 Mbps reaches that in about five minutes, so single-file-only would
  miss the flights most worth reviewing.
- **`geo/serve.py` gains HTTP Range support**, because the crossfade is
  fundamentally a seek.

Out of scope: photos and panoramas; drawing video pixels into WebGL (the blend
is CSS compositing only, so no CORS/canvas-taint concerns); audio; any change
to the flat map.

## Design

### 1. Media resolution (Python)

`flightmap` gains `--link-originals` and `--link-base`, matching `photomap`'s
semantics — the second requires the first, as it already does there.

A new helper fills `Track.media: list[str] | None`, one href per segment in
segment order, called by the CLI after scanning:

- For each segment name, resolve the **actual sibling file on disk** rather
  than guessing a stem: DJI writes `.MP4`, some tools write `.mp4`, and the
  container can be `.MOV`. Only files that exist are linked; a segment with no
  resolvable video contributes `null`.
- Hrefs are relative to the map's output directory, or prefixed with
  `--link-base` when given.
- **Allowed under `--redact fuzz`**, matching `photomap`, which already permits
  the same combination and warns rather than refusing ("Linked/attached
  original files still carry exact GPS in their EXIF"). Two commands behaving
  differently on the same flag pair would be a usability trap, and there is a
  principled line: fuzz corrupts *derived geometry*, so deriving geometry from
  it is refused — the gaze draws a footprint at a knowingly-wrong place — but a
  file reference is not a derived claim. The *blend* is disabled instead
  (see §8).

Keeping resolution in the CLI leaves the writers pure: `flights_to_geojson`
emits whatever `Track.media` holds and never touches the filesystem.

### 2. Segment identity must travel on the point

`join_split_flights` (`geo/flightmap.py:87`) merges segments with
`prev.track.points.extend(entry.track.points)` at line 129, so the boundary is
`len(prev.track.points)` immediately before that call. **Recording boundary
indices there would be wrong**: `_decimate_points` runs *after* joining and
thins the track to roughly one point per second, keeping first and last, which
invalidates any index captured earlier.

So `TrackPoint` gains `segment: int = 0`, set during the join for each appended
segment. Decimation then carries it for free, and every later consumer sees the
right value without bookkeeping. The field is defaulted, so every existing
construction site — including tests — is unaffected.

### 3. Time to (file, offset)

**The in-file offset is already in the data.** Each point's `timestamp` is its
raw SRT cue, which is video-relative, and `join_split_flights` rebases only
`utc` — it never touches `timestamp`. So `_cue_seconds(p.timestamp)` is exactly
the offset within that point's own video file, for joined and single-file
flights alike.

New per-flight GeoJSON properties, emitted only when `Track.media` is present:

| Property | Shape | Meaning |
| --- | --- | --- |
| `media` | list, one per segment | href per segment, `null` where unresolved |
| `cue_s` | per-point array | offset within that point's own video file |
| `seg_i` | per-point array | segment index; omitted when every point is 0 |

`cue_s` follows the `times_s` contract: parallel to `coordinates`, same length.
`seg_i` is omitted for the common single-file case, and its absence means "all
zero" — a folder of single-file flights pays nothing.

At sample `i` the viewer needs `media[seg_i[i]]` and `cue_s[i]`. Nothing else.

### 4. HTTP Range in `geo/serve.py`

`_QuietHandler` extends `SimpleHTTPRequestHandler`, which does not implement
Range. Without it Safari refuses to play at all and Chrome re-requests from
byte zero on every seek.

Add a `send_head` override that:

- advertises `Accept-Ranges: bytes` on every file response;
- parses a single `Range: bytes=start-end` (open-ended on either side) and
  answers `206 Partial Content` with `Content-Range` and the exact byte slice;
- answers `416 Range Not Satisfiable` with a `Content-Range: bytes */<size>`
  when the range falls outside the file;
- falls back to a plain `200` for multi-range requests, which no browser needs
  for media playback.

This is unit-testable without a browser and benefits the existing 360° pano
viewer too.

### 5. The overlay and the blend control

One `<video>` element over the map canvas: `position: absolute`, covering the
map, `pointer-events: none` so it never eats a click meant for the terrain,
`muted` and `playsinline`. Its `opacity` is the blend.

- **A blend slider in the ghost HUD** (`#ghost-blend`), 0-100. This is the
  control that matters: held mid-way you see both layers at once, which is the
  whole point.
- **`V` toggles the extremes** (0 ↔ 100) with a short CSS opacity transition,
  for when you just want to swap. It joins `Escape`, `ArrowLeft` and
  `ArrowRight` in the existing `ghostKeys` handler
  (`geo/flightmap3d_html.py:398`) and, like them, calls `preventDefault`.
- The element is created only when the current flight has a resolvable video,
  and removed when it does not, so a flight without media has no dead control.

`src` is swapped when the current sample crosses into a different segment;
`currentTime` is set from `cue_s`. A `src` swap resets playback state, so the
swap sets `currentTime` again once `loadedmetadata` fires.

### 6. Playback sync

Two regimes, because browsers cannot decode reliably at 20× or 60×:

- **Speed ≤ 4×:** `video.playbackRate = pb.speed` and `play()`, re-seeking
  whenever `|video.currentTime − cue_s[sample]|` exceeds 0.25 s. Small drift is
  expected and correcting it every frame would thrash the decoder.
- **Above 4×, or paused, or scrubbing:** the video stays paused and seeks on
  each sample change. At those speeds it is a slideshow, which is honest — the
  alternative is a decoder that silently falls behind and shows the wrong
  second.

### 7. Framing alignment

Ghost mode already calls `setVerticalFieldOfView(fl.vfov)`, so the map's
vertical field of view is the camera's. The video is sized to the container's
full height directly (`height: 100%; width: auto`, centred with
`left: 50%; transform: translateX(-50%)`) rather than `object-fit: contain`.
`contain` only fits by height when the container is *wider* in aspect than the
video; on a narrower one — a tall window, a tablet, a portrait phone — it fits
by width instead, and the vertical framing silently shrinks (whole-branch
review C1: ~16% for 16:9 footage in a 1200×800 window). Sizing to height keeps
the vertical match true by construction, in every container shape, which is
what the alignment claim actually rests on.

Horizontal framing crops instead, in both directions depending on which is
wider: the video overflows past the map's sides, or the map shows either side
of the video, and the map container's own `overflow: hidden` clips whichever
overflows. That is the correct compromise — distorting either layer to force a
horizontal match would make the comparison meaningless, and only the vertical
axis is load-bearing for the alignment check.

### 8. Failure posture and edge cases

| Condition | Behaviour |
| --- | --- |
| `--redact fuzz` | Linking is allowed (see §1), but **the crossfade blend is disabled**, and the HUD says why: positions are deliberately coarsened by ~100 m, so overlaying real footage on that reconstruction would invite a comparison against geometry we know is wrong. The premise of the feature, not just its privacy posture, is what fuzz breaks. Same shape as the gaze gate — feature off, reason stated — without diverging from `photomap` on the CLI. |
| `--redact drop` | The track is removed upstream, so there is no flight to link media to and nothing to render. |
| No `--link-originals` | No `media` property, no video element, no slider. The 3D map is exactly what it is today. |
| Segment with no resolvable file | `media[s]` is `null`; the crossfade is unavailable while the clock is inside that segment. `media[s]` being `null` is exactly the fact that there is no filename left to name (whole-branch review I2) — the HUD says "no video for this part of the flight" rather than asserting one it does not have. |
| Flight has no `vfov_deg` | The map's own FOV is an estimate, so the alignment is approximate. Reuse the existing estimated badge wording rather than inventing a second vocabulary. |
| Video fails to load (moved, unsupported codec) | The slider disables itself and the HUD names the file, worded as what the `<video>` `error` event actually tells us — "could not load: `<file>`" — since the same event fires for a moved file, a wrong href base, a transport failure and an undecodable codec alike (whole-branch review I3). No silent blank overlay. |
| Not in the cockpit | The slider lives in the ghost HUD, so the crossfade is a cockpit feature. Third-person playback is unchanged. |
| `file://` | Works with no server: relative `<video src>` seeks natively. This is the common path and needs no Range. |

## Testing

**Range support** is unit-tested in Python with no browser: a served file
fetched whole; `bytes=0-99`, `bytes=100-`, `bytes=-100`; a `416` for a range
past the end; `Accept-Ranges` present; and a multi-range request falling back
to `200` with the whole body.

**Browser tests get a real, seekable video without ffmpeg, a committed binary,
or fabricated bytes.** Chromium records its own canvas via `MediaRecorder` and
the result is served as a blob URL. This was verified empirically before the
spec was written: VP9 WebM, ~38 KB for two seconds, **finite** duration
(1.9656 s), and a seek to 1.0 s landed exactly at 1.0. The honest limit is that
it is WebM rather than MP4, so these tests prove our seek logic, segment
mapping and blend wiring — not MP4 decoding, which is the browser's job.

Covered: the video element appears only when media resolves and is absent
otherwise; the blend slider drives opacity; the key toggles the extremes;
`currentTime` tracks `cue_s` as the clock moves; crossing a segment boundary
swaps `src` and re-seeks; a `null` segment disables the control and names the
file; the speed regimes (`playbackRate` at 1×, paused-and-seeking at 60×); and
`--link-originals` refused under `--redact fuzz`.

Python-side: `TrackPoint.segment` set correctly across a join and **preserved
through decimation** — the trap §2 exists to avoid; `cue_s` equal to the raw
cue time for both joined and single-file flights; `media` emitted only when
resolved; href resolution across `.MP4`/`.mp4`/`.MOV` and a missing sibling.

## Docs

`docs/geospatial.md` gains a crossfade subsection after the Camera's gaze one,
covering the slider, the key, what `--link-originals` does and why it is
opt-in, that the videos must travel with a shared map, and the two honesty
limits (refused under redaction; approximate alignment without a focal length).
The `--serve` note gains a line that seeking now works. README gains one line.
