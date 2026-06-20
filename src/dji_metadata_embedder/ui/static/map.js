(() => {
  "use strict";

  const api = (path, init) => window.djiEmbed.api(path, init);

  let lmap = null;          // current Leaflet map
  let playTimer = null;     // playback interval id
  let frames = [];          // [{lat, lon, alt, timestamp}] per sample
  let liveMarker = null;    // moving playback marker
  let cursorEl = null;      // chart cursor <line>
  let chartX = null;        // index -> svg x scale
  let idx = 0;              // current playback index

  function altColor(alt, lo, hi) {
    const t = hi > lo ? (alt - lo) / (hi - lo) : 0; // 0 low .. 1 high
    return `hsl(${240 * (1 - t)}, 90%, 45%)`;       // 240 blue -> 0 red
  }

  function teardown() {
    if (playTimer) { clearInterval(playTimer); playTimer = null; }
    if (lmap) { lmap.remove(); lmap = null; }
    frames = [];
    liveMarker = null;
    cursorEl = null;
    chartX = null;
    idx = 0;
  }

  function drawMap(container, gj) {
    const features = gj.features || [];
    const line = features.find((f) => f.geometry && f.geometry.type === "LineString");
    const pts = features.filter((f) => f.geometry && f.geometry.type === "Point");
    frames = pts.map((f) => ({
      lon: f.geometry.coordinates[0],
      lat: f.geometry.coordinates[1],
      alt: f.geometry.coordinates[2],
      timestamp: (f.properties || {}).timestamp || "",
    }));

    lmap = L.map(container);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(lmap);

    if (line) {
      const coords = line.geometry.coordinates; // [lon, lat, alt]
      const alts = coords.map((c) => c[2]);
      const lo = Math.min(...alts), hi = Math.max(...alts);
      const latlngs = coords.map((c) => [c[1], c[0]]);
      for (let i = 0; i < coords.length - 1; i++) {
        const mid = (coords[i][2] + coords[i + 1][2]) / 2;
        L.polyline([latlngs[i], latlngs[i + 1]],
          { color: altColor(mid, lo, hi), weight: 4 }).addTo(lmap);
      }
      lmap.fitBounds(L.latLngBounds(latlngs).pad(0.1));
      L.circleMarker(latlngs[0], { color: "#2e7d32", radius: 7 })
        .bindPopup("Start").addTo(lmap);
      L.circleMarker(latlngs[latlngs.length - 1], { color: "#c62828", radius: 7 })
        .bindPopup("End").addTo(lmap);
    } else if (frames.length) {
      lmap.setView([frames[0].lat, frames[0].lon], 16);
    } else {
      lmap.setView([0, 0], 2);
    }
    lmap.invalidateSize();
    if (frames.length) {
      liveMarker = L.circleMarker([frames[0].lat, frames[0].lon],
        { color: "#1565c0", radius: 6, fillOpacity: 1 }).addTo(lmap);
    }
  }

  function drawChart(svg) {
    const W = 600, H = 120, pad = 4;
    const ns = "http://www.w3.org/2000/svg";
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    svg.innerHTML = "";
    chartX = null;
    cursorEl = null;
    if (frames.length < 2) return;
    const alts = frames.map((f) => f.alt);
    const lo = Math.min(...alts), hi = Math.max(...alts);
    const span = hi > lo ? hi - lo : 1;
    chartX = (i) => pad + (i / (frames.length - 1)) * (W - 2 * pad);
    const y = (a) => H - pad - ((a - lo) / span) * (H - 2 * pad);
    const d = frames
      .map((f, i) => `${i ? "L" : "M"}${chartX(i).toFixed(1)},${y(f.alt).toFixed(1)}`)
      .join(" ");
    const path = document.createElementNS(ns, "path");
    path.setAttribute("d", d);
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", "#1565c0");
    path.setAttribute("stroke-width", "2");
    svg.appendChild(path);
    cursorEl = document.createElementNS(ns, "line");
    cursorEl.setAttribute("y1", "0");
    cursorEl.setAttribute("y2", String(H));
    cursorEl.setAttribute("stroke", "#c62828");
    cursorEl.setAttribute("stroke-width", "1");
    svg.appendChild(cursorEl);
  }

  function setIndex(i, slider, label) {
    if (!frames.length) return;
    idx = Math.max(0, Math.min(frames.length - 1, i));
    const f = frames[idx];
    if (liveMarker) liveMarker.setLatLng([f.lat, f.lon]);
    if (cursorEl && chartX) {
      const xv = chartX(idx).toFixed(1);
      cursorEl.setAttribute("x1", xv);
      cursorEl.setAttribute("x2", xv);
    }
    if (slider) slider.value = String(idx);
    if (label) label.textContent = f.timestamp || `#${idx}`;
  }

  function render(root) {
    teardown();
    root.innerHTML = `
      <section class="panel">
        <h2>Map</h2>
        <form id="map-form">
          <label>SRT file
            <input type="text" name="srt" required placeholder="/path/to/DJI_0001.SRT">
          </label>
          <label>Redact GPS
            <select name="redact">
              <option value="none">none</option>
              <option value="drop">drop</option>
              <option value="fuzz">fuzz</option>
            </select>
          </label>
          <div class="actions"><button type="submit">Load</button></div>
        </form>
        <p id="map-msg" class="muted"></p>
        <div id="lmap"></div>
        <svg id="alt-chart" aria-label="Altitude profile"></svg>
        <div class="playback">
          <button type="button" id="play-btn" disabled>&#9654;</button>
          <input type="range" id="scrub" min="0" max="0" value="0" disabled>
          <span id="frame-label" class="muted"></span>
        </div>
      </section>`;

    const form = root.querySelector("#map-form");
    const msg = root.querySelector("#map-msg");
    const container = root.querySelector("#lmap");
    const svg = root.querySelector("#alt-chart");
    const playBtn = root.querySelector("#play-btn");
    const slider = root.querySelector("#scrub");
    const label = root.querySelector("#frame-label");

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      teardown();
      svg.innerHTML = "";
      playBtn.disabled = true;
      slider.disabled = true;
      slider.value = "0";
      msg.textContent = "Loading…";
      msg.className = "muted";
      const fd = new FormData(form);
      try {
        const gj = await api("/api/geojson", {
          method: "POST",
          body: JSON.stringify({ srt: fd.get("srt"), redact: fd.get("redact") }),
        });
        const hasTrack = (gj.features || []).some((f) => f.geometry);
        if (!hasTrack) {
          msg.textContent = "No GPS track in this clip.";
          return;
        }
        msg.textContent = "";
        drawMap(container, gj);
        drawChart(svg);
        if (frames.length) {
          slider.max = String(frames.length - 1);
          slider.disabled = false;
          playBtn.disabled = false;
          setIndex(0, slider, label);
        }
      } catch (err) {
        msg.textContent = "Error: " + err.message;
        msg.className = "err";
      }
    });

    slider.addEventListener("input", () =>
      setIndex(parseInt(slider.value, 10), null, label));

    playBtn.addEventListener("click", () => {
      if (playTimer) {
        clearInterval(playTimer);
        playTimer = null;
        playBtn.innerHTML = "&#9654;"; // play
        return;
      }
      playBtn.innerHTML = "&#10073;&#10073;"; // pause
      playTimer = setInterval(() => {
        if (idx >= frames.length - 1) {
          clearInterval(playTimer);
          playTimer = null;
          playBtn.innerHTML = "&#9654;";
          return;
        }
        setIndex(idx + 1, slider, label);
      }, 50);
    });
  }

  window.djiMap = { render };
})();
