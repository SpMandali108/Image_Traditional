import os, re, urllib.parse

base = 'android/app/src/main/assets/web'
pages = ['home.html', 'kediya.html', 'choli.html', 'fancy_subcategories.html']

missing = 0
found = 0

for p in pages:
    fpath = os.path.join(base, p)
    if not os.path.exists(fpath):
        print(f"Page missing: {fpath}")
        continue
    with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
        html = f.read()
    
    refs = re.findall(r'[\'\"](/static/[^\'\"?#]+)', html)
    for ref in set(refs):
        decoded = urllib.parse.unquote(ref)
        target = os.path.join(base, decoded.lstrip('/'))
        if os.path.exists(target):
            found += 1
        else:
            print(f'MISSING in {p}: {ref} -> {target}')
            missing += 1

# Check subcategory pages
sub_dir = os.path.join(base, 'fancy_sub')
if os.path.exists(sub_dir):
    for f in os.listdir(sub_dir):
        if f.endswith('.html'):
            with open(os.path.join(sub_dir, f), 'r', encoding='utf-8', errors='ignore') as sf:
                html = sf.read()
            refs = re.findall(r'[\'\"](/static/[^\'\"?#]+)', html)
            for ref in set(refs):
                decoded = urllib.parse.unquote(ref)
                target = os.path.join(base, decoded.lstrip('/'))
                if os.path.exists(target):
                    found += 1
                else:
                    print(f'MISSING in fancy_sub/{f}: {ref} -> {target}')
                    missing += 1

print(f"VERIFICATION COMPLETED: Found {found} assets, Missing {missing} assets.")
