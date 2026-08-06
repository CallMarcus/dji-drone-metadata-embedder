"""JS for the --airspace zone volumes on the 3D flightmap (#424).

Same contract as :mod:`.flightmap3d_gaze_js`: plain browser JS embedded by
string substitution, appended at the END of the 3D app so ``map``,
``terrainElevAt`` and the flights panel exist. It registers its own
``load`` listener; the app's own listener is registered first, so by the
time this one runs the panel is built and the airspace toggle can append
to it.

Volumes state published data and make no determination: one neutral
colour, restriction class in the popup only, entered-zone emphasis by
opacity (a fact the evaluator established, not a verdict).

Heights: fill-extrusion prisms are measured from the rendered terrain
surface, so an AGL ceiling is exact by construction. An AMSL ceiling
subtracts the surface elevation sampled at the centroid of each of the zone's polygon parts —
constant per part, so the volume top follows the terrain instead of
sitting flat at the published altitude; a panel note discloses that, and
the popup always states the published limit verbatim. With terrain off or
failed, extrusion measures from sea level, where AMSL is again exact and
AGL is the flat view's known approximation. A zone with no stated ceiling
(or a computed height at/below the surface, where fill-extrusion cannot
draw) renders as a draped footprint — never an invented volume.

Cold DEM tiles read as elevation 0 (see sculptSettle), so AMSL heights
re-sample on the same bounded-timer pattern once terrain firms up.
"""

from __future__ import annotations

from .flightmap_airspace_js import AIRSPACE_POPUP_JS

