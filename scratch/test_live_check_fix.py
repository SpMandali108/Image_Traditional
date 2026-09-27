import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

import unittest
from datetime import datetime
from website import create_app
from website.general.db import db, navaratri_products
from website.navaratri.nservices import (
    get_navaratri_product,
    is_product_available_for_rent,
    normalize_product_code,
    check_booking_conflict
)
from website.navaratri.ncycle import get_selected_collection, get_active_cycle

app = create_app()

def run_tests():
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['logged_in'] = True

        print("="*60)
        print("TEST 1: Product Code Normalization & Lookup in navaratri_products")
        print("="*60)
        test_cases = [
            ("C1", True),
            ("c1", True),
            (" C1 ", True),
            ("C-1", True),
            ("C 1", True),
            ("C148", True),
            ("c148", True),
            ("K1", True),
            ("k10", True),
            ("K173", True),
            ("XYZ999", False),
            ("C", False),
            ("", False),
        ]
        for raw_code, expected_found in test_cases:
            doc = get_navaratri_product(raw_code)
            found = doc is not None
            code_in_doc = doc.get("code") if doc else None
            rentable, reason = is_product_available_for_rent(raw_code)
            print(f"Input: '{raw_code}' -> found={found} (code_in_doc={code_in_doc}), rentable={rentable}, reason='{reason}'")
            if expected_found:
                assert found, f"Expected '{raw_code}' to be found in navaratri_products!"
                assert rentable, f"Expected '{raw_code}' to be rentable!"
            else:
                assert not found, f"Expected '{raw_code}' to NOT be found in navaratri_products!"
                assert not rentable, f"Expected '{raw_code}' to not be rentable!"

        print("\n" + "="*60)
        print("TEST 2: API Route /api/check-product with various inputs")
        print("="*60)
        api_test_cases = [
            ("C1", "2026-10-01", True),
            ("c1", "01-10-26", True),
            (" C1 ", "2026-10-01", True),
            ("C-1", "2026-10-01", True),
            ("C148", "2026-10-02", True),
            ("k10", "2026-10-03", True),
            ("XYZ_FAKE", "2026-10-01", False),
            ("C", "2026-10-01", False),
        ]
        for code, date, expected_avail in api_test_cases:
            resp = client.get(f"/api/check-product?product_code={code}&date={date}")
            assert resp.status_code == 200 or (not expected_avail and resp.status_code in [200, 400]), f"Unexpected status {resp.status_code}"
            data = resp.get_json()
            print(f"API Check '{code}' on {date} -> status={resp.status_code}, data={data}")
            if expected_avail:
                assert data.get("available") is True, f"Expected available=True for {code}: {data}"
            else:
                assert data.get("available") is False, f"Expected available=False for {code}: {data}"

        print("\n" + "="*60)
        print("TEST 3: API Route /api/suggest-products")
        print("="*60)
        resp = client.get("/api/suggest-products")
        assert resp.status_code == 200
        codes = resp.get_json()
        print(f"Total suggested codes: {len(codes)}")
        print(f"Sample suggestions: {codes[:10]} ... {codes[-10:]}")
        assert len(codes) >= 370, f"Expected at least 370 codes, got {len(codes)}"
        assert "C1" in codes
        assert "C148" in codes
        assert "K173" in codes

        print("\n" + "="*60)
        print("TEST 4: Booking Conflict Verification")
        print("="*60)
        # Check active cycle bookings
        active_col = get_selected_collection()
        print(f"Active collection: {active_col.name}")
        sample_booking = active_col.find_one({"bookings": {"$exists": True, "$ne": {}}})
        if sample_booking:
            b_dict = sample_booking.get("bookings", {})
            for b_date, b_prods in b_dict.items():
                if b_prods:
                    p = b_prods[0]
                    # Check conflict on the booked date
                    resp_conf = client.get(f"/api/check-product?product_code={p}&date={b_date}")
                    conf_data = resp_conf.get_json()
                    print(f"Conflicting check for booked item '{p}' on '{b_date}' -> {conf_data}")
                    assert conf_data.get("available") is False, f"Booked product should not be available!"
                    # Exclude the booking mobile to verify exclude_mobile works
                    cust_mob = sample_booking.get("mobile")
                    resp_excl = client.get(f"/api/check-product?product_code={p}&date={b_date}&exclude_mobile={cust_mob}")
                    excl_data = resp_excl.get_json()
                    print(f"Exclude customer's own mobile ({cust_mob}) -> {excl_data}")
                    assert excl_data.get("available") is True, f"Should be available when excluding own mobile!"
                    break

        print("\n" + "="*60)
        print("TEST 5: Sold Costume Verification")
        print("="*60)
        test_sold_code = "C99"
        # Temporarily mark C99 as sold
        navaratri_products.update_one({"code": test_sold_code}, {"$set": {"on_rent": False}})
        try:
            resp_sold = client.get(f"/api/check-product?product_code={test_sold_code}&date=01-10-26")
            sold_data = resp_sold.get_json()
            print(f"Sold item check for '{test_sold_code}' -> {sold_data}")
            assert sold_data.get("available") is False
            assert "no longer available for rent" in sold_data.get("reason", "")
        finally:
            # Restore C99
            navaratri_products.update_one({"code": test_sold_code}, {"$set": {"on_rent": True}})

        print("\n" + "="*60)
        print("ALL TESTS PASSED SUCCESSFULLY!")
        print("="*60)

if __name__ == "__main__":
    run_tests()
