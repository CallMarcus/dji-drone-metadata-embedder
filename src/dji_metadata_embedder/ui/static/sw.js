// Minimal service worker. Present so the browser exposes "Install app"
// for PWA installability. Network-first with no caching because the
// backend is local and always available.

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
  event.respondWith(
    fetch(event.request).catch(
      () => new Response("Server offline", { status: 503, statusText: "Offline" })
    )
  );
});
