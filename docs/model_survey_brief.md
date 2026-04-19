# DJI Model Survey — Deep-Research Brief

_Last updated: 2026-04-19 · Tracks issue
[#182](https://github.com/CallMarcus/dji-drone-metadata-embedder/issues/182)._

This document stores the deep-research prompts used to survey new DJI
drone models for SRT parser support. Copy one prompt at a time into a
premium deep-research tool (ChatGPT Deep Research, Gemini Deep Research,
Perplexity Pro, etc.). Run both prompts in parallel when possible so the
two reports can be diff'd against each other before any parser work
starts.

The eventual survey output lives in `docs/MODEL_SURVEY.md` (to be created
from the reports). This file is only the input side of the process.

## When to re-run the research

- A new DJI model ships or is announced with SRT telemetry output.
- A firmware update is rumoured to have changed the SRT layout on an
  existing model.
- An "Add now" recommendation has been open for >3 months with no
  follow-up issue — re-check whether public samples have appeared.

## How to use the two reports

1. Run both prompts in parallel; expect 5–15 minutes each.
2. Diff the summary tables. Any model where the two tools disagree on
   format family, sample count, or recommendation is a manual-verify
   candidate.
3. Trust the overlap (samples cited by both) first; treat singletons as
   "one-source" findings that need a second look before action.
4. For every model both tools flag "Add now", open a follow-up issue
   titled `feat(parser): add support for <Model>` with acceptance
   criteria mirroring `CLAUDE.md` §7 — ChatGPT's prompt produces a
   ready-to-copy issue body.
5. For "Wait — sample needed" models, use Gemini's "gap list" to pick
   the single community channel (subreddit thread, forum section,
   Discord) to ask in.

## Ground-truth reminders (for the maintainer, not the LLM)

The prompts already include these, but if you need to tweak them:

- **Currently supported format families** — Square-bracket (Mini 3/4
  Pro), HTML-style extended (Air 3), Legacy `GPS(lat,lon,alt)` (Avata
  2), RTK-extended (Mavic 3 Enterprise). Documented in
  `docs/SRT_FORMATS.md`.
- **Parser contract** — regex-driven, lives in
  `src/dji_metadata_embedder/embedder.py`; each family has a golden
  fixture under `samples/<model>/` and `tests/fixtures/`.
- **Adding-a-model checklist** — `CLAUDE.md` §7 describes the full
  workflow (sample → regex → fixture → docs updates).

## Prompt A — ChatGPT Deep Research

```text
You are a specialist researcher helping maintainers of
`CallMarcus/dji-drone-metadata-embedder` (Python, v1.2.0, on GitHub) decide
which new DJI drone models are worth adding parser support for. Your output
will feed GitHub issue #182. Do deep, cited research; do not invent samples.

===== PROJECT CONTEXT =====

The project embeds DJI telemetry from SRT subtitle files into MP4s via
FFmpeg (no re-encode) and converts to GPX/CSV. Parsers are regex-driven.

Currently supported SRT format families (with golden fixtures):
1. "Square-bracket" — Mini 3/4 Pro lineage. Example line:
   [latitude: 59.111100] [longitude: 18.222200] [rel_alt: 10.0 abs_alt: 105.1]
   [iso: 100] [shutter: 1/1000] [fnum: 280]
2. "HTML-style extended" — Air 3 lineage. Multi-line blocks wrapped in
   <font>…</font>, with fields like F/2.8, SS 1000, ISO 100, EV +0,
   DZOOM 1.0, GPS (lat, lon, alt), RTK status, HOME(…).
3. "Legacy GPS(...)" — Avata 2 lineage. Single-line:
   GPS(lat,lon,alt) BAROMETER:alt
4. "RTK-extended" — Mavic 3 Enterprise lineage, adds RTK precision fields
   and extended camera metadata on top of the HTML-style layout.

===== MODELS TO SURVEY =====

Priority order (rough user demand):
1. DJI Mini 5 Pro
2. DJI Air 3S
3. DJI Mavic 4 Pro (if released)
4. DJI Neo
5. DJI Avata 3 (if released)
6. DJI Mini 4K
7. DJI FPV v2 (and whether original DJI FPV was ever formally supported)
8. DJI Inspire 3
9. DJI Matrice 4 / M30 / M350 RTK (enterprise/RTK)
10. Any other current DJI consumer/enterprise model with telemetry SRT
    (including Agras agricultural line if it writes SRT)

===== WHAT COUNTS AS A USABLE SAMPLE =====

A sample qualifies only if ALL of these are true:
- It is a real SRT file with ≥5 seconds of telemetry (not reconstructed
  from memory, not a screenshot of a single frame).
- A direct URL or reproducible source exists (YouTube description, forum
  thread with attached file, GitHub repo, public Drive/Dropbox link).
- Field layout is consistent across the file.
- Every telemetry token has an identifiable meaning (lat/lon, relative
  alt, absolute alt, barometer, gimbal pitch/yaw/roll, ISO, shutter,
  fnum, EV, focal length, RTK status/accuracy, home point, speed).

Paired .DAT flight log or .MP4 is a bonus, not a requirement.

===== SEARCH STRATEGY (use all) =====

- GitHub code search for ".SRT" files in repos mentioning each model.
- forum.dji.com, Reddit r/dji + r/DJI_Avata + r/drones + r/dji_fpv.
- YouTube: description text + pinned comments of review videos from
  CineD, DC Rainmaker, drone reviewers; also auto-captioned SRT overlays.
- Public sample packs from review sites (PetaPixel, CineD, Heliguy,
  B&H Explora, DPReview).
- DJI SDK / Mobile SDK docs, DJI Pilot 2 manual, DJI Fly manual.
- Chinese-language sources: hdphoto.net, 5iMX, Weibo drone groups, DJI
  China community — translate as needed.
- Firmware release notes on DJI download pages for each model.

Cross-check: if two sources disagree on the format family, note it.

===== OUTPUT FORMAT =====

1. **Summary table** — one row per model, columns:
   Model | Release status | SRT format family (existing lineage name or
   "novel — see dossier") | # of public samples found | Parser effort
   (Trivial / Moderate / Large) | Recommendation (Add now / Wait /
   Skip) | One-line rationale.

2. **Per-model dossier** (one section per model). For each:
   - Release status (shipping / pre-order / cancelled / rumoured) with
     firmware version(s) observed.
   - Every public sample URL found, deduplicated, with a one-line
     description (e.g. "30-sec Mini 5 Pro clip posted to r/dji on
     2025-11-04, SRT attached in comments").
   - Sample confidence: Confirmed first-hand / Reported / Rumoured.
   - Field layout: list each telemetry token and its decoded meaning.
     Flag unknown tokens explicitly.
   - Firmware variation: has the format changed across firmwares?
   - Parser effort justification (what existing regex it could
     inherit, what new tokens need handling).
   - **Proposed regex sketch** if the sample is clear enough, in the
     style of Python `re` with named groups.
   - **Ready-to-copy GitHub issue body** titled
     `feat(parser): add support for <Model>` with acceptance
     criteria mirroring `CLAUDE.md §7`.

3. **Prioritized action list** at the end: "Add immediately" /
   "Sample request needed" / "Skip", each with 1–2 sentences.

===== HARD CONSTRAINTS =====

- Cite every claim with a URL. Separate "confirmed URL" from "paraphrase
  without URL" — the latter must be flagged.
- Do NOT invent SRT sample content. If a sample is described in a source
  but the file itself isn't downloadable, say "sample described but not
  downloadable" and record the source anyway.
- Do NOT propose changes to CI, packaging, or non-parser code.
- If you cannot find any public SRT for a model, say so and recommend
  "Wait — community sample request".
- Keep the regex sketches tied to actual quoted lines from real samples.
  If no sample, no regex.

Begin now.
```

## Prompt B — Gemini Deep Research

```text
Act as a drone-community researcher for the open-source project
`CallMarcus/dji-drone-metadata-embedder`. The maintainers need to decide
which current DJI models have publicly documented SRT telemetry formats
worth adding to the parser. Your output feeds issue #182. Every sample
must be cited with a URL.

===== BACKGROUND THE PROJECT ALREADY HAS =====

The project parses four existing DJI SRT format families:
- Square-bracket (Mini 3/4 Pro): [latitude: …] [longitude: …]
  [rel_alt: … abs_alt: …] [iso: …] [shutter: …] [fnum: …]
- HTML-style extended (Air 3): <font>…F/2.8, SS 1000, ISO 100, EV +0,
  DZOOM 1.0, GPS (lat,lon,alt), RTK, HOME(…)…</font>
- Legacy (Avata 2): GPS(lat,lon,alt) BAROMETER:alt
- RTK-extended (Mavic 3 Enterprise): HTML-style + RTK precision.

These already have regex parsers + golden fixtures. Do not re-document
them; focus research on the NEW models below.

===== MODELS TO INVESTIGATE =====

1. DJI Mini 5 Pro
2. DJI Air 3S
3. DJI Mavic 4 Pro (if released)
4. DJI Neo
5. DJI Avata 3 (if released)
6. DJI Mini 4K
7. DJI FPV v2 (and confirm whether the original DJI FPV ever had a
   documented SRT format)
8. DJI Inspire 3
9. DJI Matrice 4 / M30 / M350 RTK
10. Any other shipping DJI model with SRT telemetry output, incl.
    Agras agricultural models.

===== WHERE TO LOOK (lean on Google + YouTube strength) =====

Prioritize sources Gemini indexes well:
- YouTube video descriptions, pinned comments, and auto-captioned SRT
  overlays on clips uploaded by pilot reviewers (search
  "<model> SRT subtitle telemetry", "<model> DJI Fly subtitle file").
- Reddit (r/dji, r/DJI_Avata, r/drones, r/dji_fpv) — threads where
  pilots paste or attach SRT files.
- forum.dji.com, mavicpilots.com, phantompilots.com, djipilots.net.
- Chinese-language communities: hdphoto.net, 5iMX, Weibo drone groups,
  Baidu Tieba, DJI China community. Translate when needed.
- DJI firmware release notes and DJI Fly / DJI Pilot 2 manuals.
- Review articles from CineD, DC Rainmaker, PetaPixel, DPReview,
  Heliguy, B&H Explora that publish raw sample footage + SRT.
- GitHub code search for ".SRT" files and repos mentioning each
  model's name.

For each sample URL, verify the link resolves and the file is actually
downloadable. If behind a paywall/login, flag it.

===== QUALITY BAR =====

A sample counts only if the SRT file (or pasted SRT content) is:
- Real — not re-typed from memory, not a photo of one frame.
- Long enough (≥5 s of telemetry lines).
- Layout-consistent across the clip.
- Tokens are mappable to known meanings (lat/lon, relative alt,
  absolute alt, barometer, gimbal pitch/yaw/roll, ISO, shutter, fnum,
  EV, focal length, RTK status, home point, speed).

Paired MP4 + .DAT is a bonus.

===== DELIVERABLE FORMAT =====

1. **Cross-model summary table** with columns:
   Model | Release status & newest firmware seen | Format family
   (existing lineage or "novel") | # distinct sample URLs | Parser
   effort (Trivial / Moderate / Large) | Recommendation (Add now /
   Wait / Skip).

2. **Per-model dossier** with:
   - Release status + firmware range observed.
   - Bullet list of every sample URL, deduplicated, with a one-line
     description and the date of the source.
   - Sample confidence rating (Confirmed / Reported / Rumoured).
   - Exact field layout — list every token seen, its decoded meaning,
     and whether it appears in existing format families or is novel.
   - Firmware drift notes: has the format changed between firmwares?
   - A short quoted example (≤10 lines) from one verified sample.
   - Parser-effort justification.

3. **Gap list** — models with zero downloadable samples. For each,
   suggest the single best community channel to ask for a sample
   (specific subreddit thread, forum section, Discord server, etc.).

4. **Prioritized action list**: "Add immediately" / "Sample request
   needed" / "Skip", with one-sentence rationale each.

===== HARD RULES =====

- Every sample URL must be verifiable. No paraphrased samples.
- Do not invent field names or regex. If you cannot quote a real line,
  mark the field layout "unknown — sample needed".
- Translate Chinese-language findings into English but preserve the
  original URL.
- Do not re-document the four format families listed under
  "Background"; they're already in the codebase.
- Scope: parser + sample discovery only. Ignore CI, packaging,
  release, and UI concerns.

Begin now, and cite everything.
```

## After the reports come back

1. Save both raw reports as `docs/research/<date>-chatgpt.md` and
   `docs/research/<date>-gemini.md` (gitignored or committed — your
   call). Keeping the raw reports around makes it obvious when the
   evidence for an "Add now" decision goes stale.
2. Produce the consolidated `docs/MODEL_SURVEY.md` that issue #182 asks
   for. The summary table from either report is a good starting
   skeleton.
3. Open per-model follow-up issues for every "Add now" recommendation,
   using ChatGPT's ready-to-copy issue bodies. Cross-link them to #182.
4. If the two reports disagree meaningfully, capture the disagreement in
   `docs/MODEL_SURVEY.md` rather than silently picking one — future
   readers benefit from knowing what's still uncertain.
