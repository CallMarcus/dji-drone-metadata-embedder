(() => {
  "use strict";

  const tokenMeta = document.querySelector('meta[name="djiembed-token"]');
  const token = tokenMeta ? tokenMeta.content : "";

  async function api(path, init = {}) {
    const headers = new Headers(init.headers || {});
    headers.set("X-DJIEmbed-Token", token);
    if (init.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    const res = await fetch(path, { ...init, headers, credentials: "same-origin" });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`${res.status} ${res.statusText}${text ? `: ${text}` : ""}`);
    }
    const ct = res.headers.get("content-type") || "";
    return ct.includes("application/json") ? res.json() : res.text();
  }

  function setActiveTab(name) {
    document.querySelectorAll(".tab").forEach((el) => {
      el.classList.toggle("active", el.dataset.tab === name);
    });
  }

  function stub(message) {
    return (root) => {
      root.innerHTML = `<section class="panel"><p class="muted">${message}</p></section>`;
    };
  }

  function esc(s) {
    return String(s).replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }

  function kvList(obj) {
    return Object.entries(obj)
      .map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`)
      .join("");
  }

  async function renderDoctor(root) {
    root.innerHTML = '<section class="panel"><p class="muted">Loading…</p></section>';
    try {
      const d = await api("/api/doctor");
      const status = d.dependencies_ok
        ? '<span class="ok">All dependencies verified</span>'
        : `<span class="err">Missing: ${d.missing.map(esc).join(", ")}</span>`;
      const tools = Object.entries(d.tools)
        .map(([name, ver]) => {
          const ok = ver && ver !== "not available";
          const cls = ok ? "ok" : "err";
          return `<dt>${esc(name)}</dt><dd class="${cls}">${esc(ver || "not available")}</dd>`;
        })
        .join("");
      root.innerHTML = `
        <section class="panel">
          <h2>Doctor</h2>
          <p>dji-embed ${esc(d.app_version)} — ${status}</p>
          <h3>External tools</h3>
          <dl class="kv">${tools}</dl>
          <h3>System</h3>
          <dl class="kv">${kvList(d.system)}</dl>
        </section>`;
    } catch (e) {
      root.innerHTML = `<section class="panel"><p class="err">Error: ${esc(e.message)}</p></section>`;
    }
  }

  async function renderEmbed(root) {
    let recents = { folders: [] };
    try { recents = await api("/api/recent-folders"); } catch (_) {}
    const recentOpts = recents.folders.map((f) => `<option value="${esc(f)}">`).join("");

    root.innerHTML = `
      <section class="panel">
        <h2>Embed</h2>
        <form id="embed-form">
          <label>Footage folder
            <input type="text" name="directory" list="recent-folders" required placeholder="/path/to/footage">
          </label>
          <datalist id="recent-folders">${recentOpts}</datalist>

          <label><input type="checkbox" name="overwrite"> Overwrite original files in place</label>

          <label>Redact GPS
            <select name="redact">
              <option value="none">none</option>
              <option value="drop">drop</option>
              <option value="fuzz">fuzz</option>
            </select>
          </label>

          <details>
            <summary>Advanced</summary>
            <label><input type="checkbox" name="exiftool"> Also use ExifTool for GPS metadata</label>
            <label><input type="checkbox" name="dat_auto"> Auto-detect DAT flight logs</label>
            <label>DAT log file <input type="text" name="dat" placeholder="optional path"></label>
            <label>Output folder <input type="text" name="output" placeholder="optional; ignored if overwrite is set"></label>
            <label><input type="checkbox" name="verbose"> Verbose output</label>
          </details>

          <div class="actions">
            <button type="submit">Run</button>
            <button type="button" id="cancel-btn" disabled>Cancel</button>
          </div>
        </form>
        <p id="job-status" class="muted"></p>
        <pre id="job-log" aria-live="polite"></pre>
      </section>`;

    const form = root.querySelector("#embed-form");
    const logEl = root.querySelector("#job-log");
    const statusEl = root.querySelector("#job-status");
    const cancelBtn = root.querySelector("#cancel-btn");
    const runBtn = form.querySelector('button[type="submit"]');
    let currentJob = null;
    let stream = null;

    function setStatus(text, cls = "muted") {
      statusEl.textContent = text;
      statusEl.className = cls;
    }

    cancelBtn.addEventListener("click", async () => {
      if (!currentJob) return;
      try {
        await api(`/api/jobs/${currentJob}/cancel`, { method: "POST" });
        setStatus("cancelling…", "warn");
      } catch (e) {
        setStatus("cancel failed: " + e.message, "err");
      }
    });

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      const body = Object.fromEntries(fd.entries());
      ["overwrite", "exiftool", "dat_auto", "verbose"].forEach((k) => {
        body[k] = form.elements[k].checked;
      });

      logEl.textContent = "";
      setStatus("starting…", "muted");
      runBtn.disabled = true;
      cancelBtn.disabled = false;

      try {
        const { job_id } = await api("/api/jobs/embed", {
          method: "POST",
          body: JSON.stringify(body),
        });
        currentJob = job_id;
        setStatus(`running (${job_id.slice(0, 8)})`, "warn");

        stream = new EventSource(`/api/jobs/${job_id}/events`);
        stream.onmessage = (ev) => {
          let msg;
          try { msg = JSON.parse(ev.data); } catch { return; }
          if (msg.type === "log") {
            logEl.textContent += msg.msg + "\n";
            logEl.scrollTop = logEl.scrollHeight;
          } else if (msg.type === "status") {
            const cls = msg.status === "succeeded" ? "ok"
                      : msg.status === "failed" ? "err" : "warn";
            setStatus(msg.status + (msg.error ? " — " + msg.error : ""), cls);
            runBtn.disabled = false;
            cancelBtn.disabled = true;
            stream.close();
            stream = null;
            currentJob = null;
          }
        };
        stream.onerror = () => {
          // Browser auto-reconnects; nothing to do unless terminal status already sent.
        };
      } catch (e) {
        setStatus("error: " + e.message, "err");
        runBtn.disabled = false;
        cancelBtn.disabled = true;
      }
    });
  }

  async function renderValidate(root) {
    let recents = { folders: [] };
    try { recents = await api("/api/recent-folders"); } catch (_) {}
    const recentOpts = recents.folders.map((f) => `<option value="${esc(f)}">`).join("");

    root.innerHTML = `
      <section class="panel">
        <h2>Validate</h2>
        <form id="validate-form">
          <label>Folder with SRT/MP4 pairs
            <input type="text" name="directory" list="validate-recents" required placeholder="/path/to/footage">
          </label>
          <datalist id="validate-recents">${recentOpts}</datalist>
          <label>Drift threshold (seconds)
            <input type="number" name="drift_threshold" step="0.1" min="0" value="1.0">
          </label>
          <div class="actions">
            <button type="submit">Run</button>
          </div>
        </form>
        <div id="validate-result"></div>
      </section>`;

    const form = root.querySelector("#validate-form");
    const out = root.querySelector("#validate-result");
    const runBtn = form.querySelector('button[type="submit"]');

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      const body = {
        directory: fd.get("directory"),
        drift_threshold: parseFloat(fd.get("drift_threshold") || "1.0"),
      };
      out.innerHTML = '<p class="muted">Scanning…</p>';
      runBtn.disabled = true;
      try {
        const r = await api("/api/validate", {
          method: "POST",
          body: JSON.stringify(body),
        });
        const issuesHtml = (r.issues || []).length
          ? `<h3>Issues</h3><ul>${r.issues.map((i) => `<li class="err">${esc(i)}</li>`).join("")}</ul>`
          : "";
        const warningsHtml = (r.warnings || []).length
          ? `<h3>Warnings</h3><ul>${r.warnings.map((w) => `<li class="warn">${esc(w)}</li>`).join("")}</ul>`
          : "";
        const filesHtml = (r.file_analyses || []).length
          ? `<h3>Files</h3>
             <table class="table">
               <thead><tr><th>File</th><th>Valid</th><th>SRT points</th><th>Drift (s)</th></tr></thead>
               <tbody>${r.file_analyses.map((f) => `
                 <tr>
                   <td>${esc(f.srt_file ? f.srt_file.split(/[\\/]/).pop() : "—")}</td>
                   <td class="${f.valid ? "ok" : "err"}">${f.valid ? "yes" : "no"}</td>
                   <td>${esc(f.srt_points ?? "—")}</td>
                   <td>${esc(f.drift_seconds ?? "—")}</td>
                 </tr>`).join("")}</tbody>
             </table>`
          : "";
        const summary = `<p>Total: <strong>${r.total_files}</strong> &middot; Valid pairs: <strong class="${r.valid_pairs === r.total_files && r.total_files > 0 ? "ok" : "warn"}">${r.valid_pairs}</strong></p>`;
        out.innerHTML = summary + issuesHtml + warningsHtml + filesHtml;
      } catch (e) {
        out.innerHTML = `<p class="err">Error: ${esc(e.message)}</p>`;
      } finally {
        runBtn.disabled = false;
      }
    });
  }

  function renderConvert(root) {
    root.innerHTML = `
      <section class="panel">
        <h2>Convert</h2>
        <form id="convert-form">
          <label>SRT file
            <input type="text" name="srt" required placeholder="/path/to/DJI_0001.SRT">
          </label>
          <label>Format
            <select name="format">
              <option value="gpx">GPX</option>
              <option value="csv">CSV</option>
            </select>
          </label>
          <label>Output path <span class="muted">(optional; defaults next to source)</span>
            <input type="text" name="output" placeholder="leave blank to use default">
          </label>
          <div class="actions">
            <button type="submit">Convert</button>
          </div>
        </form>
        <div id="convert-result"></div>
      </section>`;

    const form = root.querySelector("#convert-form");
    const out = root.querySelector("#convert-result");
    const runBtn = form.querySelector('button[type="submit"]');

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      out.innerHTML = '<p class="muted">Converting…</p>';
      runBtn.disabled = true;
      try {
        const r = await api("/api/convert", {
          method: "POST",
          body: JSON.stringify({
            srt: fd.get("srt"),
            format: fd.get("format"),
            output: fd.get("output"),
          }),
        });
        out.innerHTML = `<p class="ok">Wrote ${esc(r.format.toUpperCase())}: <code>${esc(r.output)}</code></p>`;
      } catch (e) {
        out.innerHTML = `<p class="err">Error: ${esc(e.message)}</p>`;
      } finally {
        runBtn.disabled = false;
      }
    });
  }

  function renderCheck(root) {
    root.innerHTML = `
      <section class="panel">
        <h2>Check</h2>
        <p class="muted">Inspect a single media file for embedded GPS, altitude, and creation time metadata.</p>
        <form id="check-form">
          <label>File path
            <input type="text" name="path" required placeholder="/path/to/DJI_0001.MP4">
          </label>
          <div class="actions">
            <button type="submit">Check</button>
          </div>
        </form>
        <div id="check-result"></div>
      </section>`;

    const form = root.querySelector("#check-form");
    const out = root.querySelector("#check-result");
    const runBtn = form.querySelector('button[type="submit"]');

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const path = new FormData(form).get("path");
      out.innerHTML = '<p class="muted">Checking…</p>';
      runBtn.disabled = true;
      try {
        const r = await api("/api/check", {
          method: "POST",
          body: JSON.stringify({ path }),
        });
        const meta = r.metadata || {};
        const rows = Object.entries(meta).length
          ? Object.entries(meta).map(([k, v]) =>
              `<dt>${esc(k)}</dt><dd class="${v ? "ok" : "err"}">${v ? "present" : "missing"}</dd>`
            ).join("")
          : '<dt class="muted">no data</dt><dd class="muted">(tool unavailable or unreadable file)</dd>';
        out.innerHTML = `
          <p class="muted"><code>${esc(r.path)}</code></p>
          <dl class="kv">${rows}</dl>`;
      } catch (e) {
        out.innerHTML = `<p class="err">Error: ${esc(e.message)}</p>`;
      } finally {
        runBtn.disabled = false;
      }
    });
  }

  const routes = {
    doctor: renderDoctor,
    embed: renderEmbed,
    validate: renderValidate,
    convert: renderConvert,
    check: renderCheck,
  };

  function render() {
    const hash = (window.location.hash || "#/doctor").replace(/^#\/?/, "") || "doctor";
    const route = routes[hash] || routes.doctor;
    setActiveTab(routes[hash] ? hash : "doctor");
    route(document.getElementById("app"));
  }

  window.djiEmbed = { api, routes, render };
  window.addEventListener("hashchange", render);
  window.addEventListener("DOMContentLoaded", render);
})();
