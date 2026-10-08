import os
import sys
import json
from datetime import datetime
from bson import ObjectId

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ["APP_ENV"] = "production"

from website.general.db import client, MONGO_DB_PRODUCTION

prod_db = client[MONGO_DB_PRODUCTION]
nav_2026 = prod_db["Navaratri_2026"]
nav_cust = prod_db["Navaratri_Customers"]
nav_logs = prod_db["Navaratri_2026_logs"]
form_col = prod_db["Form"]
form_logs = prod_db["Form_logs"]

BACKUP_DIR = os.path.join(os.getcwd(), "data", "backups")
os.makedirs(BACKUP_DIR, exist_ok=True)

print("======================================================================")
print("PRODUCTION CLEANUP: PRESERVE ONLY OFFICIALLY REGISTERED CURRENT CYCLE")
print("======================================================================")

# 1. BASELINE COUNTS BEFORE CLEANUP
count_nav_cust_before = nav_cust.count_documents({})
count_nav_2026_before = nav_2026.count_documents({})
count_nav_logs_before = nav_logs.count_documents({})
count_form_before = form_col.count_documents({})

print(f"BASELINE PRODUCTION STATE BEFORE CLEANUP:")
print(f"  Navaratri_Customers: {count_nav_cust_before}")
print(f"  Navaratri_2026 Bookings: {count_nav_2026_before}")
print(f"  Navaratri_2026 Logs: {count_nav_logs_before}")
print(f"  Form Bookings: {count_form_before}")

# 2. IDENTIFY OFFICIALLY REGISTERED CURRENT-CYCLE CUSTOMERS
cc_bookings = list(nav_2026.find())
cc_mobiles = set(str(b.get("mobile") or "").strip() for b in cc_bookings if b.get("mobile"))
print(f"\nOfficially registered bookings in current cycle (Navaratri 2026): {len(cc_bookings)}")
print(f"Unique customer mobiles in current cycle: {len(cc_mobiles)}")

# Confirm these 57 exist in Navaratri_Customers
cc_cust_preserved = list(nav_cust.find({"mobile": {"$in": list(cc_mobiles)}}))
print(f"Officially registered current-cycle customers to preserve: {len(cc_cust_preserved)}")
assert len(cc_cust_preserved) == len(cc_mobiles), "Mismatch between bookings and customer records!"

# 3. IDENTIFY RECORDS SCHEDULED FOR DELETION
# A. Customers outside the current active cycle
customers_to_delete = list(nav_cust.find({"mobile": {"$nin": list(cc_mobiles)}}))
print(f"\nOld/test customers scheduled for deletion: {len(customers_to_delete)}")

# Double-check preservation: none of the preserved customers must be in customers_to_delete
delete_mobiles = set(str(c.get("mobile") or "").strip() for c in customers_to_delete)
overlap = delete_mobiles.intersection(cc_mobiles)
assert len(overlap) == 0, f"SAFETY VIOLATION: Current cycle customer found in deletion set: {overlap}"

# B. Fake bookings in Form (2 confirmed test bookings)
fake_booking_mobiles = ["9999988888", "9999988887"]
fake_bookings_to_delete = list(form_col.find({"mobile": {"$in": fake_booking_mobiles}}))
print(f"Fake bookings scheduled for deletion in Form: {len(fake_bookings_to_delete)}")
assert len(fake_bookings_to_delete) == 2, f"Expected 2 fake bookings in Form, found {len(fake_bookings_to_delete)}"

# C. Fake/test logs in Navaratri_2026_logs
test_log_mobiles = [
    "9999900001", "9888800001", "9888800004", "9888800002",
    "9999900002", "9988776655", "9876543210", "9428610384",
    "9601500802", "9998781371"
]
fake_logs_to_delete = list(nav_logs.find({"mobile": {"$in": test_log_mobiles}}))
print(f"Fake/test logs scheduled for deletion in Navaratri_2026_logs: {len(fake_logs_to_delete)}")
assert len(fake_logs_to_delete) == 60, f"Expected 60 fake logs in Navaratri_2026_logs, found {len(fake_logs_to_delete)}"

# Verify that none of the fake logs belong to officially registered customers
log_delete_mobiles = set(str(l.get("mobile") or "").strip() for l in fake_logs_to_delete)
log_overlap = log_delete_mobiles.intersection(cc_mobiles)
assert len(log_overlap) == 0, f"SAFETY VIOLATION: Current cycle customer found in log deletion set: {log_overlap}"

# 4. BACKUP REQUIREMENT: CREATE AND VERIFY COMPLETE PRE-DELETION BACKUP
timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_filename = f"production_cleanup_backup_{timestamp_str}.json"
backup_filepath = os.path.join(BACKUP_DIR, backup_filename)

