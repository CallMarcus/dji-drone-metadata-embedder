"""JS/CSS/assets shared by the photo-rendering HTML map writers.

One source of truth for the photo-marker app — pins, clusters, popups,
hover previews, and the Pannellum 360° viewer — so the standalone photomap
and the combined map (#322) cannot drift apart; same contract as
:mod:`.flightmap_js` on the flight side. The snippets are plain browser JS
embedded by string substitution.

:data:`PHOTO_LAYER_JS` expects three globals to exist before it runs:
``map`` (the Leaflet map), ``esc`` (the HTML escaper), and
``photoFeatures`` (the GeoJSON ``Point`` features to render). It defines
``photoCluster``/``panoCluster``/``photoMarkers``/``panoMarkers``/
``photoLatLngs`` for the embedding template's layer control and bounds
logic. :data:`PANO_JS` is appended by templates only when panoramas are
linked, so ``pannellum`` and the overlay elements are guaranteed to exist
whenever a ``pano-open`` anchor does.
"""

from __future__ import annotations

# Pinned releases + Subresource Integrity hashes. Leaflet pins stay in the
# templates; the markercluster hashes were computed from the unpkg 1.5.3
# assets (sha256, base64) when photomap_html was written.
CLUSTER_VERSION = "1.5.3"
CLUSTER_JS_SRI = "sha256-Hk4dIpcqOSb0hZjgyvFOP+cEmDXUKKNE/tT542ZbNQg="
CLUSTER_CSS_SRI = "sha256-YU3qCpj/P06tdPBJGPax0bm6Q1wltfwjsho5TR4+TYc="
CLUSTER_DEFAULT_CSS_SRI = "sha256-YSWCMtmNZNwqex4CEw1nQhvFub2lmU7vcCKP+XVwwXA="

# Pannellum (360 panorama viewer) — same pinned+SRI CDN pattern as Leaflet.
# Emitted only when the map contains linked GPano panoramas.
PANNELLUM_VERSION = "2.5.6"
PANNELLUM_CSS_SRI = "sha256-p/HXuG8QaPIo2S8bCu+VvUHR4uEnhVFlc62/VS7ieT0="
PANNELLUM_JS_SRI = "sha256-oosvezOf0KYCxnad8dymrUOvc7yMalvmcglxUonBKpo="

PHOTO_CSS = """  .photo-popup img { max-width: 260px; height: auto; display: block; margin-bottom: 4px; }
  .photo-popup .photo-credit { opacity: .75; font-size: 90%; }
  .photo-tooltip img { max-width: 160px; height: auto; display: block; margin-bottom: 2px; }
  /* The hover-previews toggle (issue #345) borrows the layer-control card. */
  .hover-control { padding: 5px 8px; font: 12px/1.4 sans-serif; }
  .hover-control label { cursor: pointer; user-select: none; }
  /* Per-type markers (issue #283): blue dot = photo, orange dot = 360 pano.
     The same classes render the swatches in the layer-control legend, and
     the cluster tints derive from the same two custom properties. */
  :root { --pin-photo: #2a81cb; --pin-pano: #f69730; }
  .photo-pin { display: block; width: 14px; height: 14px; border-radius: 50%;
               border: 2.5px solid #fff; box-shadow: 0 0 4px rgba(0,0,0,.5);
               box-sizing: content-box; }
  .pin-photo { background: var(--pin-photo); }
  .pin-pano  { background: var(--pin-pano); }
  .pin-swatch { display: inline-block; vertical-align: -3px;
                margin-right: 2px; }
  /* Touch tap target (issue #295): the visible dot keeps its size but sits
     centered inside a larger transparent hit box on coarse pointers. */
  .pin-hit { display: flex; width: 100%; height: 100%;
             align-items: center; justify-content: center; }
  /* Both cluster tints replace markercluster's default color ramp: its
     "large" (>=100) orange is nearly identical to the pano tint, which would
     contradict the orange-means-panorama legend on dense photo maps. */
  .photo-cluster {
    background-color: color-mix(in srgb, var(--pin-photo) 40%, transparent); }
  .photo-cluster div { color: #fff;
    background-color: color-mix(in srgb, var(--pin-photo) 80%, transparent); }
  .pano-cluster {
    background-color: color-mix(in srgb, var(--pin-pano) 40%, transparent); }
  .pano-cluster div {
    background-color: color-mix(in srgb, var(--pin-pano) 80%, transparent); }"""

