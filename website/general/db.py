import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

mongo_url = os.environ.get("client")

client = MongoClient(mongo_url, tls=True, tlsAllowInvalidCertificates=True)

db = client["Image_Traditional"]

collection = db["Form"]
fancy_2024_2025 = db["Fancy"]
fancy_collection = db["Fancy_2025_2026"]
products_collection = db["products"]
bags = db["bags"]
products = db["Storage"]
fcustomers = db["Fancy_Customers"]
finventory = db["Fancy_Inventory"]
ncustomers = db["Navaratri_Customers"]
custom_localities = db["Custom_Localities"]

raw_id = os.environ.get("ADMIN_ID")
raw_pass = os.environ.get("ADMIN_PASS")

ADMIN_ID = (raw_id if raw_id else "IMGTRADE1008").strip().strip('"\'')
ADMIN_PASS = (raw_pass if raw_pass else "212010").strip().strip('"\'')