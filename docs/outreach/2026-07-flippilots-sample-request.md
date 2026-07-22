# FlipPilots.com sample-request post (2026-07)

Ready-to-paste copy for FlipPilots.com (sister forum to MavicPilots.com),
asking DJI Flip owners for a short clip plus its raw `.SRT` so we can add
first-class parser support. Follows the 2026-05 outreach drafts in this
folder and issue
[#182](https://github.com/CallMarcus/dji-drone-metadata-embedder/issues/182).

This draft is archival — not part of the published MkDocs site
(see `exclude_docs:` in `mkdocs.yml`).

---

**Title:** `Open-source telemetry tool needs a 10–30s clip + SRT from your DJI Flip — help us add support`

**Body:**

Hi FlipPilots,

I maintain **DJI Metadata Embedder** ([GitHub](https://github.com/CallMarcus/dji-drone-metadata-embedder)), a free, open-source (MIT) tool that reads the telemetry DJI records with every flight and turns it into useful things: it embeds GPS metadata into your MP4s so Windows Photos / Google Photos can find them by place (no re-encoding, no quality loss), maps every flight in a folder on one interactive map, pins your photos on a clustered photo map, and exports flight tracks to GPX / CSV / KML for Google Earth and mapping software.

It started as a command-line tool (`dji-embed`, still there for those who like terminals), but there's now also a **Windows desktop app** — a regular installer, folder in, map or telemetry out, no terminal needed, with FFmpeg and ExifTool bundled.

Models like the Mini 3/4 Pro, Mini 5 Pro, Air 3/3S, Neo 2, and Avata 2/360 are already fully supported with test fixtures. **The DJI Flip isn't yet — because we've never gotten our hands on a raw SRT file from one.** That's where you come in.

**If you own a Flip, a couple of minutes gets your aircraft first-class support in the next release:**

1. In DJI Fly, enable **Video Subtitles** (camera settings) *before* recording — without it no `.SRT` is written.
2. Fly a brief hover — **10–30 seconds is plenty**. It doesn't need to be pretty footage or a scenic location; we just need the telemetry.
3. Pull both files off the storage: the `.SRT` and, ideally, the matching MP4 clip (the video lets us validate end-to-end, not just parse the text).

**How to share:**

- **DM me** a cloud share link (Google Drive, Dropbox, WeTransfer, etc.), or
- **Email** the files or a link to **marcus@callmarcus.com**

⚠️ Please don't paste the SRT contents directly into a forum reply — forum formatting silently mangles the spacing inside the telemetry tokens, and the file needs to arrive byte-exact.

**Privacy:** happy to anonymise the GPS coordinates (rounded to ~100 m) before anything is committed as a public test fixture — just say so when you share. You'll be credited in the release changelog unless you'd rather stay anonymous.

The project is MIT-licensed, free, no telemetry, no monetisation — the only thing between us and supporting the Flip is one clean sample. Thanks for reading, and happy to answer questions in this thread.

---

## Posting checklist

- [ ] FlipPilots.com

Track responses in issue
[#182](https://github.com/CallMarcus/dji-drone-metadata-embedder/issues/182).
When a usable sample lands, open a focused
`feat(parser): add support for DJI Flip` issue.
