const CACHE_NAME = 'futbolpro-static-v3';
const ASSETS = [
  '/static/teams/images/logo.png',
  '/static/teams/images/logo-192.png',
  '/static/teams/images/logo-512.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      // Only cache static assets which are guaranteed to return 200 OK
      return cache.addAll(ASSETS);
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys.map(key => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  // Only handle GET requests
  if (event.request.method !== 'GET') {
    return;
  }

  const url = new URL(event.request.url);

  // If it's one of our static assets, try to serve from cache, fallback to network
  if (ASSETS.some(asset => url.pathname.endsWith(asset) || url.pathname === asset)) {
    event.respondWith(
      caches.match(event.request).then(cachedResponse => {
        return cachedResponse || fetch(event.request);
      })
    );
  }
  // For other requests (like / or /login/ which are dynamic and can redirect),
  // we do NOT call event.respondWith(), letting the browser handle them natively.
  // This prevents ERR_FAILED errors on redirects or authentication checks.
});
