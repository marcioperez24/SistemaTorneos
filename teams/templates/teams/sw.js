const CACHE_NAME = 'futbolpro-v2';
const ASSETS = [
  '/',
  '/login/',
  '/static/teams/images/logo.png',
  '/static/teams/images/logo-192.png',
  '/static/teams/images/logo-512.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
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
  // Simple fetch bypass for non-GET requests to prevent error with CSRF
  if (event.request.method !== 'GET') {
    return;
  }
  
  event.respondWith(
    caches.match(event.request).then(cachedResponse => {
      if (cachedResponse) {
        return cachedResponse;
      }
      return fetch(event.request).catch(err => {
        console.log('Fetch failed, user might be offline:', err);
      });
    })
  );
});