AIRSPACE_3D_JS = AIRSPACE_POPUP_JS + """\
const airspace = JSON.parse(document.getElementById('airspace-data').textContent);
const AIRSPACE_COLOR = '#4a6a8a';
const airspaceState = { on: true };

function zoneCentroid(ring) {
  // Vertex mean of the exterior ring (closed: first point repeats last,
  // so skip the closer) — enough precision for a disclosed approximation.
  const n = ring.length > 1 ? ring.length - 1 : ring.length;
  let x = 0, y = 0;
  for (let i = 0; i < n; i++) { x += ring[i][0]; y += ring[i][1]; }
  return [x / n, y / n];
}

function zoneHeightM(z, centroid) {
  if (z.upper_ref !== 'AMSL') return z.upper_m;
  const e = terrainElevAt(centroid);
  return e == null ? z.upper_m : z.upper_m - e;
}

function airspaceFeatures() {
  const vol = [], flat = [];
  airspace.zones.forEach((z, zi) => {
    z.polygons.forEach(ring => {
      // Zone-level holes attach to every exterior — same convention as
      // the 2D map and the evaluator's hole subtraction (#422).
      const geom = { type: 'Polygon',
                     coordinates: [ring].concat(z.holes || []) };
      const props = { zi: zi, entered: z.entered.length > 0 };
      if (z.upper_m != null) {
        const hgt = zoneHeightM(z, zoneCentroid(ring));
        if (hgt > 0) {
          props.hgt = hgt;
          vol.push({ type: 'Feature', properties: props, geometry: geom });
          return;
        }
        // Ceiling at/below the rendered surface: fill-extrusion cannot
        // draw there — fall through to the footprint; the popup still
        // states the published limit.
      }
      flat.push({ type: 'Feature', properties: props, geometry: geom });
    });
  });
  return { vol: vol, flat: flat };
}

function setAirspaceData() {
  const f = airspaceFeatures();
  const v = map.getSource('airspace-vol');
  if (v) v.setData({ type: 'FeatureCollection', features: f.vol });
  const s = map.getSource('airspace-flat');
  if (s) s.setData({ type: 'FeatureCollection', features: f.flat });
}

function applyAirspaceVisibility() {
  const v = airspaceState.on ? 'visible' : 'none';
  ['airspace-volume', 'airspace-volume-entered', 'airspace-footprint']
    .forEach(id => {
      if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', v);
    });
}

function hasAmslVolume() {
  return airspace.zones.some(
    z => z.upper_m != null && z.upper_ref === 'AMSL');
}

function airspaceSettle() {
  // Cold DEM tiles answer elevation 0, so the first AMSL height pass can
  // be sea-level based. Bounded retry, same shape as sculptSettle — and a
  // genuine sea-level zone simply settles on the final pass.
  if (!(map.getTerrain && map.getTerrain())) return;
  const amsl = airspace.zones.find(
    z => z.upper_m != null && z.upper_ref === 'AMSL');
  if (!amsl) return;
  const probe = zoneCentroid(amsl.polygons[0]);
  let tries = 20;
  const retry = () => {
    const e = terrainElevAt(probe);
    if ((typeof e === 'number' && e !== 0) || --tries <= 0) {
      setAirspaceData();
      return;
    }
    setTimeout(retry, 250);
  };
  setTimeout(retry, 250);
}

function mountAirspacePanel() {
  const panel = document.getElementById('flights-panel');
  if (!panel) return;
  if (airspace.covered) {
    // Toggle registered even for an empty fetch: "fetched and empty"
    // must stay distinguishable from "never fetched" (2D parity).
    panel.appendChild(document.createElement('hr'));
    const label = document.createElement('label');
    const box = document.createElement('input');
    box.type = 'checkbox';
    box.id = 'airspace-toggle';
    box.checked = airspaceState.on;
    box.addEventListener('change', () => {
      airspaceState.on = box.checked;
      applyAirspaceVisibility();
    });
    label.appendChild(box);
    label.appendChild(document.createTextNode(' Airspace zones'));
    panel.appendChild(label);
  }
  const notes = airspace.notes.slice();
  if (hasAmslVolume()) {
    notes.push('AMSL ceiling volumes are approximated from the terrain ' +
               'elevation at each zone centre; popups state the ' +
               'published limits.');
  }
  if (notes.length) {
    const div = document.createElement('div');
    div.className = 'panel-note';
    div.id = 'airspace-notes';
    notes.forEach(n => {
      const line = document.createElement('div');
      line.textContent = n;
      div.appendChild(line);
    });
    panel.appendChild(div);
  }
}

if (map) {
  map.on('load', () => {
    const f = airspaceFeatures();
    map.addSource('airspace-vol', { type: 'geojson',
      data: { type: 'FeatureCollection', features: f.vol } });
    map.addSource('airspace-flat', { type: 'geojson',
      data: { type: 'FeatureCollection', features: f.flat } });
    // Two volume layers on one source: fill-extrusion-opacity is
    // layer-level only (the sculpture documents why), so the entered
    // emphasis needs a filtered twin, not a data-driven expression.
    map.addLayer({ id: 'airspace-volume', type: 'fill-extrusion',
      source: 'airspace-vol', filter: ['!', ['get', 'entered']],
      paint: { 'fill-extrusion-color': AIRSPACE_COLOR,
               'fill-extrusion-base': 0,
               'fill-extrusion-height': ['get', 'hgt'],
               'fill-extrusion-opacity': 0.25,
               'fill-extrusion-vertical-gradient': false } });
    map.addLayer({ id: 'airspace-volume-entered', type: 'fill-extrusion',
      source: 'airspace-vol', filter: ['get', 'entered'],
      paint: { 'fill-extrusion-color': AIRSPACE_COLOR,
               'fill-extrusion-base': 0,
               'fill-extrusion-height': ['get', 'hgt'],
               'fill-extrusion-opacity': 0.4,
               'fill-extrusion-vertical-gradient': false } });
    map.addLayer({ id: 'airspace-footprint', type: 'fill',
      source: 'airspace-flat',
      paint: { 'fill-color': AIRSPACE_COLOR,
               'fill-opacity': ['case', ['get', 'entered'], 0.3, 0.15] } });
    ['airspace-volume', 'airspace-volume-entered', 'airspace-footprint']
      .forEach(id => {
        map.on('click', id, ev => {
          const z = airspace.zones[ev.features[0].properties.zi];
          const el = document.createElement('div');
          el.innerHTML = zonePopupHtml(z);
          new maplibregl.Popup({ maxWidth: '320px' })
            .setLngLat(ev.lngLat).setDOMContent(el).addTo(map);
        });
        map.on('mouseenter', id, () => {
          map.getCanvas().style.cursor = 'pointer';
        });
        map.on('mouseleave', id, () => {
          map.getCanvas().style.cursor = '';
        });
      });
    mountAirspacePanel();
    airspaceSettle();
  });
}
"""
