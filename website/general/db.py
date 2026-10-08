import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# ==============================================================================
# 🛡️ ENVIRONMENT-BASED DATABASE ISOLATION SYSTEM
# ==============================================================================
# The server environment MUST be determined strictly from server-side environment
# variables. Never trust client requests, parameters, headers, or cookies.

raw_app_env = os.environ.get("APP_ENV")
if not raw_app_env or not raw_app_env.strip():
    raise RuntimeError(
        "CRITICAL SERVER CONFIGURATION ERROR: 'APP_ENV' environment variable is missing or empty. "
        "It must be explicitly set to 'production' or 'testing'. "
        "Silent fallback to production is strictly forbidden to prevent test data pollution."
    )

APP_ENV = raw_app_env.strip().lower()
if APP_ENV not in ("production", "testing"):
    raise RuntimeError(
        f"CRITICAL SERVER CONFIGURATION ERROR: Unsupported APP_ENV='{raw_app_env}'. "
        "Allowed values are strictly 'production' or 'testing'. "
        "Silent fallback to production is strictly forbidden."
    )

MONGO_DB_PRODUCTION = (os.environ.get("MONGO_DB_PRODUCTION") or "Image_Traditional").strip()
MONGO_DB_TESTING = (os.environ.get("MONGO_DB_TESTING") or "Image_Traditional_Test").strip()

if APP_ENV == "production":
    SELECTED_DB_NAME = MONGO_DB_PRODUCTION
elif APP_ENV == "testing":
    SELECTED_DB_NAME = MONGO_DB_TESTING
else:
    raise RuntimeError(f"CRITICAL SERVER CONFIGURATION ERROR: Unknown APP_ENV='{APP_ENV}'")

# Centralized MongoDB connection
mongo_url = os.environ.get("MONGO_URI") or os.environ.get("client")
if not mongo_url:
    raise RuntimeError(
        "CRITICAL SERVER CONFIGURATION ERROR: Neither 'MONGO_URI' nor 'client' MongoDB connection string is set."
    )

try:
    import certifi
    client = MongoClient(mongo_url, tls=True, tlsCAFile=certifi.where())
except Exception:
    client = MongoClient(mongo_url, tls=True, tlsAllowInvalidCertificates=True)

db = client[SELECTED_DB_NAME]

# Server-side startup/configuration check logging
print(f"[APP ENV] {APP_ENV}", flush=True)
print(f"[DB] {SELECTED_DB_NAME}", flush=True)


def ensure_testing_db_ready(database):
    """
    Ensures that the isolated testing database has the required baseline configuration
    (e.g., active Navaratri cycle and Fancy cycle, seeded categories) so that automated
    testing flows (creating bookings, selling, editing, payment tests) can function seamlessly
    without needing manual administrative cycle creation.
    GUARANTEE: Only invoked when APP_ENV == 'testing'. Never touches production.
    """
    from datetime import datetime

    # 1. Ensure Navaratri cycle exists and is active
    try:
        n_cycles = database["navaratri_cycles"]
        if n_cycles.count_documents({"status": "active"}) == 0:
            n_cycles.insert_one({
                "name": "Navaratri 2026 Test",
                "collection_name": "Navaratri_2026",
                "start_date": datetime.now().strftime("%d-%m-%y"),
                "end_date": None,
                "status": "active",
                "created_at": datetime.utcnow(),
                "edit_override": True
            })
    except Exception as e:
        print(f"[TEST DB INIT NOTICE] navaratri_cycles: {e}", flush=True)

    # 2. Ensure Fancy cycle exists and is active
    try:
        f_cycles = database["fancy_cycles"]
        if f_cycles.count_documents({"status": "active"}) == 0:
            f_cycles.insert_one({
                "name": "Summer 2026 to Diwali 2026 Test",
                "collection_name": "Fancy_2026_2026",
                "start_date": datetime.now().strftime("%d-%m-%y"),
                "end_date": None,
                "status": "active",
                "created_at": datetime.utcnow()
            })
    except Exception as e:
        print(f"[TEST DB INIT NOTICE] fancy_cycles: {e}", flush=True)

    # 3. Ensure test custom localities
    try:
        locs = database["Custom_Localities"]
        if locs.count_documents({}) == 0:
            locs.insert_many([
                {"name": "Ahmedabad", "city": "Ahmedabad"},
                {"name": "Vadodara", "city": "Vadodara"},
                {"name": "Surat", "city": "Surat"}
            ])
    except Exception as e:
        pass


if APP_ENV == "testing":
    ensure_testing_db_ready(db)


# ==============================================================================
# CENTRALIZED COLLECTION EXPORTS (All routes and services bind to these)
# ==============================================================================
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
navaratri_products = db["navaratri_products"]
costume_groups = db["costume_groups"]
costumes = db["navaratri_products"]
navaratri_cycles = db["navaratri_cycles"]
fancy_cycles = db["fancy_cycles"]


raw_id = os.environ.get("ADMIN_ID")
raw_pass = os.environ.get("ADMIN_PASS")

ADMIN_ID = (raw_id if raw_id else "IMGTRADE1008").strip().strip('"\'')
ADMIN_PASS = (raw_pass if raw_pass else "212010").strip().strip('"\'')