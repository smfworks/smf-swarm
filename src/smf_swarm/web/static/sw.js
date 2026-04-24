/** SMF Predict — Service Worker for PWA offline support */

const CACHE_NAME = "smf-predict-v1";
const STATIC_ASSETS = [
    "/",
    "/css/main.css",
    "/js/main.js",
    "/js/charts.js",
    "/js/history.js",
    "/manifest.json",
];

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
    );
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((names) => Promise.all(
            names.filter(n => n !== CACHE_NAME).map(n => caches.delete(n))
        ))
    );
    self.clients.claim();
});

self.addEventListener("fetch", (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Only cache same-origin static assets; never cache API calls
    if (url.origin !== self.location.origin) return;
    if (request.method !== "GET") return;
    if (url.pathname.startsWith("/api/")) return;

    event.respondWith(
        caches.match(request).then((cached) => cached || fetch(request))
    );
});
