const CACHE_NAME = 'yiyi-v1';
const FILES = ['index.html', 'data.json', 'manifest.json'];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME)
      .then((c) => c.addAll(FILES))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (e) => {
  e.respondWith(
    fetch(e.request)
      .catch(() =>
        caches.match(e.request).then((r) => r || caches.match('index.html'))
      )
  );
});
