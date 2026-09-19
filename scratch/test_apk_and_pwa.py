import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from website import create_app

app = create_app()
app.config['TESTING'] = True
client = app.test_client()

print("--- Starting APK & PWA Verification Suite ---")

# 1. Launcher Route /app - Unauthenticated redirects to /login
res = client.get('/app', follow_redirects=False)
assert res.status_code == 302, f"/app unauthenticated returned {res.status_code}, expected 302"
assert '/login' in res.headers.get('Location', ''), f"Redirect was {res.headers.get('Location')}, expected /login"
print("[OK] TEST 1 PASSED: /app unauthenticated redirects to /login.")

# 2. Launcher Route /app - Authenticated redirects to /admin
with client.session_transaction() as sess:
    sess['logged_in'] = True

res = client.get('/app', follow_redirects=False)
assert res.status_code == 302, f"/app authenticated returned {res.status_code}, expected 302"
assert '/admin' in res.headers.get('Location', ''), f"Redirect was {res.headers.get('Location')}, expected /admin"
print("[OK] TEST 2 PASSED: /app authenticated redirects to /admin.")

# 3. Public Pages - Must NOT contain Download APK button or leaked internal actions
with client.session_transaction() as sess:
    sess.clear()

public_pages = ['/', '/kediya', '/choli', '/catalogue/fancy/', '/login']
for path in public_pages:
    res = client.get(path)
    assert res.status_code == 200, f"{path} returned {res.status_code}"
    html = res.get_data(as_text=True)
    assert 'id="apkDownloadBtn"' not in html, f"Security violation: apkDownloadBtn exposed on public page {path}!"
    assert 'id="adminDownloadApkBtn"' not in html, f"Security violation: adminDownloadApkBtn exposed on public page {path}!"
    assert 'Download Image Traditional App' not in html, f"Security violation: Download APK CTA leaked on public page {path}!"
    print(f"[OK] TEST 3 PASSED: Public page '{path}' has NO Download APK buttons.")

# 4. Authenticated Admin Area - Must contain Download APK buttons
with client.session_transaction() as sess:
    sess['logged_in'] = True

res = client.get('/admin')
assert res.status_code == 200, f"/admin returned {res.status_code}"
admin_html = res.get_data(as_text=True)
assert 'id="apkDownloadBtn"' in admin_html, "apkDownloadBtn missing from admin panel header!"
assert 'id="adminDownloadApkBtn"' in admin_html, "adminDownloadApkBtn missing from admin dashboard!"
print("[OK] TEST 4 PASSED: Admin panel correctly exposes private Download APK CTAs to logged-in admin.")

# 5. Download APK Route Protection
with client.session_transaction() as sess:
    sess.clear()

res = client.get('/download/app', follow_redirects=False)
assert res.status_code == 302, f"Unauthenticated /download/app returned {res.status_code}, expected 302 redirect"
assert '/login' in res.headers.get('Location', ''), "Unauthenticated /download/app did not redirect to /login"
print("[OK] TEST 5 PASSED: /download/app is securely protected by login authentication.")

# 6. Android Project Files Verification
android_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'android'))
required_files = [
    'build.gradle.kts',
    'settings.gradle.kts',
    'gradle.properties',
    'local.properties',
    'app/build.gradle.kts',
    'app/proguard-rules.pro',
    'app/src/main/AndroidManifest.xml',
    'app/src/main/java/com/imagetraditional/app/MainActivity.kt',
    'app/src/main/java/com/imagetraditional/app/WebAppInterface.kt',
    'app/src/main/res/layout/activity_main.xml',
    'app/src/main/res/values/strings.xml',
    'app/src/main/res/values/colors.xml',
    'app/src/main/res/values/themes.xml',
    'app/src/main/res/mipmap-mdpi/ic_launcher.png',
    'app/src/main/res/mipmap-hdpi/ic_launcher.png',
    'app/src/main/res/mipmap-xhdpi/ic_launcher.png',
    'app/src/main/res/mipmap-xxhdpi/ic_launcher.png',
    'app/src/main/res/mipmap-xxxhdpi/ic_launcher.png',
]

for rf in required_files:
    full_p = os.path.join(android_root, rf)
    assert os.path.exists(full_p), f"Required Android project file missing: {rf}"
print("[OK] TEST 6 PASSED: All Android Studio project files, Kotlin code, layouts, and mipmaps verified.")

# 7. Authenticated APK Binary Download
with client.session_transaction() as sess:
    sess['logged_in'] = True

res = client.get('/download/app')
assert res.status_code == 200, f"Authenticated /download/app failed with {res.status_code}"
assert res.content_type == 'application/vnd.android.package-archive', f"Unexpected content-type: {res.content_type}"
assert len(res.data) > 4 * 1024 * 1024, f"APK size too small: {len(res.data)} bytes"
print(f"[OK] TEST 7 PASSED: /download/app served valid APK binary ({len(res.data) / (1024*1024):.2f} MB).")

# 8. Verify APK Zip Structure (Valid APK file)
import zipfile
release_apk = os.path.join(android_root, 'app', 'build', 'outputs', 'apk', 'release', 'ImageTraditional.apk')
assert os.path.exists(release_apk), f"Release APK missing: {release_apk}"
with zipfile.ZipFile(release_apk, 'r') as z:
    names = z.namelist()
    assert 'AndroidManifest.xml' in names, "AndroidManifest.xml missing from compiled APK!"
    assert any(n.startswith('classes') and n.endswith('.dex') for n in names), "DEX files missing from compiled APK!"
    assert 'resources.arsc' in names, "resources.arsc missing from compiled APK!"
    print(f"[OK] TEST 8 PASSED: Release APK archive verified (contains {len(names)} entries, valid DEX and Manifest).")

debug_apk = os.path.join(android_root, 'app', 'build', 'outputs', 'apk', 'debug', 'ImageTraditional-debug.apk')
assert os.path.exists(debug_apk), f"Debug APK missing: {debug_apk}"
with zipfile.ZipFile(debug_apk, 'r') as z:
    names = z.namelist()
    assert 'AndroidManifest.xml' in names, "AndroidManifest.xml missing from debug APK!"
    print(f"[OK] TEST 9 PASSED: Debug APK archive verified (contains {len(names)} entries).")

print("--- ALL 9 TESTS PASSED SUCCESSFULLY! ---")

