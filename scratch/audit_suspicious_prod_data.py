import os
import re
import json
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
mongo_url = os.environ.get("client") or os.environ.get("MONGO_URI")
client = MongoClient(mongo_url, tls=True, tlsAllowInvalidCertificates=True)
prod_db = client["Image_Traditional"]

regex = re.compile(r"test|dummy|fake|sample|flow|repro|temp", re.I)
phone_regex = re.compile(r"^99999|^123456|^00000|^88888")

collections_to_check = [
    "Navaratri_Customers",
    "Navaratri_2026",
    "Navaratri_2026_logs",
    "Form",
    "Form_logs",
    "Fancy_Customers",
    "Fancy_2026_2026",
    "Fancy_2025_2026",
    "Fancy"
]

report = {}
total_found = 0

for col_name in collections_to_check:
    col = prod_db[col_name]
    query = {
        "$or": [
            {"name": regex},
            {"Name": regex},
            {"mobile": phone_regex}
        ]
    }
    docs = list(col.find(query))
    if docs:
        col_list = []
        for d in docs:
            total_found += 1
            col_list.append({
                "_id": str(d.get("_id")),
                "name": str(d.get("name") or d.get("Name") or ""),
                "mobile": str(d.get("mobile") or ""),
                "action": str(d.get("action") or ""),
                "date_stamp": str(d.get("date_stamp") or ""),
                "time_stamp": str(d.get("time_stamp") or ""),
                "details": str(d.get("details") or "").replace("\u20b9", "Rs. ")
            })
        report[col_name] = col_list

with open("scratch/suspicious_production_records.json", "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

print(f"Audit completed successfully. Total records found: {total_found}")
for col, items in report.items():
    print(f"  Collection '{col}': {len(items)} records")
