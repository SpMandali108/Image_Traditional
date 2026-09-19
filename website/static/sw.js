/**
 * Image Traditional - Progressive Web App Service Worker
 * Version: 1.0.1
 * Provides offline capabilities for Public Catalogue, seamless updates,
 * and enforces strict network-only security for Admin Panel routes.
 */

const CACHE_VERSION = 'it-pwa-v1.0.2';
const CORE_CACHE = `image-traditional-core-${CACHE_VERSION}`;
const PAGES_CACHE = `image-traditional-pages-${CACHE_VERSION}`;
const IMAGES_CACHE = `image-traditional-images-${CACHE_VERSION}`;
const DATA_CACHE = `image-traditional-data-${CACHE_VERSION}`;

// Maximum number of images to retain in cache storage (LRU limit)
const MAX_IMAGE_CACHE_ITEMS = 350;

// Core shell assets to precache on install
const PRECACHE_ASSETS = [
  '/',
  '/kediya',
  '/choli',
  '/catalogue/fancy/',
  '/offline.html',
  '/manifest.json',
  '/static/CSS/base.css',
  '/static/CSS/home.css',
  '/static/JS/base.js',
  '/static/JS/home.js',
  '/static/JS/pwa-manager.js',
  '/static/Home_Img/favicon.png',
  '/static/Home_Img/costume.webp',
  '/static/Home_Img/kediya.webp',
  '/static/Home_Img/choli.webp',
  '/static/Icons/icon-192x192.png',
  '/static/Icons/icon-512x512.png',
  '/static/Icons/icon-maskable-192x192.png',
  '/static/Icons/icon-maskable-512x512.png',
  '/static/Icons/apple-touch-icon.png'
];

// Admin route prefixes that MUST NEVER be cached and require a live database connection
const ADMIN_ROUTE_PREFIXES = [
  '/app',
  '/admin',
  '/login',
  '/logout',
  '/fancy_admin',
  '/navaratri_admin',
  '/book',
  '/modify',
  '/delete',
  '/available',
  '/calendar',
  '/check',
  '/Storage',
  '/dashboard',
  '/search',
  '/profile',
  '/listing',
  '/dashboard_listing',
  '/navaratri_booking',
  '/pay_remaining',
  '/download-bill',
  '/download-customer',
  '/export_bookings',
  '/export-calendar-bookings',
  '/export_product_report',
  '/generate-qr',
  '/QR',
  '/update_status',
  '/get_statuses',
  '/clear_statuses',
  '/code',
  '/add_bag',
  '/add_product',
  '/address_manager',
  '/api/update_customer_address',
  '/api/add_custom_locality',
  '/api/send-whatsapp-auto',
  '/api/storage-search',
  '/api/check-product',
  '/api/suggest-products'
];

/**
 * Checks whether a given URL is a private/admin route
 */
function isAdminRoute(url) {
  const pathname = url.pathname;
  
  // Notice: /catalogue/fancy/ is public, but /fancy and /fancy/* are admin!
  if (pathname.startsWith('/fancy') && !pathname.startsWith('/catalogue/fancy')) {
    return true;
  }

  return ADMIN_ROUTE_PREFIXES.some(prefix => pathname.startsWith(prefix));
}

// ── 1. INSTALL EVENT ────────────────────────────────────────────────────────
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CORE_CACHE)
      .then((cache) => {
        // Use Promise.allSettled so any non-fatal single asset failure doesn't abort install
        return Promise.allSettled(
          PRECACHE_ASSETS.map((url) => {
            return cache.add(new Request(url, { cache: 'reload' })).catch((err) => {
              console.warn(`[SW] Precache item failed: ${url}`, err);
            });
          })
        );
      })
      .then(() => {
        // Activate immediately so new versions take over smoothly
        return self.skipWaiting();
      })
  );
});

// ── 2. ACTIVATE EVENT ───────────────────────────────────────────────────────
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames.map((cacheName) => {
            if (
              cacheName.startsWith('image-traditional-') &&
              !cacheName.endsWith(CACHE_VERSION)
            ) {
              console.log(`[SW] Removing obsolete cache: ${cacheName}`);
              return caches.delete(cacheName);
            }
          })
        );
      })
      .then(() => {
        // Claim clients immediately so all tabs run the active service worker
        return self.clients.claim();
      })
  );
});

