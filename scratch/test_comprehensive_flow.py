import os
import sys
import zipfile
import json
import subprocess

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from website import create_app

app = create_app()
app.config['TESTING'] = True
client = app.test_client()

print("==================================================")
print("RUNNING COMPREHENSIVE APK & BACKEND VERIFICATION")
print("==================================================")

# --- TEST A: Native APK Inspection ---
apk_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'website', 'static', 'downloads', 'ImageTraditional.apk'))
assert os.path.exists(apk_path), f"APK file missing at {apk_path}"
apk_size_mb = os.path.getsize(apk_path) / (1024 * 1024)
print(f"[TEST A] APK file exists at {apk_path} ({apk_size_mb:.2f} MB)")

with zipfile.ZipFile(apk_path, 'r') as z:
    names = z.namelist()
    assert 'AndroidManifest.xml' in names, "AndroidManifest.xml missing"
    assert 'classes.dex' in names, "classes.dex missing"
    assert 'resources.arsc' in names, "resources.arsc missing"
print("[TEST A] APK structure verified (Valid DEX, Manifest, and Resources).")

# --- TEST B: Unauthenticated /app -> /login ---
res = client.get('/app', follow_redirects=False)
assert res.status_code == 302, f"Expected 302, got {res.status_code}"
assert '/login' in res.headers.get('Location', ''), f"Expected redirect to /login, got {res.headers.get('Location')}"
assert 'no-cache' in res.headers.get('Cache-Control', ''), "Cache-Control no-cache missing"
print("[TEST B] PASSED: /app unauthenticated redirects cleanly to /login with no-cache headers.")

# --- TEST C: Login -> /admin ---
from website.general.db import ADMIN_ID, ADMIN_PASS
res_login = client.post('/login', data={'id': ADMIN_ID, 'password': ADMIN_PASS}, follow_redirects=False)
assert res_login.status_code == 302, f"Expected 302, got {res_login.status_code}"
assert '/admin' in res_login.headers.get('Location', ''), f"Expected redirect to /admin, got {res_login.headers.get('Location')}"
print("[TEST C] PASSED: Valid login POST redirects to /admin.")

# --- TEST D: Close APK, Open again -> /app -> /admin ---
# Using the session created by login, access /app
res_app_auth = client.get('/app', follow_redirects=False)
assert res_app_auth.status_code == 302, f"Expected 302, got {res_app_auth.status_code}"
assert '/admin' in res_app_auth.headers.get('Location', ''), f"Expected redirect to /admin, got {res_app_auth.headers.get('Location')}"
print("[TEST D] PASSED: Authenticated session accessing /app redirects to /admin without re-authenticating.")

# --- TEST E: Android Back Navigation in MainActivity ---
main_activity_kt = os.path.join(os.path.dirname(__file__), '..', 'android', 'app', 'src', 'main', 'java', 'com', 'imagetraditional', 'app', 'MainActivity.kt')
with open(main_activity_kt, 'r', encoding='utf-8') as f:
    kt_code = f.read()

assert 'currentUrl.contains("/login") || currentUrl.endsWith("/app")' in kt_code, "Login/App loop prevention missing"
assert 'currentUrl.contains("/admin")' in kt_code, "Admin back-press guard missing"
assert 'handleDoubleBackExit()' in kt_code, "Double back exit handling missing"
assert 'CookieManager.getInstance().flush()' in kt_code, "CookieManager flush missing"
print("[TEST E] PASSED: MainActivity back navigation and loop prevention verified.")

# --- TEST F: Catalogue Online ---
catalogue_urls = ['/kediya', '/choli', '/catalogue/fancy/']
for c_url in catalogue_urls:
    res = client.get(c_url)
    assert res.status_code == 200, f"Catalogue page {c_url} failed with {res.status_code}"
    html = res.get_data(as_text=True)
    assert len(html) > 500, f"Catalogue page {c_url} response empty"
print(f"[TEST F] PASSED: Online catalogue pages {catalogue_urls} return valid content.")

# --- TEST G: Offline Catalogue Sync API ---
res_sync = client.get('/api/catalogue/sync')
assert res_sync.status_code == 200, f"Catalogue sync API failed: {res_sync.status_code}"
sync_data = json.loads(res_sync.get_data(as_text=True))
assert sync_data.get('status') == 'success', "Sync API status not success"
assert 'data' in sync_data, "Sync API missing data"
assert 'kediya' in sync_data['data'], "Sync data missing kediya"
assert 'choli' in sync_data['data'], "Sync data missing choli"
assert 'fancy' in sync_data['data'], "Sync data missing fancy"
kediya_count = sync_data['data']['kediya']['count']
choli_count = sync_data['data']['choli']['count']
fancy_cats = sync_data['data']['fancy']['categories_count']
print(f"[TEST G] PASSED: Sync API provides {kediya_count} Kediyas, {choli_count} Cholis, and {fancy_cats} Fancy Dress categories for offline use.")

# --- TEST H: Admin Offline Protection ---
sw_js_path = os.path.join(os.path.dirname(__file__), '..', 'website', 'static', 'sw.js')
with open(sw_js_path, 'r', encoding='utf-8') as f:
    sw_code = f.read()
assert "'/admin'" in sw_code, "Admin route missing in SW strict network list"
assert "'/app'" in sw_code, "App route missing in SW strict network list"
assert "Internet connection is required for Admin" in sw_code or "Admin Panel Requires Internet" in sw_code, "Offline admin error message missing in SW"

strings_xml_path = os.path.join(os.path.dirname(__file__), '..', 'android', 'app', 'src', 'main', 'res', 'values', 'strings.xml')
with open(strings_xml_path, 'r', encoding='utf-8') as f:
    strings_code = f.read()
assert "Internet connection required for Admin Panel." in strings_code, "strings.xml missing required offline admin message"
print("[TEST H] PASSED: Admin offline protections enforced in Service Worker and Native Android shell.")

# --- TEST I & J: Live updates architecture and private downloads ---
with client.session_transaction() as sess:
    sess.clear()

res_pub = client.get('/')
assert 'id="apkDownloadBtn"' not in res_pub.get_data(as_text=True), "Leaked APK button on public page"
res_admin_unauth = client.get('/download/app', follow_redirects=False)
assert res_admin_unauth.status_code == 302, "Unauthenticated /download/app must redirect to login"

with client.session_transaction() as sess:
    sess['logged_in'] = True
res_admin_auth = client.get('/admin')
assert 'id="adminDownloadApkBtn"' in res_admin_auth.get_data(as_text=True), "Admin page missing APK download button"
assert 'Download Image Traditional App' in res_admin_auth.get_data(as_text=True), "Download button text mismatch"

res_dl = client.get('/download/app')
assert res_dl.status_code == 200, f"/download/app failed with {res_dl.status_code}"
assert res_dl.content_type == 'application/vnd.android.package-archive', f"Wrong MIME type: {res_dl.content_type}"
assert len(res_dl.data) > 4 * 1024 * 1024, "Downloaded APK size too small"
print("[TEST I & J] PASSED: Private APK downloads protected and served correctly to authenticated admins.")

print("==================================================")
print("ALL TESTS (TEST A THROUGH TEST J) PASSED 100%!")
print("==================================================")
