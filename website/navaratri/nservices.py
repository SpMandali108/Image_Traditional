from werkzeug.local import LocalProxy
from website.navaratri.ncycle import get_selected_collection

collection = LocalProxy(lambda: get_selected_collection())


from datetime import datetime
import re

def normalize_product_code(code):
    """Normalize product code by stripping hyphens, spaces, and converting to uppercase."""
    if not code:
        return ""
    return re.sub(r'[^A-Z0-9]', '', str(code).strip().upper())

def parse_date_tuple(date_input):
    """Extract (year, month, day) tuple from various date string formats."""
    if not date_input:
        return None
    s = str(date_input).strip()
    for fmt in ("%d-%m-%y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            dt = datetime.strptime(s, fmt)
            return (dt.year, dt.month, dt.day)
        except ValueError:
            pass
    m = re.match(r'^(\d{1,4})[\-/](\d{1,2})[\-/](\d{1,4})$', s)
    if m:
        p1, p2, p3 = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if p1 > 1000:
            return (p1, p2, p3)
        else:
            yr = p3 if p3 > 100 else (2000 + p3 if p3 < 70 else 1900 + p3)
            return (yr, p2, p1)
    return None

# ------------------ CONFLICT CHECK ------------------
def check_booking_conflict(date, products, exclude_mobile=None):
    conflicts = []
    target_date_tuple = parse_date_tuple(date)

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
        prod_norm = normalize_product_code(prod)
        if not prod_norm:
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
                d_key_str = str(d_key).strip()
                date_matches = (d_key_str in valid_dates)
                if not date_matches and target_date_tuple:
                    k_tuple = parse_date_tuple(d_key_str)
                    if k_tuple and k_tuple == target_date_tuple:
                        date_matches = True

                if date_matches:
                    p_items = p_list if isinstance(p_list, list) else [p_list]
                    for p in p_items:
                        p_str = str(p).strip().upper()
                        p_norm = normalize_product_code(p)
                        if p_str == prod_clean or (prod_norm and prod_norm == p_norm):
                            found_conflict = {
                                "product": prod_clean or p_str,
                                "date": date,
                                "customer_name": doc.get("Name", "Unknown"),
                                "customer_mobile": cust_mobile
                            }
                            break
                    if found_conflict:
                        break
            if found_conflict:
                conflicts.append(found_conflict)
                break

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
