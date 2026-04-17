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

  const routes = {
    doctor: stub("Doctor tab — wiring in a later commit."),
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
