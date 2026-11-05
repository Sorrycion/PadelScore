// PadelScore's service worker (served at /sw.js so it covers the whole site). It only
// makes the installed app nicer offline: pages always come from the network (results
// change all the time), and when there's no connection a small offline page shows
// instead of the browser's error. Nothing else is cached.
const CACHE = "padelscore-offline-v1";
const OFFLINE = "/static/offline.html";

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.add(OFFLINE)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(
    keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)))));
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  if (event.request.mode !== "navigate") return;  // everything else: the browser as usual
  event.respondWith(fetch(event.request).catch(() => caches.match(OFFLINE)));
});
