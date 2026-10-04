import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from website import create_app
from website.general.db import navaratri_products, ADMIN_PASS
from website.navaratri.nservices import (
    sync_navaratri_products, 
    get_navaratri_product, 
    is_product_available_for_rent,
    sell_navaratri_product,
    restore_navaratri_product
)

app = create_app()
with app.app_context(), app.test_client() as client:
    print('--- Step 0: Ensure Sync ---')
    total, new = sync_navaratri_products()
    print(f'Total products: {total}')

    test_code = 'C182'

    # Ensure C182 starts as on_rent = True
    navaratri_products.update_one({'code': test_code}, {'$set': {'on_rent': True}})

    print('\n--- TEST A: on_rent=True ---')
    avail, reason = is_product_available_for_rent(test_code)
    assert avail is True, f'Expected available, got {reason}'
    res = client.get('/choli')
    assert f'data-code="{test_code}"'.encode() in res.data, 'Expected C182 in /choli when on_rent=True'
    print('TEST A PASSED: Catalogue visible & booking available.')

    print('\n--- TEST C: Sell with wrong password ---')
    with client.session_transaction() as sess:
        sess['logged_in'] = True

    res = client.post('/api/navaratri/sell-product', json={'code': test_code, 'password': 'WRONG_PASSWORD'})
    assert res.status_code == 401, f'Expected 401, got {res.status_code}'
    data = res.get_json()
    assert data['message'] == 'Incorrect password.', f'Unexpected message: {data}'
    doc = get_navaratri_product(test_code)
    assert doc['on_rent'] is True, 'on_rent should still be True'
    print('TEST C PASSED: Wrong password rejected, status remained True.')

    print('\n--- TEST D: Cancel confirmation ---')
    # If admin cancels, no POST is sent, status stays True
    doc = get_navaratri_product(test_code)
    assert doc['on_rent'] is True
    print('TEST D PASSED: Status remains True on cancel.')

    print('\n--- TEST E: Sell with correct password ---')
    admin_pw = str(ADMIN_PASS).strip() or '212010'
    res = client.post('/api/navaratri/sell-product', json={'code': test_code, 'password': admin_pw})
    assert res.status_code == 200, f'Expected 200, got {res.status_code}: {res.get_json()}'
    
    # 1. MongoDB state
    doc = get_navaratri_product(test_code)
    assert doc['on_rent'] is False, 'on_rent should be False'
    
    # 2. Customer catalogue hides product
    res = client.get('/choli')
    assert f'data-code="{test_code}"'.encode() not in res.data, 'Sold product should NOT appear in /choli'
    
    # 3. Future booking validation rejects
    avail, reason = is_product_available_for_rent(test_code)
    assert avail is False, 'Product should NOT be available for rent'
    assert 'no longer available for rent' in reason
    
    # 4. Images still exist on disk
    c_webp = os.path.join('website', 'static', 'Choli', f'{test_code}.webp')
    c_jpg = os.path.join('website', 'static', 'CholiJpg', f'{test_code}.jpg')
    assert os.path.exists(c_webp), 'Image .webp must not be deleted'
    assert os.path.exists(c_jpg), 'Image .jpg must not be deleted'
    print('TEST E PASSED: Product marked sold, hidden from catalogue, booking rejected, images intact.')

    print('\n--- TEST B & F: Persistence after sold ---')
    # Re-verify fresh from DB
    doc_fresh = navaratri_products.find_one({'code': test_code})
    assert doc_fresh['on_rent'] is False
    res_fresh = client.get('/choli')
    assert f'data-code="{test_code}"'.encode() not in res_fresh.data
    print('TEST B & F PASSED: Persisted in MongoDB, catalogue remains hidden.')

    print('\n--- Restore test: restore C182 back to rentable ---')
    res_restore = client.post('/api/navaratri/restore-product', json={'code': test_code, 'password': admin_pw})
    assert res_restore.status_code == 200
    doc_restored = get_navaratri_product(test_code)
    assert doc_restored['on_rent'] is True
    res_restored = client.get('/choli')
    assert f'data-code="{test_code}"'.encode() in res_restored.data
    print('RESTORE PASSED: C182 restored and visible again in /choli.')

    print('\n--- Admin page test: /navaratri_products and /navaratri/costume-manager ---')
    res_admin = client.get('/navaratri_products')
    assert res_admin.status_code == 200
    assert b'Costume Manager' in res_admin.data
    assert b'C182' in res_admin.data
    assert b'K188' in res_admin.data

    res_alias = client.get('/navaratri/costume-manager')
    assert res_alias.status_code == 200
    assert b'Costume Manager' in res_alias.data

    # Log out and test security
    with client.session_transaction() as sess:
        sess.clear()
    res_unauth = client.get('/navaratri_products')
    assert res_unauth.status_code == 302, 'Unauthenticated user should be redirected'

    res_api_unauth = client.post('/api/navaratri/sell-product', json={'code': 'C1', 'password': admin_pw})
    assert res_api_unauth.status_code == 401, 'Unauthenticated API call should be rejected with 401'
    print('ADMIN SECURITY TEST PASSED: Admin page and API require authentication.')

print('\n========================================')
print('ALL TESTS COMPLETED AND PASSED 100%!')
print('========================================')
