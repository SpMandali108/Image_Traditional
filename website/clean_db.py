import sys
sys.path.insert(0, '.')
from website.general.db import ncustomers, fcustomers

n_cleaned = 0
for c in ncustomers.find():
    a = c.get('address')
    n = c.get('name')
    changed = False
    upd = {}
    if isinstance(a, str) and ('\r' in a or '\n' in a):
        upd['address'] = a.replace('\r', ' ').replace('\n', ' ').strip()
        changed = True
    if isinstance(n, str) and ('\r' in n or '\n' in n):
        upd['name'] = n.replace('\r', ' ').replace('\n', ' ').strip()
        changed = True
    if changed:
        ncustomers.update_one({'_id': c['_id']}, {'$set': upd})
        n_cleaned += 1

f_cleaned = 0
for c in fcustomers.find():
    a = c.get('address')
    n = c.get('name')
    changed = False
    upd = {}
    if isinstance(a, str) and ('\r' in a or '\n' in a):
        upd['address'] = a.replace('\r', ' ').replace('\n', ' ').strip()
        changed = True
    if isinstance(n, str) and ('\r' in n or '\n' in n):
        upd['name'] = n.replace('\r', ' ').replace('\n', ' ').strip()
        changed = True
    if changed:
        fcustomers.update_one({'_id': c['_id']}, {'$set': upd})
        f_cleaned += 1

print(f"SUCCESS: Cleaned {n_cleaned} Navaratri and {f_cleaned} Fancy records in MongoDB!")
