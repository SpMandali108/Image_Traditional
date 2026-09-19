import os, re

for root, dirs, files in os.walk('website'):
    for file in files:
        if file.endswith('.py'):
            p = os.path.join(root, file)
            with open(p, 'r', encoding='utf-8', errors='ignore') as f:
                c = f.read()
                for m in re.finditer(r'@(\w+)\.route\([\'\"]([^\'\"]+)[\'\"]', c):
                    print(f"{m.group(1)} -> {m.group(2)} ({p})")
