// PullSound Service Worker for PWA offline support

const CACHE_NAME = 'pullsound-v2.1.0';
const urlsToCache = [
  '/',
  '/index.html',
  '/styles.css',
  '/theme-toggle.css',
  '/light-mode-overrides.css',
  '/visual-enhancements.css',
  '/script.js',
  '/visual-enhancements.js',
  '/feature-modules.js',
  '/mass-download.js',
  '/feature-modules.js',
  '/favicon.svg',
  '/manifest.json',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
  'https://cdn.socket.io/4.5.4/socket.io.min.js',
  'https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@700&family=Inter:wght@400;500;600;700&display=swap'
];

// Install event - cache resources
self.addEventListener('install', (event) => {
  
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        return cache.addAll(urlsToCache);
      })
      .then(() => globalThis.skipWaiting())
  );
});

// Activate event - clean old caches
self.addEventListener('activate', (event) => {
  
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => globalThis.clients.claim())
  );
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip cross-origin requests to avoid SW promise rejection errors (like GTM)
  if (url.origin !== self.location.origin) {
    return;
  }

  // Skip caching for Socket.IO and WebSocket connections
  if (url.pathname.includes('/socket.io/') || 
      url.protocol === 'ws:' || 
      url.protocol === 'wss:') {
    return; // Let the browser handle it directly
  }

  // Skip caching for Chrome extensions (unsupported scheme)
  if (url.protocol === 'chrome-extension:') {
    return; // Cannot cache extension requests
  }

  // Skip caching for API requests (always fetch fresh)
  if (url.pathname.startsWith('/api/')) {
    return event.respondWith(fetch(request));
  }

  // Cache-first strategy for app shell
  event.respondWith(
    caches.match(request)
      .then((response) => {
        if (response) {
          return response;
        }

        // Clone the request
        const fetchRequest = request.clone();

        return fetch(fetchRequest).then((response) => {
          // Return early if not cacheable
          if (!response?.ok || response.status !== 200 || response.type !== 'basic') {
            return response;
          }

          // Clone and cache the valid response, then return it
          const responseToCache = response.clone();
          return caches.open(CACHE_NAME).then((cache) => {
            cache.put(request, responseToCache);
            return response;
          });
        }).catch(() => {
          // Network error - serve offline page if available
          if (request.destination === 'document') {
            return caches.match('/index.html');
          }
          throw new Error('Network error and no cached fallback');
        });
      })
  );
});

// Handle messages from clients
globalThis.addEventListener('message', (event) => {
  // Verify origin to prevent malicious messages
  if (!event.origin || new URL(event.origin).origin !== globalThis.location.origin) {
    console.warn('[Service Worker] Message from unknown origin rejected:', event.origin);
    return;
  }
  
  if (event.data?.type === 'SKIP_WAITING') {
    globalThis.skipWaiting();
  }
  
  if (event.data?.type === 'CLEAR_CACHE') {
    caches.delete(CACHE_NAME).then(() => {
    });
  }
});

// Background sync for downloads (future enhancement)
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-downloads') {
    // Implement background download sync logic here
  }
});