// ── 3. FETCH EVENT ──────────────────────────────────────────────────────────
self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);

  // Ignore non-http requests (e.g. chrome-extension://)
  if (!url.protocol.startsWith('http')) {
    return;
  }

  // Cross-origin requests (e.g. Google Fonts, Font Awesome CDN)
  if (url.origin !== self.location.origin) {
    if (url.hostname.includes('fonts.googleapis.com') ||
        url.hostname.includes('fonts.gstatic.com') ||
        url.hostname.includes('cdnjs.cloudflare.com')) {
      event.respondWith(staleWhileRevalidate(request, CORE_CACHE));
      return;
    }
    // Let other cross-origin requests proceed over network
    return;
  }

  // A. ADMIN & MUTATION ROUTES: STRICT NETWORK-ONLY (Never Cache!)
  if (isAdminRoute(url) || request.method !== 'GET') {
    event.respondWith(
      fetch(request).catch(() => {
        // If user is offline and attempted to access admin panel
        if (request.mode === 'navigate') {
          return new Response(
            `<!DOCTYPE html>
            <html lang="en">
            <head>
              <meta charset="UTF-8">
              <meta name="viewport" content="width=device-width, initial-scale=1.0">
              <title>Admin Connection Required | Image Traditional</title>
              <style>
                body {
                  margin: 0;
                  background: #050D1F;
                  color: #f1f5f9;
                  font-family: system-ui, -apple-system, sans-serif;
                  display: flex;
                  align-items: center;
                  justify-content: center;
                  min-height: 100vh;
                  padding: 20px;
                  text-align: center;
                }
                .box {
                  background: #0F1F3D;
                  border: 1px solid rgba(212, 175, 55, 0.3);
                  border-radius: 16px;
                  padding: 36px 24px;
                  max-width: 480px;
                  box-shadow: 0 10px 30px rgba(0,0,0,0.6);
                }
                .icon { font-size: 3rem; margin-bottom: 12px; }
                h1 { color: #f5d580; font-size: 1.5rem; margin-bottom: 12px; }
                p { color: #94a3b8; font-size: 0.95rem; line-height: 1.6; margin-bottom: 24px; }
                .btn {
                  display: inline-block;
                  background: #d4af37;
                  color: #050D1F;
                  text-decoration: none;
                  font-weight: 700;
                  padding: 10px 20px;
                  border-radius: 8px;
                  transition: transform 0.2s;
                }
                .btn:hover { transform: translateY(-2px); }
              </style>
            </head>
            <body>
              <div class="box">
                <div class="icon">🔒</div>
                <h1>Admin Panel Requires Internet</h1>
                <p>Administrative functions interact directly with the live MongoDB Atlas database and cannot be executed offline. Please reconnect to the internet to perform bookings and management tasks.</p>
                <div style="display:flex; flex-direction:column; gap:10px; margin:20px 0;">
                  <a href="/kediya" class="btn" style="background:#1e293b; color:#d4af37; border:1px solid #d4af37;">🕺 Browse Saved Kediya</a>
                  <a href="/choli" class="btn" style="background:#1e293b; color:#d4af37; border:1px solid #d4af37;">💃 Browse Saved Choli</a>
                  <a href="/catalogue/fancy/" class="btn" style="background:#1e293b; color:#d4af37; border:1px solid #d4af37;">🎭 Browse Saved Fancy Dress</a>
                </div>
                <button type="button" onclick="window.location.reload()" class="btn">🔄 Retry Connection</button>
              </div>
            </body>
            </html>`,
            {
              status: 503,
              headers: { 'Content-Type': 'text/html; charset=utf-8' }
            }
          );
        }

        // Return JSON error for offline admin API requests
        return new Response(
          JSON.stringify({
            status: 'offline',
            message: 'Internet connection is required for Admin operations.'
          }),
          {
            status: 503,
            headers: { 'Content-Type': 'application/json' }
          }
        );
      })
    );
    return;
  }

  // B. CATALOGUE SYNC API ROUTE (/api/catalogue/sync)
  if (url.pathname === '/api/catalogue/sync') {
    event.respondWith(networkFirst(request, DATA_CACHE, 2500));
    return;
  }

  // C. PUBLIC CATALOGUE HTML PAGES (Home, /kediya, /choli, /catalogue/fancy/*)
  if (request.mode === 'navigate' || request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(networkFirstPage(request));
    return;
  }

  // D. CATALOGUE IMAGES (/static/Kediya/, /static/Choli/, /static/Products/, /static/Icons/, /static/Home_Img/)
  if (
    request.destination === 'image' ||
    url.pathname.startsWith('/static/Kediya') ||
    url.pathname.startsWith('/static/Choli') ||
    url.pathname.startsWith('/static/Products') ||
    url.pathname.startsWith('/static/Icons') ||
    url.pathname.startsWith('/static/Home_Img')
  ) {
    event.respondWith(cacheFirstImage(request));
    return;
  }

  // E. CORE STATIC ASSETS (CSS, JS, Fonts)
  if (
    url.pathname.startsWith('/static/CSS/') ||
    url.pathname.startsWith('/static/JS/') ||
    url.pathname.endsWith('.js') ||
    url.pathname.endsWith('.css')
  ) {
    event.respondWith(staleWhileRevalidate(request, CORE_CACHE));
    return;
  }

  // F. DEFAULT FALLBACK
  event.respondWith(
    caches.match(request).then((cached) => {
      return cached || fetch(request);
    })
  );
});