PANO_HEAD = (
    '<link rel="stylesheet"\n'
    f'      href="https://unpkg.com/pannellum@{PANNELLUM_VERSION}/build/pannellum.css"\n'
    f'      integrity="{PANNELLUM_CSS_SRI}" crossorigin="" />\n'
    "<style>\n"
    "  #pano-overlay { display: none; position: fixed; inset: 0; z-index: 2000;\n"
    "                  background: rgba(0,0,0,.85); }\n"
    "  #pano-viewer { position: absolute; inset: 48px 0 0 0; }\n"
    "  #pano-close { position: absolute; top: 8px; right: 16px; z-index: 2001;\n"
    "                font-size: 28px; line-height: 1; color: #fff;\n"
    "                background: none; border: none; cursor: pointer; }\n"
    "  #pano-viewer .pano-blocked { color: #fff; max-width: 32em;\n"
    "    margin: 20vh auto 0; padding: 0 1em; text-align: center;\n"
    "    font: 16px/1.6 system-ui, sans-serif; }\n"
    "</style>"
)

PANO_OVERLAY = (
    '<div id="pano-overlay">'
    '<button id="pano-close" type="button" aria-label="Close">&#10005;</button>'
    '<div id="pano-viewer"></div>'
    "</div>"
)

PANO_SCRIPT = (
    f'<script src="https://unpkg.com/pannellum@{PANNELLUM_VERSION}/build/pannellum.js"\n'
    f'        integrity="{PANNELLUM_JS_SRI}" crossorigin=""></script>'
)

# Appended to _APP_JS only when panoramas are present, so `pannellum` and the
# overlay elements are guaranteed to exist whenever a `pano-open` anchor does.
PANO_JS = """
let panoViewer = null;
const panoOverlay = document.getElementById('pano-overlay');
const panoContainer = document.getElementById('pano-viewer');
function openPano(a) {
  const src = a.getAttribute('href');
  if (panoViewer) { panoViewer.destroy(); panoViewer = null; }
  panoOverlay.style.display = 'block';
  if (location.protocol === 'file:') {
    // Browsers refuse WebGL pixel access to images on file:// pages, so the
    // viewer cannot work for maps opened straight from disk.
    panoContainer.innerHTML = '<div class="pano-blocked">' +
      '360\\u00b0 view is blocked by the browser for maps opened straight ' +
      'from disk.<br>Use the "open original" link in the popup, or rebuild ' +
      'the map with:<br><code>dji-embed photomap &lt;your folder&gt; ' +
      '--serve</code></div>';
    return;
  }
  // Reset so a previous file:// message (or dead viewer DOM) never lingers.
  panoContainer.innerHTML = '';
  // Lazy: the original file is only fetched here, on first click. Pannellum
  // renders its own error text in the container if the load fails (missing
  // file, WebGL texture limit); the popup's plain link remains the fallback.
  const cfg = { type: 'equirectangular', panorama: src, autoLoad: true };
  // Initial view (#309) and credit (#310) arrive as data- attributes.
  if (a.dataset.yaw !== undefined) cfg.yaw = Number(a.dataset.yaw);
  if (a.dataset.pitch !== undefined) cfg.pitch = Number(a.dataset.pitch);
  if (a.dataset.hfov !== undefined) cfg.hfov = Number(a.dataset.hfov);
  // Pannellum renders the author byline with innerHTML — esc() is mandatory.
  if (a.dataset.credit) cfg.author = esc(a.dataset.credit);
  panoViewer = pannellum.viewer('pano-viewer', cfg);
  // Pannellum reports every load failure as "the file could not be
  // accessed", which reads as a missing file. On older graphics hardware
  // the usual cause is a panorama too large for the GPU to hold (#471),
  // and the file is fine — say so, and point at the link that still works.
  panoViewer.on('error', msg => {
    if (panoViewer) { panoViewer.destroy(); panoViewer = null; }
    panoContainer.innerHTML = '<div class="pano-blocked">' +
      esc(msg) + '<br><br>Very large panoramas (8000\\u00a0px and wider) ' +
      'can exceed what older graphics hardware can display, even when the ' +
      'file itself is fine. The "open original" link in the popup shows ' +
      'the image itself.</div>';
  });
}
function closePano() {
  panoOverlay.style.display = 'none';
  if (panoViewer) { panoViewer.destroy(); panoViewer = null; }
}
document.getElementById('pano-close').addEventListener('click', closePano);
document.addEventListener('keydown', e => { if (e.key === 'Escape') closePano(); });
document.addEventListener('click', e => {
  const a = e.target.closest && e.target.closest('a.pano-open');
  if (a) { e.preventDefault(); openPano(a); }
});
"""

