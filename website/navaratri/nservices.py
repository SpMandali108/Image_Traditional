# nservices.py

from ..general.db import collection


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


# ------------------ BEST PRODUCTS ------------------
def find_best_products_by_letter(data):
    c_counts, k_counts = {}, {}

    for booking in data:
        bookings = booking.get("bookings", {})
        if not isinstance(bookings, dict):
            continue

        for products in bookings.values():
            if isinstance(products, list):
                for p in products:
                    p = p.strip().upper()
                    if p.startswith("C"):
                        c_counts[p] = c_counts.get(p, 0) + 1
                    elif p.startswith("K"):
                        k_counts[p] = k_counts.get(p, 0) + 1

    best_c = max(c_counts, key=c_counts.get) if c_counts else "N/A"
    best_k = max(k_counts, key=k_counts.get) if k_counts else "N/A"

    return best_c, c_counts.get(best_c, 0), best_k, k_counts.get(best_k, 0)


# ------------------ HIGHEST CUSTOMER ------------------
def find_highest_booking_customer(data):
    totals = {}

    for booking in data:
        name = booking.get("Name", "Unknown")
        try:
            price = int(booking.get("total_price", 0))
        except:
            price = 0

        totals[name] = totals.get(name, 0) + price

    if not totals:
        return "N/A", 0

    best = max(totals, key=totals.get)
    return best, totals[best]


# ------------------ PRODUCT COUNTS ------------------
def get_all_product_counts():
    counts = {}

    for customer in collection.find():
        bookings = customer.get("bookings", {})
        if not isinstance(bookings, dict):
            continue

        for products in bookings.values():
            if isinstance(products, str):
                products = [p.strip() for p in products.split(",")]

            if isinstance(products, list):
                for p in products:
                    p = p.strip().upper()
                    if p:
                        counts[p] = counts.get(p, 0) + 1

    return counts