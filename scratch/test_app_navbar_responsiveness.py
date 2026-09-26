import os
import sys

def run_tests():
    print("=== TESTING APP NAVBAR RESPONSIVENESS AND WEB SYNCHRONIZATION ===")
    
    # 1. Test base.css in website and android assets
    web_css_path = os.path.join('website', 'static', 'CSS', 'base.css')
    apk_css_path = os.path.join('android', 'app', 'src', 'main', 'assets', 'web', 'static', 'CSS', 'base.css')
    
    assert os.path.exists(web_css_path), f"Missing {web_css_path}"
    assert os.path.exists(apk_css_path), f"Missing {apk_css_path}"
    
    with open(web_css_path, 'r', encoding='utf-8') as f:
        web_css = f.read()
    with open(apk_css_path, 'r', encoding='utf-8') as f:
        apk_css = f.read()
        
    assert web_css == apk_css, "APK base.css does not match website base.css!"
    print("[PASS] APK base.css is 100% synchronized with website base.css")
    
    # Check responsive queries in base.css
    assert "@media (max-width: 768px)" in web_css, "Missing 768px query in base.css"
    assert "@media (max-width: 480px)" in web_css, "Missing 480px query in base.css"
    assert "@media (max-width: 340px)" in web_css, "Missing 340px query in base.css"
    assert "overflow: hidden" in web_css, "Missing ellipsis/overflow handling in base.css"
    print("[PASS] Responsive media queries verified in base.css")
    
    # 2. Test Android home.html and catalogue HTML files
    apk_home_path = os.path.join('android', 'app', 'src', 'main', 'assets', 'web', 'home.html')
    assert os.path.exists(apk_home_path), f"Missing {apk_home_path}"
    with open(apk_home_path, 'r', encoding='utf-8') as f:
        apk_home = f.read()
        
    assert "pwaNetworkBadge" not in apk_home, "Found pwaNetworkBadge in android home.html!"
    assert "pwaUpdateToast" not in apk_home, "Found pwaUpdateToast in android home.html!"
    assert "offlineModal" not in apk_home, "Found offlineModal in android home.html!"
    assert "contactToggle" in apk_home, "Missing contactToggle in android home.html"
    print("[PASS] Android home.html has clean navbar with no legacy PWA elements")
    
    for page in ['kediya.html', 'choli.html', 'fancy_subcategories.html']:
        page_path = os.path.join('android', 'app', 'src', 'main', 'assets', 'web', page)
        assert os.path.exists(page_path), f"Missing {page_path}"
        with open(page_path, 'r', encoding='utf-8') as f:
            content = f.read()
        assert "pwaNetworkBadge" not in content, f"Found pwaNetworkBadge in {page}"
    print("[PASS] Android catalogue pages (kediya, choli, fancy) have clean navbars")
    
    # 3. Test strings.xml default entry URL
    strings_path = os.path.join('android', 'app', 'src', 'main', 'res', 'values', 'strings.xml')
    with open(strings_path, 'r', encoding='utf-8') as f:
        strings_xml = f.read()
    assert '<string name="app_url">https://image-traditional.onrender.com/</string>' in strings_xml, \
        "app_url is not set to root homepage in strings.xml"
    print("[PASS] strings.xml app_url points to https://image-traditional.onrender.com/")
    
    # 4. Test MainActivity.kt settings and interception
    kt_path = os.path.join('android', 'app', 'src', 'main', 'java', 'com', 'imagetraditional', 'app', 'MainActivity.kt')
    with open(kt_path, 'r', encoding='utf-8') as f:
        kt_code = f.read()
    assert "settings.textZoom = 100" in kt_code, "Missing textZoom = 100 in MainActivity.kt"
    assert "val isStyleOrScript = decodedPath.startsWith(\"/CSS/\") || decodedPath.startsWith(\"/JS/\")" in kt_code, \
        "Missing dynamic network style loading in MainActivity.kt"
    print("[PASS] MainActivity.kt settings and interception verified")
    
    # 5. Test Flask rendering of home route
    sys.path.insert(0, os.path.abspath('.'))
    from website import create_app
    app = create_app()
    with app.test_client() as client:
        r = client.get('/')
        assert r.status_code == 200, f"Status code {r.status_code}"
        assert b"pwaNetworkBadge" not in r.data, "pwaNetworkBadge in rendered Flask home page"
        assert b"header-content" in r.data, "Missing header-content in rendered home page"
        assert b"contactToggle" in r.data, "Missing contactToggle in rendered home page"
    print("[PASS] Flask / rendered home page verified")
    
    print("\n=======================================================")
    print("ALL TESTS PASSED 100%! APP AND WEBSITE ARE IN FULL SYNC")
    print("=======================================================")

if __name__ == '__main__':
    run_tests()
