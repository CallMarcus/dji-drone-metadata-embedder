# DJI Model Survey — Telemetry SRT Format Assessment

_Consolidated from three deep-research passes (Gemini, DeepSeek, ChatGPT) plus
direct analysis of comparator sample files. Tracks issue
[#182](https://github.com/CallMarcus/dji-drone-metadata-embedder/issues/182)._

_Last updated: 2026-04-19_

---

## TL;DR

**No 2024–2026 target model has a qualifying public SRT sample today.**
Community sample requests are the required next step before any parser work
starts. Two confirmed prior-art format families from adjacent-generation
enterprise models are already available for lineage analysis (see §Comparator
samples below).

---

## Summary table

| Model | Status | SRT exists? | Format family (inference) | Parser effort | Action |
|---|---|---|---|---|---|
| DJI Mini 5 Pro | Shipping | Yes (reported) | Square-bracket (likely) | Moderate | Sample request |
| DJI Air 3S | Shipping | Yes (official) | HTML-style extended (likely) | Moderate | Sample request |
| DJI Mavic 4 Pro | Shipping | Yes (first-hand) | Possibly novel extended | Large | Sample request |
| DJI Neo | Shipping | Unconfirmed | Unknown | Large | Sample request |
| DJI Flip | Shipping (2025) | Yes (official) | Square-bracket (likely) | Trivial | Sample request |
| DJI Avata 360 | Shipping | Yes (official) | Legacy / Avata 2 (likely) | Trivial | Sample request |
| DJI FPV (original) | Legacy / used | Ambiguous (sidecar or embedded) | Legacy or embedded | Large | Sample request + media-path check |
| DJI Inspire 3 | Shipping | Unknown | Unknown / cinema workflow | Large | Sample request |
| DJI Matrice 4E/4T | Shipping (Jan 2025) | Yes (indirect) | RTK compact single-line (likely) | Moderate | Sample request |
| DJI Matrice 30/30T | Shipping | Yes (indirect) | RTK compact single-line (likely) | Moderate | Sample request |
| DJI Matrice 350 RTK | Shipping (May 2023) | Yes (indirect) | RTK compact single-line (likely) | Moderate | **Best enterprise first target** |
| DJI Mini 4K | Shipping | **No** — subtitles embedded in MP4 | N/A | N/A | **Skip** |
| DJI Avata 3 | Not released | N/A | N/A | N/A | **Skip** (wait) |
| DJI FPV v2 | Not a distinct aircraft | N/A | N/A | N/A | **Skip** (product ambiguous) |
| DJI Agras (T10/T20/T50) | Shipping | Unknown | Unknown | Large | Skip (low demand) |

---

## Comparator samples — available today, no outreach needed

The `JuanIrache/DJI_SRT_Parser` repository contains real SRT files from
adjacent-generation enterprise models:

### Family A — Legacy-with-unit (`matrice_300.srt`)

```
GPS(36.6146,-6.1120,0.0M) BAROMETER:0.3M
```

Fields: `GPS(lat, lon, altM)` · `BAROMETER:altM`

**Relationship to existing parser:**
This is superficially the same as the Avata 2 Legacy family
(`GPS(lat,lon,alt) BAROMETER(alt)`) but with two differences:

1. GPS altitude carries an `M` unit suffix inside the tuple: `0.0M` not `0.0`
2. BAROMETER uses colon notation: `BAROMETER:0.3M` not `BAROMETER(91.2)`

**Current parser gap:** The existing regex
`GPS\(([+-]?\d+\.?\d*),\s*([+-]?\d+\.?\d*),\s*([+-]?\d+\.?\d*)\)`
does **not** match `GPS(lat,lon,0.0M)` — after capturing `0.0` it expects `)` but
finds `M`. Avata 2 has no unit suffix so it parses correctly; M300 does not.

**Fix is trivial** — add optional unit suffix:
```python
# Before: r"GPS\(([+-]?\d+\.?\d*),\s*([+-]?\d+\.?\d*),\s*([+-]?\d+\.?\d*)\)"
# After:
r"GPS\(([+-]?\d+\.?\d*),\s*([+-]?\d+\.?\d*),\s*([+-]?\d+\.?\d*)[A-Za-z]*\)"
```

### Family B — RTK compact single-line (`p4_rtk.SRT`, `p4p_sample.SRT`)

```
F/5.6, SS 400, ISO 100, EV 0, GPS (-58.851745, -34.237922, 15), HOME (-58.847509, -34.232707, -57.98m), D 698.70m, H 85.80m, H.S 0.00m/s, V.S 0.00m/s, F.PRY (2.7°, -7.0°, 110.1°), G.PRY (-24.4°, 0.0°, 110.4°)
```

Fields:

| Token | Meaning | Notes |
|---|---|---|
| `F/5.6` | f-number | Different notation from `[fnum: 280]` |
| `SS 400` | Shutter speed | Different from `[shutter: 1/400]` |
| `ISO 100` | ISO | Same label, different delimiter style |
| `EV 0` | Exposure value | |
| `GPS (lat, lon, alt_int)` | GPS position | Space after GPS; altitude is integer |
| `HOME (lat, lon, altm)` | Home point | With altitude in metres |
| `D 698.70m` | Distance from home point | |
| `H 85.80m` | Height above takeoff | |
| `H.S 0.00m/s` | Horizontal speed | |
| `V.S 0.00m/s` | Vertical speed | |
| `F.PRY (°, °, °)` | Aircraft pitch / roll / yaw | Not in consumer formats |
| `G.PRY (°, °, °)` | Gimbal pitch / roll / yaw | |

The P4P sample (`p4p_sample.SRT`) is a reduced version of the same family —
same `F/N, SS N, ISO N, EV N, GPS (lon, lat, alt_int)` core, no HOME or PRY
fields. Note: the P4P coordinate order appears to be `(lon, lat)` rather than
`(lat, lon)`; verify with a known location before implementing.

**Relationship to existing parser:**
This is an entirely new format family not covered by any current regex.
The camera fields use free-standing comma-separated tokens rather than
square-bracket wrappers. `GPS (` (with space) differs from both
`GPS(` (Legacy) and the `[latitude: …]` square-bracket format. A new parser
branch is required.

**Effort: Moderate.** The format is well-structured and single-line — a
self-contained regex will work. The novel fields (HOME, D, H, H.S, V.S,
F.PRY, G.PRY) need to be decoded and stored, but there are no embedded HTML
or multi-line state concerns.

**Predicted M350 RTK format:**
M350 RTK is the current-generation successor to the M300 in the enterprise
line. It may use the RTK compact single-line family (P4 RTK lineage) or an
evolution of the legacy-with-unit family (M300 lineage). We cannot confirm
which without a real file. Either way, the M300 trivial fix above is a safe
prerequisite.

---

## Model notes

### Resolved contradictions (three tools agreed)

- **Mini 4K does not emit a sidecar `.SRT`** — subtitles are embedded in
  the MP4 container. Confirmed independently by DeepSeek (DJI forum post)
  and ChatGPT (MavicPilots lineage analysis). **Skip.**
- **Avata 3 is not released** — no validated product page found by any tool.
  **Skip / wait.**
- **"DJI FPV v2" is not a distinct aircraft** — ChatGPT's source #7
  (`dji.com/mobile/fpv`) confirms this is the Digital FPV System (goggles
  ecosystem), not a new airframe. **Skip** (product target is undefined).

### Models to add to sample-request posts

**Consumer tier (ask in r/dji, r/mavicpilots, MavicPilots.com, DJI forum):**

- **DJI Mini 5 Pro** — first-hand MavicPilots post confirms standalone SRT
  with many fields; very likely square-bracket lineage (Mini 3/4 Pro
  successor). Best consumer candidate.
- **DJI Air 3S** — officially confirmed SRT support; expected HTML-style
  extended (Air 3 successor).
- **DJI Mavic 4 Pro** — first-hand confirmation of `.SRT` + `.LRF` files on
  internal storage (MavicPilots thread 155866). Tri-camera + new gimbal may
  add novel tokens; treat as possibly novel until a file proves otherwise.
- **DJI Neo** — indirect tooling support; unconfirmed format; lower priority
  than the three above.
- **DJI Flip** — officially confirmed SRT; square-bracket family expected;
  trivial once sample arrives.
- **DJI Avata 360** — officially confirmed SRT; Avata 2 Legacy format likely;
  trivial once sample arrives.

**Enterprise tier (ask in r/UAVmapping, r/CommercialDronePilots,
DJI Enterprise Forum, commercialdronepilots.com):**

- **DJI Matrice 350 RTK** — best enterprise first target; strongest
  inheritance from P4 RTK compact single-line family; SkyeBrowse workflow
  docs confirm active `.SRT` use. Request a sample captured with RTK in
  "FIX" state to guarantee full precision fields.
- **DJI Matrice 30/30T** — second enterprise target; same reasoning.
- **DJI Matrice 4E/4T** — third; newer, higher format uncertainty.

**Cinematic / other:**

- **DJI FPV (original)** — `JuanIrache/DJI_SRT_Parser` lists it as tested;
  media-path ambiguity (sidecar vs embedded) must be resolved before parser
  work. Request raw file from goggles storage, not post-processed clip.
- **DJI Inspire 3** — cinema/RTK platform; completely unknown format; lower
  priority than Matrice series.
- **DJI Agras** — no positive SRT evidence; out of scope for now.

---

## Sample-request template

When posting on forums or Reddit, adapt this template:

```
Subject: [Open-source project] Need raw .SRT telemetry file from [MODEL]

Hi — I'm a contributor to the open-source dji-drone-metadata-embedder project
(github.com/CallMarcus/dji-drone-metadata-embedder), which embeds DJI
telemetry into MP4 files and converts it to GPX/CSV. We're adding support for
[MODEL] and need a real .SRT file to write the parser against.

Request:
- Fly a brief hover (10–30 seconds is plenty; no sensitive location needed)
- Enable "Video Subtitles" in DJI Fly / DJI Pilot 2 before recording
- Upload the raw .SRT file to Google Drive / Dropbox / GitHub Gist and share
  the link (do NOT paste into Reddit — formatting strips the delimiters)

[For Air 3S]: Please also share one file shot in D-Log M and one in Rec.709 —
we need to map the color-profile token.

[For Mavic 4 Pro]: If possible, zoom or change focal length mid-clip so we
can see the dynamic focal-length token change.

[For Matrice 350 RTK / 30 / 4E]: Please capture with RTK in "FIX" state so
we see full precision fields.

Thank you! Your file will be committed as a golden test fixture in our samples/
directory (GPS coordinates will be anonymised if you prefer).
```

---

## Prior-art libraries

| Library | Language | Tested models relevant to this survey |
|---|---|---|
| `JuanIrache/DJI_SRT_Parser` | JavaScript | Matrice 300, Phantom 4 RTK, Phantom 4 Pro, DJI FPV, Inspire (some versions) |
| `pypi.org/project/dji-telemetry/` | Python | Claims Neo 2 support (square-bracket style example) |

Both are worth reviewing when implementing new format families. The
`JuanIrache` library in particular has real golden fixtures available.

---

## Next steps (for issue #182)

1. Post sample-request threads targeting Mini 5 Pro, Mavic 4 Pro, Air 3S,
   and M350 RTK (one community thread each).
2. In parallel, open two focused implementation issues using the findings
   above as acceptance criteria:
   - `fix(parser): handle GPS altitude unit suffix (M300/Legacy-with-unit
     family)` — trivial regex tweak, can be done without a new sample.
   - `feat(parser): add RTK compact single-line family (P4 RTK lineage)` —
     Moderate effort; `p4_rtk.SRT` from JuanIrache is a valid starting
     fixture.
3. Once a Mini 5 Pro or Air 3S sample arrives, open
   `feat(parser): add support for <Model>` following `CLAUDE.md §7`.
4. Update this file when new samples land or contradictions are resolved.

---

## Raw research reports

Individual tool outputs archived under `docs/research/`:
- `2026-04-19-gemini.md` — Gemini Deep Research (low technical yield)
- `2026-04-19-deepseek.md` — DeepSeek (297 pages; best per-model reasoning)
- `2026-04-19-chatgpt.md` — ChatGPT Deep Research (strongest citations, 24 URLs)

The brief used to generate these runs is in `docs/model_survey_brief.md`.
