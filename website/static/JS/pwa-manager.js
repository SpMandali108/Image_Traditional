/**
 * Image Traditional - Progressive Web App (PWA) Client Manager
 * Handles Service Worker lifecycle, Install Prompt, Network Monitoring,
 * IndexedDB Catalogue Synchronization, and Offline Protection.
 */

(function () {
  'use strict';

  // ── 1. GLOBAL STATE & CONSTANTS ──────────────────────────────────────────
  let deferredInstallPrompt = null;
  let isUpdatingWorker = false;
  const DB_NAME = 'ImageTraditionalCatalogueDB';
  const DB_VERSION = 1;

  // Detect iOS Safari & Standalone mode
  const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
  const isStandalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;

  // Capture install prompt at top level immediately before any other events fire
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredInstallPrompt = e;
    console.log('[PWA] beforeinstallprompt event captured.');
    const headerBtn = document.getElementById('pwaInstallBtn');
    if (headerBtn) {
      headerBtn.classList.add('pulse-glow');
    }
  });

  // ── 2. INITIALIZATION ON DOM READY ────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    initServiceWorker();
    initInstallPrompt();
    initNetworkMonitor();
    initIndexedDB();
    initOfflineGuards();

    // If online, perform background sync of catalogue data
    if (navigator.onLine) {
      syncCatalogueData();
    }
  });

  // ── 3. SERVICE WORKER REGISTRATION & UPDATES ──────────────────────────────
  function initServiceWorker() {
    if (!('serviceWorker' in navigator)) {
      console.log('[PWA] Service workers are not supported by this browser.');
      return;
    }

    window.addEventListener('load', () => {
      navigator.serviceWorker
        .register('/service-worker.js', { scope: '/' })
        .then((registration) => {
          console.log('[PWA] Service Worker registered with scope:', registration.scope);

          // Check if an updated service worker is already waiting
          if (registration.waiting) {
            showUpdateToast(registration.waiting);
          }

          // Monitor for new service worker installation
          registration.addEventListener('updatefound', () => {
            const newWorker = registration.installing;
            if (!newWorker) return;

            newWorker.addEventListener('statechange', () => {
              if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                // New update available
                showUpdateToast(newWorker);
              }
            });
          });

          // Check for service worker updates periodically (every 30 mins)
          setInterval(() => {
            if (navigator.onLine) {
              registration.update().catch(() => {});
            }
          }, 30 * 60 * 1000);

          // Also check for updates when returning online
          window.addEventListener('online', () => {
            registration.update().catch(() => {});
          });
        })
        .catch((error) => {
          console.error('[PWA] Service Worker registration failed:', error);
        });

      // Reload smoothly when new service worker takes control
      navigator.serviceWorker.addEventListener('controllerchange', () => {
        if (isUpdatingWorker) {
          window.location.reload();
        }
      });
    });
  }

  function showUpdateToast(worker) {
    const toast = document.getElementById('pwaUpdateToast');
    const updateBtn = document.getElementById('pwaUpdateBtn');
    if (!toast || !updateBtn) return;

    toast.style.display = 'flex';

    updateBtn.onclick = () => {
      isUpdatingWorker = true;
      if (worker) {
        worker.postMessage({ type: 'SKIP_WAITING' });
      }
      toast.style.display = 'none';
    };
  }

  // ── 4. PWA INSTALL PROMPT HANDLING (Private Admin App) ───────────────────
  function initInstallPrompt() {
    const headerInstallBtn = document.getElementById('pwaInstallBtn');
    const adminPwaSection = document.getElementById('adminPwaInstallSection');
    const adminActionBtn = document.getElementById('adminInstallActionBtn');
    const installModal = document.getElementById('iosInstallModal');
    const iosBlock = document.getElementById('iosInstructionsBlock');
    const adBlock = document.getElementById('androidDesktopInstructionsBlock');
    const modalDesc = document.getElementById('pwaModalDesc');

    // If neither element exists (unauthenticated public visitor), exit
    if (!headerInstallBtn && !adminActionBtn) {
      return;
    }

    // If app is running in standalone mode (already installed & launched as app)
    if (isStandalone) {
      if (headerInstallBtn) headerInstallBtn.style.display = 'none';
      if (adminActionBtn) {
        adminActionBtn.disabled = true;
        adminActionBtn.innerHTML = '<span class="icon">✔</span><span>App Installed</span>';
        adminActionBtn.style.opacity = '0.75';
        adminActionBtn.style.cursor = 'default';
      }
      return;
    }

    // App is in browser mode - ensure admin install options are visible and ready
    if (headerInstallBtn) {
      headerInstallBtn.style.display = 'inline-flex';
      if (deferredInstallPrompt) {
        headerInstallBtn.classList.add('pulse-glow');
      }
    }
    if (adminPwaSection) {
      adminPwaSection.style.display = 'block';
    }

    async function triggerInstallFlow() {
      // Case 1: Browser has fired native beforeinstallprompt (Chromium / Android Chrome / Edge)
      if (deferredInstallPrompt) {
        if (headerInstallBtn) headerInstallBtn.classList.remove('pulse-glow');
        deferredInstallPrompt.prompt();

        const { outcome } = await deferredInstallPrompt.userChoice;
        console.log(`[PWA] Install prompt outcome: ${outcome}`);

        if (outcome === 'accepted') {
          deferredInstallPrompt = null;
          if (headerInstallBtn) headerInstallBtn.style.display = 'none';
          if (adminActionBtn) {
            adminActionBtn.disabled = true;
            adminActionBtn.innerHTML = '<span class="icon">✔</span><span>App Installed</span>';
            adminActionBtn.style.opacity = '0.75';
          }
          showStatusNotice('Image Traditional App Installed!', 'success');
        }
        return;
      }

      // Case 2: Browser has not fired prompt or is iOS / Safari / Firefox
      if (installModal) {
        if (isIOS) {
          if (iosBlock) iosBlock.style.display = 'block';
          if (adBlock) adBlock.style.display = 'none';
          if (modalDesc) modalDesc.textContent = 'Follow these quick steps to install Image Traditional on your iPhone or iPad:';
        } else {
          if (iosBlock) iosBlock.style.display = 'none';
          if (adBlock) adBlock.style.display = 'block';
          if (modalDesc) modalDesc.textContent = 'Follow these quick steps to install Image Traditional on your computer or mobile:';
        }
        installModal.style.display = 'flex';
      }
    }

    if (headerInstallBtn) {
      headerInstallBtn.addEventListener('click', triggerInstallFlow);
    }
    if (adminActionBtn) {
      adminActionBtn.addEventListener('click', triggerInstallFlow);
    }

    // Detect when app was successfully installed
    window.addEventListener('appinstalled', () => {
      console.log('[PWA] Image Traditional successfully installed!');
      if (headerInstallBtn) headerInstallBtn.style.display = 'none';
      if (adminActionBtn) {
        adminActionBtn.disabled = true;
        adminActionBtn.innerHTML = '<span class="icon">✔</span><span>App Installed</span>';
        adminActionBtn.style.opacity = '0.75';
      }
      deferredInstallPrompt = null;
      showStatusNotice('App Installed Successfully!', 'success');
    });
  }

  // ── 5. REAL-TIME NETWORK STATUS MONITORING ────────────────────────────────
  function initNetworkMonitor() {
    const badge = document.getElementById('pwaNetworkBadge');
    if (!badge) return;

    const dot = badge.querySelector('.pwa-dot');
    const text = badge.querySelector('.pwa-status-text');

    function updateNetworkStatus(online) {
      const isAdmin = window.location.pathname.startsWith('/admin') ||
                      window.location.pathname.startsWith('/fancy') && !window.location.pathname.startsWith('/catalogue/fancy') ||
                      window.location.pathname.startsWith('/navaratri') ||
                      window.location.pathname.startsWith('/book');

      if (online) {
        badge.className = 'pwa-status-badge online';
        if (text) text.textContent = 'Online';

        // Trigger synchronization when coming back online
        syncCatalogueData(true);
      } else {
        badge.className = 'pwa-status-badge offline';
        if (text) {
          text.textContent = isAdmin
            ? 'Offline — Connection required for Admin'
            : 'Offline — Showing saved catalogue';
        }
      }
    }

    window.addEventListener('online', () => updateNetworkStatus(true));
    window.addEventListener('offline', () => updateNetworkStatus(false));

    // Initialize state
    updateNetworkStatus(navigator.onLine);
  }

  // ── 6. INDEXEDDB CATALOGUE STORAGE & SYNCHRONIZATION ──────────────────────
  let dbPromise = null;

  function initIndexedDB() {
    if (!('indexedDB' in window)) {
      console.log('[PWA] IndexedDB not supported by this browser.');
      return;
    }

    dbPromise = new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onupgradeneeded = (e) => {
        const db = e.target.result;

        // Structured catalogue items store
        if (!db.objectStoreNames.contains('catalogue_items')) {
          const itemStore = db.createObjectStore('catalogue_items', { keyPath: 'unique_key' });
          itemStore.createIndex('category', 'category', { unique: false });
          itemStore.createIndex('subCategory', 'subCategory', { unique: false });
          itemStore.createIndex('name', 'name', { unique: false });
        }

        // Metadata store (for versions and timestamps)
        if (!db.objectStoreNames.contains('catalogue_meta')) {
          db.createObjectStore('catalogue_meta', { keyPath: 'key' });
        }
      };

      request.onsuccess = (e) => resolve(e.target.result);
      request.onerror = (e) => reject(e.target.error);
    });
  }

  async function syncCatalogueData(isReconnection = false) {
    if (!navigator.onLine) return;

    const badge = document.getElementById('pwaNetworkBadge');
    const text = badge?.querySelector('.pwa-status-text');

    if (isReconnection && badge && text) {
      badge.className = 'pwa-status-badge syncing';
      text.textContent = 'Back online — Updating Catalogue...';
    }

    try {
      const response = await fetch('/api/catalogue/sync', {
        headers: { 'Cache-Control': 'no-cache' }
      });

      if (!response.ok) throw new Error('Sync failed with status ' + response.status);

      const json = await response.json();
      if (json.status !== 'success' || !json.data) return;

      const db = await dbPromise;
      if (!db) return;

      const tx = db.transaction(['catalogue_items', 'catalogue_meta'], 'readwrite');
      const itemStore = tx.objectStore('catalogue_items');
      const metaStore = tx.objectStore('catalogue_meta');

      const imageUrlsToPrecache = [];

      // A. Store Kediya items
      if (json.data.kediya && Array.isArray(json.data.kediya.items)) {
        json.data.kediya.items.forEach((item) => {
          itemStore.put({
            unique_key: `kediya_${item.name}`,
            category: 'kediya',
            subCategory: 'all',
            name: item.name,
            image: item.image,
            img_url: `/static/Kediya/${item.image}`
          });
        });
      }

      // B. Store Choli items
      if (json.data.choli && Array.isArray(json.data.choli.items)) {
        json.data.choli.items.forEach((item) => {
          itemStore.put({
            unique_key: `choli_${item.name}`,
            category: 'choli',
            subCategory: 'all',
            name: item.name,
            image: item.image,
            img_url: `/static/Choli/${item.image}`
          });
        });
      }

      // C. Store Fancy items
      if (json.data.fancy && Array.isArray(json.data.fancy.categories)) {
        json.data.fancy.categories.forEach((cat) => {
          if (Array.isArray(cat.items)) {
            cat.items.forEach((item) => {
              itemStore.put({
                unique_key: `fancy_${cat.name}_${item.file}`,
                category: 'fancy',
                subCategory: cat.name,
                name: item.name,
                file: item.file,
                desc: item.desc,
                img_url: item.img_url
              });
            });
          }
        });
      }

      // D. Store sync metadata
      metaStore.put({
        key: 'sync_info',
        version: json.version,
        updated_at: json.updated_at,
        last_sync_client: Date.now()
      });

      // Notify Service Worker to pre-warm top images
      if (navigator.serviceWorker.controller && imageUrlsToPrecache.length > 0) {
        navigator.serviceWorker.controller.postMessage({
          type: 'PRECACHE_URLS',
          urls: imageUrlsToPrecache.slice(0, 50)
        });
      }

      if (isReconnection && badge && text) {
        badge.className = 'pwa-status-badge success';
        text.textContent = 'Catalogue updated';
        setTimeout(() => {
          badge.className = 'pwa-status-badge online';
          text.textContent = 'Online';
        }, 3500);
      }
    } catch (err) {
      console.warn('[PWA] Catalogue sync skipped or offline:', err.message);
      if (isReconnection && badge && text) {
        badge.className = 'pwa-status-badge online';
        text.textContent = 'Online';
      }
    }
  }

  // ── 7. OFFLINE BOOKING & ADMIN PROTECTION GUARDS ──────────────────────────
  function initOfflineGuards() {
    // Intercept clicks on WhatsApp / Booking buttons when offline
    document.addEventListener('click', (e) => {
      const target = e.target.closest('#whatsappInquiryBtn, .action-btn-whatsapp, .inquiry-box a');
      if (target && !navigator.onLine) {
        e.preventDefault();
        e.stopPropagation();

        showOfflineBookingModal(
          "You are browsing the offline catalogue. Live availability check and booking inquiries require an active internet connection. Please connect to the internet to proceed, or call us directly."
        );
      }

      // Guard Admin buttons if clicked while offline
      const adminSubmitBtn = e.target.closest('form button[type="submit"], form input[type="submit"]');
      if (adminSubmitBtn && !navigator.onLine) {
        const isAdmin = window.location.pathname.startsWith('/admin') ||
                        window.location.pathname.startsWith('/fancy') && !window.location.pathname.startsWith('/catalogue/fancy') ||
                        window.location.pathname.startsWith('/navaratri') ||
                        window.location.pathname.startsWith('/book');
        if (isAdmin) {
          e.preventDefault();
          e.stopPropagation();
          showOfflineBookingModal(
            "Internet connection required. Administrative actions write directly to the live MongoDB Atlas database and cannot be performed offline."
          );
        }
      }
    }, true);
  }

  function showOfflineBookingModal(message) {
    const modal = document.getElementById('offlineModal');
    const msgEl = document.getElementById('offlineModalMsg');
    if (modal) {
      if (msgEl && message) msgEl.textContent = message;
      modal.style.display = 'flex';
    } else {
      alert(message);
    }
  }

  function showStatusNotice(msg, type = 'info') {
    const banner = document.createElement('div');
    banner.className = `pwa-toast-banner ${type}`;
    banner.textContent = msg;
    document.body.appendChild(banner);
    setTimeout(() => {
      banner.style.opacity = '0';
      setTimeout(() => banner.remove(), 400);
    }, 4000);
  }

  // Expose useful utilities to window for template scripts
  window.ImageTraditionalPWA = {
    syncCatalogueData,
    isStandalone: () => isStandalone,
    isOnline: () => navigator.onLine
  };

})();
