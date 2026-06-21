import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from website.general.db import db

ncustomers = db.Navaratri_Customers
collection = db.Navaratri_2026

print("Starting inline migration...")
for b in collection.find():
    m = b.get("mobile")
    if m:
        res = ncustomers.update_one(
            {"mobile": m},
            {
                "$set": {
                    "group": b.get("group", ""),
                    "reference": b.get("reference", "")
                }
            }
        )
        print(f"Updated {m}: matched={res.matched_count}, modified={res.modified_count}")

print("Checking updated documents:")
cust = ncustomers.find_one({"mobile": "9327836080"})
print("Customer 1:", cust)
cust2 = ncustomers.find_one({"mobile": "9428610384"})
print("Customer 2:", cust2)
