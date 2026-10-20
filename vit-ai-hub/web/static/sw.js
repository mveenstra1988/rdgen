/* VIT AI Hub — minimal PWA shell cache */
const CACHE = "vit-ai-hub-shell-v261";
const SHELL = [
  "/",
  "/static/styles.css",
  "/static/app.js",
  "/static/logo-mark.png",
  "/static/logo-wordmark.png",
  "/manifest.webmanifest",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  // Never cache API / chat
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/v1/")) return;
  event.respondWith(
    caches.match(req).then((hit) => hit || fetch(req).then((res) => {
      if (res.ok && (url.pathname.startsWith("/static/") || url.pathname === "/")) {
        const clone = res.clone();
        caches.open(CACHE).then((c) => c.put(req, clone));
      }
      return res;
    }).catch(() => caches.match("/") || Response.error()))
  );
});
