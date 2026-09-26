import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from website import create_app
from website.general.db import navaratri_products, ADMIN_PASS
from website.navaratri.nservices import get_navaratri_product

app = create_app()

with app.app_context(), app.test_client() as client:
    # Login admin
    with client.session_transaction() as sess:
        sess['logged_in'] = True

    admin_pw = str(ADMIN_PASS).strip() or '212010'
    test_code = 'C181'

    # Ensure C181 starts as on_rent = True
    navaratri_products.update_one({'code': test_code}, {'$set': {'on_rent': True}})

    print('--- Step 1: Check Booking Manager (/navaratri_booking) contains Sell Form ---')
    r_bm = client.get('/navaratri_booking')
    assert r_bm.status_code == 200, f'Expected 200, got {r_bm.status_code}'
    assert b'Sell Form' in r_bm.data, 'Missing Sell Form button in Booking Manager!'
    assert b'bookingSellCode' in r_bm.data, 'Missing bookingSellCode in Booking Form!'
    assert b'bookingSellPassword' in r_bm.data, 'Missing bookingSellPassword in Booking Form!'
    assert b'bookingSellBtn' in r_bm.data, 'Missing bookingSellBtn in Booking Form!'
    assert b'dedicatedSellModal' in r_bm.data, 'Missing dedicatedSellModal in Booking Manager!'
    assert b'Sets on_rent = false' in r_bm.data, 'Missing on_rent explanation badge!'
    print('PASS 1: Booking Manager contains embedded Sell Form and dedicated Sell Form modal.')

    print('\n--- Step 2: Check Standalone Booking Form (/book) contains Sell Form ---')
    r_book = client.get('/book')
    assert r_book.status_code == 200, f'Expected 200, got {r_book.status_code}'
    assert b'Sell Form' in r_book.data, 'Missing Sell Form button in /book!'
    assert b'bookSellCode' in r_book.data, 'Missing bookSellCode in /book!'
    assert b'bookSellPassword' in r_book.data, 'Missing bookSellPassword in /book!'
    assert b'bookSellBtn' in r_book.data, 'Missing bookSellBtn in /book!'
    print('PASS 2: /book contains embedded Sell Form section and button.')

    print(f'\n--- Step 3: Verify initial on_rent status of {test_code} is True ---')
    doc_initial = get_navaratri_product(test_code)
    assert doc_initial['on_rent'] is True, f'Expected on_rent=True, got {doc_initial.get("on_rent")}'
    r_chk = client.get(f'/api/check-product?product_code={test_code}&date=2026-10-15')
    assert r_chk.status_code == 200
    chk_data = r_chk.get_json()
    assert chk_data['available'] is True, f'Expected available, got {chk_data}'
    print(f'PASS 3: {test_code} is initially on_rent: True and available for rent.')

    print(f'\n--- Step 4: Execute Sell Form action on {test_code} (changes on_rent from True to False) ---')
    r_sell = client.post('/api/navaratri/sell-product', json={'code': test_code, 'password': admin_pw})
    assert r_sell.status_code == 200, f'Expected 200, got {r_sell.status_code}: {r_sell.get_json()}'
    sell_res = r_sell.get_json()
    assert sell_res['success'] is True
    print(f'Sell API response: {sell_res}')

    # Check MongoDB directly
    doc_after = get_navaratri_product(test_code)
    assert doc_after['on_rent'] is False, f'Expected on_rent=False, got {doc_after.get("on_rent")}'
    print(f'PASS 4: MongoDB document {test_code} successfully changed on_rent from True to False!')

    print('\n--- Step 5: Verify future bookings are blocked with clear message ---')
    r_chk_sold = client.get(f'/api/check-product?product_code={test_code}&date=2026-10-15')
    assert r_chk_sold.status_code == 200
    chk_sold_data = r_chk_sold.get_json()
    assert chk_sold_data['available'] is False, 'Sold product should NOT be available'
    assert 'no longer available for rent' in chk_sold_data['reason']
    print(f'PASS 5: Booking check correctly blocked: {chk_sold_data["reason"]}')

    print('\n--- Step 6: Verify product is hidden from customer catalogue ---')
    r_cat = client.get('/choli')
    assert f'data-code="{test_code}"'.encode() not in r_cat.data, f'Sold product {test_code} should be hidden from catalogue!'
    print(f'PASS 6: {test_code} is completely hidden from customer catalogue.')

    print(f'\n--- Step 7: Clean up by restoring {test_code} back to on_rent=True ---')
    r_res = client.post('/api/navaratri/restore-product', json={'code': test_code, 'password': admin_pw})
    assert r_res.status_code == 200
    doc_clean = get_navaratri_product(test_code)
    assert doc_clean['on_rent'] is True
    print(f'PASS 7: Restored {test_code} to on_rent: True successfully.')

print('\n=============================================')
print('ALL BOOKING MANAGER SELL FORM TESTS PASSED!')
print('=============================================')
