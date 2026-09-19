import os
import sys
import shutil
import urllib.parse

sys.path.insert(0, os.path.abspath('.'))
from website import create_app

def build_web_assets():
    print("=== EXPORTING PUBLIC PAGES & ASSETS FOR OFFLINE APK ===")
    app = create_app()

    base_assets_dir = os.path.join('android', 'app', 'src', 'main', 'assets', 'web')
    os.makedirs(base_assets_dir, exist_ok=True)
    fancy_sub_dir = os.path.join(base_assets_dir, 'fancy_sub')
    os.makedirs(fancy_sub_dir, exist_ok=True)

    with app.test_client() as client:
        # 1. Render Home page
        r = client.get('/')
        assert r.status_code == 200, f"Failed to render /: {r.status_code}"
        home_html_path = os.path.join(base_assets_dir, 'home.html')
        with open(home_html_path, 'wb') as f:
            f.write(r.data)
        print(f"[OK] Rendered Home page -> {home_html_path} ({len(r.data)} bytes)")

        # 2. Render Kediya page
        r = client.get('/kediya')
        assert r.status_code == 200, f"Failed to render /kediya: {r.status_code}"
        kediya_html_path = os.path.join(base_assets_dir, 'kediya.html')
        with open(kediya_html_path, 'wb') as f:
            f.write(r.data)
        print(f"[OK] Rendered Kediya catalogue -> {kediya_html_path} ({len(r.data)} bytes)")

        # 3. Render Choli page
        r = client.get('/choli')
        assert r.status_code == 200, f"Failed to render /choli: {r.status_code}"
        choli_html_path = os.path.join(base_assets_dir, 'choli.html')
        with open(choli_html_path, 'wb') as f:
            f.write(r.data)
        print(f"[OK] Rendered Choli catalogue -> {choli_html_path} ({len(r.data)} bytes)")

        # 4. Render Fancy Subcategories page
        r = client.get('/catalogue/fancy/')
        assert r.status_code == 200, f"Failed to render /catalogue/fancy/: {r.status_code}"
        fancy_subcat_path = os.path.join(base_assets_dir, 'fancy_subcategories.html')
        with open(fancy_subcat_path, 'wb') as f:
            f.write(r.data)
        print(f"[OK] Rendered Fancy Categories -> {fancy_subcat_path} ({len(r.data)} bytes)")

        # 5. Render each of the 20 Fancy Subcategory pages
        icon_map = [
            "Bhagwan", "Mataji", "Profession", "Freedom Fighter", "Regional",
            "Wild Animals", "Domestic Animals", "Water Animals", "Insects", "Birds",
            "Fruits", "Vegetables", "Halloween", "Cartoon", "Superhero",
            "International", "Flexi", "Nature", "Tiranga", "Others"
        ]
        for sub in icon_map:
            encoded_sub = urllib.parse.quote(sub)
            r = client.get(f'/catalogue/fancy/{encoded_sub}/')
            if r.status_code == 200:
                sub_file = os.path.join(fancy_sub_dir, f"{sub}.html")
                with open(sub_file, 'wb') as f:
                    f.write(r.data)
                print(f"[OK] Rendered Fancy Subcategory '{sub}' ({len(r.data)} bytes)")
            else:
                print(f"[WARN] Could not render subcategory '{sub}': status {r.status_code}")

    # 6. Copy static assets to assets/web/static/
    static_src = os.path.join('website', 'static')
    static_dst = os.path.join(base_assets_dir, 'static')
    os.makedirs(static_dst, exist_ok=True)

    folders_to_copy = [
        'Home_Img',
        'Icons',
        'CSS',
        'JS',
        'Kediya',
        'Choli',
        os.path.join('Products', 'Fancy')
    ]

    for folder in folders_to_copy:
        src_path = os.path.join(static_src, folder)
        dst_path = os.path.join(static_dst, folder)
        if os.path.exists(src_path):
            print(f"Copying {folder} to APK assets...")
            if os.path.exists(dst_path):
                shutil.rmtree(dst_path)
            shutil.copytree(src_path, dst_path)
            print(f"[OK] Copied {folder} successfully.")
        else:
            print(f"[WARN] Folder not found: {src_path}")

    print("\n=== WEB ASSETS EXPORT COMPLETED SUCCESSFULLY! ===")

if __name__ == '__main__':
    build_web_assets()
