"""JS helpers shared by the 2D and 3D flightmap HTML writers.

One source of truth for the popup renderer and track palette so the two
templates cannot drift apart. The snippet is plain browser JS embedded by
string concatenation — it must stay dependency-free and must not reference
Leaflet or MapLibre.
"""

from __future__ import annotations

FLIGHT_POPUP_JS = """const esc = s => String(s).replace(/[&<>"']/g,
  ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));

// 12 visually distinct track colours, cycled when a folder has more flights.
const PALETTE = ['#e6194b', '#3cb44b', '#4363d8', '#f58231', '#911eb4',
                 '#42d4f4', '#f032e6', '#bfef45', '#469990', '#9a6324',
                 '#800000', '#000075'];

function fmtDuration(total) {
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const mm = h ? String(m).padStart(2, '0') : String(m);
  return (h ? h + ':' + mm : mm) + ':' + String(s).padStart(2, '0');
}

function popupHtml(p) {
  let html = `<div class="flight-popup"><b>${esc(p.name || '')}</b>`;
  if (p.start) html += `<br>${esc(p.start)}`;
  if (p.duration_s != null) html += `<br>duration: ${fmtDuration(p.duration_s)}`;
  if (p.height_min != null) {
    html += `<br>height: ${p.height_min} to ${p.height_max} m above takeoff`;
  } else if (p.alt_min != null) {
    html += `<br>altitude: ${p.alt_min} to ${p.alt_max} m (as logged)`;
  }
  html += `<br>${p.points} GPS point${p.points === 1 ? '' : 's'}`;
  if (p.segments) {
    html += `<br>recorded across ${p.segments.length} files: ` +
            `${esc(p.segments[0])} → ${esc(p.segments[p.segments.length - 1])}`;
  }
  html += '</div>';
  return html;
}"""
