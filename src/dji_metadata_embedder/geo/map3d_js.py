"""MapLibre photo layer for the combined map's 3D page (#514).

``PHOTO_3D_JS`` is spliced into the 3D template's ``__PHOTO_3D_JS__`` slot
after the loader has filled ``photoFeatures``. It reassigns the two
``photoHooks`` the template always defines (``addLayers`` on map load,
``panelRows`` while the layer panel is built) and is a no-op when the page
carries no photo features. Popup HTML comes from the shared
``PHOTO_POPUP_JS`` (``buildPopup``), spliced in ahead of this block by
:func:`~.map_html.mixed_to_3d_html`.
"""

from __future__ import annotations

# Same two colours as the 2D pin CSS (photomap_js.PHOTO_CSS), so the legend
# means the same thing on both pages: blue is a photo, orange a 360° pano.
PIN_PHOTO = "#2a81cb"
PIN_PANO = "#f69730"

PHOTO_3D_CSS = """  .photo-popup img { max-width: 260px; height: auto; display: block;
                     margin-bottom: 4px; }
  .photo-popup .photo-credit { opacity: .75; font-size: 90%; }
  .pin-swatch { display: inline-block; width: 10px; height: 10px;
                border-radius: 50%; border: 2px solid #fff;
                box-shadow: 0 0 2px rgba(0,0,0,.5); vertical-align: -1px;
                margin: 0 4px 0 2px; }
  /* A co-located-photo popup (#514 I2) stacks several .photo-popup bodies;
     let it scroll rather than run off the bottom of the viewport. */
  .maplibregl-popup-content { max-height: 70vh; overflow-y: auto; }"""

