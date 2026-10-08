import os
import sys
import json
import random
import string
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv

# Set working directory
sys.path.insert(0, os.path.abspath("."))

load_dotenv()
mongo_url = os.environ.get("client") or os.environ.get("MONGO_URI")
client = MongoClient(mongo_url, tls=True, tlsAllowInvalidCertificates=True)
prod_db = client["Image_Traditional"]
test_db = client["Image_Traditional_Test"]

from website import create_app
from website.general.data_review import scan_suspicious_entities, safe_delete_candidate_entity, mark_entity_retained, BACKUP_DIR

def run_tests():
    print("=" * 75)
    print("RUNNING COMPREHENSIVE DATA REVIEW, CLEANUP & ISOLATION VERIFICATION")
    print("=" * 75)

    # =========================================================================
    # PART 1: TEST ADMIN DATA REVIEW & SAFE BACKUP / DELETION MECHANISM
    # =========================================================================
    print("\n--- PART 1: Testing Safe Admin Review, Backups & Retention ---")
    app = create_app()

    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess['logged_in'] = True

        # 1. Test GET /admin/data-review
        r_page = c.get('/admin/data-review')
        assert r_page.status_code == 200, f"Data review page failed with {r_page.status_code}"
        print("  [PASSED] GET /admin/data-review loaded successfully (HTTP 200).")

        # 2. Test Backup Export endpoint
        r_export = c.get('/admin/data-review/export?format=json', headers={'Accept': 'application/json'})
        assert r_export.status_code == 200, f"Export failed with {r_export.status_code}"
        export_data = r_export.get_json()
        assert export_data.get('success') is True, "Export response indicated failure"
        backup_file = export_data.get('backup_file')
        assert os.path.exists(backup_file), f"Backup file {backup_file} was not written to disk"
        print(f"  [PASSED] Full pre-cleanup backup successfully created at: {backup_file}")

        # 3. Test Retaining genuine / uncertain developer records
        retain_mobile = "9876543210" # Shashwat Mandali
        r_retain = c.post('/admin/data-review/retain', json={"mobile": retain_mobile, "notes": "Developer Genuine Account"})
        assert r_retain.status_code == 200
        retained_doc = prod_db["Audit_Retained_Records"].find_one({"mobile": retain_mobile})
        assert retained_doc is not None, "Record was not saved in Audit_Retained_Records"
        print(f"  [PASSED] Mobile {retain_mobile} safely marked as RETAINED / GENUINE.")

        # 4. Test protection: attempting to delete retained record should be BLOCKED
        blocked_delete = safe_delete_candidate_entity(retain_mobile, "212010", target_db=prod_db)
        assert blocked_delete["success"] is False, "Deletion of retained record should have failed"
        assert "marked as RETAINED" in blocked_delete["error"]
        print(f"  [PASSED] Safety guard active: deletion of retained record {retain_mobile} was properly blocked.")

        # 5. Test deletion with wrong password -> should be BLOCKED
        test_delete_mobile = "9799988889" # Repro Test Customer Edited
        wrong_pass_res = safe_delete_candidate_entity(test_delete_mobile, "wrong_password_999", target_db=prod_db)
        assert wrong_pass_res["success"] is False
        assert "Invalid administrator password" in wrong_pass_res["error"]
        print(f"  [PASSED] Security guard active: deletion with invalid password was properly blocked.")

        # 6. Test authorized deletion of verified fake test record
        pre_cust = prod_db["Navaratri_Customers"].find_one({"mobile": test_delete_mobile})
        pre_booking = prod_db["Navaratri_2026"].find_one({"mobile": test_delete_mobile})
        pre_logs_count = prod_db["Navaratri_2026_logs"].count_documents({"mobile": test_delete_mobile})
        print(f"  Target verified test entity {test_delete_mobile}: Customer={bool(pre_cust)}, Booking={bool(pre_booking)}, Logs={pre_logs_count}")

        if pre_cust or pre_booking or pre_logs_count > 0:
            del_result = safe_delete_candidate_entity(test_delete_mobile, "212010", target_db=prod_db)
            assert del_result["success"] is True, f"Authorized deletion failed: {del_result}"
            pre_del_backup = del_result["backup_file"]
            assert os.path.exists(pre_del_backup), "Pre-deletion backup was not created"
            print(f"  [PASSED] Pre-deletion backup created before deleting: {del_result['backup_filename']}")
            print(f"  [PASSED] Safely removed {del_result['total_deleted']} documents: {del_result['deleted_details']}")

            # Verify documents are gone from production
            post_cust = prod_db["Navaratri_Customers"].find_one({"mobile": test_delete_mobile})
            post_booking = prod_db["Navaratri_2026"].find_one({"mobile": test_delete_mobile})
            post_logs_count = prod_db["Navaratri_2026_logs"].count_documents({"mobile": test_delete_mobile})
            assert post_cust is None, "Customer should be deleted from production"
            assert post_booking is None, "Booking should be deleted from production"
            assert post_logs_count == 0, "Logs should be deleted from production"
            print(f"  [PASSED] Verified target test records completely removed from production.")

    # =========================================================================
    # PART 2: RIGOROUS AGY RANDOM TESTING SIMULATION (ISOLATION UNDER PRESSURE)
    # =========================================================================
    print("\n--- PART 2: AGY Random Automated Testing Traffic Simulation ---")
    
    # Record production baseline
    prod_baseline_cust = prod_db["Navaratri_Customers"].count_documents({})
    prod_baseline_bookings = prod_db["Navaratri_2026"].count_documents({})
    prod_baseline_logs = prod_db["Navaratri_2026_logs"].count_documents({})
    print(f"Production Baseline before AGY simulation:")
    print(f"  Navaratri_Customers: {prod_baseline_cust}")
    print(f"  Navaratri_2026 bookings: {prod_baseline_bookings}")
    print(f"  Navaratri_2026_logs: {prod_baseline_logs}")

    # Execute random AGY simulation in a dedicated subprocess with APP_ENV=testing
    import subprocess
    
    sim_script = """
import os
import sys
import json
import random
import string
from datetime import datetime

os.environ['APP_ENV'] = 'testing'
from website import create_app
from website.general.db import db, SELECTED_DB_NAME, APP_ENV

assert SELECTED_DB_NAME == 'Image_Traditional_Test', 'Must use test DB'
assert APP_ENV == 'testing', 'Must be testing environment'

app = create_app()
random_test_mobiles = []

with app.test_client() as test_client:
    with test_client.session_transaction() as sess:
        sess['logged_in'] = True

    for i in range(5):
        rand_digits = "".join(random.choices(string.digits, k=8))
        rand_mobile = f"91{rand_digits}"
        random_test_mobiles.append(rand_mobile)
        rand_name = f"AGY_Random_User_{''.join(random.choices(string.ascii_uppercase, k=6))}"
        rand_addr = f"Random Street {random.randint(100, 999)}, AGY Zone"
        rand_price = str(random.randint(1000, 5000))
        rand_given = str(random.randint(500, int(rand_price)))
        rand_prod = f"T{random.randint(10000, 99999)}"
        rand_date = f"1{i+1}-10-26"

        print(f"  -> AGY Submitting POST /book: {rand_name} ({rand_mobile}), Product: {rand_prod}, Date: {rand_date}, Total: {rand_price}")
        resp = test_client.post('/book', data={
            'name': rand_name,
            'mobile': rand_mobile,
            'address': rand_addr,
            'price': rand_price,
            'given_price': rand_given,
            'deposit': '500',
            'date': rand_date,
            'product': rand_prod
        }, follow_redirects=True)
        assert resp.status_code == 200, f"Booking {i} failed"

    # Also test AGY fetching logs
    r_logs = test_client.get('/navaratri_logs/api')
    assert r_logs.status_code == 200
    logs_payload = r_logs.get_json()
    assert logs_payload.get('success') is True
    print(f"  -> AGY successfully fetched {len(logs_payload.get('logs', []))} testing logs from isolated DB.")

with open('scratch/agy_sim_mobiles.json', 'w') as f:
    json.dump(random_test_mobiles, f)
"""
    env = os.environ.copy()
    env["APP_ENV"] = "testing"
    sim_proc = subprocess.run([sys.executable, "-c", sim_script], env=env, capture_output=True, text=True, cwd=os.path.abspath("."))
    print("SIM STDOUT:\n", sim_proc.stdout)
    if sim_proc.stderr:
        print("SIM STDERR:\n", sim_proc.stderr)
    assert sim_proc.returncode == 0, f"AGY simulation failed with exit code {sim_proc.returncode}"

    with open('scratch/agy_sim_mobiles.json', 'r') as f:
        random_test_mobiles = json.load(f)

    # =========================================================================
    # PART 3: PROVE ZERO POLLUTION IN PRODUCTION
    # =========================================================================
    print("\n--- PART 3: Verifying Production Remained 100% Untouched ---")
    prod_post_cust = prod_db["Navaratri_Customers"].count_documents({})
    prod_post_bookings = prod_db["Navaratri_2026"].count_documents({})
    prod_post_logs = prod_db["Navaratri_2026_logs"].count_documents({})

    print(f"Production State after 5 random AGY submissions:")
    print(f"  Navaratri_Customers: {prod_post_cust} (expected {prod_baseline_cust})")
    print(f"  Navaratri_2026 bookings: {prod_post_bookings} (expected {prod_baseline_bookings})")
    print(f"  Navaratri_2026_logs: {prod_post_logs} (expected {prod_baseline_logs})")

    assert prod_post_cust == prod_baseline_cust, "FATAL: Production customers changed!"
    assert prod_post_bookings == prod_baseline_bookings, "FATAL: Production bookings changed!"
    assert prod_post_logs == prod_baseline_logs, "FATAL: Production logs changed!"

    # Verify none of the 5 random test mobiles exist anywhere in production
    for mob in random_test_mobiles:
        found_in_prod_cust = prod_db["Navaratri_Customers"].find_one({"mobile": mob})
        found_in_prod_booking = prod_db["Navaratri_2026"].find_one({"mobile": mob})
        found_in_prod_log = prod_db["Navaratri_2026_logs"].find_one({"mobile": mob})
        assert found_in_prod_cust is None, f"FATAL: Random mobile {mob} leaked to production customer DB!"
        assert found_in_prod_booking is None, f"FATAL: Random mobile {mob} leaked to production booking DB!"
        assert found_in_prod_log is None, f"FATAL: Random mobile {mob} leaked to production logs DB!"

        # Verify they DO exist in test_db
        found_in_test_cust = test_db["Navaratri_Customers"].find_one({"mobile": mob})
        found_in_test_booking = test_db["Navaratri_2026"].find_one({"mobile": mob})
        assert found_in_test_cust is not None, f"Expected random mobile {mob} in test_db customers"
        assert found_in_test_booking is not None, f"Expected random mobile {mob} in test_db bookings"

    print("  [PASSED] All 5 random AGY submissions exist strictly in Image_Traditional_Test.")
    print("  [PASSED] Exactly ZERO random AGY submissions reached Image_Traditional.")

    # Reset environment back to production
    os.environ["APP_ENV"] = "production"

    print("\n" + "=" * 75)
    print("ALL VERIFICATIONS COMPLETED SUCCESSFULLY WITH 100% DATA INTEGRITY!")
    print("=" * 75)

if __name__ == "__main__":
    run_tests()
