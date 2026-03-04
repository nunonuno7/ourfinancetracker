
// Service worker disabled to avoid CSP errors with external CDN resources
// Uncomment and modify if you need offline functionality in the future

/*
const CACHE_NAME = 'ourfinancetracker-cache-v1';
const urlsToCache = [
  '/'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request).then(response => response || fetch(event.request))
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => Promise.all(
      cacheNames.filter(cacheName => cacheName !== CACHE_NAME).map(cacheName => caches.delete(cacheName))
    ))
  );
});
*/
