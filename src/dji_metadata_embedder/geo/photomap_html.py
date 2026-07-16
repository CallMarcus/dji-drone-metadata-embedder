"""Render a photo list as a standalone, self-contained HTML map.

Same contract as :mod:`.html_viewer`: the photo GeoJSON (with base64 EXIF
thumbnails) is embedded in a ``<script type="application/json">`` block and a
small vanilla Leaflet app renders it. Markers are clustered with
Leaflet.markercluster so archive-scale folders (many shots per church, many
churches) stay readable. Leaflet, the cluster plugin, and the OpenStreetMap
basemap load from the network; the photo data itself is embedded.
Linked GPano panoramas additionally pull in Pannellum (same pinned+SRI
pattern) for an in-page 360° viewer.
"""

from __future__ import annotations

import json
import logging
from html import escape
from pathlib import Path

from .photomap import PhotoPoint, photos_to_geojson

logger = logging.getLogger(__name__)

# Pinned releases + Subresource Integrity hashes. Leaflet pins match
# html_viewer.py; the markercluster hashes were computed from the unpkg 1.5.3
# assets (sha256, base64) when this module was written.
_LEAFLET_VERSION = "1.9.4"
_LEAFLET_CSS_SRI = "sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
_LEAFLET_JS_SRI = "sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
_CLUSTER_VERSION = "1.5.3"
_CLUSTER_JS_SRI = "sha256-Hk4dIpcqOSb0hZjgyvFOP+cEmDXUKKNE/tT542ZbNQg="
_CLUSTER_CSS_SRI = "sha256-YU3qCpj/P06tdPBJGPax0bm6Q1wltfwjsho5TR4+TYc="
_CLUSTER_DEFAULT_CSS_SRI = "sha256-YSWCMtmNZNwqex4CEw1nQhvFub2lmU7vcCKP+XVwwXA="

# Pannellum (360 panorama viewer) — same pinned+SRI CDN pattern as Leaflet.
# Emitted only when the map contains linked GPano panoramas.
_PANNELLUM_VERSION = "2.5.6"
_PANNELLUM_CSS_SRI = "sha256-p/HXuG8QaPIo2S8bCu+VvUHR4uEnhVFlc62/VS7ieT0="
_PANNELLUM_JS_SRI = "sha256-oosvezOf0KYCxnad8dymrUOvc7yMalvmcglxUonBKpo="

_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Photo map — {title}</title>
<!-- Leaflet + markercluster + OpenStreetMap tiles load from the network;
     the photo data (incl. thumbnails) is embedded below. -->
<link rel="stylesheet"
      href="https://unpkg.com/leaflet@{leaflet}/dist/leaflet.css"
      integrity="{leaflet_css_sri}" crossorigin="" />
<link rel="stylesheet"
      href="https://unpkg.com/leaflet.markercluster@{cluster}/dist/MarkerCluster.css"
      integrity="{cluster_css_sri}" crossorigin="" />
