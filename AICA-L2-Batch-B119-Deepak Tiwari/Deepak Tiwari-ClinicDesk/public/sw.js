/* Service worker - makes the app installable and fast to open.
 *
 * Two rules (same as the original system):
 *  1. It NEVER touches Firebase traffic. Patient data, sign-in and invoice numbers always go to the
 *     network and are never stored here: health information must not sit in a cache on a shared device.
 *     (Firebase calls are cross-origin, and this worker ignores every cross-origin request.)
 *  2. Pages are fetched network-first, so a new deployment is picked up on the next launch. The cache
 *     is only a fallback when there is no connection. Static, hashed build files are cache-first.
 * Bump CACHE_VERSION if you ever change this file.
 */
const CACHE_VERSION = 'clinic-v1';
const SHELL = ['/', '/index.html', '/manifest.webmanifest', '/icons/icon-192.png', '/icons/icon-512.png', '/icons/maskable-512.png', '/icons/logo.png'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE_VERSION).then((c) => Promise.all(SHELL.map((u) => c.add(u).catch(() => {})))));
  self.skipWaiting();
});
self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k)));
    await self.clients.claim();
  })());
});
self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;                    // rule 1
  if (req.mode === 'navigate') {                                       // rule 2
    e.respondWith((async () => {
      try {
        const fresh = await fetch(req);
        const c = await caches.open(CACHE_VERSION); c.put('/index.html', fresh.clone());
        return fresh;
      } catch {
        const c = await caches.open(CACHE_VERSION);
        return (await c.match('/index.html')) || new Response('<h1>Offline</h1><p>Connect to the internet to use the clinic app.</p>', { headers: { 'Content-Type': 'text/html' } });
      }
    })());
    return;
  }
  e.respondWith((async () => {
    const c = await caches.open(CACHE_VERSION), hit = await c.match(req);
    const net = fetch(req).then((r) => { if (r && r.ok && r.type === 'basic') c.put(req, r.clone()); return r; }).catch(() => null);
    return hit || (await net) || new Response('', { status: 504 });
  })());
});
