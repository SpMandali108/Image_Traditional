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