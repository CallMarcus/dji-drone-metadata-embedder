# Sample-request post drafts (2026-05)

Ready-to-paste copy for community outreach to source raw `.SRT` telemetry
files for the post-2024 DJI lineup. Backed by `docs/MODEL_SURVEY.md` and
issue [#182](https://github.com/CallMarcus/dji-drone-metadata-embedder/issues/182).

These drafts are archival — they are not part of the published MkDocs
site (see `exclude_docs:` in `mkdocs.yml`).

---

## 1) r/dji + r/mavicpilots (consumer cross-post)

**Title:** `[Open source] Need a 10–30s raw .SRT from your Mini 5 Pro / Air 3S / Mavic 4 Pro / Neo / Flip / Avata 360 — help us add parser support`

**Body:**

Hi all — I help maintain [dji-drone-metadata-embedder](https://github.com/CallMarcus/dji-drone-metadata-embedder), an open-source Python tool that bakes DJI telemetry from `.SRT` files into the matching MP4 (subtitle track + GPS metadata) and exports flight tracks to GPX / CSV / JSON. Mini 3/4 Pro, Air 3, Avata 2, and Mavic 3 Enterprise are already first-class.

We've surveyed the post-2024 lineup and **none of the new models has a publicly available SRT we can write a parser against**. So we're asking the community: if you own one of these and can spare a couple of minutes, you'd unlock first-class support for the model in our next release.

**Models we'd love samples from (any of them helps):**

- DJI Mini 5 Pro
- DJI Air 3S
- DJI Mavic 4 Pro
- DJI Neo
- DJI Flip
- DJI Avata 360

**What we need:**

1. **Enable "Video Subtitles" in DJI Fly *before* you record** (Settings → Camera → Video Subtitles). Without this no `.SRT` is generated.
2. **Fly a brief hover** — 10–30 seconds is plenty. No sensitive location needed; we don't need beautiful footage, just a clean SRT with all telemetry tokens populated.
3. **Upload the raw `.SRT` to Google Drive / Dropbox / GitHub Gist / Pastebin (raw)** and share the link in a comment or DM. **⚠️ Do NOT paste the SRT contents into a Reddit comment** — Reddit's markdown silently strips the delimiter spacing and breaks the format. The file has to arrive byte-exact.

**Bonus asks (only if convenient):**

- **Air 3S:** one clip in D-Log M and one in Rec.709 — helps us map the color-profile token.
- **Mavic 4 Pro:** change focal length (zoom) mid-clip — exposes the dynamic focal-length token.
- **Anyone:** if your drone also writes a `.LRF` or `.DAT` next to the MP4, those help end-to-end validation but are not required.

**Privacy:** GPS coordinates can be anonymised before the file is committed as a test fixture if you prefer — just say so. Your handle will be credited in the changelog unless you'd rather stay anonymous.

Thanks! Even one good sample meaningfully moves a model from "best-effort" to "fully tested with golden fixtures." Happy to answer questions.

---

## 2) r/UAVmapping + r/CommercialDronePilots (enterprise)

**Title:** `[Open source] Looking for raw .SRT samples from Matrice 350 RTK / M30 / M4E to extend an open-source telemetry tool`

**Body:**

Hi — open-source maintainer here. Our tool [dji-drone-metadata-embedder](https://github.com/CallMarcus/dji-drone-metadata-embedder) embeds DJI `.SRT` telemetry into MP4 files and exports tracks to GPX/CSV. We've just shipped support for the P4 RTK / Phantom 4 Pro compact single-line format and want to extend it to the current Matrice line. We don't have first-hand fixtures.

**Models we'd love a sample from:**

- DJI Matrice 350 RTK *(highest priority — direct successor to M300)*
- DJI Matrice 30 / 30T
- DJI Matrice 4E / 4T

**Critical detail for RTK formats:** please record with **RTK in "FIX" state** (not "FLOAT" or single-point). The full-precision lat/lon/altitude fields only appear when RTK is fixed, and that's exactly what we need to write the parser against.

**What to do:**

1. Enable Video Subtitles in DJI Pilot 2 before recording.
2. 10–30 seconds of any flight is enough. Indoor or generic outdoor location is fine — we're after the format, not the data.
3. Upload the raw `.SRT` to a cloud share or Gist. **Do not paste the contents into a Reddit comment** — Reddit's renderer mangles delimiter spacing.

If your workflow generates a sidecar `.LRF` or a flight-controller `.DAT`, those are useful but optional.

Anonymising coordinates is fine if you'd prefer — let us know and we'll redact before committing as a test fixture. Happy to credit (or not) in the changelog.

This unlocks GPX export and metadata embedding for every operator on these airframes. Thanks.

---

## 3) MavicPilots.com forum (long-form)

**Title:** `Open-source SRT telemetry tool needs sample files from new DJI models (Mini 5 Pro, Air 3S, Mavic 4 Pro, Neo, Flip, Avata 360)`

**Body:**

Hi MavicPilots,

I help maintain an open-source Python project called **dji-drone-metadata-embedder** ([GitHub](https://github.com/CallMarcus/dji-drone-metadata-embedder)). It does two things:

1. Takes a folder of DJI MP4s and their matching `.SRT` telemetry files, and embeds the telemetry as a subtitle track in the MP4 plus GPS metadata at the container level.
2. Converts `.SRT` telemetry to GPX (for Google Earth, mapping software) or CSV (for analysis).

It already supports Mini 3/4 Pro, Air 3, Avata 2, and Mavic 3 Enterprise with golden test fixtures. After auditing the current DJI lineup, we found that **no public source we could find has a usable raw SRT for any of the post-2024 models**. People paste screenshots, embed video clips, or use proprietary viewers — but the raw text rarely surfaces, and when it does on Reddit/forums the markdown engine strips the delimiter spacing that makes the format parseable.

So I'm asking here directly. If you own one of these drones, **a 10-second hover with Video Subtitles enabled gives us everything we need to add first-class support for your aircraft in our next release**:

| Model | Priority | Format family (predicted) |
|---|---|---|
| DJI Mini 5 Pro | High | Square-bracket (Mini 3/4 Pro lineage) |
| DJI Air 3S | High | HTML-style extended (Air 3 lineage) |
| DJI Mavic 4 Pro | High | Possibly novel — first-hand reports of new tokens |
| DJI Neo | Medium | Unconfirmed |
| DJI Flip | Medium | Square-bracket (likely trivial once a sample lands) |
| DJI Avata 360 | Medium | Avata 2 legacy (likely trivial) |

### How to capture a usable sample

1. Open DJI Fly → camera settings → enable **Video Subtitles**.
2. Power on, hover for 10–30 seconds, land.
3. Pull both files off the SD card / internal storage. We want the `.SRT`. The MP4 isn't strictly needed but helps end-to-end validation.

### How to share it

Upload the **raw `.SRT` file** to one of:

- Google Drive
- Dropbox
- A GitHub Gist (set to "raw" view)
- WeTransfer
- Any pastebin in *raw* mode

Then paste the link in a reply here, or PM it to me.

**⚠️ Please do not paste the SRT contents directly into a forum/Reddit reply.** The forum's markdown formatter silently strips spaces inside `[token: value]` pairs and breaks the parse. The file has to travel byte-exact.

### Bonus asks (only if it's no trouble)

- **Air 3S owners:** one clip in **D-Log M** and one in **Rec.709**. The color-profile token differs and we need both to map it correctly.
- **Mavic 4 Pro owners:** change focal length (zoom) mid-clip if you can. This forces the dynamic focal-length token to fire — otherwise it stays static and we can't see the format.
- **Anyone:** if your drone writes a `.DAT` flight log next to the MP4, that's gold for cross-validation but completely optional.

### Privacy

Coordinates can be anonymised (rounded to ~100 m) before the file is committed as a public test fixture in the repository — just say so when you share. We'll credit you in the release changelog unless you'd rather stay anonymous; if so, we'll just note the model and date.

This is genuinely community-funded work. The project is MIT-licensed, no telemetry, no monetisation, and the only thing standing between us and supporting your aircraft is one clean SRT file.

Thanks for reading. Happy to answer questions in this thread.

---

## Posting checklist

- [ ] r/dji
- [ ] r/mavicpilots (cross-post or fresh post)
- [ ] r/UAVmapping (enterprise variant)
- [ ] r/CommercialDronePilots (enterprise variant)
- [ ] MavicPilots.com forum (long-form variant)
- [ ] Optional: DJI official forum / DJI Enterprise forum

Track responses in issue [#182](https://github.com/CallMarcus/dji-drone-metadata-embedder/issues/182). When a usable sample lands, open a focused `feat(parser): add support for <Model>` issue per `CLAUDE.md` §7.