// ── STRATEGY IMPLEMENTATIONS ────────────────────────────────────────────────

/**
 * Network-First for HTML Pages with short timeout and fallback to cache / offline.html
 */
async function networkFirstPage(request) {
  try {
    // 2.5s network timeout to prevent hanging on weak connections
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 2500);

    const networkResponse = await fetch(request, { signal: controller.signal });
    clearTimeout(timeoutId);

    if (networkResponse && networkResponse.status === 200) {
      const cache = await caches.open(PAGES_CACHE);
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (err) {
    // Network failed or timed out: fall back to cached page
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }

    // Try core cache (e.g. pre-cached /, /kediya, /choli, etc.)
    const coreCached = await caches.match(request.url);
    if (coreCached) {
      return coreCached;
    }

    // If completely offline and page never visited, return offline fallback page
    const offlinePage = await caches.match('/offline.html');
    if (offlinePage) {
      return offlinePage;
    }

    return new Response('Offline: Page not cached yet. Reconnect to browse.', {
      status: 503,
      headers: { 'Content-Type': 'text/plain' }
    });
  }
}

/**
 * Network-First for Data API (/api/catalogue/sync)
 */
async function networkFirst(request, cacheName, timeoutMs = 2500) {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    const networkResponse = await fetch(request, { signal: controller.signal });
    clearTimeout(timeoutId);

    if (networkResponse && networkResponse.status === 200) {
      const cache = await caches.open(cacheName);
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (err) {
    const cached = await caches.match(request);
    if (cached) {
      return cached;
    }
    return new Response(
      JSON.stringify({ status: 'offline', message: 'Offline - showing stored cache' }),
      { status: 200, headers: { 'Content-Type': 'application/json' } }
    );
  }
}

/**
 * Stale-While-Revalidate for CSS, JS, and Fonts
 */
async function staleWhileRevalidate(request, cacheName) {
  const cachedResponse = await caches.match(request);

  const fetchPromise = fetch(request)
    .then(async (networkResponse) => {
      if (networkResponse && networkResponse.status === 200) {
        const cache = await caches.open(cacheName);
        cache.put(request, networkResponse.clone());
      }
      return networkResponse;
    })
    .catch(() => cachedResponse);

  return cachedResponse || fetchPromise;
}

/**
 * Cache-First for Images with LRU size limit
 */
async function cacheFirstImage(request) {
  const cached = await caches.match(request);
  if (cached) {
    return cached;
  }

  try {
    const networkResponse = await fetch(request);
    if (networkResponse && networkResponse.status === 200) {
      const cache = await caches.open(IMAGES_CACHE);
      cache.put(request, networkResponse.clone());
      trimCache(IMAGES_CACHE, MAX_IMAGE_CACHE_ITEMS);
    }
    return networkResponse;
  } catch (err) {
    // Return fallback icon if offline and image not cached
    const fallback = await caches.match('/static/Home_Img/favicon.png');
    return fallback || new Response('', { status: 404 });
  }
}

/**
 * Trim cache to keep it under maxItems
 */
async function trimCache(cacheName, maxItems) {
  try {
    const cache = await caches.open(cacheName);
    const keys = await cache.keys();
    if (keys.length > maxItems) {
      // Remove the oldest 20 items
      const deleteCount = keys.length - maxItems + 20;
      for (let i = 0; i < deleteCount; i++) {
        await cache.delete(keys[i]);
      }
    }
  } catch (e) {
    // Non-fatal cache trim error
  }
}

// ── 4. MESSAGE EVENT ────────────────────────────────────────────────────────
self.addEventListener('message', (event) => {
  const data = event.data;
  if (!data) return;

  if (data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }

  if (data.type === 'GET_VERSION') {
    event.ports[0]?.postMessage({ version: CACHE_VERSION });
  }

  if (data.type === 'PRECACHE_URLS' && Array.isArray(data.urls)) {
    caches.open(IMAGES_CACHE).then((cache) => {
      data.urls.forEach((url) => {
        cache.match(url).then((existing) => {
          if (!existing) {
            fetch(url).then((res) => {
              if (res.status === 200) cache.put(url, res);
            }).catch(() => {});
          }
        });
      });
    });
  }
});
