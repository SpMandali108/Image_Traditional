import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from website import create_app
from website.general.db import db
from website.navaratri.nservices import log_action
from website.general.utils import get_ist_now, format_log_timestamp
from website.navaratri.ncycle import get_active_cycle

app = create_app()

with app.test_request_context():
    from flask import session
    active_cycle = get_active_cycle()
    if active_cycle:
        session["navaratri_cycle_id"] = str(active_cycle["_id"])
        print(f"Set active cycle: {active_cycle.get('name')}")

    now = get_ist_now()
    print(f"Current IST DateTime: {now.strftime('%d/%m/%Y %H:%M:%S')}")

    # Test inserting a test log
    log_action("Test Customer", "9999999999", "book", "Test booking created for verification.")

    # Fetch latest log from Navaratri_2026_logs
    latest_log = db.Navaratri_2026_logs.find_one({"mobile": "9999999999"})
    print("\nInserted Log Document in DB:")
    print(latest_log)

    if latest_log:
        d, t, sort_ts = format_log_timestamp(latest_log.get("timestamp"), latest_log.get("date_stamp"), latest_log.get("time_stamp"))
        print(f"\nFormatted Output for UI:")
        print(f"  Date: {d} (Format: DD/MM/YYYY)")
        print(f"  Time: {t} (Format: 24hrs HH:MM:SS)")
        print(f"  Sort Timestamp (ms): {sort_ts}")
        
        # Clean up test log
        db.Navaratri_2026_logs.delete_one({"_id": latest_log["_id"]})
        print("\nTest log cleaned up.")