PHOTO_3D_JS = (
    """
// --- Photo and panorama pins (#514): one clustered GeoJSON source, three
// circle layers. No DOM markers (a 400-photo folder must not become 400
// DOM nodes over WebGL) and no symbol text: the page declares no glyph
// source, and adding a font server would break its keyless, self-contained
// contract, so cluster size carries the count and a click expands it.
const PIN_PHOTO = '"""
    + PIN_PHOTO
    + """', PIN_PANO = '"""
    + PIN_PANO
    + """';
const photoShown = { photo: true, pano: true };
// Street level: past this zoom the source stops clustering altogether, so a
// cluster whose expansion zoom lands above it never actually separates:
// its points are stacked on the same pixel (see the cluster click handler
// below). One constant feeds both the source option and that comparison.
const CLUSTER_MAX_ZOOM = 17;

function shownPhotoData() {
  return { type: 'FeatureCollection',
           features: photoFeatures.filter(f => photoShown[f.properties.type]) };
}

// A toggle rebuilds the source data rather than hiding a layer: clusters
// mix both types, so hiding "photos" must also shrink the clusters.
function applyPhotoVisibility() {
  const src = map.getSource('photos');
  if (src) src.setData(shownPhotoData());
}

photoHooks.addLayers = function () {
  if (!photoFeatures.length) return;
  map.addSource('photos', {
    type: 'geojson', data: shownPhotoData(),
    cluster: true,
    clusterRadius: 50,     // px; a 7 px pin needs less than markercluster's 80
    clusterMaxZoom: CLUSTER_MAX_ZOOM,
    // Any pano in the cluster tints it orange, so the legend's "orange is a
    // 360°" promise survives clustering.
    clusterProperties: {
      panos: ['+', ['case', ['==', ['get', 'type'], 'pano'], 1, 0]] },
  });
  map.addLayer({ id: 'photo-clusters', type: 'circle', source: 'photos',
    filter: ['has', 'point_count'],
    paint: {
      'circle-color': ['case', ['>', ['get', 'panos'], 0], PIN_PANO, PIN_PHOTO],
      'circle-opacity': 0.7,
      // 1 / 10 / 50 photos: the three sizes markercluster uses on the 2D map.
      'circle-radius': ['step', ['get', 'point_count'], 14, 10, 18, 50, 22],
      'circle-stroke-color': '#fff', 'circle-stroke-width': 2 } });
  const pinLayer = (id, type, color) => map.addLayer({
    id: id, type: 'circle', source: 'photos',
    filter: ['all', ['!', ['has', 'point_count']], ['==', ['get', 'type'], type]],
    paint: { 'circle-color': color, 'circle-radius': 7,
             'circle-stroke-color': '#fff', 'circle-stroke-width': 2.5 } });
  pinLayer('photo-pins', 'photo', PIN_PHOTO);
  pinLayer('pano-pins', 'pano', PIN_PANO);
  ['photo-clusters', 'photo-pins', 'pano-pins'].forEach(id => {
    map.on('mouseenter', id, () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', id, () => { map.getCanvas().style.cursor = ''; });
  });
  // Builds one popup from however many photo features share the click (or
  // the cluster): each feature's own buildPopup() body, concatenated, with
  // a one-line count heading when there's more than one (#514 I2). Redact
  // fuzz's 3-decimal grid and AEB/burst shots routinely land several photos
  // on the same point, and past CLUSTER_MAX_ZOOM they share a pixel too, so
  // "just show the top one" silently hides the rest.
  const openPhotoPopup = (features, lngLat) => {
    const el = document.createElement('div');
    if (features.length > 1) {
      const heading = document.createElement('p');
      heading.textContent = `${features.length} photos here`;
      el.appendChild(heading);
    }
    features.forEach(f => {
      const body = document.createElement('div');
      body.innerHTML = buildPopup(f);   // every field passes through esc()
      el.appendChild(body);
    });
    new maplibregl.Popup({ maxWidth: '300px' })
      .setLngLat(lngLat).setDOMContent(el).addTo(map);
  };
  map.on('click', 'photo-clusters', ev => {
    const f = ev.features[0];
    const src = map.getSource('photos');
    src.getClusterExpansionZoom(f.properties.cluster_id).then(z => {
      if (z > CLUSTER_MAX_ZOOM) {
        // This cluster never actually splits: even unclustered (past
        // CLUSTER_MAX_ZOOM there's no clustering left to zoom into) its
        // points render on the same pixel. Easing there would show a single
        // pin and hide the rest, so list them here instead (the 2D map's
        // marker cluster spiderfies the same case). getClusterLeaves is a
        // Promise in MapLibre 5.
        src.getClusterLeaves(f.properties.cluster_id, Infinity, 0)
          .then(leaves => openPhotoPopup(leaves, f.geometry.coordinates));
        return;
      }
      map.easeTo({ center: f.geometry.coordinates, zoom: z });
    });
  });
  // One handler across both pin layers, not one per layer: a photo and a
  // pano at the same point past CLUSTER_MAX_ZOOM would otherwise open two
  // popups (each layer-bound handler sees only its own layer's features).
  map.on('click', ev => {
    const hits = map.queryRenderedFeatures(ev.point,
                                           { layers: ['photo-pins', 'pano-pins'] });
    if (hits.length) openPhotoPopup(hits, hits[0].geometry.coordinates);
  });
};

// #514 I1: a click on a pin also fires any flight click handler underneath
// it, because MapLibre's layer-delegated listeners each run independently.
// A drone photo sits on its own flight path by construction, and on the
// flat map the pin is a DOM marker that swallows the click before it
// reaches the track; here the flight handler must check this itself before
// opening its own popup. photoFeatures.length guards a page with no photo
// layers at all (queryRenderedFeatures on a layer id that was never added
// throws).
photoHooks.hits = function (point) {
  if (!photoFeatures.length) return false;
  return map.queryRenderedFeatures(point, {
    layers: ['photo-clusters', 'photo-pins', 'pano-pins'],
  }).length > 0;
};

photoHooks.panelRows = function (panel) {
  const present = t => photoFeatures.some(f => f.properties.type === t);
  const row = (type, id, color, text) => {
    if (!present(type)) return;
    const label = document.createElement('label');
    const box = document.createElement('input');
    box.type = 'checkbox';
    box.id = id;
    box.checked = true;
    box.addEventListener('change', () => {
      photoShown[type] = box.checked;
      applyPhotoVisibility();
    });
    label.appendChild(box);
    const swatch = document.createElement('span');
    swatch.className = 'pin-swatch';
    swatch.style.background = color;
    label.appendChild(swatch);
    label.appendChild(document.createTextNode(text));
    panel.appendChild(label);
  };
  row('photo', 'photo-toggle', PIN_PHOTO, 'Photos');
  row('pano', 'pano-toggle', PIN_PANO, '360\\u00b0 panoramas');
  if (present('photo') || present('pano')) {
    if (flights.length) panel.appendChild(document.createElement('hr'));
  }
};
"""
)
