"""JS for the --airspace zone overlay on the 2D flightmap (#413 PR 2).

Same contract as :mod:`.flightmap_js`: plain browser JS embedded by string
substitution. This snippet is injected into the 2D app BETWEEN the flight
loop and the fitBounds/layer-control block, so it can rely on ``map``,
``overlays`` and ``esc`` existing, zones registered here appear in the
same layer control, and ``bringToBack()`` puts them under the tracks that
were just added. One neutral style for every zone — the published
restriction class is popup data, not a color: this map states facts and
makes no determination.
"""

from __future__ import annotations

AIRSPACE_OVERLAY_JS = """\
const airspace = JSON.parse(document.getElementById('airspace-data').textContent);

function zonePopupHtml(z) {
  let html = `<div class="flight-popup"><b>${esc(z.name)}</b>`;
  if (z.id && z.id !== z.name) html += `<br>${esc(z.id)}`;
  html += `<br>${esc(z.restriction)}`;
  html += `<br>upper limit: ${z.upper ? esc(z.upper) : 'not stated'}`;
  html += `<br>lower limit: ${z.lower ? esc(z.lower) : 'not stated'}`;
  html += z.applicability.length
    ? `<br>applies: ${z.applicability.map(esc).join('; ')}`
    : '<br>applies: permanently';
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
  html += `<hr>${esc(z.source.feed)} — ${esc(z.source.license)}` +
          `<br>fetched ${esc(z.source.fetched)}`;
  html += '</div>';
  return html;
}

const zoneGroup = L.layerGroup();
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
    L.polygon(rings.map(r => r.map(c => [c[1], c[0]])), style)
      .bindPopup(zonePopupHtml(z)).addTo(zoneGroup);
  });
});
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
