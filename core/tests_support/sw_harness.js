// Runs the REAL service-worker source against mock browser APIs and prints what it did as JSON.
// Usage: node sw_harness.js path/to/sw.js
const fs = require("fs");
const vm = require("vm");

const ORIGIN = "https://pesawise.test";
const src = fs.readFileSync(process.argv[2], "utf8");

const stores = new Map();                                   // cache name -> Map(url -> response)
const norm = (u, ignoreSearch) => { const x = new URL(u); return ignoreSearch ? x.origin + x.pathname : x.href; };
class MockCache {
  constructor(name) { this.name = name; if (!stores.has(name)) stores.set(name, new Map()); this.map = stores.get(name); }
  async addAll(urls) { for (const u of urls) this.map.set(norm(new URL(u, ORIGIN).href), { ok: true, tag: "precached:" + u }); }
  async put(req, res) { this.map.set(norm(req.url), res); }
  async keys() { return [...this.map.keys()].map((u) => ({ url: u })); }
  async delete(req) { return this.map.delete(norm(req.url)); }
  async match(req, opts = {}) {
    const url = typeof req === "string" ? new URL(req, ORIGIN).href : req.url;
    for (const [k, v] of this.map) if (norm(k, opts.ignoreSearch) === norm(url, opts.ignoreSearch)) return v;
    return undefined;
  }
}
const caches = {
  open: async (n) => new MockCache(n),
  keys: async () => [...stores.keys()],
  delete: async (n) => stores.delete(n),
  match: async (req, opts) => { for (const n of stores.keys()) { const r = await new MockCache(n).match(req, opts); if (r) return r; } },
};

let online = true;
const network = new Map();                                  // url -> response body tag
const fetchLog = [];
const fakeFetch = async (req) => {
  fetchLog.push(req.url);
  if (!online) throw new TypeError("offline");
  const tag = network.get(req.url) || "network:" + req.url;
  return { ok: true, tag, clone() { return { ok: true, tag }; } };
};

const listeners = {};
const selfObj = { location: { origin: ORIGIN }, addEventListener: (t, f) => { listeners[t] = f; }, skipWaiting: () => {}, clients: { claim: () => {} } };
vm.runInNewContext(src, { self: selfObj, caches, fetch: fakeFetch, URL, Promise, console });

const req = (path, { method = "GET", mode = "same-origin", origin = ORIGIN } = {}) => ({ method, mode, url: origin + path });
async function fire(request) {
  let handled = false, responsePromise = null;
  listeners.fetch({ request, respondWith: (p) => { handled = true; responsePromise = Promise.resolve(p); } });
  return { handled, response: handled ? await responsePromise : null };
}
const cachedUrls = (name) => [...(stores.get(name) || new Map()).keys()].map((k) => new URL(k).pathname);

(async () => {
  const out = {};
  let installDone; listeners.install({ waitUntil: (p) => { installDone = p; } }); await installDone;
  const cacheName = [...stores.keys()][0];
  out.cacheName = cacheName;
  out.precached = cachedUrls(cacheName);

  out.post = (await fire(req("/expenses/add/", { method: "POST", mode: "navigate" }))).handled;   // a real form submit is a navigation
  out.crossOrigin = (await fire(req("/npm/bootstrap.css", { origin: "https://cdn.example" }))).handled;

  network.set(ORIGIN + "/expenses/daily/", "PRIVATE-EXPENSE-PAGE");
  const nav = await fire(req("/expenses/daily/", { mode: "navigate" }));
  out.navOnline = { handled: nav.handled, body: nav.response && nav.response.tag };
  out.cachedAfterNav = cachedUrls(cacheName);

  out.download = (await fire(req("/reports/export/pdf/?kind=monthly"))).handled;
  out.cachedAfterDownload = cachedUrls(cacheName);

  const s1 = await fire(req("/static/css/style.css?v=3"));
  out.staticFirst = { handled: s1.handled, body: s1.response && s1.response.tag };
  await new Promise((r) => setTimeout(r, 10));
  out.cachedAfterStatic = cachedUrls(cacheName);

  // an OLD copy of a script is already cached; the server now has a NEW version
  await new MockCache(cacheName).put({ url: ORIGIN + "/static/js/theme.js" }, { ok: true, tag: "OLD-THEME-JS" });
  network.set(ORIGIN + "/static/js/theme.js?v=newhash", "NEW-THEME-JS");
  const fresh = await fire(req("/static/js/theme.js?v=newhash"));
  out.staleCopyOnline = fresh.response && fresh.response.tag;
  await new Promise((r) => setTimeout(r, 10));

  online = false;
  const navOff = await fire(req("/", { mode: "navigate" }));
  out.navOffline = { handled: navOff.handled, body: navOff.response && navOff.response.tag };
  const s2 = await fire(req("/static/css/style.css?v=4"));
  out.staticOffline = { handled: s2.handled, body: s2.response && s2.response.tag };
  const s3 = await fire(req("/static/js/theme.js?v=newhash"));
  out.staleOffline = s3.response && s3.response.tag;
  out.neverRespondsUndefined = [out.staticOffline.body, out.staleOffline].every((b) => typeof b === "string");
  online = true;

  stores.set("pesawise-static-old", new Map()); stores.set("someone-elses-cache", new Map());
  let actDone; listeners.activate({ waitUntil: (p) => { actDone = p; } }); await actDone;
  out.cachesAfterActivate = [...stores.keys()].sort();
  console.log(JSON.stringify(out));
})();
