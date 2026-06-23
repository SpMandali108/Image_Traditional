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