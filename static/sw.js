// ParkVoice PWA - Offline Service Worker (Network-First Strategy)
const CACHE_NAME = 'parkvoice-offline-v8';
const ASSETS_TO_CACHE = [
  '/',
  '/static/index.html',
  '/static/style.css',
  '/static/app.js',
  '/static/manifest.webmanifest',
  '/static/icons/icon.svg',
  '/static/vendor/leaflet/leaflet.js',
  '/static/vendor/leaflet/leaflet.css',
  '/static/vendor/leaflet/marker-icon.png',
  '/static/vendor/leaflet/marker-icon-2x.png',
  '/static/vendor/leaflet/marker-shadow.png'
];

// Install: Cache critical static shell and activate immediately
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[ServiceWorker] Caching app shell assets');
      return cache.addAll(ASSETS_TO_CACHE);
    }).then(() => self.skipWaiting())
  );
});

// Activate: Immediately purge all older caches and take control
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keyList) => {
      return Promise.all(
        keyList.map((key) => {
          if (key !== CACHE_NAME) {
            console.log('[ServiceWorker] Purging old cache:', key);
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch: Network-First Strategy
// 1. When the server is online, always fetch fresh files directly from the server.
// 2. When the server is stopped, do NOT serve a zombie webpage. Let the request fail
//    so the browser reflects that localhost:8001 is actually stopped.
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // For API calls, bypass the service worker completely.
  // Direct browser networking avoids the browser's 30-second ServiceWorker event execution timeout.
  if (url.pathname.startsWith('/api/')) {
    return;
  }

  // Network-First for static assets and page navigations
  event.respondWith(
    fetch(event.request)
      .then((networkResponse) => {
        // Cache the latest response on the fly
        if (networkResponse && networkResponse.status === 200 && networkResponse.type === 'basic') {
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseToCache);
          });
        }
        return networkResponse;
      })
      .catch((error) => {
        // When server is stopped on port 8001, do not serve cached zombie shell.
        // Let the failure be visible so the user knows port 8001 is offline.
        throw error;
      })
  );
});
