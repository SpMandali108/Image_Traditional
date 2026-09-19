import os
import sys

# Ensure proper working directory
sys.path.insert(0, os.path.abspath('.'))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from website import create_app

app = create_app()
client = app.test_client()

print("--- Starting Private PWA & /app Verification Suite ---")

# 1. Manifest
res = client.get('/manifest.json')
assert res.status_code == 200, f"manifest failed: {res.status_code}"
manifest_data = res.get_json()
assert manifest_data["start_url"] == "/app", f"start_url is {manifest_data['start_url']}, expected /app"
assert manifest_data["id"] == "/app", f"id is {manifest_data['id']}, expected /app"
assert manifest_data["name"] == "Image Traditional"
assert manifest_data["display"] == "standalone"
assert manifest_data["theme_color"] == "#050D1F"
assert len(manifest_data["icons"]) >= 2
print("[OK] TEST 1 PASSED: /manifest.json configured with start_url: /app and standalone display.")

# 2. /app Route Unauthenticated -> Redirects to /login
res = client.get('/app', follow_redirects=False)
assert res.status_code == 302, f"/app unauthenticated returned {res.status_code}, expected 302"
assert '/login' in res.headers.get('Location', ''), f"Redirect location was {res.headers.get('Location')}, expected /login"
print("[OK] TEST 2 PASSED: /app unauthenticated redirects cleanly to /login.")

# 3. /app Route Authenticated -> Redirects to /admin
with client.session_transaction() as sess:
    sess['logged_in'] = True

res = client.get('/app', follow_redirects=False)
assert res.status_code == 302, f"/app authenticated returned {res.status_code}, expected 302"
assert '/admin' in res.headers.get('Location', ''), f"Redirect location was {res.headers.get('Location')}, expected /admin"
print("[OK] TEST 3 PASSED: /app authenticated redirects cleanly to /admin.")

# Clear session for public tests
with client.session_transaction() as sess:
    sess.clear()

# 4. Public Pages - Must NOT contain Install App button
public_pages = ['/', '/kediya', '/choli', '/catalogue/fancy/', '/login']
for path in public_pages:
    res = client.get(path)
    assert res.status_code == 200, f"{path} returned {res.status_code}"
    html = res.get_data(as_text=True)
    assert 'id="pwaInstallBtn"' not in html, f"Security violation: pwaInstallBtn exposed on public page {path}!"
    assert 'id="homeInstallBtn"' not in html, f"Security violation: homeInstallBtn exposed on public page {path}!"
    assert 'Install Image Traditional App' not in html, f"Install CTA text leaked on public page {path}!"
    print(f"[OK] TEST 4 PASSED: Public page '{path}' has NO Install App button.")

# 5. Authenticated Admin Area - Must contain Install App CTA
with client.session_transaction() as sess:
    sess['logged_in'] = True

res = client.get('/admin')
assert res.status_code == 200, f"/admin returned {res.status_code}"
admin_html = res.get_data(as_text=True)
assert 'id="pwaInstallBtn"' in admin_html, "pwaInstallBtn missing from admin panel header!"
assert 'id="adminInstallActionBtn"' in admin_html, "adminInstallActionBtn missing from admin dashboard!"
print("[OK] TEST 5 PASSED: Admin panel correctly exposes private Install App CTAs to logged-in admin.")

# Clear session
with client.session_transaction() as sess:
    sess.clear()

# 6. Service Worker
res = client.get('/service-worker.js')
assert res.status_code == 200, f"sw failed: {res.status_code}"
assert res.headers.get('Service-Worker-Allowed') == '/'
sw_content = res.get_data(as_text=True)
assert 'it-pwa-v1.0.2' in sw_content
assert "'/app'" in sw_content
print("[OK] TEST 6 PASSED: /service-worker.js served with Service-Worker-Allowed: / and v1.0.2.")

# 7. Offline Fallback
res = client.get('/offline.html')
assert res.status_code == 200, f"offline.html failed: {res.status_code}"
assert "Saved Catalogue Available" in res.get_data(as_text=True)
print("[OK] TEST 7 PASSED: /offline.html served successfully.")

# 8. Catalogue Sync API
res = client.get('/api/catalogue/sync')
assert res.status_code == 200, f"sync failed: {res.status_code}"
data = res.get_json()
assert data['status'] == 'success'
assert len(data['data']['kediya']['items']) > 0
assert len(data['data']['choli']['items']) > 0
assert len(data['data']['fancy']['categories']) > 0
print("[OK] TEST 8 PASSED: /api/catalogue/sync returning complete structured catalogue.")

# 9. Admin Protection (Security Check)
admin_routes = ['/admin', '/fancy_admin', '/navaratri_admin', '/book', '/fancy', '/modify', '/delete', '/calendar']
for route in admin_routes:
    res = client.get(route)
    assert res.status_code in (302, 401), f"Admin route {route} was not protected! Status: {res.status_code}"
print("[OK] TEST 9 PASSED: All admin management routes require authentication.")

# 10. Icons existence check
from PIL import Image
icons = [
    ('website/static/Icons/icon-192x192.png', (192, 192)),
    ('website/static/Icons/icon-512x512.png', (512, 512)),
    ('website/static/Icons/icon-maskable-192x192.png', (192, 192)),
    ('website/static/Icons/icon-maskable-512x512.png', (512, 512)),
    ('website/static/Icons/apple-touch-icon.png', (180, 180))
]
for icon_path, expected_size in icons:
    assert os.path.exists(icon_path), f"Icon missing: {icon_path}"
    im = Image.open(icon_path)
    assert im.size == expected_size, f"Icon {icon_path} size {im.size} != {expected_size}"
print("[OK] TEST 10 PASSED: All PWA icons (192, 512, maskable, apple-touch) verified.")

print("\n--- ALL 10 TESTS PASSED SUCCESSFULLY! ---")
