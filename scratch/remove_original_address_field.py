import sys
import os

sys.path.insert(0, os.getcwd())

from website.general.db import fcustomers, ncustomers

print("Removing 'original_address' field from all customer records in MongoDB...")

f_res = fcustomers.update_many({"original_address": {"$exists": True}}, {"$unset": {"original_address": ""}})
n_res = ncustomers.update_many({"original_address": {"$exists": True}}, {"$unset": {"original_address": ""}})

print(f"Fancy Customers modified: {f_res.modified_count}")
print(f"Navaratri Customers modified: {n_res.modified_count}")
print("Done! 'original_address' field has been completely removed.")
