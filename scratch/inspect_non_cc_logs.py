import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from website.general.db import client, MONGO_DB_PRODUCTION

prod_db = client[MONGO_DB_PRODUCTION]
nav_2026 = prod_db['Navaratri_2026']
nav_logs = prod_db['Navaratri_2026_logs']

cc_mobiles = set(str(b.get('mobile') or '').strip() for b in nav_2026.find() if b.get('mobile'))
all_logs = list(nav_logs.find())
non_cc_logs_with_mobile = [l for l in all_logs if str(l.get('mobile') or '').strip() and str(l.get('mobile') or '').strip() not in cc_mobiles]

print(f"Total non-cc logs with mobile: {len(non_cc_logs_with_mobile)}")
for l in non_cc_logs_with_mobile:
    det = str(l.get('details') or '').replace('\u20b9', 'Rs.')
    print(f"{l.get('mobile')} | {l.get('name')} | {l.get('action')} | {l.get('date_stamp')} | {det[:70]} | {l.get('_id')}")
