import sys
sys.path.insert(0, '.')
from website.general.db import ncustomers

for c in ncustomers.find({"name": {"$regex": "brijesh", "$options": "i"}}):
    print("Name:", repr(c.get("name")), "| Locality:", repr(c.get("locality")), "| Address:", repr(c.get("address")))
