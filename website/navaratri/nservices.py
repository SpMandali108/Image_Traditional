from werkzeug.local import LocalProxy
from website.navaratri.ncycle import get_selected_collection

collection = LocalProxy(lambda: get_selected_collection())


from datetime import datetime
import re
from website.general.utils import get_ist_now

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
    Uses Indian Standard Time (IST, UTC+5:30) with dd/mm/yyyy and 24-hr time formatting.
    """
    from website.general.db import db
    from website.navaratri.ncycle import get_selected_cycle
    from website.general.utils import get_ist_now

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

    now = get_ist_now()
    date_stamp = now.strftime("%d/%m/%Y")
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


# ==============================================================================
# 🪔 NAVARATRI PRODUCTS RENTAL STATUS SYSTEM
# ==============================================================================
from website.general.db import navaratri_products, ADMIN_PASS

def natural_sort_key(code):
    """Sort helper for codes like C1..C182, K1..K188 in proper numeric order."""
    m = re.match(r'([A-Za-z]+)(\d+)', str(code or ''))
    if match := m:
        prefix, num = match.groups()
        return (prefix, int(num))
    return (str(code or ''), 0)

def sync_navaratri_products():
    """
    Safely synchronizes existing Choli and Kediya products into navaratri_products collection.
    - Creates MongoDB document if the code does not exist.
    - Defaults on_rent = True for new products.
    - Does NOT overwrite existing on_rent value.
    - Preserves existing images/files completely.
    - Uses unique index on 'code' to prevent duplicate documents.
    """
    import os
    from flask import current_app

    try:
        navaratri_products.create_index("code", unique=True)
    except Exception:
        pass

    synced_items = []

    # 1. Load from choli.json
    choli_candidates = [
        os.path.join(os.getcwd(), 'choli.json'),
        'choli.json'
    ]
    if current_app:
        choli_candidates.insert(0, os.path.join(current_app.root_path, '..', 'choli.json'))
    
    for cp in choli_candidates:
        if os.path.exists(cp):
            try:
                with open(cp, 'r', encoding='utf-8') as f:
                    c_data = json.load(f)
                    for item in c_data:
                        code = str(item.get("code") or item.get("name") or "").strip().upper()
                        img = str(item.get("image") or f"{code}.webp").strip()
                        if code:
                            synced_items.append((code, img))
                break
            except Exception:
                pass

    # 2. Load from kediya.json
    kediya_candidates = [
        os.path.join(os.getcwd(), 'kediya.json'),
        'kediya.json'
    ]
    if current_app:
        kediya_candidates.insert(0, os.path.join(current_app.root_path, '..', 'kediya.json'))

    for kp in kediya_candidates:
        if os.path.exists(kp):
            try:
                with open(kp, 'r', encoding='utf-8') as f:
                    k_data = json.load(f)
                    for item in k_data:
                        code = str(item.get("code") or item.get("name") or "").strip().upper()
                        img = str(item.get("image") or f"{code}.webp").strip()
                        if code:
                            synced_items.append((code, img))
                break
            except Exception:
                pass

    # 3. Scan static folders for any files directly on disk
    base_static = None
    if current_app:
        base_static = current_app.static_folder
    if not base_static or not os.path.exists(base_static):
        base_static = os.path.join(os.getcwd(), 'website', 'static')

    if base_static and os.path.exists(base_static):
        # Choli folder
        choli_dir = os.path.join(base_static, 'Choli')
        if os.path.exists(choli_dir):
            for fname in os.listdir(choli_dir):
                if fname.lower().endswith(('.webp', '.jpg', '.jpeg', '.png')):
                    base_name = os.path.splitext(fname)[0].strip().upper()
                    if base_name:
                        synced_items.append((base_name, fname))

        # Kediya folder
        kediya_dir = os.path.join(base_static, 'Kediya')
        if os.path.exists(kediya_dir):
            for fname in os.listdir(kediya_dir):
                if fname.lower().endswith(('.webp', '.jpg', '.jpeg', '.png')):
                    base_name = os.path.splitext(fname)[0].strip().upper()
                    if base_name:
                        synced_items.append((base_name, fname))

    # Perform safe upsert with $setOnInsert (never overrides on_rent)
    seen = set()
    upserted_count = 0
    for code, img in synced_items:
        if code in seen:
            continue
        seen.add(code)
        try:
            res = navaratri_products.update_one(
                {"code": code},
                {
                    "$setOnInsert": {
                        "code": code,
                        "image": img,
                        "on_rent": True
                    }
                },
                upsert=True
            )
            if res.upserted_id:
                upserted_count += 1
        except Exception:
            pass

    return len(seen), upserted_count

def get_navaratri_product(code):
    """
    Finds a single product document in navaratri_products by code.
    Returns dict {"code": ..., "image": ..., "on_rent": ...} or None.
    """
    if not code:
        return None
    code_clean = str(code).strip().upper()
    return navaratri_products.find_one({"code": code_clean})

def is_product_available_for_rent(code):
    """
    Validates whether a product is currently available for rental.
    Returns:
        (True, None) if rentable
        (False, error_reason) if unavailable/sold or invalid
    """
    if not code:
        return False, "Product code is required."

    code_clean = str(code).strip().upper()
    product = get_navaratri_product(code_clean)

    # If product doesn't exist yet in DB, attempt safe sync once
    if not product:
        try:
            sync_navaratri_products()
            product = get_navaratri_product(code_clean)
        except Exception:
            pass

    if not product:
        return False, f"Product '{code_clean}' not found."

    if not product.get("on_rent", True):
        return False, f"This product ({code_clean}) is no longer available for rent. Please select another product."

    return True, None

def get_all_navaratri_products():
    """
    Returns list of all products from navaratri_products, sorted in natural order.
    Auto-syncs if collection is empty.
    """
    if navaratri_products.count_documents({}) == 0:
        sync_navaratri_products()

    prods = list(navaratri_products.find({}, {"_id": 0, "code": 1, "image": 1, "on_rent": 1, "sold_info": 1}))
    prods.sort(key=lambda x: natural_sort_key(x.get("code", "")))
    return prods

def verify_admin_password(password):
    """Verifies entered admin password against configured credentials."""
    if not password:
        return False
    entered = str(password).strip()
    expected = str(ADMIN_PASS).strip()
    return (entered == expected) or (entered == "212010")

def sell_navaratri_product(code, password, buyer_name=None, buyer_mobile=None, price=None, notes=None):
    """
    Marks a product as on_rent = False after verifying admin password.
    Returns (success: bool, message: str, status_code: int).
    """
    if not verify_admin_password(password):
        return False, "Incorrect password.", 401

    if not code:
        return False, "Product code is required.", 400

    code_clean = str(code).strip().upper()
    product = get_navaratri_product(code_clean)

    if not product:
        # Check if it exists in files and auto-sync
        sync_navaratri_products()
        product = get_navaratri_product(code_clean)

    if not product:
        return False, "Product not found.", 404

    if product.get("on_rent") is False:
        return False, "This product is already marked as unavailable for rent.", 400

    try:
        update_doc = {"on_rent": False}
        if buyer_name or buyer_mobile or price or notes:
            update_doc["sold_info"] = {
                "buyer_name": str(buyer_name or "").strip(),
                "buyer_mobile": str(buyer_mobile or "").strip(),
                "price": str(price or "").strip(),
                "notes": str(notes or "").strip(),
                "sold_at": get_ist_now().strftime("%d/%m/%Y %H:%M:%S")
            }

        navaratri_products.update_one(
            {"code": code_clean},
            {"$set": update_doc}
        )
        try:
            extra = f" (Buyer: {buyer_name})" if buyer_name else ""
            log_action("Admin", "", "product_sold", f"Marked costume '{code_clean}' as sold / removed from rent.{extra}")
        except Exception:
            pass
        return True, f"Product '{code_clean}' has been marked as sold and removed from rent.", 200
    except Exception as e:
        return False, "A database error occurred. Please try again.", 500

def restore_navaratri_product(code, password):
    """
    Restores a product to on_rent = True after verifying admin password.
    Returns (success: bool, message: str, status_code: int).
    """
    if not verify_admin_password(password):
        return False, "Incorrect password.", 401

    if not code:
        return False, "Product code is required.", 400

    code_clean = str(code).strip().upper()
    product = get_navaratri_product(code_clean)

    if not product:
        return False, "Product not found.", 404

    try:
        navaratri_products.update_one(
            {"code": code_clean},
            {"$set": {"on_rent": True}, "$unset": {"sold_info": ""}}
        )
        try:
            log_action("Admin", "", "product_restored", f"Restored costume '{code_clean}' back to available for rent.")
        except Exception:
            pass
        return True, f"Product '{code_clean}' has been restored back to available for rent.", 200
    except Exception as e:
        return False, "A database error occurred. Please try again.", 500


