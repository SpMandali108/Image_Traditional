from werkzeug.local import LocalProxy
from website.navaratri.ncycle import get_selected_collection

collection = LocalProxy(lambda: get_selected_collection())


import re

# ------------------ CONFLICT CHECK ------------------
def check_booking_conflict(date, products, exclude_mobile=None):
    conflicts = []

    # Support both 2-digit year ("24-10-25") and 4-digit year ("24-10-2025") key formats
    date_candidates = [date]
    try:
        parts = date.split('-')
        if len(parts) == 3:
            d, m, y = parts[0], parts[1], parts[2]
            if len(y) == 2:
                date_candidates.append(f"{d}-{m}-20{y}")
            elif len(y) == 4:
                date_candidates.append(f"{d}-{m}-{y[2:]}")
    except Exception:
        pass

    valid_dates = set(date_candidates)

    try:
        all_docs = list(collection.find())
    except Exception:
        all_docs = []

    for prod in products:
        prod_clean = str(prod).strip().upper()
        if not prod_clean:
            continue

        found_conflict = None
        for doc in all_docs:
            cust_mobile = str(doc.get("mobile", "")).strip()
            if exclude_mobile and cust_mobile == str(exclude_mobile).strip():
                continue

            cust_bookings = doc.get("bookings", {})
            if not isinstance(cust_bookings, dict):
                continue

            for d_key, p_list in cust_bookings.items():
                if d_key in valid_dates or str(d_key).strip() in valid_dates:
                    if isinstance(p_list, list):
                        for p in p_list:
                            if str(p).strip().upper() == prod_clean:
                                found_conflict = {
                                    "product": prod_clean,
                                    "date": date,
                                    "customer_name": doc.get("Name", "Unknown"),
                                    "customer_mobile": cust_mobile
                                }
                                break
                    elif isinstance(p_list, str) and p_list.strip().upper() == prod_clean:
                        found_conflict = {
                            "product": prod_clean,
                            "date": date,
                            "customer_name": doc.get("Name", "Unknown"),
                            "customer_mobile": cust_mobile
                        }
                        break
                if found_conflict:
                    break
            if found_conflict:
                break

        if found_conflict:
            conflicts.append(found_conflict)

    return len(conflicts) > 0, conflicts


from website.general.utils import (
    find_best_products_by_letter,
    find_highest_booking_customer,
    sanitize_latin1,
    get_all_product_counts as _get_all_product_counts
)

def get_all_product_counts():
    return _get_all_product_counts(collection)


def log_action(name, mobile, action, details):
    """
    Log an action for the Navaratri portal.
    Logs are stored in a collection specific to the selected cycle: f"{collection_name}_logs".
    """
    from datetime import datetime
    from website.general.db import db
    from website.navaratri.ncycle import get_selected_cycle

    cycle = get_selected_cycle()
    if not cycle:
        return

    collection_name = cycle.get("collection_name")
    if not collection_name:
        return

    logs_col = db[f"{collection_name}_logs"]

    # Try to find the name if it is not provided
    if not name and mobile:
        try:
            # First search selected cycle collection
            cust = db[collection_name].find_one({"mobile": mobile})
            if cust:
                name = cust.get("Name") or cust.get("name")
            else:
                # Fallback to general navaratri customers
                from website.general.db import ncustomers
                cust = ncustomers.find_one({"mobile": mobile})
                if cust:
                    name = cust.get("name") or cust.get("Name")
        except Exception:
            pass

    now = datetime.now()
    date_stamp = now.strftime("%Y-%m-%d")
    time_stamp = now.strftime("%H:%M:%S")

    log_entry = {
        "name": name or "",
        "mobile": mobile or "",
        "action": action,
        "details": details,
        "date_stamp": date_stamp,
        "time_stamp": time_stamp,
        "timestamp": now
    }

    try:
        logs_col.insert_one(log_entry)
    except Exception:
        pass
