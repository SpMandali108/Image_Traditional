import os
import re
from urllib.parse import unquote

ASSETS_DIR = os.path.abspath("android/app/src/main/assets/web")
STATIC_DIR = os.path.join(ASSETS_DIR, "static")

html_files = []
for root, dirs, files in os.walk(ASSETS_DIR):
    for f in files:
        if f.endswith(".html"):
            html_files.append(os.path.relpath(os.path.join(root, f), ASSETS_DIR))

print(f"Total HTML files in APK assets: {len(html_files)}")
for h in sorted(html_files):
    print(f"  - {h}")

# Check all images referenced in HTML files
all_referenced_images = set()
missing_images = []
found_images = 0

for h_rel in html_files:
    h_path = os.path.join(ASSETS_DIR, h_rel)
    with open(h_path, "r", encoding="utf-8", errors="ignore") as fp:
        content = fp.read()
    
    # Find all src="..." and url_for or /static/
    img_matches = re.findall(r'src=["\']([^"\']+)["\']', content)
    for src in img_matches:
        if "/static/" in src or src.startswith("static/"):
            clean_src = src.split("?")[0].split("#")[0]
            idx = clean_src.find("/static/")
            if idx != -1:
                rel_static = clean_src[idx + len("/static/"):]
            elif clean_src.startswith("static/"):
                rel_static = clean_src[len("static/"):]
            else:
                continue
            rel_static = unquote(rel_static)
            all_referenced_images.add((rel_static, h_rel))

print(f"\nTotal unique static references found in HTML files: {len(all_referenced_images)}")

for rel_static, page in sorted(all_referenced_images):
    actual_path = os.path.join(STATIC_DIR, rel_static.replace("/", os.sep))
    # Also check underscore/space variations
    norm_space = rel_static.replace("_", " ")
    norm_underscore = rel_static.replace(" ", "_")
    alt_space = os.path.join(STATIC_DIR, norm_space.replace("/", os.sep))
    alt_underscore = os.path.join(STATIC_DIR, norm_underscore.replace("/", os.sep))

    if os.path.exists(actual_path):
        found_images += 1
    elif os.path.exists(alt_space) or os.path.exists(alt_underscore):
        print(f"[CASE MISMATCH] Referenced: {rel_static} on {page}")
    else:
        # Check if it's jpg fallback to webp
        if rel_static.endswith(".jpg"):
            webp_path = os.path.join(STATIC_DIR, rel_static.replace(".jpg", ".webp").replace("KediyaJpg", "Kediya").replace("CholiJpg", "Choli").replace("/", os.sep))
            if os.path.exists(webp_path):
                # JPG fallback is okay if WebP exists and WebView intercepts
                continue
        missing_images.append((rel_static, page))

print(f"Direct matches found: {found_images}")
print(f"Missing static files: {len(missing_images)}")
for m, page in missing_images:
    print(f"  MISSING: {m} (in {page})")
