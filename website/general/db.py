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

import secrets
ADMIN_ID = os.environ.get("ADMIN_ID")
ADMIN_PASS = os.environ.get("ADMIN_PASS")

if not ADMIN_ID or not ADMIN_PASS:
    if not ADMIN_ID:
        ADMIN_ID = secrets.token_urlsafe(16)
        print(f"WARNING: ADMIN_ID not configured! Using random: {ADMIN_ID}")
    if not ADMIN_PASS:
        ADMIN_PASS = secrets.token_urlsafe(16)
        print(f"WARNING: ADMIN_PASS not configured! Using random: {ADMIN_PASS}")