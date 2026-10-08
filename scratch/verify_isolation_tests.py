import os
import sys
import subprocess
import json
from datetime import datetime

# Set working directory to workspace
sys.path.insert(0, os.path.abspath("."))

def run_cmd(cmd_list, env_override=None):
    env = os.environ.copy()
    if env_override:
        env.update(env_override)
    result = subprocess.run(
        cmd_list,
        capture_output=True,
        text=True,
        env=env,
        cwd=os.path.abspath(".")
    )
    return result

def main():
    print("=" * 70)
    print("STARTING DATA ISOLATION VERIFICATION TEST SUITE")
    print("=" * 70)

    # -------------------------------------------------------------
    # TEST 5: Fail-safe verification for invalid/missing APP_ENV
    # -------------------------------------------------------------
    print("\n[TEST 5] Testing fail-safe behavior with invalid and missing APP_ENV...")

    # Case A: Invalid APP_ENV
    res_invalid = run_cmd(
        [sys.executable, "-c", "import os; from website.general.db import db"],
        env_override={"APP_ENV": "invalid_mode_xyz"}
    )
    print(f"Case A: APP_ENV='invalid_mode_xyz' -> Return code: {res_invalid.returncode}")
    assert res_invalid.returncode != 0, "Application must fail on invalid APP_ENV"
    assert "CRITICAL SERVER CONFIGURATION ERROR: Unsupported APP_ENV" in res_invalid.stderr, "Error message must be clear"
    print("  --> PASSED: Application rejected invalid APP_ENV safely with clear error.")

    # Case B: Missing/Empty APP_ENV
    res_empty = run_cmd(
        [sys.executable, "-c", "import os; from website.general.db import db"],
        env_override={"APP_ENV": ""}
    )
    print(f"Case B: APP_ENV='' -> Return code: {res_empty.returncode}")
    assert res_empty.returncode != 0, "Application must fail on missing/empty APP_ENV"
    assert "CRITICAL SERVER CONFIGURATION ERROR: 'APP_ENV' environment variable is missing" in res_empty.stderr, "Error message must be clear"
    print("  --> PASSED: Application rejected empty APP_ENV safely with clear error.")
    print("TEST 5 PASSED!\n")

    # -------------------------------------------------------------
    # Connect directly to MongoDB cluster to verify both DBs independently
    # -------------------------------------------------------------
    from pymongo import MongoClient
    from dotenv import load_dotenv
    load_dotenv()
    mongo_url = os.environ.get("client") or os.environ.get("MONGO_URI")
    client = MongoClient(mongo_url, tls=True, tlsAllowInvalidCertificates=True)
    prod_db = client["Image_Traditional"]
    test_db = client["Image_Traditional_Test"]

    initial_prod_cust_count = prod_db["Navaratri_Customers"].count_documents({})
    initial_prod_booking_count = prod_db["Navaratri_2026"].count_documents({})
    initial_prod_logs_count = prod_db["Navaratri_2026_logs"].count_documents({})

    print(f"Baseline Production Data State:")
    print(f"  - Navaratri_Customers: {initial_prod_cust_count}")
    print(f"  - Navaratri_2026 bookings: {initial_prod_booking_count}")
    print(f"  - Navaratri_2026_logs: {initial_prod_logs_count}")

    # -------------------------------------------------------------
    # TEST 1 & 2 & 3: Run under APP_ENV=testing
    # -------------------------------------------------------------
    test_mobile = "9888800099"
    test_name = "AGY Automated Test Customer"
    test_product = "C1"
    test_date = datetime.now().strftime("%d-%m-%y")

    # Clean up previous test artifact if any in test_db only
    test_db["Navaratri_Customers"].delete_many({"mobile": test_mobile})
    test_db["Navaratri_2026"].delete_many({"mobile": test_mobile})
    test_db["Navaratri_2026_logs"].delete_many({"mobile": test_mobile})

    # Execute test script under APP_ENV=testing
    test_script_code = f"""
import os
import sys
os.environ['APP_ENV'] = 'testing'
from website import create_app
from website.general.db import db, SELECTED_DB_NAME, APP_ENV

print(f'Runtime DB: {{SELECTED_DB_NAME}}, APP_ENV: {{APP_ENV}}')
assert SELECTED_DB_NAME == 'Image_Traditional_Test', 'Must use Image_Traditional_Test'
assert APP_ENV == 'testing', 'Must be testing environment'

app = create_app()
with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['logged_in'] = True
    
    # 1. Create booking via POST /book
    form_data = {{
        'name': '{test_name}',
        'mobile': '{test_mobile}',
        'address': 'Test Isolation Address, Testing City',
        'price': '1500',
        'given_price': '1000',
        'deposit': '500',
        'date': '{test_date}',
        'product': '{test_product}'
    }}
    res = client.post('/book', data=form_data, follow_redirects=True)
    assert res.status_code == 200, f'Booking failed with status {{res.status_code}}'
    print('Booking HTTP POST completed successfully.')

    # 2. Access logs API
    logs_res = client.get('/navaratri_logs/api')
    assert logs_res.status_code == 200, 'Navaratri logs API failed'
    data = logs_res.get_json()
    assert data.get('success') is True
    log_names = [l.get('name') for l in data.get('logs', [])]
    assert '{test_name}' in log_names, f'Test customer not found in logs: {{log_names}}'
    print('Testing logs verified on test Admin Logs API endpoint.')
"""
    print("\n[TEST 1, 2, 3] Running test client with APP_ENV=testing...")
    test_run = run_cmd([sys.executable, "-c", test_script_code], env_override={"APP_ENV": "testing"})
    print("STDOUT:", test_run.stdout)
    if test_run.stderr:
        print("STDERR:", test_run.stderr)
    assert test_run.returncode == 0, f"Testing process failed with return code {test_run.returncode}"

    # VERIFY TEST 1: Customer isolation
    print("\n[VERIFY TEST 1] Checking customer isolation...")
    in_test_cust = test_db["Navaratri_Customers"].find_one({"mobile": test_mobile})
    in_prod_cust = prod_db["Navaratri_Customers"].find_one({"mobile": test_mobile})
    print(f"  - Exists in Image_Traditional_Test: {in_test_cust is not None} ({in_test_cust.get('name') if in_test_cust else 'None'})")
    print(f"  - Exists in Image_Traditional (prod): {in_prod_cust is not None}")
    assert in_test_cust is not None, "Customer MUST exist in Image_Traditional_Test"
    assert in_prod_cust is None, "Customer MUST NOT exist in Image_Traditional production DB"
    print("  --> PASSED: Customer exists ONLY in Image_Traditional_Test!")

    # VERIFY TEST 2: Booking isolation
    print("\n[VERIFY TEST 2] Checking booking isolation...")
    in_test_booking = test_db["Navaratri_2026"].find_one({"mobile": test_mobile})
    in_prod_booking = prod_db["Navaratri_2026"].find_one({"mobile": test_mobile})
    current_prod_booking_count = prod_db["Navaratri_2026"].count_documents({})
    print(f"  - Booking in Image_Traditional_Test: {in_test_booking is not None} (Products: {in_test_booking.get('bookings') if in_test_booking else 'None'})")
    print(f"  - Booking in Image_Traditional (prod): {in_prod_booking is not None}")
    print(f"  - Prod bookings count before: {initial_prod_booking_count}, after: {current_prod_booking_count}")
    assert in_test_booking is not None, "Booking MUST exist in Image_Traditional_Test"
    assert in_prod_booking is None, "Booking MUST NOT exist in Image_Traditional production DB"
    assert current_prod_booking_count == initial_prod_booking_count, "Production booking count MUST remain completely unchanged"
    print("  --> PASSED: Booking exists ONLY in Image_Traditional_Test, Production is completely untouched!")

    # VERIFY TEST 3: Log isolation
    print("\n[VERIFY TEST 3] Checking log isolation...")
    test_logs = list(test_db["Navaratri_2026_logs"].find({"mobile": test_mobile}))
    prod_logs = list(prod_db["Navaratri_2026_logs"].find({"mobile": test_mobile}))
    current_prod_logs_count = prod_db["Navaratri_2026_logs"].count_documents({})
    print(f"  - Logs count in Image_Traditional_Test: {len(test_logs)}")
    print(f"  - Logs count in Image_Traditional (prod): {len(prod_logs)}")
    print(f"  - Prod logs count before: {initial_prod_logs_count}, after: {current_prod_logs_count}")
    assert len(test_logs) > 0, "Test log MUST exist in Image_Traditional_Test"
    assert len(prod_logs) == 0, "Test log MUST NOT exist in Image_Traditional production DB"
    assert current_prod_logs_count == initial_prod_logs_count, "Production logs count MUST remain completely unchanged"
    print("  --> PASSED: Test logs exist ONLY in Image_Traditional_Test!")

    # -------------------------------------------------------------
    # TEST 4: Run application under APP_ENV=production
    # -------------------------------------------------------------
    print("\n[TEST 4] Verifying application under APP_ENV=production...")
    prod_script_code = """
import os
import sys
os.environ['APP_ENV'] = 'production'
from website import create_app
from website.general.db import db, SELECTED_DB_NAME, APP_ENV

print(f'Runtime DB: {SELECTED_DB_NAME}, APP_ENV: {APP_ENV}')
assert SELECTED_DB_NAME == 'Image_Traditional', 'Must use Image_Traditional'
assert APP_ENV == 'production', 'Must be production environment'

app = create_app()
with app.test_client() as client:
    res = client.get('/')
    assert res.status_code == 200, 'Home page failed'
    with client.session_transaction() as sess:
        sess['logged_in'] = True
    admin_res = client.get('/admin')
    assert admin_res.status_code == 200, 'Admin page failed'
    html = admin_res.get_data(as_text=True)
    assert 'PRODUCTION ENVIRONMENT' in html, 'Production banner missing on admin page'
    assert 'PRODUCTION' in html, 'Production badge missing in header'
    print('Production admin UI successfully loaded with PRODUCTION badges.')

    logs_res = client.get('/navaratri_logs/api')
    assert logs_res.status_code == 200, 'Production logs API failed'
    prod_data = logs_res.get_json()
    assert prod_data.get('success') is True
    prod_log_names = [l.get('name') for l in prod_data.get('logs', [])]
    assert 'AGY Automated Test Customer' not in prod_log_names, 'Test customer found in production logs API!'
    print('Verified production logs endpoint contains ZERO test entries.')
"""
    prod_run = run_cmd([sys.executable, "-c", prod_script_code], env_override={"APP_ENV": "production"})
    print("STDOUT:", prod_run.stdout)
    if prod_run.stderr:
        print("STDERR:", prod_run.stderr)
    assert prod_run.returncode == 0, f"Production check failed with return code {prod_run.returncode}"
    print("  --> PASSED: Production environment functions identically and loads Image_Traditional with proper UI badges!")

    print("\n" + "=" * 70)
    print("ALL 5 DATA ISOLATION TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 70)

if __name__ == "__main__":
    main()