PHOTO_LAYER_JS = """// Per-type markers (issue #283): photos and 360 panoramas get their own
// colored pin and their own cluster group, so clusters stay type-pure and
// each type can be toggled independently.
const isPano = f => (f.properties || {}).pano === true;
// Touch handling (issue #295): hover is a mouse concept. On touch devices the
// first tap opened the sticky tooltip, which then covered the pin and
// swallowed the tap meant for it ("huge image of the pin icon" on iPhone).
// Capability check, not UA sniffing: no hover / coarse pointer → no hover
// tooltips, and the pin's tap target grows while the dot stays the same size.
// The click popup (whose thumbnail opens the 360 viewer) is the touch path.
const TOUCH = window.matchMedia('(hover: none), (pointer: coarse)').matches;
const PIN_BOX = TOUCH ? 34 : 19;
const pinIcon = cls => L.divIcon({
  className: '',
  html: `<span class="pin-hit"><span class="photo-pin ${cls}"></span></span>`,
  iconSize: [PIN_BOX, PIN_BOX], iconAnchor: [PIN_BOX / 2, PIN_BOX / 2],
  popupAnchor: [0, -PIN_BOX / 2]
});
const photoIcon = pinIcon('pin-photo');
const panoIcon = pinIcon('pin-pano');
// The two groups cluster independently, so a photo blob and a pano blob can
// land on the exact same point (routine with --redact fuzz, which rounds
// both types to the same 3-decimal grid). Anchoring the pano blob slightly
// off-center keeps the photo blob underneath visible and clickable instead
// of fully occluded.
const PANO_CLUSTER_ANCHOR = L.point(31, 31);
// Mirrors markercluster's default icon (count + small/medium/large sizing)
// with a per-type color scheme (see the .photo-cluster/.pano-cluster CSS).
const clusterIcon = (cls, anchor) => c => {
  const n = c.getChildCount();
  const size = n < 10 ? 'small' : n < 100 ? 'medium' : 'large';
  return L.divIcon({
    html: `<div><span>${n}</span></div>`,
    className: `marker-cluster marker-cluster-${size} ${cls}`,
    iconSize: L.point(40, 40), iconAnchor: anchor
  });
};
const photoCluster = L.markerClusterGroup({
  chunkedLoading: true, iconCreateFunction: clusterIcon('photo-cluster') });
const panoCluster = L.markerClusterGroup({
  chunkedLoading: true,
  iconCreateFunction: clusterIcon('pano-cluster', PANO_CLUSTER_ANCHOR) });
const photoMarkers = [];
const panoMarkers = [];
const photoLatLngs = [];

// #472: thumbnails are data URIs and still decode async, so Leaflet measures
// the popup before the image has a size. Declaring the known pixel size up
// front makes that pre-decode layout (and the tip anchor) correct; thumbs
// without parsed dimensions fall back to the bare tag.
function imgDims(p) {
  return (typeof p.tw === 'number' && typeof p.th === 'number')
    ? ` width="${p.tw}" height="${p.th}"` : '';
}

function buildPopup(f) {
  const p = f.properties || {};
  let inner = '';
  if (p.thumb) {
    // Honest thumbnails (#441): a square opening-view crop and the full
    // 2:1 strip look nothing alike — the title says which one this is.
    const kind = p.vthumb ? 'Opening view of the panorama'
      : (p.pano ? 'Full 360° panorama' : '');
    inner += `<img src="data:image/jpeg;base64,${esc(p.thumb)}" alt=""` +
      imgDims(p) + (kind ? ` title="${kind}"` : '') + `>`;
  }
  // Every text line is presence-guarded: --popup-fields (issue #296) strips
  // properties from the embedded data, so nothing here may assume one exists.
  if (p.name) inner += `<b>${esc(p.name)}</b>`;
  let html = '<div class="photo-popup">';
  if (p.link && p.pano) {
    // GPano panorama: the thumbnail/name click opens the embedded 360 viewer
    // (see _PANO_JS); a plain "open original" link is appended below. The
    // pano's initial view (#309) and credit (#310) ride along as data-
    // attributes for openPano. yaw/pitch/hfov are numbers straight from the
    // embedded JSON, never strings.
    let attrs = '';
    if (typeof p.yaw === 'number') attrs += ` data-yaw="${p.yaw}"`;
    if (typeof p.pitch === 'number') attrs += ` data-pitch="${p.pitch}"`;
    if (typeof p.hfov === 'number') attrs += ` data-hfov="${p.hfov}"`;
    if (p.credit) attrs += ` data-credit="${esc(p.credit)}"`;
    html += `<a href="${esc(p.link)}" class="pano-open"${attrs}>${inner}</a>`;
  } else if (p.link) {
    // Opt-in (--link-originals): thumbnail + filename open the original file.
    html += `<a href="${esc(p.link)}" target="_blank" rel="noopener">${inner}</a>`;
  } else {
    html += inner;
  }
  if (p.timestamp) html += `<br>${esc(p.timestamp)}`;
  if (p.camera) html += `<br>${esc(p.camera)}`;
  if (p.link && p.pano) {
    html += `<br><a href="${esc(p.link)}" target="_blank" rel="noopener">open original</a>`;
  }
  if (p.alt !== undefined) html += `<br>altitude: ${Number(p.alt).toFixed(0)} m`;
  if (p.credit) html += `<br><span class="photo-credit">${esc(p.credit)}</span>`;
  html += '</div>';
  return html;
}

// Hover preview (issue #273): thumbnail + filename in a sticky tooltip so a
// map can be skimmed without clicking every pin. Thumb-less points fall back
// to a filename-only tooltip.
function buildTooltip(f) {
  const p = f.properties || {};
  let html = '<div class="photo-tooltip">';
  if (p.thumb) {
    html += `<img src="data:image/jpeg;base64,${esc(p.thumb)}" alt=""${imgDims(p)}>`;
  }
  html += `${esc(p.name || '')}</div>`;
  return html;
}

// Hover previews are opt-in (issue #345): as the default they added a second
// interaction before the popup's details and link. A small control (mouse
// devices only — touch never had tooltips, #295) restores #273's skimming
// tooltips, and the choice is remembered per browser. localStorage can throw
// (Safari private mode, file://), so failing to remember is silent.
const HOVER_KEY = 'djiembed-photomap-hover';
const readHoverPref = () => {
  try { return localStorage.getItem(HOVER_KEY) === '1'; } catch (e) { return false; }
};
const writeHoverPref = on => {
  try { localStorage.setItem(HOVER_KEY, on ? '1' : '0'); } catch (e) {}
};
const allMarkers = [];
function setHoverPreviews(on) {
  for (const [marker, f] of allMarkers) {
    if (on) {
      marker.bindTooltip(() => buildTooltip(f), { sticky: true, direction: 'top' });
    } else {
      marker.unbindTooltip();
    }
  }
}

for (const f of photoFeatures) {
  const c = f.geometry.coordinates;                  // [lon, lat, alt]
  photoLatLngs.push([c[1], c[0]]);
  const pano = isPano(f);
  const marker = L.marker([c[1], c[0]], { icon: pano ? panoIcon : photoIcon })
    .bindPopup(() => buildPopup(f), { maxWidth: 300 });
  allMarkers.push([marker, f]);
  (pano ? panoMarkers : photoMarkers).push(marker);
}
photoCluster.addLayers(photoMarkers);
panoCluster.addLayers(panoMarkers);
if (photoMarkers.length) map.addLayer(photoCluster);
if (panoMarkers.length) map.addLayer(panoCluster);

// #472 belt-and-braces: a thumbnail that finishes decoding after the popup
// opened (no declared dimensions, or a cache-cold decode) re-runs the popup's
// layout pass so the box and tip anchor match the real content size.
map.on('popupopen', e => {
  const img = e.popup.getElement().querySelector('.photo-popup img');
  if (img && !img.complete) {
    img.addEventListener('load', () => e.popup.update(), { once: true });
  }
});
if (!TOUCH) {
  const HoverControl = L.Control.extend({
    onAdd() {
      const div = L.DomUtil.create(
        'div', 'leaflet-control-layers hover-control');
      div.innerHTML =
        '<label><input type="checkbox" id="hover-toggle"> Hover previews</label>';
      // Without this, a click on the checkbox also pans/zooms the map.
      L.DomEvent.disableClickPropagation(div);
      return div;
    }
  });
  new HoverControl({ position: 'topright' }).addTo(map);
  const hoverToggle = document.getElementById('hover-toggle');
  hoverToggle.checked = readHoverPref();
  if (hoverToggle.checked) setHoverPreviews(true);
  hoverToggle.addEventListener('change', () => {
    setHoverPreviews(hoverToggle.checked);
    writeHoverPref(hoverToggle.checked);
  });
}"""