backup_payload = {
    "timestamp": datetime.now().isoformat(),
    "database": MONGO_DB_PRODUCTION,
    "reason": "production_cleanup_current_cycle_boundary",
    "summary": {
        "officially_registered_customers_preserved": len(cc_cust_preserved),
        "old_test_customers_to_delete": len(customers_to_delete),
        "fake_bookings_to_delete": len(fake_bookings_to_delete),
        "fake_logs_to_delete": len(fake_logs_to_delete)
    },
    "preserved_customer_mobiles": sorted(list(cc_mobiles)),
    "records_to_delete": {
        "Navaratri_Customers": [
            {k: (str(v) if isinstance(v, ObjectId) else (v.isoformat() if isinstance(v, datetime) else v)) for k, v in doc.items()}
            for doc in customers_to_delete
        ],
        "Form_fake_bookings": [
            {k: (str(v) if isinstance(v, ObjectId) else (v.isoformat() if isinstance(v, datetime) else v)) for k, v in doc.items()}
            for doc in fake_bookings_to_delete
        ],
        "Navaratri_2026_fake_logs": [
            {k: (str(v) if isinstance(v, ObjectId) else (v.isoformat() if isinstance(v, datetime) else v)) for k, v in doc.items()}
            for doc in fake_logs_to_delete
        ]
    }
}

print(f"\nWriting pre-deletion backup to: {backup_filepath}")
with open(backup_filepath, "w", encoding="utf-8") as f:
    json.dump(backup_payload, f, indent=2, default=str)

# Verify backup exists, is non-empty, and readable
if not os.path.exists(backup_filepath):
    raise RuntimeError(f"CRITICAL BACKUP ERROR: Backup file does not exist at {backup_filepath}. Deletion ABORTED.")

backup_size = os.path.getsize(backup_filepath)
if backup_size == 0:
    raise RuntimeError(f"CRITICAL BACKUP ERROR: Backup file is 0 bytes at {backup_filepath}. Deletion ABORTED.")

# Verify contents by reloading
with open(backup_filepath, "r", encoding="utf-8") as f:
    reloaded_backup = json.load(f)
assert reloaded_backup["summary"]["old_test_customers_to_delete"] == len(customers_to_delete)
assert reloaded_backup["summary"]["fake_bookings_to_delete"] == len(fake_bookings_to_delete)
assert reloaded_backup["summary"]["fake_logs_to_delete"] == len(fake_logs_to_delete)
print(f"[OK] Backup verified successfully ({backup_size} bytes). Proceeding with atomic deletions.")

# 5. EXECUTE CONTROLLED CLEANUP
# A. Remove customers outside current active cycle
res_cust = nav_cust.delete_many({"mobile": {"$nin": list(cc_mobiles)}})
print(f"Deleted {res_cust.deleted_count} customer documents from Navaratri_Customers.")

# B. Remove fake bookings from Form
res_book = form_col.delete_many({"mobile": {"$in": fake_booking_mobiles}})
print(f"Deleted {res_book.deleted_count} fake booking documents from Form.")

# C. Remove fake logs from Navaratri_2026_logs
res_logs = nav_logs.delete_many({"mobile": {"$in": test_log_mobiles}})
print(f"Deleted {res_logs.deleted_count} fake log documents from Navaratri_2026_logs.")

# 6. POST-CLEANUP VERIFICATION
count_nav_cust_after = nav_cust.count_documents({})
count_nav_2026_after = nav_2026.count_documents({})
count_nav_logs_after = nav_logs.count_documents({})
count_form_after = form_col.count_documents({})

print("\n======================================================================")
print("POST-CLEANUP AUDIT RESULTS")
print("======================================================================")
print(f"Navaratri_Customers: {count_nav_cust_before} -> {count_nav_cust_after}")
print(f"Navaratri_2026 Bookings: {count_nav_2026_before} -> {count_nav_2026_after}")
print(f"Navaratri_2026 Logs: {count_nav_logs_before} -> {count_nav_logs_after}")
print(f"Form Bookings: {count_form_before} -> {count_form_after}")

# Verify 100% of current cycle customers still exist
remaining_cust_mobiles = set(c.get("mobile") for c in nav_cust.find())
missing_customers = cc_mobiles - remaining_cust_mobiles
assert len(missing_customers) == 0, f"CRITICAL INTEGRITY FAILURE: Missing customers: {missing_customers}"
print(f"\n[PASSED] All {len(cc_mobiles)} officially registered current-cycle customers are 100% PRESERVED!")
print(f"[PASSED] Exactly {res_cust.deleted_count} old/test customers removed.")
print(f"[PASSED] Exactly {res_book.deleted_count} fake bookings removed.")
print(f"[PASSED] Exactly {res_logs.deleted_count} fake logs removed.")
print(f"[PASSED] Exactly {count_nav_logs_after} genuine current-cycle logs preserved.")
print(f"[PASSED] Pre-deletion backup location: {backup_filepath}")
