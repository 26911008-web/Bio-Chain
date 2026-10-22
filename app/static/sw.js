/* Service worker Bio-Chain — app shell offline + pemicu Background Sync.
 *
 * - Halaman (/) : network-first, jatuh ke cache bila offline → aplikasi tetap terbuka di blank spot.
 * - Pustaka CDN (Leaflet, Chart.js, QR scanner, font) : stale-while-revalidate → scanner QR tetap ada offline
 *   setelah sekali dibuka saat online.
 * - /api/* TIDAK pernah di-cache (data harus segar; tulis lewat antrean IndexedDB di halaman).
 * - Background Sync (Chrome/Edge Android): saat sinyal kembali, SW membangunkan halaman yang terbuka untuk
 *   mengirim antrean. Safari/Firefox tidak mendukung → halaman memakai event 'online' & interval.
 */
const VERSION = "biochain-shell-v13";         // v13: prototipe 1–3 + perbaikan audit (UI multi-biomassa)
const SHELL = ["/", "/static/tokens.css", "/static/components.css", "/static/app.js", "/static/ui-enhance.js", "/static/field-ops.js",
               "/static/factory-ops.js"];  // three.js sengaja tidak di-precache

self.addEventListener("install", event => {
  event.waitUntil(caches.open(VERSION).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", event => {
  event.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", event => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin === location.origin && (url.pathname.startsWith("/api/") || url.pathname.startsWith("/uploads/"))) return;

  if (req.mode === "navigate") {
    event.respondWith(fetch(req).then(res => {
      const copy = res.clone();
      caches.open(VERSION).then(c => c.put("/", copy));
      return res;
    }).catch(() => caches.match("/")));
    return;
  }
  const cacheable = url.origin === location.origin
    || /(cdn\.jsdelivr\.net|unpkg\.com|cdnjs\.cloudflare\.com|fonts\.(googleapis|gstatic)\.com)$/.test(url.hostname);
  if (!cacheable) return;                                   // tile peta OSM: tidak disimpan (kebijakan OSM)
  event.respondWith(caches.open(VERSION).then(async cache => {
    const hit = await cache.match(req);
    const net = fetch(req).then(res => {
      if (res && (res.ok || res.type === "opaque")) cache.put(req, res.clone());
      return res;
    }).catch(() => hit);
    return hit || net;
  }));
});

self.addEventListener("sync", event => {
  if (event.tag !== "biochain-outbox") return;
  event.waitUntil(self.clients.matchAll({ includeUncontrolled: true, type: "window" })
    .then(list => list.forEach(c => c.postMessage("flush-outbox"))));
});
