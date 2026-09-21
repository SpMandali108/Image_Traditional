import os
import re

routes = []
for root, dirs, files in os.walk('website'):
    for f in files:
        if f.endswith('.py'):
            filepath = os.path.join(root, f)
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as fp:
                content = fp.read()
            pattern = re.compile(r'(@[\w\.]+\.route\([^)]+\)\s*)+(def\s+(\w+)\s*\([^)]*\):(?:\n(?:[ \t]+.*|\s*))*?)(?=\n\S|\Z)', re.MULTILINE)
            for m in pattern.finditer(content):
                decorators = re.findall(r'@[\w\.]+\.route\(([^)]+)\)', m.group(0))
                func_body = m.group(0)
                func_name = m.group(3)
                has_auth = 'logged_in' in func_body
                for dec in decorators:
                    route_url = dec.split(',')[0].strip(' "\'')
                    routes.append((route_url, func_name, filepath, has_auth))

print(f"Total routes found: {len(routes)}")
print("\n--- PUBLIC ROUTES (NO LOGIN REQUIRED) ---")
public_routes = []
for r, fn, fp, auth in routes:
    if not auth:
        public_routes.append((r, fn, fp))
        print(f"Route: {r:<40} Function: {fn:<25} File: {fp}")

print(f"\nTotal Public Routes: {len(public_routes)}")
