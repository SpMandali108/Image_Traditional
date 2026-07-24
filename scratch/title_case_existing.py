import sys
import os

sys.path.insert(0, os.getcwd())

from website.general.db import fcustomers, ncustomers, custom_localities

def to_title_case(text):
    if not text:
        return ""
    words = str(text).split()
    title_words = []
    for w in words:
        if w.upper() in ("CTM", "SG", "S.G.", "C.G.", "C.G", "S.G"):
            title_words.append(w.upper())
        else:
            title_words.append(w.capitalize())
    return " ".join(title_words)

print("Title-casing all existing locality and address fields in MongoDB...")

f_count = 0
for c in fcustomers.find():
    loc = c.get("locality")
    addr = c.get("address")
    upd = {}
    if loc and loc != to_title_case(loc):
        upd["locality"] = to_title_case(loc)
    if addr and addr != to_title_case(addr):
        upd["address"] = to_title_case(addr)
    if upd:
        fcustomers.update_one({"_id": c["_id"]}, {"$set": upd})
        f_count += 1

n_count = 0
for c in ncustomers.find():
    loc = c.get("locality")
    addr = c.get("address")
    upd = {}
    if loc and loc != to_title_case(loc):
        upd["locality"] = to_title_case(loc)
    if addr and addr != to_title_case(addr):
        upd["address"] = to_title_case(addr)
    if upd:
        ncustomers.update_one({"_id": c["_id"]}, {"$set": upd})
        n_count += 1

cloc_count = 0
for cl in custom_localities.find():
    name = cl.get("name")
    if name and name != to_title_case(name):
        custom_localities.update_one({"_id": cl["_id"]}, {"$set": {"name": to_title_case(name)}})
        cloc_count += 1

print(f"Fancy Customers title-cased: {f_count}")
print(f"Navaratri Customers title-cased: {n_count}")
print(f"Custom Localities title-cased: {cloc_count}")
print("Done!")
