import sys
import os
import re

sys.path.insert(0, os.getcwd())

from website.general.db import fcustomers, ncustomers, custom_localities
from website.navaratri.nroutes import KNOWN_LOCALITIES
from website.fancy.froutes import KNOWN_LOCALITIES_FANCY
from website.general.utils import resolve_customer_locality

localities = list(set(KNOWN_LOCALITIES + KNOWN_LOCALITIES_FANCY + [c.get('name') for c in custom_localities.find() if c.get('name')]))

print("Starting MongoDB address & locality auto-migration...")

# 1. Update Fancy Customers
f_custs = list(fcustomers.find())
f_updated = 0

for c in f_custs:
    loc = resolve_customer_locality(c, localities)
    if loc:
        raw_addr = (c.get("address") or "").strip()
        orig_addr = c.get("original_address") or raw_addr
        
        pattern = re.compile(r'[, \t]*\b' + re.escape(loc.strip()) + r'\b\s*$', re.IGNORECASE)
        cleaned_addr = pattern.sub('', raw_addr).strip() or raw_addr

        upd = {}
        if not c.get("locality"):
            upd["locality"] = loc
        if c.get("address") != cleaned_addr and cleaned_addr:
            upd["address"] = cleaned_addr
        if not c.get("original_address"):
            upd["original_address"] = orig_addr

        if upd:
            fcustomers.update_one({"_id": c["_id"]}, {"$set": upd})
            f_updated += 1

# 2. Update Navaratri Customers
n_custs = list(ncustomers.find())
n_updated = 0

for c in n_custs:
    loc = resolve_customer_locality(c, localities)
    if loc:
        raw_addr = (c.get("address") or "").strip()
        orig_addr = c.get("original_address") or raw_addr
        
        pattern = re.compile(r'[, \t]*\b' + re.escape(loc.strip()) + r'\b\s*$', re.IGNORECASE)
        cleaned_addr = pattern.sub('', raw_addr).strip() or raw_addr

        upd = {}
        if not c.get("locality"):
            upd["locality"] = loc
        if c.get("address") != cleaned_addr and cleaned_addr:
            upd["address"] = cleaned_addr
        if not c.get("original_address"):
            upd["original_address"] = orig_addr

        if upd:
            ncustomers.update_one({"_id": c["_id"]}, {"$set": upd})
            n_updated += 1

print(f"SUCCESS: Auto-migrated {f_updated} Fancy Customer records!")
print(f"SUCCESS: Auto-migrated {n_updated} Navaratri Customer records!")
