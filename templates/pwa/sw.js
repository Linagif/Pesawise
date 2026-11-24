/* PesaWise service worker ({{ version }}).
   PRIVACY: this worker never caches pages, API responses, exports or anything personal. It caches only the app's own
   static files (CSS, JS, icons) and one generic offline page. */
const VERSION = "{{ version }}";
const STATIC_CACHE = "pesawise-static-" + VERSION;
const OFFLINE_URL = "{{ offline_url }}";
const PRECACHE = {{ precache_json|safe }};

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(STATIC_CACHE).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith("pesawise-") && k !== STATIC_CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;                       // never touch form submissions or saves
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;            // CDN files: let the browser handle them

  if (request.mode === "navigate") {                          // a page: always from the network, never stored
    event.respondWith(fetch(request).catch(() => caches.match(OFFLINE_URL)));
    return;
  }
  if (url.pathname.startsWith("/static/")) {                  // our own CSS/JS/images: cached, refreshed in the background
    event.respondWith(
      caches.open(STATIC_CACHE).then(async (cache) => {
        const cached = await cache.match(request, { ignoreSearch: true });
        const network = fetch(request).then((response) => {
          if (response && response.ok) cache.put(request, response.clone());
          return response;
        }).catch(() => cached);
        return cached || network;
      })
    );
  }
  /* anything else (downloads, data requests): network only, no respondWith, nothing cached */
});