<link rel="stylesheet"
      href="https://unpkg.com/leaflet.markercluster@{cluster}/dist/MarkerCluster.Default.css"
      integrity="{cluster_default_css_sri}" crossorigin="" />
{pano_head}
<style>
  html, body {{ height: 100%; margin: 0; }}
  #map {{ height: 100%; }}
  .photo-popup img {{ max-width: 260px; display: block; margin-bottom: 4px; }}
  .photo-tooltip img {{ max-width: 160px; display: block; margin-bottom: 2px; }}
  /* Per-type markers (issue #283): blue dot = photo, orange dot = 360 pano.
     The same classes render the swatches in the layer-control legend, and
     the cluster tints derive from the same two custom properties. */
  :root {{ --pin-photo: #2a81cb; --pin-pano: #f69730; }}
  .photo-pin {{ display: block; width: 14px; height: 14px; border-radius: 50%;
               border: 2.5px solid #fff; box-shadow: 0 0 4px rgba(0,0,0,.5);
               box-sizing: content-box; }}
  .pin-photo {{ background: var(--pin-photo); }}
  .pin-pano  {{ background: var(--pin-pano); }}
  .pin-swatch {{ display: inline-block; vertical-align: -3px;
                margin-right: 2px; }}
  /* Touch tap target (issue #295): the visible dot keeps its size but sits
     centered inside a larger transparent hit box on coarse pointers. */
  .pin-hit {{ display: flex; width: 100%; height: 100%;
             align-items: center; justify-content: center; }}
  /* Both cluster tints replace markercluster's default color ramp: its
     "large" (>=100) orange is nearly identical to the pano tint, which would
     contradict the orange-means-panorama legend on dense photo maps. */
  .photo-cluster {{
    background-color: color-mix(in srgb, var(--pin-photo) 40%, transparent); }}
  .photo-cluster div {{ color: #fff;
    background-color: color-mix(in srgb, var(--pin-photo) 80%, transparent); }}
  .pano-cluster {{
    background-color: color-mix(in srgb, var(--pin-pano) 40%, transparent); }}
  .pano-cluster div {{
    background-color: color-mix(in srgb, var(--pin-pano) 80%, transparent); }}
</style>
</head>
<body>
<div id="map"></div>
{pano_overlay}
<script type="application/json" id="photo-data">
{data}
</script>
<script src="https://unpkg.com/leaflet@{leaflet}/dist/leaflet.js"
        integrity="{leaflet_js_sri}" crossorigin=""></script>
<script src="https://unpkg.com/leaflet.markercluster@{cluster}/dist/leaflet.markercluster.js"
        integrity="{cluster_js_sri}" crossorigin=""></script>
{pano_scripts}
<script>
{app_js}
</script>
</body>
</html>
"""

_PANO_HEAD = (
    '<link rel="stylesheet"\n'
    f'      href="https://unpkg.com/pannellum@{_PANNELLUM_VERSION}/build/pannellum.css"\n'
    f'      integrity="{_PANNELLUM_CSS_SRI}" crossorigin="" />\n'
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

_PANO_OVERLAY = (
    '<div id="pano-overlay">'
    '<button id="pano-close" type="button" aria-label="Close">&#10005;</button>'
    '<div id="pano-viewer"></div>'
    "</div>"
)

_PANO_SCRIPT = (
    f'<script src="https://unpkg.com/pannellum@{_PANNELLUM_VERSION}/build/pannellum.js"\n'
    f'        integrity="{_PANNELLUM_JS_SRI}" crossorigin=""></script>'
)

# Appended to _APP_JS only when panoramas are present, so `pannellum` and the
# overlay elements are guaranteed to exist whenever a `pano-open` anchor does.
_PANO_JS = """
let panoViewer = null;
const panoOverlay = document.getElementById('pano-overlay');
const panoContainer = document.getElementById('pano-viewer');
function openPano(src) {
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
  panoViewer = pannellum.viewer('pano-viewer', {
    type: 'equirectangular', panorama: src, autoLoad: true
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
  if (a) { e.preventDefault(); openPano(a.getAttribute('href')); }
});
"""


_APP_JS = """
const data = JSON.parse(document.getElementById('photo-data').textContent);
const map = L.map('map');
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

const esc = s => String(s).replace(/[&<>"']/g,
  ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));

const points = (data.features || []).filter(
  f => f.geometry && f.geometry.type === 'Point');

// Per-type markers (issue #283): photos and 360 panoramas get their own
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
const latlngs = [];

function buildPopup(f) {
  const p = f.properties || {};
  let inner = '';
  if (p.thumb) {
    inner += `<img src="data:image/jpeg;base64,${esc(p.thumb)}" alt="">`;
  }
  inner += `<b>${esc(p.name || '')}</b>`;
  let html = '<div class="photo-popup">';
  if (p.link && p.pano) {
    // GPano panorama: the thumbnail/name click opens the embedded 360 viewer
    // (see _PANO_JS); a plain "open original" link is appended below.
    html += `<a href="${esc(p.link)}" class="pano-open">${inner}</a>`;
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
  html += `<br>altitude: ${Number(p.alt || 0).toFixed(0)} m</div>`;
  return html;
}

// Hover preview (issue #273): thumbnail + filename in a sticky tooltip so a
// map can be skimmed without clicking every pin. Thumb-less points fall back
// to a filename-only tooltip. Bound only when the device really hovers
// (issue #295) — on touch the tooltip hijacked the first tap and hid the pin.
function buildTooltip(f) {
  const p = f.properties || {};
  let html = '<div class="photo-tooltip">';
  if (p.thumb) {
    html += `<img src="data:image/jpeg;base64,${esc(p.thumb)}" alt="">`;
  }
  html += `${esc(p.name || '')}</div>`;
  return html;
}

for (const f of points) {
  const c = f.geometry.coordinates;                  // [lon, lat, alt]
  latlngs.push([c[1], c[0]]);
  const pano = isPano(f);
  const marker = L.marker([c[1], c[0]], { icon: pano ? panoIcon : photoIcon })
    .bindPopup(() => buildPopup(f), { maxWidth: 300 });
  if (!TOUCH) {
    marker.bindTooltip(() => buildTooltip(f), { sticky: true, direction: 'top' });
  }
  (pano ? panoMarkers : photoMarkers).push(marker);
}
photoCluster.addLayers(photoMarkers);
panoCluster.addLayers(panoMarkers);
if (photoMarkers.length) map.addLayer(photoCluster);
if (panoMarkers.length) map.addLayer(panoCluster);
if (photoMarkers.length && panoMarkers.length) {
  // Expanded control doubles as the legend: the labels reuse the pin CSS as
  // colored swatches. Only shown when the folder actually mixes types.
  L.control.layers(null, {
    '<span class="photo-pin pin-photo pin-swatch"></span>Photos': photoCluster,
    '<span class="photo-pin pin-pano pin-swatch"></span>360° panoramas':
      panoCluster
  }, { collapsed: false }).addTo(map);
}
if (latlngs.length > 1) {
  map.fitBounds(L.latLngBounds(latlngs).pad(0.1), { maxZoom: 17 });
} else if (latlngs.length === 1) {
  map.setView(latlngs[0], 16);
} else {
  map.setView([0, 0], 2);
}
"""


def photos_to_html(
    points: list[PhotoPoint], title: str, *, link_base: str | None = None
) -> str:
    """Return a complete self-contained HTML photo map.

    ``link_base`` (issue #253): when not ``None``, popups link the thumbnail
    and filename to the original photo file — ``""`` means the originals sit
    beside the HTML, otherwise a folder/URL prefix. Such links only resolve
    while the originals stay reachable; the default (``None``) keeps the map
    fully self-contained. GPano panoramas always render as distinct,
    toggleable orange markers (issue #283); the embedded Pannellum 360°
    viewer additionally activates when links are enabled.
    """
    geojson = photos_to_geojson(
        points, include_thumbnails=True, link_base=link_base
    )
    # Escape "<" to "\\u003c" (a JSON Unicode escape) so JSON.parse round-trips
    # it while no literal "</script>" can break out of the data block.
    data = json.dumps(geojson).replace("<", "\\u003c")
    pano_enabled = link_base is not None and any(p.is_pano for p in points)
    return _TEMPLATE.format(
        title=escape(title),
        leaflet=_LEAFLET_VERSION,
        leaflet_css_sri=_LEAFLET_CSS_SRI,
        leaflet_js_sri=_LEAFLET_JS_SRI,
        cluster=_CLUSTER_VERSION,
        cluster_css_sri=_CLUSTER_CSS_SRI,
        cluster_default_css_sri=_CLUSTER_DEFAULT_CSS_SRI,
        cluster_js_sri=_CLUSTER_JS_SRI,
        data=data,
        pano_head=_PANO_HEAD if pano_enabled else "",
        pano_overlay=_PANO_OVERLAY if pano_enabled else "",
        pano_scripts=_PANO_SCRIPT if pano_enabled else "",
        app_js=_APP_JS + (_PANO_JS if pano_enabled else ""),
    )


def write_photos_html(
    points: list[PhotoPoint],
    output_path: Path,
    title: str,
    *,
    link_base: str | None = None,
) -> Path:
    """Write *points* as an HTML map to *output_path* and return it."""
    output_path.write_text(
        photos_to_html(points, title, link_base=link_base), encoding="utf-8"
    )
    logger.info("HTML photo map created: %s", output_path)
    return output_path
