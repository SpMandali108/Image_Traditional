import os
from pymongo import MongoClient
from dotenv import load_dotenv
from pprint import pprint

load_dotenv()
mongo_url = os.environ.get("client")
client = MongoClient(mongo_url, tls=True, tlsAllowInvalidCertificates=True)
db = client["Image_Traditional"]

print("Collections in database:")
print(db.list_collection_names())

# Check cycles
print("\nFancy cycles:")
if "fancy_cycles" in db.list_collection_names():
    cycles = list(db["fancy_cycles"].find())
    pprint(cycles)
else:
    print("No fancy_cycles collection found!")

# Let's inspect some booking documents in the active collections
print("\nActive collections inspection:")
for col_name in db.list_collection_names():
    if "fancy" in col_name.lower() or col_name == "Form":
        col = db[col_name]
        doc = col.find_one()
        if doc:
            print(f"\nSample document in collection '{col_name}':")
            pprint(doc)
            print("Fields and types:")
            for k, v in doc.items():
                print(f"  {k}: {type(v)} = {v}")
