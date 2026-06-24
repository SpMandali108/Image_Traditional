from werkzeug.local import LocalProxy
from website.navaratri.ncycle import get_selected_collection

collection = LocalProxy(lambda: get_selected_collection())


# ------------------ CONFLICT CHECK ------------------
def check_booking_conflict(date, products, exclude_mobile=None):
    conflicts = []

    for product in products:
        query = {f"bookings.{date}": {"$elemMatch": {"$eq": product}}}

        if exclude_mobile:
            query["mobile"] = {"$ne": exclude_mobile}

        existing_booking = collection.find_one(query)

        if existing_booking:
            conflicts.append({
                "product": product,
                "date": date,
                "customer_name": existing_booking.get("Name", "Unknown"),
                "customer_mobile": existing_booking.get("mobile", "Unknown")
            })

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
