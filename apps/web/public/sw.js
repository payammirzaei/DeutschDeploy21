const CACHE = "dd21-public-v2";
const PUBLIC_ASSETS = ["/icon.svg", "/manifest.webmanifest"];

function isSafeStaticRequest(request) {
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return false;
  if (request.destination === "document") return false;
  if (url.pathname.startsWith("/api/")) return false;

  return (
    url.pathname.startsWith("/_next/static/") ||
    url.pathname === "/icon.svg" ||
    url.pathname === "/manifest.webmanifest"
  );
}

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(PUBLIC_ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)))),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET" || !isSafeStaticRequest(request)) return;

  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached;

      return fetch(request).then((response) => {
        if (response.ok) {
          const copy = response.clone();
          void caches.open(CACHE).then((cache) => cache.put(request, copy));
        }
        return response;
      });
    }),
  );
});
