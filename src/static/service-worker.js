const CACHE_NAME = 'xiaozhi-webrtc-cache-v2';
const APP_SHELL = [
  '/static/manifest.webmanifest',
  '/static/js/vue.min.js',
  '/static/js/pixi.js',
  '/static/js/cubism4.min.js',
  '/static/js/live2dcubismcore.min.js',
  '/static/js/live2d.js',
  '/static/favicon.ico'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.map((key) => {
      if (key !== CACHE_NAME) {
        return caches.delete(key);
      }
      return undefined;
    })))
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  event.respondWith(
    fetch(request)
      .then((response) => {
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, clone)).catch(() => {});
        return response;
      })
      .catch(() => caches.match(request))
  );
});


