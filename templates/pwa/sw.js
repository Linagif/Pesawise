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
  if (url.pathname.startsWith("/static/")) {                  // our own CSS/JS/images: ALWAYS fetched fresh when online, so an
    event.respondWith(                                        // update can never be stuck behind an old cached copy
      fetch(request).then((response) => {
        if (response && response.ok) {
          const copy = response.clone();
          caches.open(STATIC_CACHE).then(async (cache) => {
            const stored = await cache.keys();            // drop older versions of this same file first, so the
            await Promise.all(stored                      // offline fallback can only ever return the latest one
              .filter((k) => new URL(k.url).pathname === url.pathname && k.url !== request.url)
              .map((k) => cache.delete(k)));
            await cache.put(request, copy);
          });
        }
        return response;
      }).catch(() => caches.match(request, { ignoreSearch: true }))   // offline: fall back to the last copy we saw
    );
    return;
  }
  /* anything else (downloads, data requests): network only, no respondWith, nothing cached */
});
