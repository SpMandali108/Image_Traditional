import sys
import os
import re

sys.path.insert(0, os.getcwd())

try:
    from website.general.db import fcustomers, ncustomers, custom_localities
    from website.navaratri.nroutes import KNOWN_LOCALITIES
    from website.fancy.froutes import KNOWN_LOCALITIES_FANCY
    from website.general.utils import resolve_customer_locality

    localities = list(set(KNOWN_LOCALITIES + KNOWN_LOCALITIES_FANCY + [c.get('name') for c in custom_localities.find() if c.get('name')]))

    f_custs = list(fcustomers.find())
    f_updated = 0
    f_samples = []

    for c in f_custs:
        loc = resolve_customer_locality(c, localities)
        if loc:
            raw_addr = (c.get("address") or "").strip()
            orig_addr = c.get("original_address") or raw_addr
            pattern = re.compile(r'[, \t]*\b' + re.escape(loc.strip()) + r'\b\s*$', re.IGNORECASE)
            cleaned_addr = pattern.sub('', raw_addr).strip() or raw_addr
            
            if c.get("locality") != loc or c.get("address") != cleaned_addr:
                f_updated += 1
                if len(f_samples) < 5:
                    f_samples.append({
                        "old_addr": raw_addr,
                        "new_addr": cleaned_addr,
                        "locality": loc,
                        "old_loc": c.get("locality")
                    })

    n_custs = list(ncustomers.find())
    n_updated = 0
    n_samples = []

    for c in n_custs:
        loc = resolve_customer_locality(c, localities)
        if loc:
            raw_addr = (c.get("address") or "").strip()
            orig_addr = c.get("original_address") or raw_addr
            pattern = re.compile(r'[, \t]*\b' + re.escape(loc.strip()) + r'\b\s*$', re.IGNORECASE)
            cleaned_addr = pattern.sub('', raw_addr).strip() or raw_addr
            
            if c.get("locality") != loc or c.get("address") != cleaned_addr:
                n_updated += 1
                if len(n_samples) < 5:
                    n_samples.append({
                        "old_addr": raw_addr,
                        "new_addr": cleaned_addr,
                        "locality": loc,
                        "old_loc": c.get("locality")
                    })

    print(f"Fancy Customers to update: {f_updated} / {len(f_custs)}")
    print("Fancy Samples:")
    for s in f_samples:
        print("  ", s)

    print(f"\nNavaratri Customers to update: {n_updated} / {len(n_custs)}")
    print("Navaratri Samples:")
    for s in n_samples:
        print("  ", s)

except Exception as e:
    import traceback
    traceback.print_exc()
