import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from website import create_app

app = create_app()

with app.app_context(), app.test_client() as client:
    with client.session_transaction() as sess:
        sess['logged_in'] = True

    res = client.get('/navaratri_booking')
    assert res.status_code == 200, f'Expected 200, got {res.status_code}'

    html = res.data.decode('utf-8')

    # Find the customerCountBadge value
    match = re.search(r'<span class="badge-gold" id="customerCountBadge">(\d+)</span>', html)
    assert match, 'customerCountBadge not found in HTML'
    server_count = int(match.group(1))
    print(f'Server rendered customer count badge: {server_count}')

    # Count how many ledger entries are in desktop container
    desktop_match = re.search(r'id="customerListContainer"[\s\S]*?(<div class="offcanvas|\Z)', html)
    assert desktop_match, 'desktop container not found'
    desktop_entries_count = len(re.findall(r'class="ledger-entry\s', desktop_match.group(0)))
    print(f'Desktop ledger entries in HTML: {desktop_entries_count}')
    assert desktop_entries_count == server_count, f'Expected desktop entries ({desktop_entries_count}) == server_count ({server_count})'

    # Check mobile container
    mobile_match = re.search(r'id="mobileCustomerListContainer"[\s\S]*?(</div\s*>\s*</div\s*>\s*</div|\Z)', html)
    assert mobile_match, 'mobile container not found'
    mobile_entries_count = len(re.findall(r'class="ledger-entry\s', mobile_match.group(0)))
    print(f'Mobile ledger entries in HTML: {mobile_entries_count}')
    assert mobile_entries_count == server_count, f'Expected mobile entries ({mobile_entries_count}) == server_count ({server_count})'

    # Total in entire DOM is 2x, which was causing the bug when querying globally!
    total_in_dom = len(re.findall(r'class="ledger-entry\s', html))
    print(f'Total in DOM across both containers: {total_in_dom} (2 x {server_count})')
    assert total_in_dom == 2 * server_count

    # Check JavaScript search() code to confirm it queries #customerListContainer and NOT globally .ledger-entry
    assert "document.querySelectorAll('#customerListContainer .ledger-entry')" in html, 'JS search() must query #customerListContainer!'
    assert "document.querySelectorAll('#mobileCustomerListContainer .ledger-entry')" in html, 'JS search() must query #mobileCustomerListContainer!'
    assert "total = desktopEntries.length || mobileEntries.length;" in html, 'Total must equal single list length!'
    print('PASS: JavaScript search() properly targets #customerListContainer and does NOT double count!')

print('\n=============================================')
print('CUSTOMER COUNT DOUBLE-COUNTING BUG RESOLVED!')
print('=============================================')
