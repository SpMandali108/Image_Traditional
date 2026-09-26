/**
 * Image Traditional - Service Worker & PWA Cache Cleanup
 * Ensures clean removal of any previously registered service workers and IndexedDB caches.
 */
(function () {
  'use strict';

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.getRegistrations().then(function (registrations) {
      for (var i = 0; i < registrations.length; i++) {
        registrations[i].unregister();
      }
    });
  }

  if ('caches' in window) {
    caches.keys().then(function (keys) {
      for (var j = 0; j < keys.length; j++) {
        caches.delete(keys[j]);
      }
    });
  }

  if ('indexedDB' in window) {
    try {
      indexedDB.deleteDatabase('ImageTraditionalOfflineDB');
    } catch (e) {}
  }
})();
