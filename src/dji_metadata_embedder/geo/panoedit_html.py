"""Editor page for panoedit (#440): Pannellum viewer + live GPano readout
+ save/auto-advance. Served by :mod:`.panoedit`; no build step, hand-rolled
JS like the other geo HTML modules. The Pannellum pin/SRI is imported from
photomap_js so the two viewers can never drift apart."""

from __future__ import annotations

import json

from .provenance import stamp
from .photomap_js import (
    PANNELLUM_CSS_SRI,
    PANNELLUM_JS_SRI,
    PANNELLUM_VERSION,
)

# The page's own backstop for a save request that never returns. Must
# outlast both of the server's ExifTool timeouts (panoedit._WRITE_TIMEOUT,
# applied to the write and again to the read-back) so the server's better
# message wins in the normal case; tests pin the relationship.
_DEFAULT_SAVE_TIMEOUT_MS = 135000

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>360° view editor</title>
<link rel="stylesheet"
      href="https://unpkg.com/pannellum@{pannellum}/build/pannellum.css"
      integrity="{pannellum_css_sri}" crossorigin="" />
<style>
  html, body {{ margin: 0; height: 100%; background: #111; color: #eee;
    font: 14px system-ui, sans-serif; }}
  #viewer {{ position: fixed; inset: 0 0 96px 0; }}
  #readout {{ position: fixed; top: 12px; left: 12px; z-index: 10;
    background: rgba(0,0,0,.65); padding: 8px 12px; border-radius: 6px;
    font-variant-numeric: tabular-nums; line-height: 1.5; }}
  #readout b {{ color: #ffd24d; }}
  #readout .saved {{ color: #9fc7e8; }}
  #savebar {{ position: fixed; top: 12px; right: 12px; z-index: 10;
    text-align: right; }}
  #savebar button {{ font: inherit; padding: 8px 18px; border: 0;
    border-radius: 6px; background: #2a81cb; color: #fff; cursor: pointer; }}
  #savebar button:disabled {{ background: #555; color: #bbb;
    cursor: default; }}
  /* Reset and Compare are second thoughts next to Save, not rivals. */
  #reset, #compare {{ background: #3a3a3a; padding: 8px 14px; }}
  #compare.on {{ background: #7a5c14; color: #fff; }}
  #status {{ margin-top: 6px; min-height: 1.2em; }}
  #status.err {{ color: #ff7b6b; }}
  #strip {{ position: fixed; left: 0; right: 0; bottom: 0; height: 96px;
    background: #1b1b1b; display: flex; align-items: center; gap: 6px;
    overflow-x: auto; padding: 0 48px; box-sizing: border-box;
    scroll-behavior: smooth; }}
  /* Long filenames meant only a couple of chips fit (#532): cap and
     ellipsize — the full name is the chip's title and the readout. */
  .chip {{ flex: 0 0 auto; padding: 6px 10px; border-radius: 5px;
    background: #2a2a2a; cursor: pointer; white-space: nowrap;
    max-width: 17ch; overflow: hidden; text-overflow: ellipsis; }}
  .chip.active {{ outline: 2px solid #2a81cb; }}
  .chip .dot {{ display: inline-block; width: 8px; height: 8px;
    border-radius: 50%; background: #666; margin-right: 6px; }}
  .chip.hasview .dot {{ background: #5ec26a; }}
  #counter {{ position: fixed; right: 12px; bottom: 104px; z-index: 10;
    color: #ddd; background: rgba(0,0,0,.55); padding: 4px 10px;
    border-radius: 6px; }}
  #note {{ position: fixed; left: 12px; bottom: 104px; z-index: 10;
    color: #ccc; font-size: 12px; background: rgba(0,0,0,.55);
    padding: 4px 10px; border-radius: 6px; }}
  /* Sits over the viewer when Pannellum cannot show the image: its own
     "could not be accessed" text blames the file, which is almost never
     the real cause on the machines this happens to (#471). */
  #panoerr {{ position: fixed; inset: 0 0 96px 0; z-index: 20;
    display: none; align-items: center; justify-content: center;
    padding: 0 2em; background: rgba(17,17,17,.93); }}
  #panoerr > div {{ max-width: 36em; line-height: 1.6; text-align: center; }}
  #panoerr b {{ color: #ff7b6b; }}
  #panoerr code {{ color: #ffd24d; }}
  /* Big flanking arrows for the film strip — a field tester found the
     bare scrollbar too fiddly with 200+ panoramas (#532). */
  .stripnav {{ position: fixed; bottom: 0; height: 96px; width: 40px;
    z-index: 11; border: 0; background: #262626; color: #ddd;
    font-size: 26px; cursor: pointer; }}
  .stripnav:hover {{ background: #333; }}
  #stripback {{ left: 0; }}
  #stripfwd {{ right: 0; }}
</style>
</head>
<body>
<div id="viewer"></div>
<div id="panoerr"><div></div></div>
<div id="readout">loading…</div>
<div id="savebar">
  <button id="save" type="button">Save view (Enter)</button>
  <button id="reset" type="button" title="Back to this file's opening view"
    >Reset (Esc)</button>
  <button id="compare" type="button"
    title="Compare the saved view with the one you are composing"
    >Show saved (C)</button>
  <div id="status"></div>
</div>
<div id="counter"></div>
<div id="note">{backup_note} N/P: next/previous. Esc: back to the opening
view. C: compare with the saved one.</div>
<div id="strip"></div>
<button id="stripback" class="stripnav" type="button"
  title="Scroll the file strip back" aria-label="Scroll the file strip back"
  >&#8249;</button>
<button id="stripfwd" class="stripnav" type="button"
  title="Scroll the file strip forward"
  aria-label="Scroll the file strip forward">&#8250;</button>
<script src="https://unpkg.com/pannellum@{pannellum}/build/pannellum.js"
        integrity="{pannellum_js_sri}" crossorigin=""></script>
<script>
"use strict";
const TOKEN = {token};
const SERVE = {serve};
const SAVE_TIMEOUT_MS = {save_timeout_ms};
let files = [], idx = 0, viewer = null, saving = false;
// The view this file opened at (its saved view, or Pannellum's defaults
// where none is saved) and the one being composed when the comparison
// flips away from it (#473).
let openingView = null, pendingView = null, showingSaved = false;
let compareArmed = false;
window.__panoReady = false;
const $ = (id) => document.getElementById(id);

function norm360(d) {{ return ((d % 360) + 360) % 360; }}

function plain(s) {{ return String(s).replace(/[<>&"]/g, ""); }}

// Why this panorama probably failed. Pannellum reports every load failure
// as "the file could not be accessed", including the decode and GPU-memory
// failures that oversized equirects hit on older hardware (#471).
function panoAdvice(f) {{
  const oversize = SERVE.maxWidth && f.width > SERVE.maxWidth;
  if (f.downscaled)
    return "It is already shown downscaled to " + SERVE.maxWidth +
      " px, so the size alone should not be the problem. Reopening it, or "
      + "restarting the editor with a smaller <code>--max-width</code>, is "
      + "the next thing to try.";
  if (oversize && SERVE.hint)
    return plain(SERVE.hint);
  if (oversize)
    // Oversized, downscaling was meant to apply, and it did not: the
    // rendition could not be built (the terminal says why).
    return "It should have been shown downscaled to " + SERVE.maxWidth +
      " px but could not be, so the full-size image was served - see the "
      + "terminal for the reason. A panorama this large can exhaust an "
      + "older GPU's memory even when the file itself is fine.";
  if (f.width > 4000)
    return "Panoramas this large can exhaust an older GPU's memory even "
      + "when the file itself is fine. Restart the editor with "
      + "<code>--max-width 4000</code> to view smaller copies of them; "
      + "the files on disk are never modified.";
  return "Check that the file is a readable JPEG and that this browser has "
    + "WebGL enabled.";
}}

function renderPanoError(f, msg) {{
  const size = (f.width && f.height) ? f.width + " x " + f.height + " px"
    : "size unknown";
  $("panoerr").firstElementChild.innerHTML =
    "<b>Could not display " + plain(f.name || "this panorama") + "</b> ("
    + size + ").<br>" + plain(msg) + "<br><br>" + panoAdvice(f);
  $("panoerr").style.display = "flex";
}}

function showPanoError(msg) {{
  const failed = idx;
  renderPanoError(files[failed] || {{}}, msg);
  // Re-read the list before settling on the advice: `downscaled` is a
  // prediction until the image has been requested, and by now the server
  // knows whether the rendition was actually built. Advice from the
  // prediction can point away from the setting that would fix it.
  fetch("/api/list").then((r) => r.json()).then((list) => {{
    if (list[failed]) files[failed] = list[failed];
    if (idx === failed) renderPanoError(files[failed], msg);
  }}).catch(() => {{}});
}}

function clearPanoError() {{
  $("panoerr").style.display = "none";
}}

function currentView() {{
  const f = files[idx];
  return {{
    heading: norm360(f.pose + viewer.getYaw()),
    pitch: Math.max(-90, Math.min(90, viewer.getPitch())),
    hfov: Math.max(10, Math.min(170, viewer.getHfov())),
  }};
}}

// Reset / compare (#473) -------------------------------------------------

const EASE_MS = 400;

function viewerView() {{
  return {{ yaw: viewer.getYaw(), pitch: viewer.getPitch(),
    hfov: viewer.getHfov() }};
}}

function lookAt(v) {{ viewer.lookAt(v.pitch, v.yaw, v.hfov, EASE_MS); }}

function viewsDiffer(a, b) {{
  return !a || !b || Math.abs(a.yaw - b.yaw) > 0.5
    || Math.abs(a.pitch - b.pitch) > 0.5 || Math.abs(a.hfov - b.hfov) > 0.5;
}}

function updateCompare() {{
  const f = files[idx] || {{}};
  const compare = $("compare");
  // Nothing to compare against until a view has been saved for this file.
  compare.disabled = !(f.hasView && openingView);
  compare.classList.toggle("on", showingSaved);
  compare.textContent = showingSaved ? "Back to yours (C)" : "Show saved (C)";
  // Saving while the saved view is on screen would rewrite the file with
  // what it already contains, which is the pointless write #473 is about.
  $("save").disabled = saving || showingSaved;
  $("reset").disabled = !openingView;
}}

// Snap back to the view this file opened at: the point of Reset is to
// leave a good existing view alone without rewriting the file.
function resetView() {{
  // Not mid-save: the write in flight is of the view that was on screen
  // when it started, and moving the camera under it would leave Reset
  // and the comparison pointing at something that is not on disk.
  if (!viewer || !openingView || saving) return;
  showingSaved = false;
  pendingView = null;
  lookAt(openingView);
  updateCompare();
  $("status").className = "";
  $("status").textContent = files[idx] && files[idx].hasView
    ? "Back to the saved view" : "Back to the opening view";
}}

// Flip between what is on disk and what you have composed, so the choice
// to overwrite is made against the alternative rather than from memory.
function toggleCompare() {{
  if (!viewer || !openingView || !files[idx] || !files[idx].hasView
      || saving) return;
  if (showingSaved) {{
    const back = pendingView;
    showingSaved = false;
    pendingView = null;
    if (back) lookAt(back);
  }} else {{
    pendingView = viewerView();
    showingSaved = true;
    // Armed only once the ease has landed, so the animation towards the
    // saved view is not itself read as the user moving away from it.
    compareArmed = false;
    setTimeout(() => {{ compareArmed = showingSaved; }}, EASE_MS + 150);
    lookAt(openingView);
  }}
  updateCompare();
}}

// Any movement while the saved view is shown means the user has moved on
// from comparing: their new framing is the pending one from here. Watched
// as a divergence rather than hooked to mousedown, because Pannellum also
// pans with the arrow keys and zooms with the wheel — leaving Save
// disabled on a view the user has visibly changed.
function dropCompare() {{
  if (!showingSaved) return;
  showingSaved = false;
  compareArmed = false;
  pendingView = null;
  updateCompare();
}}

function renderStrip() {{
  const strip = $("strip");
  strip.textContent = "";
  let active = null;
  files.forEach((f, i) => {{
    const chip = document.createElement("div");
    chip.className = "chip" + (i === idx ? " active" : "")
      + (f.hasView ? " hasview" : "");
    // Chips ellipsize long names (#532); the title carries the full one.
    chip.title = f.name;
    const dot = document.createElement("span");
    dot.className = "dot";
    chip.appendChild(dot);
    chip.appendChild(document.createTextNode(f.name));
    chip.addEventListener("click", () => navigate(i));
    strip.appendChild(chip);
    if (i === idx) active = chip;
  }});
  // Keep the current file in sight: with hundreds of panoramas and
  // save/auto-advance, the strip otherwise scrolls away from where the
  // work is (#532). block: "nearest" so the page itself never jumps.
  if (active) active.scrollIntoView({{ inline: "center", block: "nearest" }});
  $("counter").textContent = (idx + 1) + " / " + files.length;
}}

// Every user-initiated move between panoramas. A save in flight owns the
// file it started on: leaving mid-write would apply its answer to whatever
// is on screen when it lands (#473/#475).
function navigate(i) {{
  if (saving || i < 0 || i >= files.length) return;
  open(i);
}}

function open(i) {{
  idx = i;
  window.__panoReady = false;
  openingView = null;
  pendingView = null;
  showingSaved = false;
  compareArmed = false;
  clearPanoError();
  if (viewer) {{ viewer.destroy(); viewer = null; }}
  const f = files[i];
  const cfg = {{ type: "equirectangular", panorama: "/img/" + f.index,
    autoLoad: true, minHfov: 10, maxHfov: 170, showFullscreenCtrl: false }};
  if (f.yaw !== null) cfg.yaw = f.yaw;
  if (f.pitch !== null) cfg.pitch = f.pitch;
  if (f.hfov !== null) cfg.hfov = f.hfov;
  viewer = pannellum.viewer("viewer", cfg);
  window.__viewer = viewer;
  viewer.on("load", () => {{
    // Read the opening view off the viewer rather than the file: for a
    // panorama with no saved view that is Pannellum's own default, which
    // is exactly what Reset should return to.
    openingView = viewerView();
    updateCompare();
    window.__panoReady = true;
  }});
  viewer.on("error", showPanoError);
  viewer.on("mousedown", dropCompare);
  viewer.on("touchstart", dropCompare);
  $("status").textContent = "";
  updateCompare();
  renderStrip();
}}

function readoutLoop() {{
  if (viewer && files.length) {{
    // Wheel zoom and arrow-key panning never reach the mousedown handler,
    // so the comparison is retired by watching the view itself.
    if (showingSaved && compareArmed
        && viewsDiffer(viewerView(), openingView)) dropCompare();
    const v = currentView();
    // The file's saved opening values beside the live ones (#493), so a
    // view can be lined up against them deliberately. Compass heading via
    // the same pose + yaw math as the save path; kept current by the
    // server's read-back after each save. No saved view, no line.
    const f = files[idx];
    let savedLine = "";
    if (f.hasView && f.yaw !== null && f.pitch !== null && f.hfov !== null) {{
      savedLine = "<br><span class=\\"saved\\">Saved " +
        norm360(f.pose + f.yaw).toFixed(1) + "° · " +
        f.pitch.toFixed(1) + "° · " +
        f.hfov.toFixed(1) + "°</span>";
    }}
    $("readout").innerHTML =
      "<b>" + files[idx].name.replace(/[<>&]/g, "") + "</b><br>" +
      "Heading " + v.heading.toFixed(1) + "° · " +
      "Pitch " + v.pitch.toFixed(1) + "° · " +
      "FOV " + v.hfov.toFixed(1) + "°" + savedLine +
      // Whose numbers these are matters while comparing (#473).
      (showingSaved ? "<br>showing the saved view" : "");
  }}
  requestAnimationFrame(readoutLoop);
}}

async function save() {{
  // Enter reaches here even though the button is disabled while the saved
  // view is on screen; rewriting the file with its own contents is not a
  // save, it is noise.
  if (saving || !viewer || showingSaved) return;
  // The write belongs to this panorama for its whole flight, however long
  // ExifTool takes: `idx` after the await is not necessarily this file.
  const target = idx;
  saving = true;
  $("save").disabled = true;
  const status = $("status");
  status.className = "";
  status.textContent = "Saving…";
  const v = currentView();
  const slow = setTimeout(() => {{
    if (saving) status.textContent = "Still saving… (large file, or a "
      + "virus scanner looking at it)";
  }}, 4000);
  try {{
    const resp = await fetch("/api/save", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify({{ index: files[target].index, token: TOKEN,
        heading: v.heading, pitch: v.pitch, hfov: v.hfov }}),
      // The server gives up on ExifTool first and answers with a real
      // message; this is the backstop for the request itself vanishing,
      // so the button always comes back (#475). Undefined on browsers
      // without AbortSignal.timeout, where the old behaviour is still
      // better than a broken save.
      signal: typeof AbortSignal.timeout === "function"
        ? AbortSignal.timeout(SAVE_TIMEOUT_MS) : undefined,
    }});
    const body = await resp.json();
    if (!resp.ok) throw new Error(body.error || ("HTTP " + resp.status));
    Object.assign(files[target], body);
    status.textContent = "Saved ✓";
    if (target + 1 < files.length) {{
      open(target + 1);
      $("status").textContent = "Saved ✓";
    }} else {{
      // Staying on this file: what was just written is now its saved view.
      // Taken from the server's verified read-back, not from the live
      // camera, so Reset and the comparison point at what is on disk.
      openingView = (body.yaw !== null && body.yaw !== undefined)
        ? {{ yaw: body.yaw, pitch: body.pitch, hfov: body.hfov }}
        : viewerView();
      pendingView = null;
      renderStrip();
      status.textContent = "Saved ✓ — all panoramas done";
    }}
  }} catch (e) {{
    status.className = "err";
    status.textContent = (e.name === "TimeoutError" || e.name === "AbortError")
      ? "Save timed out after " + Math.round(SAVE_TIMEOUT_MS / 1000)
        + "s. The file may be locked by another program - check the "
        + "terminal for details, then try again."
      : "Save failed: " + e.message;
  }} finally {{
    clearTimeout(slow);
    saving = false;
    updateCompare();
  }}
}}

$("save").addEventListener("click", save);
$("reset").addEventListener("click", resetView);
$("compare").addEventListener("click", toggleCompare);
// A page-width jump per press: coarse on purpose, the chips themselves are
// the fine control (#532).
$("stripback").addEventListener("click", () => {{
  $("strip").scrollLeft -= $("strip").clientWidth * 0.8;
}});
$("stripfwd").addEventListener("click", () => {{
  $("strip").scrollLeft += $("strip").clientWidth * 0.8;
}});
// Half of Pannellum's ~5° per wheel notch, which a field tester found
// landed twice as far as intended (#532). Capture phase with the event
// stopped, so this replaces Pannellum's own wheel handler rather than
// stacking on it; instant (no ease) so repeated notches stay predictable.
const WHEEL_HFOV_STEP = 2.5;
$("viewer").addEventListener("wheel", (e) => {{
  e.preventDefault();
  e.stopPropagation();
  if (!viewer || !e.deltaY) return;
  viewer.setHfov(viewer.getHfov() + (e.deltaY > 0 ? 1 : -1) * WHEEL_HFOV_STEP,
    false);
}}, {{ capture: true, passive: false }});
document.addEventListener("keydown", (e) => {{
  if (e.key === "Enter") {{ e.preventDefault(); save(); }}
  else if (e.key === "Escape") {{ e.preventDefault(); resetView(); }}
  else if (e.key === "c" || e.key === "C") {{ toggleCompare(); }}
  else if (e.key === "n" || e.key === "N") {{ navigate(idx + 1); }}
  else if (e.key === "p" || e.key === "P") {{ navigate(idx - 1); }}
}});

fetch("/api/list").then((r) => r.json()).then((list) => {{
  files = list;
  const big = files.filter((f) => f.downscaled).length;
  if (big) {{
    $("note").innerHTML += "<br>" + big + " panorama" +
      (big === 1 ? " is" : "s are") + " shown downscaled to " +
      SERVE.maxWidth + " px for compatibility; the files are untouched.";
  }}
  open(0);
  readoutLoop();
}});
</script>
</body>
</html>
"""


def build_editor_page(
    token: str,
    *,
    max_width: int = 0,
    renditions: bool = True,
    hint: str = "",
    save_timeout_ms: int = _DEFAULT_SAVE_TIMEOUT_MS,
    backup: bool = True,
) -> str:
    """The complete editor page with *token* embedded.

    ``json.dumps`` alone leaves ``<`` intact, so a hostile token could
    close the script tag; ``\\u003c`` keeps the JS value identical while
    making breakout impossible. Real tokens are ``token_urlsafe`` output,
    but the page must be safe by construction, not by caller convention.

    ``max_width`` is the server's downscale ceiling (0 = off) and *hint*
    the message to show when a panorama is over it but no rendition could
    be made — both only ever reach the user through the failure overlay
    and the footer note (#471). ``save_timeout_ms`` is the page's backstop
    for a save request that never comes back; it must outlast the server's
    own ExifTool timeouts, which answer with a better message (#475).
    ``backup`` mirrors the server's write mode (#492) so the footer never
    promises a ``*_original`` copy that will not exist.
    """
    serve = {
        "maxWidth": max_width,
        "renditions": renditions,
        "hint": "" if renditions else hint,
    }
    return stamp(_PAGE.format(
        pannellum=PANNELLUM_VERSION,
        pannellum_css_sri=PANNELLUM_CSS_SRI,
        pannellum_js_sri=PANNELLUM_JS_SRI,
        token=json.dumps(token).replace("<", "\\u003c"),
        serve=json.dumps(serve).replace("<", "\\u003c"),
        save_timeout_ms=int(save_timeout_ms),
        backup_note=(
            "Saving keeps a backup of each original beside it "
            "(<code>*_original</code>)." if backup else
            "Saving writes each view straight into the file - "
            "no backup copies are kept."
        ),
    ))
