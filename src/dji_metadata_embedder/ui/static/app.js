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

  const routes = {
    doctor: renderDoctor,
    embed: stub("Embed tab — wiring in a later commit."),
    validate: stub("Validate tab — wiring in a later commit."),
    convert: stub("Convert tab — wiring in a later commit."),
    check: stub("Check tab — wiring in a later commit."),
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
