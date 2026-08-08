"""Editor page for panoedit (#440): Pannellum viewer + live GPano readout
+ save/auto-advance. Served by :mod:`.panoedit`; no build step, hand-rolled
JS like the other geo HTML modules. The Pannellum pin/SRI is imported from
photomap_html so the two viewers can never drift apart."""

from __future__ import annotations

import json

from .photomap_html import (
    _PANNELLUM_CSS_SRI,
    _PANNELLUM_JS_SRI,
    _PANNELLUM_VERSION,
)

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
  #savebar {{ position: fixed; top: 12px; right: 12px; z-index: 10;
    text-align: right; }}
  #save {{ font: inherit; padding: 8px 18px; border: 0; border-radius: 6px;
    background: #2a81cb; color: #fff; cursor: pointer; }}
  #save:disabled {{ background: #555; cursor: default; }}
  #status {{ margin-top: 6px; min-height: 1.2em; }}
  #status.err {{ color: #ff7b6b; }}
  #strip {{ position: fixed; left: 0; right: 0; bottom: 0; height: 96px;
    background: #1b1b1b; display: flex; align-items: center; gap: 6px;
    overflow-x: auto; padding: 0 12px; box-sizing: border-box; }}
  .chip {{ flex: 0 0 auto; padding: 6px 10px; border-radius: 5px;
    background: #2a2a2a; cursor: pointer; white-space: nowrap; }}
  .chip.active {{ outline: 2px solid #2a81cb; }}
  .chip .dot {{ display: inline-block; width: 8px; height: 8px;
    border-radius: 50%; background: #666; margin-right: 6px; }}
  .chip.hasview .dot {{ background: #5ec26a; }}
  #counter {{ position: fixed; right: 12px; bottom: 104px; z-index: 10;
    color: #aaa; }}
  #note {{ position: fixed; left: 12px; bottom: 104px; z-index: 10;
    color: #888; font-size: 12px; }}
</style>
</head>
<body>
<div id="viewer"></div>
<div id="readout">loading…</div>
<div id="savebar">
  <button id="save" type="button">Save view (Enter)</button>
  <div id="status"></div>
</div>
<div id="counter"></div>
<div id="note">Saving keeps a backup of each original beside it
(<code>*_original</code>). N/P: next/previous.</div>
<div id="strip"></div>
<script src="https://unpkg.com/pannellum@{pannellum}/build/pannellum.js"
        integrity="{pannellum_js_sri}" crossorigin=""></script>
<script>
"use strict";
const TOKEN = {token};
let files = [], idx = 0, viewer = null, saving = false;
window.__panoReady = false;
const $ = (id) => document.getElementById(id);

function norm360(d) {{ return ((d % 360) + 360) % 360; }}

function currentView() {{
  const f = files[idx];
  return {{
    heading: norm360(f.pose + viewer.getYaw()),
    pitch: Math.max(-90, Math.min(90, viewer.getPitch())),
    hfov: Math.max(10, Math.min(170, viewer.getHfov())),
  }};
}}

function renderStrip() {{
  const strip = $("strip");
  strip.textContent = "";
  files.forEach((f, i) => {{
    const chip = document.createElement("div");
    chip.className = "chip" + (i === idx ? " active" : "")
      + (f.hasView ? " hasview" : "");
    const dot = document.createElement("span");
    dot.className = "dot";
    chip.appendChild(dot);
    chip.appendChild(document.createTextNode(f.name));
    chip.addEventListener("click", () => open(i));
    strip.appendChild(chip);
  }});
  $("counter").textContent = (idx + 1) + " / " + files.length;
}}

function open(i) {{
  idx = i;
  window.__panoReady = false;
  if (viewer) {{ viewer.destroy(); viewer = null; }}
  const f = files[i];
  const cfg = {{ type: "equirectangular", panorama: "/img/" + f.index,
    autoLoad: true, minHfov: 10, maxHfov: 170, showFullscreenCtrl: false }};
  if (f.yaw !== null) cfg.yaw = f.yaw;
  if (f.pitch !== null) cfg.pitch = f.pitch;
  if (f.hfov !== null) cfg.hfov = f.hfov;
  viewer = pannellum.viewer("viewer", cfg);
  window.__viewer = viewer;
  viewer.on("load", () => {{ window.__panoReady = true; }});
  $("status").textContent = "";
  renderStrip();
}}

function readoutLoop() {{
  if (viewer && files.length) {{
    const v = currentView();
    $("readout").innerHTML =
      "<b>" + files[idx].name.replace(/[<>&]/g, "") + "</b><br>" +
      "Heading " + v.heading.toFixed(1) + "° · " +
      "Pitch " + v.pitch.toFixed(1) + "° · " +
      "FOV " + v.hfov.toFixed(1) + "°";
  }}
  requestAnimationFrame(readoutLoop);
}}

async function save() {{
  if (saving || !viewer) return;
  saving = true;
  $("save").disabled = true;
  const status = $("status");
  status.className = "";
  status.textContent = "Saving…";
  const v = currentView();
  try {{
    const resp = await fetch("/api/save", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify({{ index: files[idx].index, token: TOKEN,
        heading: v.heading, pitch: v.pitch, hfov: v.hfov }}),
    }});
    const body = await resp.json();
    if (!resp.ok) throw new Error(body.error || ("HTTP " + resp.status));
    Object.assign(files[idx], body);
    status.textContent = "Saved ✓";
    if (idx + 1 < files.length) {{
      open(idx + 1);
      $("status").textContent = "Saved ✓";
    }} else {{
      renderStrip();
      status.textContent = "Saved ✓ — all panoramas done";
    }}
  }} catch (e) {{
    status.className = "err";
    status.textContent = "Save failed: " + e.message;
  }} finally {{
    saving = false;
    $("save").disabled = false;
  }}
}}

$("save").addEventListener("click", save);
document.addEventListener("keydown", (e) => {{
  if (e.key === "Enter") {{ e.preventDefault(); save(); }}
  else if (e.key === "n" || e.key === "N") {{
    if (idx + 1 < files.length) open(idx + 1);
  }} else if (e.key === "p" || e.key === "P") {{
    if (idx > 0) open(idx - 1);
  }}
}});

fetch("/api/list").then((r) => r.json()).then((list) => {{
  files = list;
  open(0);
  readoutLoop();
}});
</script>
</body>
</html>
"""


def build_editor_page(token: str) -> str:
    """The complete editor page with *token* embedded.

    ``json.dumps`` alone leaves ``<`` intact, so a hostile token could
    close the script tag; ``\\u003c`` keeps the JS value identical while
    making breakout impossible. Real tokens are ``token_urlsafe`` output,
    but the page must be safe by construction, not by caller convention.
    """
    return _PAGE.format(
        pannellum=_PANNELLUM_VERSION,
        pannellum_css_sri=_PANNELLUM_CSS_SRI,
        pannellum_js_sri=_PANNELLUM_JS_SRI,
        token=json.dumps(token).replace("<", "\\u003c"),
    )
