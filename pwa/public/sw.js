/**
 * LocaTS PWA Service Worker
 * 
 * Enables:
 *   - Offline-first crowd reporting (reports saved to IndexedDB, synced on reconnect)
 *   - Asset caching for fast load
 *   - Background sync for pending reports
 */

const CACHE_NAME = 'locats-pwa-v1';
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
];

// Install — cache static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

// Activate — clean old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

// Fetch — network-first for API, cache-first for assets
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // API requests — network first, fallback to nothing (reports are in IndexedDB)
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(event.request).catch(() => {
        // Return a synthetic offline response for API calls
        return new Response(
          JSON.stringify({ offline: true, message: 'No network. Report saved locally.' }),
          { headers: { 'Content-Type': 'application/json' }, status: 503 }
        );
      })
    );
    return;
  }

  // Static assets — cache first, fallback to network
  event.respondWith(
    caches.match(event.request).then((cached) => {
      return cached || fetch(event.request).then((response) => {
        // Cache new assets
        if (response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      });
    }).catch(() => {
      // Offline fallback for navigation
      if (event.request.mode === 'navigate') {
        return caches.match('/index.html');
      }
      return new Response('Offline', { status: 503 });
    })
  );
});

// Background sync — upload pending reports when back online
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-reports') {
    event.waitUntil(syncPendingReports());
  }
});

async function syncPendingReports() {
  // Open IndexedDB and get pending reports
  const db = await openDB();
  const tx = db.transaction('reports', 'readwrite');
  const store = tx.objectStore('reports');
  const request = store.getAll();

  request.onsuccess = async () => {
    const reports = request.result.filter((r) => r.sync_status === 'pending');
    for (const report of reports) {
      try {
        const response = await fetch('/api/hazard/crowd-report', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            reporter_id: report.reporter_id,
            hazard_type: report.hazard_type,
            severity_estimate: report.severity_estimate,
            description: report.description,
            lat: report.lat,
            lon: report.lon,
          }),
        });

        if (response.ok) {
          report.sync_status = 'synced';
          store.put(report);
        }
      } catch (e) {
        // Will retry on next sync
      }
    }
  };
}

function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('locats-reports', 1);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains('reports')) {
        db.createObjectStore('reports', { keyPath: 'id', autoIncrement: true });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

// Push notification handler (for future SMS alerts relay)
self.addEventListener('push', (event) => {
  const data = event.data?.json() || {};
  const title = data.title || 'LocaTS Alert';
  const body = data.body || 'Emergency alert received.';

  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon: '/icon-192.png',
      badge: '/icon-192.png',
      vibrate: [200, 100, 200],
      data: data.url || '/',
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    clients.openWindow(event.notification.data)
  );
});
