"""JS for the --airspace zone overlay on the 2D flightmap (#413 PR 2).

Same contract as :mod:`.flightmap_js`: plain browser JS embedded by string
substitution. This snippet is injected into the 2D app BETWEEN the flight
loop and the fitBounds/layer-control block, so it can rely on ``map``,
``overlays`` and ``esc`` existing, zones registered here appear in the
same layer control, and ``bringToBack()`` puts them under the tracks that
were just added. One neutral style for every zone — the published
restriction class is popup data, not a color: this map states facts and
makes no determination.

``AIRSPACE_POPUP_JS`` (the popup builder alone) is shared with the 3D
map's :mod:`.flightmap3d_airspace_js` (#424): both maps must show the
same published facts for the same zone.

Ceiling labels (#424) are zoom-gated: a metro-area FAA grid is 300+
cells, so below ``AIRSPACE_LABEL_MIN_ZOOM`` the labels come off rather
than shout over the map.
"""

from __future__ import annotations

AIRSPACE_POPUP_JS = """\
function zonePopupHtml(z) {
  let html = `<div class="flight-popup"><b>${esc(z.name)}</b>`;
  if (z.id && z.id !== z.name) html += `<br>${esc(z.id)}`;
  html += `<br>${esc(z.restriction)}`;
  html += `<br>upper limit: ${z.upper ? esc(z.upper) : 'not stated'}`;
  html += `<br>lower limit: ${z.lower ? esc(z.lower) : 'not stated'}`;
  html += z.applicability.length
    ? `<br>applies: ${z.applicability.map(esc).join('; ')}`
    : '<br>applies: permanently';
  // #503: activation status/schedule as the feed published it. The
  // evaluator never read these (they are not machine-evaluable), and the
  // label says so — a part-time danger area still counts as entered.
  if (z.activation && z.activation.length)
    html += `<br><i>activation (published, not evaluated): ` +
            `${z.activation.map(esc).join('; ')}</i>`;
  // #565: the publisher's own free text (exceptions, contacts, reasons),
  // verbatim; the evaluator never read it and the label says so.
  if (z.notes && z.notes.length)
    html += `<br><i>published, not evaluated: ` +
            `${z.notes.map(esc).join('; ')}</i>`;
  for (const e of z.entered) {
    html += `<hr><b>${esc(e.flight)}</b> was inside this zone`;
    html += e.entry_utc
      ? `<br>${esc(e.entry_utc)} – ${esc(e.exit_utc)}`
      : '<br>(times not stated)';
    if (e.max_rel_alt_m != null)
      html += `<br>max height in zone: ${e.max_rel_alt_m} m above takeoff`;
    if (e.max_amsl_m != null)
      html += `<br>max altitude in zone: ${e.max_amsl_m} m (as logged)`;
    if (e.time_note) html += `<br><i>${esc(e.time_note)}</i>`;
  }
  html += `<hr>${esc(z.source.feed)} — ${esc(z.source.license)}`;
  if (z.source.effective) html += `<br>effective ${esc(z.source.effective)}`;
  html += `<br>fetched ${esc(z.source.fetched)}`;
  html += '</div>';
  return html;
}
"""

AIRSPACE_OVERLAY_JS = AIRSPACE_POPUP_JS + """\
const airspace = JSON.parse(document.getElementById('airspace-data').textContent);
const AIRSPACE_LABEL_MIN_ZOOM = 11;

const zoneGroup = L.layerGroup();
const labeledPolys = [];
airspace.zones.forEach(z => {
  const entered = z.entered.length > 0;
  const style = { color: '#4a6a8a', weight: entered ? 3 : 1.5,
                  fillColor: '#4a6a8a', fillOpacity: entered ? 0.15 : 0.08 };
  z.polygons.forEach(ring => {
    // Subsequent rings render as holes (Leaflet native), keeping the map
    // consistent with the evaluator's hole subtraction (#422). Zone-level
    // holes attach to every exterior — right for single-volume zones,
    // which is every zone either live feed publishes today.
    const rings = [ring].concat(z.holes || []);
    const poly = L.polygon(rings.map(r => r.map(c => [c[1], c[0]])), style)
      .bindPopup(zonePopupHtml(z)).addTo(zoneGroup);
    // Only a STATED ceiling earns a label — an unlabelled zone still has
    // its "not stated" popup, and a label must never invent a limit.
    if (z.upper) labeledPolys.push({ poly: poly, text: z.upper });
  });
});
function syncZoneLabels() {
  const show = map.getZoom() >= AIRSPACE_LABEL_MIN_ZOOM;
  labeledPolys.forEach(lp => {
    if (show && !lp.poly.getTooltip()) {
      // esc() pins the invariant: label text must never reach the DOM
      // unescaped, even though today's VerticalLimit.label() emits only
      // number+unit+datum.
      lp.poly.bindTooltip(esc(lp.text),
        { permanent: true, direction: 'center',
          className: 'airspace-label' });
    } else if (!show && lp.poly.getTooltip()) {
      lp.poly.unbindTooltip();
    }
  });
}
if (labeledPolys.length) {
  // Runs once now (harmless before the view is set: getZoom() is NaN and
  // compares false) and again after fitBounds/setView fires zoomend.
  map.on('zoomend', syncZoneLabels);
  syncZoneLabels();
}
if (airspace.covered) {
  // Registered even when empty: "fetched and empty" must stay
  // distinguishable from "never fetched".
  zoneGroup.addTo(map);
  zoneGroup.eachLayer(l => l.bringToBack());
  overlays['<span style="color:#4a6a8a">&#9632;</span> Airspace zones'] = zoneGroup;
}
if (airspace.notes.length) {
  const note = L.control({ position: 'bottomright' });
  note.onAdd = () => {
    const div = L.DomUtil.create('div', 'airspace-note');
    div.innerHTML = airspace.notes.map(esc).join('<br>');
    L.DomEvent.disableClickPropagation(div);
    return div;
  };
  note.addTo(map);
}
"""
