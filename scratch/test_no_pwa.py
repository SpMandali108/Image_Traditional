import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from website import create_app

app = create_app()
with app.app_context(), app.test_client() as client:
    # 1. Manifest
    r_man = client.get('/manifest.json')
    assert r_man.status_code == 404, f'Expected 404 for manifest, got {r_man.status_code}'
    print('PASS 1: /manifest.json returns 404 (no PWA manifest)')

    # 2. Base template on /
    r_home = client.get('/')
    assert r_home.status_code == 200
    assert b'rel="manifest"' not in r_home.data, 'Found manifest link in HTML!'
    assert b'pwa-manager.js' not in r_home.data, 'Found pwa-manager.js in HTML!'
    assert b'pwaNetworkBadge' not in r_home.data, 'Found pwaNetworkBadge in HTML!'
    assert b'iosInstallModal' not in r_home.data, 'Found iosInstallModal in HTML!'
    assert b'pwaUpdateToast' not in r_home.data, 'Found pwaUpdateToast in HTML!'
    assert b'offlineModal' not in r_home.data, 'Found offlineModal in HTML!'
    assert b'navigator.serviceWorker.getRegistrations' in r_home.data, 'Missing service worker unregister script!'
    print('PASS 2: Website HTML has no PWA elements, has automatic worker & cache cleanup script')

    # 3. sw.js returns self-retiring script
    r_sw = client.get('/sw.js')
    assert r_sw.status_code == 200
    assert b'self.registration.unregister' in r_sw.data, 'sw.js missing unregister!'
    print('PASS 3: /sw.js serves self-unregistering retirement worker')

    # 4. Native App launcher /app
    r_app = client.get('/app')
    assert r_app.status_code == 302
    assert '/login' in r_app.headers['Location']
    print('PASS 4: Native app launcher /app routes unauthenticated to /login')

    # 5. App version endpoint
    r_ver = client.get('/api/app/version')
    assert r_ver.status_code == 200
    data = r_ver.get_json()
    assert 'version_code' in data and 'apk_url' in data
    print('PASS 5: /api/app/version returns native APK metadata')

    # 6. Authenticated admin app download
    with client.session_transaction() as sess:
        sess['logged_in'] = True
    r_admin_app = client.get('/app')
    assert r_admin_app.status_code == 302
    assert '/admin' in r_admin_app.headers['Location']

    r_admin_page = client.get('/admin')
    assert r_admin_page.status_code == 200
    assert b'Download Image Traditional App' in r_admin_page.data
    assert b'adminInstallActionBtn' not in r_admin_page.data
    print('PASS 6: Admin dashboard displays direct APK download card and no PWA install button')

    # 7. Check header on /admin: "Download App" button present
    assert b'Download App' in r_admin_page.data
    print('PASS 7: Admin header has direct native APK Download App button')

print('\n======================================')
print('ALL NO-PWA VERIFICATION TESTS PASSED!')
print('======================================')
