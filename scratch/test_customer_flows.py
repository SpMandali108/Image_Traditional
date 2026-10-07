import sys
import os
from bson import ObjectId
from datetime import datetime

# Set up environment
sys.path.insert(0, os.path.abspath("."))
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from website import create_app
from website.navaratri.nservices import collection, check_booking_conflict

app = create_app()

def run_tests():
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['logged_in'] = True
        print("=== TEST 1: Check Availability with and without exclude_mobile ===")
        # Look up a real customer in DB who has bookings
        cust = collection.find_one({"bookings": {"$ne": {}}})
        assert cust is not None, "Need at least one customer with bookings for test"
        cust_mobile = cust.get('mobile')
        date_str = list(cust['bookings'].keys())[0]
        prod_code = cust['bookings'][date_str][0]

        print(f"Testing customer: {cust.get('Name')}, mobile={cust_mobile}, date={date_str}, product={prod_code}")

        # Check availability WITHOUT exclude_mobile
        res1 = client.get(f"/api/check-product?product_code={prod_code}&date={date_str}")
        data1 = res1.get_json()
        print(f"Without exclude_mobile: available={data1.get('available')}, reason={data1.get('reason')}")
        assert data1.get('available') is False, "Should be unavailable when not excluding customer mobile"

        # Check availability WITH exclude_mobile
        res2 = client.get(f"/api/check-product?product_code={prod_code}&date={date_str}&exclude_mobile={cust_mobile}")
        data2 = res2.get_json()
        print(f"With exclude_mobile={cust_mobile}: available={data2.get('available')}, reason={data2.get('reason')}")
        print("[PASSED] TEST 1 PASSED!\n")

        print("=== TEST 2: Explicit Profile Edit (Reducing payment / Reducing total) ===")
        # Create a test customer specifically for testing
        test_mobile = "9999900001"
        collection.delete_many({"mobile": test_mobile})
        
        insert_res = collection.insert_one({
            "Name": "Test Customer Flow",
            "mobile": test_mobile,
            "address": "Ahmedabad",
            "deposit": "",
            "group": "",
            "reference": "Test",
            "bookings": {"10-10-26": ["C99999TEST"]},
            "total_price": 2000,
            "given_price": 2000,
            "qr_url": "http://test.com"
        })
        test_id = str(insert_res.inserted_id)

        # 2a. Admin reduces given_price from 2000 to 1000
        res = client.post("/navaratri_booking/update", json={
            "customer_id": test_id,
            "name": "Test Customer Flow",
            "mobile": test_mobile,
            "address": "Ahmedabad",
            "group": "",
            "reference": "Test",
            "deposit": "",
            "total_price": 2000,
            "given_price": 1000,
            "bookings": [{"date": "2026-10-10", "products": ["C99999TEST"]}]
        })
        d = res.get_json()
        print("2a (Reduce payment 2000->1000):", res.status_code, d.get("message"))
        assert res.status_code == 200 and d.get("success") is True, f"Failed: {d}"
        updated_cust = collection.find_one({"_id": ObjectId(test_id)})
        assert updated_cust['given_price'] == 1000, f"Expected 1000, got {updated_cust['given_price']}"
        assert updated_cust['total_price'] == 2000, f"Expected 2000, got {updated_cust['total_price']}"

        # 2b. Admin reduces total_price from 2000 to 1500
        res = client.post("/navaratri_booking/update", json={
            "customer_id": test_id,
            "name": "Test Customer Flow",
            "mobile": test_mobile,
            "address": "Ahmedabad",
            "group": "",
            "reference": "Test",
            "deposit": "",
            "total_price": 1500,
            "given_price": 1000,
            "bookings": [{"date": "2026-10-10", "products": ["C99999TEST"]}]
        })
        d = res.get_json()
        print("2b (Reduce total 2000->1500):", res.status_code, d.get("message"))
        assert res.status_code == 200 and d.get("success") is True, f"Failed: {d}"
        updated_cust = collection.find_one({"_id": ObjectId(test_id)})
        assert updated_cust['total_price'] == 1500, f"Expected 1500, got {updated_cust['total_price']}"
        assert updated_cust['given_price'] == 1000, f"Expected 1000, got {updated_cust['given_price']}"

        # 2c. Admin tries to set given_price > total_price in explicit edit (2000 > 1500)
        res = client.post("/navaratri_booking/update", json={
            "customer_id": test_id,
            "name": "Test Customer Flow",
            "mobile": test_mobile,
            "address": "Ahmedabad",
            "group": "",
            "reference": "Test",
            "deposit": "",
            "total_price": 1500,
            "given_price": 2000,
            "bookings": [{"date": "2026-10-10", "products": ["C99999TEST"]}]
        })
        d = res.get_json()
        print("2c (Set payment > total in edit):", res.status_code, d.get("message"))
        assert res.status_code == 400 and d.get("success") is False, f"Should reject: {d}"
        assert "cannot exceed total invoice amount" in d.get("message"), f"Wrong error message: {d}"
        print("[PASSED] TEST 2 PASSED!\n")

        print("=== TEST 3: Add Booking to Existing Customer (Cumulative append) ===")
        # Current state: Total=1500, Paid=1000, Previous Due=500.
        # Customer adds new items worth 500.
        # Cumulative payable = 500 (due) + 500 (new) = 1000.
        # Customer pays 1000 today.
        res = client.post("/navaratri_booking/update", json={
            "customer_id": test_id,
            "name": "Test Customer Flow",
            "mobile": test_mobile,
            "address": "Ahmedabad",
            "group": "",
            "reference": "Test",
            "deposit": "",
            "total_price": 500,
            "given_price": 1000,
            "bookings": [{"date": "2026-10-11", "products": ["C99998TEST"]}],
            "is_append": True
        })
        d = res.get_json()
        print("3a (Append items=500, pay=1000):", res.status_code, d.get("message"))
        assert res.status_code == 200 and d.get("success") is True, f"Failed: {d}"
        updated_cust = collection.find_one({"_id": ObjectId(test_id)})
        # Total should be 1500 + 500 = 2000
        # Paid should be 1000 + 1000 = 2000
        assert updated_cust['total_price'] == 2000, f"Expected 2000, got {updated_cust['total_price']}"
        assert updated_cust['given_price'] == 2000, f"Expected 2000, got {updated_cust['given_price']}"
        assert "11-10-26" in updated_cust['bookings'], "New date not in merged bookings"
        assert "C99998TEST" in updated_cust['bookings']["11-10-26"], "New product not in merged bookings"

        # 3b. Overpayment check on append
        # Now Total=2000, Paid=2000, Due=0.
        # Add item=300. Max allowed=300. Attempt to pay 301.
        res = client.post("/navaratri_booking/update", json={
            "customer_id": test_id,
            "name": "Test Customer Flow",
            "mobile": test_mobile,
            "address": "Ahmedabad",
            "group": "",
            "reference": "Test",
            "deposit": "",
            "total_price": 300,
            "given_price": 301,
            "bookings": [{"date": "2026-10-12", "products": ["C99997TEST"]}],
            "is_append": True
        })
        d = res.get_json()
        print("3b (Overpayment on append: item=300, pay=301):", res.status_code, d.get("message"))
        assert res.status_code == 400 and d.get("success") is False, f"Should reject: {d}"
        assert "cannot exceed total outstanding amount" in d.get("message"), f"Wrong error: {d}"
        print("[PASSED] TEST 3 PASSED!\n")

        # Cleanup test customer
        collection.delete_many({"mobile": test_mobile})
        print("ALL TESTS COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
