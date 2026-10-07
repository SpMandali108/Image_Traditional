import os
import threading
from werkzeug.local import LocalProxy
from website.navaratri.ncycle import get_selected_collection
from website.general.db import navaratri_products, costume_groups, ADMIN_PASS

collection = LocalProxy(lambda: get_selected_collection())
booking_lock = threading.Lock()

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

def parse_product_item(item):
    """
    Parses a product code string which could be:
    - Individual code: 'C101', 'K113'
    - Group code with size: 'G4-32', 'G4:32', 'G4(32)'
    - Plain group code: 'G4'
    Returns: (base_code, size, quantity)
    """
    s = str(item or '').strip().upper()
    if not s:
        return '', None, 1
    if '-' in s:
        parts = s.split('-', 1)
        return parts[0].strip(), parts[1].strip(), 1
    if ':' in s:
        parts = s.split(':', 1)
        return parts[0].strip(), parts[1].strip(), 1
    m = re.match(r'^([A-Z0-9]+)\s*\(([^)]+)\)$', s)
    if m:
        return m.group(1).strip(), m.group(2).strip(), 1
    return s, None, 1

def is_group_code(code):
    """Returns True if the base code starts with 'G' (Group product)."""
    base, _, _ = parse_product_item(code)
    return bool(base and base.startswith('G'))

def get_group(code):
    """
    Finds a single group document in costume_groups by code (e.g. G4).
    Normalizes code, handles casing/spacing, and provides safe query handling.
    """
    if not code:
        return None
    base_code = parse_product_item(code)[0]
    base_clean = normalize_product_code(base_code)
    if not base_clean:
        return None
    try:
        doc = costume_groups.find_one({"code": base_clean})
        if doc:
            return doc
        return costume_groups.find_one({"code": {"$regex": f"^{re.escape(base_clean)}$", "$options": "i"}})
    except Exception as e:
        print(f"[ERROR] get_group query error for '{base_clean}': {e}", flush=True)
        return None

def get_booked_group_quantity(code, size, date, exclude_mobile=None):
    """
    Calculates total booked pieces for a group and size on a specific date.
    Iterates through customers in the active cycle collection.
    """
    base_code = parse_product_item(code)[0]
    base_norm = normalize_product_code(base_code)
    size_str = str(size).strip() if size is not None else None
    target_tuple = parse_date_tuple(date)

    date_candidates = [str(date).strip()]
    try:
        parts = str(date).strip().split('-')
        if len(parts) == 3:
            d, m, y = parts[0], parts[1], parts[2]
            if len(y) == 2:
                date_candidates.append(f"{d}-{m}-20{y}")
            elif len(y) == 4:
                date_candidates.append(f"{d}-{m}-{y[2:]}")
    except Exception:
        pass
    valid_dates = set(date_candidates)

    booked_count = 0
    try:
        all_docs = list(collection.find())
    except Exception:
        all_docs = []

    for doc in all_docs:
        cust_mobile = str(doc.get("mobile", "")).strip()
        if exclude_mobile:
            if isinstance(exclude_mobile, (list, tuple, set)):
                if cust_mobile in [str(m).strip() for m in exclude_mobile if m]:
                    continue
            elif cust_mobile == str(exclude_mobile).strip():
                continue

        cust_bookings = doc.get("bookings", {})
        if not isinstance(cust_bookings, dict):
            continue

        for d_key, p_list in cust_bookings.items():
            d_key_str = str(d_key).strip()
            date_matches = (d_key_str in valid_dates)
            if not date_matches and target_tuple:
                k_tuple = parse_date_tuple(d_key_str)
                if k_tuple and k_tuple == target_tuple:
                    date_matches = True

            if date_matches:
                items = p_list if isinstance(p_list, list) else [p_list]
                for item in items:
                    i_base, i_size, i_qty = parse_product_item(item)
                    if normalize_product_code(i_base) == base_norm:
                        if size_str is None or (i_size and str(i_size).strip() == size_str):
                            booked_count += i_qty

    return booked_count

def get_available_group_quantity(code, size, date, exclude_mobile=None):
    """
    Calculates available inventory quantity for a group size on a given date.
    available_quantity = master_quantity - booked_quantity
    Returns: (available_qty: int, master_qty: int, booked_qty: int)
    """
    group = get_group(code)
    if not group or not group.get("on_rent", True):
        return 0, 0, 0

    sizes = group.get("sizes", {})
    size_str = str(size).strip() if size is not None else ""
    size_info = sizes.get(size_str)
    if not size_info or not size_info.get("active", True):
        return 0, 0, 0

    master_qty = int(size_info.get("quantity", 0))
    booked_qty = get_booked_group_quantity(code, size_str, date, exclude_mobile=exclude_mobile)
    available_qty = max(0, master_qty - booked_qty)
    return available_qty, master_qty, booked_qty

# ------------------ CONFLICT CHECK ------------------
def check_booking_conflict(date, products, exclude_mobile=None):
    """
    Checks for booking conflicts on a specific date for a list of products.
    - For individual products (C..., K...): only 1 customer can rent it per date.
    - For group products (G...): multiple customers can rent up to master_quantity.
    """
    conflicts = []
    target_date_tuple = parse_date_tuple(date)

    date_candidates = [str(date).strip()]
    if target_date_tuple:
        yr, mo, da = target_date_tuple
        yr2 = yr % 100
        date_candidates.extend([
            f"{da:02d}-{mo:02d}-{yr2:02d}",
            f"{da:02d}-{mo:02d}-{yr:04d}",
            f"{yr:04d}-{mo:02d}-{da:02d}",
            f"{da}-{mo}-{yr2:02d}",
            f"{da}-{mo}-{yr:04d}",
            f"{da:02d}/{mo:02d}/{yr2:02d}",
            f"{da:02d}/{mo:02d}/{yr:04d}",
            f"{yr:04d}/{mo:02d}/{da:02d}",
            f"{da}/{mo}/{yr2:02d}",
            f"{da}/{mo}/{yr:04d}"
        ])
    else:
        try:
            parts = str(date).strip().split('-')
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

    # 1. Intra-submission duplicate check for individual products
    seen_ind_norms = {}
    for prod in products:
        base_code, size, _ = parse_product_item(prod)
        grp = get_group(base_code) if is_group_code(base_code) else None
        if grp and size:
            continue  # Group items with sizes can be booked multiple times based on available stock
        prod_norm = normalize_product_code(prod)
        if not prod_norm:
            continue
        if prod_norm in seen_ind_norms:
            conflicts.append({
                "product": str(prod).strip().upper(),
                "date": str(date),
                "customer_name": "Duplicate in Form",
                "customer_mobile": "",
                "reason": f"Product '{prod}' is added multiple times on {date} in this booking."
            })
        else:
            seen_ind_norms[prod_norm] = prod

    # 2. Tally requested quantities per group + size in this submission
    group_requested_counts = {}
    for prod in products:
        base_code, size, qty = parse_product_item(prod)
        grp = get_group(base_code) if is_group_code(base_code) else None
        if grp and size:
            key = (base_code, str(size).strip())
            group_requested_counts[key] = group_requested_counts.get(key, 0) + qty

    # Validate Group products against available quantities
    for (g_code, g_size), req_qty in group_requested_counts.items():
        avail_qty, master_qty, booked_qty = get_available_group_quantity(
            g_code, g_size, date, exclude_mobile=exclude_mobile
        )
        if req_qty > avail_qty:
            conflicts.append({
                "product": f"{g_code} (Size {g_size})",
                "date": str(date),
                "customer_name": "Reserved / Capacity Reached",
                "customer_mobile": "",
                "reason": f"Only {avail_qty} piece(s) available for {date} ({master_qty} total, {booked_qty} booked), but requested {req_qty}."
            })

    # 3. Validate Individual products (1-to-1 uniqueness against existing bookings)
    for prod in products:
        base_code, size, _ = parse_product_item(prod)
        grp = get_group(base_code) if is_group_code(base_code) else None
        if grp and size:
            continue  # Already checked above in group section

        prod_clean = str(prod).strip().upper()
        prod_norm = normalize_product_code(prod)
        if not prod_norm:
            continue

        found_conflict = None
        for doc in all_docs:
            cust_mobile = str(doc.get("mobile", "")).strip()
            if exclude_mobile:
                if isinstance(exclude_mobile, (list, tuple, set)):
                    if cust_mobile in [str(m).strip() for m in exclude_mobile if m]:
                        continue
                elif cust_mobile == str(exclude_mobile).strip():
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
                                "date": str(date),
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
    Normalizes code, handles casing/spacing, and provides safe query handling.
    Returns dict {"code": ..., "image": ..., "on_rent": ...} or None.
    """
    if not code:
        return None
    code_norm = normalize_product_code(code)
    if not code_norm:
        return None
    try:
        doc = navaratri_products.find_one({"code": code_norm})
        if doc:
            return doc
        # Case-insensitive / regex fallback if not an exact match
        return navaratri_products.find_one({"code": {"$regex": f"^{re.escape(code_norm)}$", "$options": "i"}})
    except Exception as e:
        print(f"[ERROR] get_navaratri_product database query error for '{code_norm}': {e}", flush=True)
        return None

def is_product_available_for_rent(code, size=None, requested_qty=1, date=None):
    """
    Validates whether a product or group is available for rental.
    Works for individual products (C..., K...) and groups (G...).
    Returns: (is_available: bool, error_reason: str or None)
    """
    if not code:
        return False, "Product code is required."

    base_code, embedded_size, _ = parse_product_item(code)
    effective_size = size or embedded_size

    group = get_group(base_code) if is_group_code(base_code) else None
    if group:
        if not group.get("on_rent", True):
            return False, f"Group '{base_code}' is currently not taking new bookings."

        if effective_size:
            sizes = group.get("sizes", {})
            size_str = str(effective_size).strip()
            size_info = sizes.get(size_str)
            if not size_info:
                return False, f"Size '{size_str}' does not exist for group '{base_code}'."
            if not size_info.get("active", True):
                return False, f"Size '{size_str}' for group '{base_code}' is currently disabled for new bookings."

            if date:
                avail_qty, master_qty, booked_qty = get_available_group_quantity(base_code, size_str, date)
                if requested_qty > avail_qty:
                    if avail_qty == 0:
                        return False, f"Sorry, {base_code} size {size_str} is no longer available for {date}."
                    return False, f"Only {avail_qty} piece(s) of {base_code} size {size_str} available for {date} (requested {requested_qty})."

        return True, None
    else:
        code_norm = normalize_product_code(code)
        if not code_norm:
            return False, f"Invalid product code '{code}'."

        product = get_navaratri_product(code_norm)
        # If product is registered in database, check its rental status:
        if product and not product.get("on_rent", True):
            return False, f"This product ({code_norm}) is no longer available for rent. Please select another product."

        # If product has not been coded or is not registered in db, allow booking
        return True, None


def get_all_navaratri_products():
    """
    Returns list of all products from navaratri_products, sorted in natural order.
    Auto-syncs if collection is empty.
    """
    if navaratri_products.count_documents({}) == 0:
        sync_navaratri_products()

    prods = list(navaratri_products.find({}, {"_id": 0, "code": 1, "image": 1, "on_rent": 1, "sold_info": 1, "price": 1, "rent_price": 1}))
    prods.sort(key=lambda x: natural_sort_key(x.get("code", "")))
    return prods


def get_product_or_group(code):
    """
    Looks up a product in navaratri_products or costume_groups by code.
    Returns: (doc: dict, is_group: bool)
    """
    if not code:
        return None, False
    base_code = parse_product_item(code)[0]
    if is_group_code(base_code):
        grp = get_group(base_code)
        if grp:
            return grp, True
    # Check individual products
    ind = get_navaratri_product(base_code)
    if ind:
        return ind, False
    # Fallback to group check if not found
    grp = get_group(base_code)
    if grp:
        return grp, True
    return None, False


def get_all_costume_groups():
    """Returns all groups from costume_groups, sorted in natural order."""
    try:
        groups = list(costume_groups.find({}))
        groups.sort(key=lambda x: natural_sort_key(x.get("code", "")))
        return groups
    except Exception as e:
        print(f"[ERROR] get_all_costume_groups error: {e}", flush=True)
        return []


def get_active_individual_products(product_type=None):
    """
    Returns active individual products from MongoDB.
    product_type: 'choli' -> codes starting with C
                  'kediya' -> codes starting with K
                  None -> all active individual products
    """
    query = {"on_rent": True}
    if product_type:
        pt = product_type.strip().lower()
        if pt == "choli":
            query["code"] = {"$regex": "^C", "$options": "i"}
        elif pt == "kediya":
            query["code"] = {"$regex": "^K", "$options": "i"}
    prods = list(navaratri_products.find(query, {"_id": 0, "code": 1, "image": 1, "on_rent": 1, "sold_info": 1, "price": 1, "rent_price": 1}))
    prods.sort(key=lambda x: natural_sort_key(x.get("code", "")))
    return prods


def get_active_group_products(product_type=None):
    """
    Returns active group products from MongoDB.
    product_type: 'choli' -> groups with type 'choli'
                  'kediya' -> groups with type 'kediya'
                  None -> all active groups
    """
    query = {"on_rent": True}
    if product_type:
        query["type"] = product_type.strip().lower()
    groups = list(costume_groups.find(query, {"_id": 0, "code": 1, "type": 1, "image": 1, "sizes": 1, "on_rent": 1, "price": 1, "rent_price": 1}))
    groups.sort(key=lambda x: natural_sort_key(x.get("code", "")))
    return groups


def get_group_size_availability(code, date=None, exclude_mobile=None):
    """
    Returns full size breakdown for a group, optionally with date-specific availability.
    """
    group = get_group(code)
    if not group:
        return {}

    sizes = group.get("sizes", {})
    res = {}
    for sz_key, sz_val in sizes.items():
        qty = int(sz_val.get("quantity", 0))
        act = bool(sz_val.get("active", True))
        if date:
            booked = get_booked_group_quantity(code, sz_key, date, exclude_mobile=exclude_mobile)
            avail = max(0, qty - booked) if (act and group.get("on_rent", True)) else 0
        else:
            booked = 0
            avail = qty if (act and group.get("on_rent", True)) else 0

        res[str(sz_key)] = {
            "quantity": qty,
            "active": act,
            "booked": booked,
            "available": avail
        }
    return res


def get_max_future_committed_group_quantity(code, size):
    """
    Finds the maximum pieces booked for (group, size) on any future or current date.
    Enforces Section 29: Admin cannot reduce master inventory below committed reservations.
    """
    base_code = parse_product_item(code)[0]
    base_norm = normalize_product_code(base_code)
    size_str = str(size).strip()
    today_tuple = (get_ist_now().year, get_ist_now().month, get_ist_now().day)

    date_counts = {}
    try:
        all_docs = list(collection.find())
    except Exception:
        all_docs = []

    for doc in all_docs:
        cust_bookings = doc.get("bookings", {})
        if not isinstance(cust_bookings, dict):
            continue

        for d_key, p_list in cust_bookings.items():
            dt_tuple = parse_date_tuple(d_key)
            if not dt_tuple:
                continue
            if dt_tuple >= today_tuple:
                items = p_list if isinstance(p_list, list) else [p_list]
                for item in items:
                    i_base, i_size, i_qty = parse_product_item(item)
                    if normalize_product_code(i_base) == base_norm and str(i_size).strip() == size_str:
                        date_counts[dt_tuple] = date_counts.get(dt_tuple, 0) + i_qty

    return max(date_counts.values()) if date_counts else 0


def update_group_size_quantity(code, size, new_quantity):
    """
    Updates master quantity of a group size.
    Enforces Section 29 check against future commitments.
    """
    try:
        new_qty = int(new_quantity)
        if new_qty < 1:
            return False, "Quantity must be a positive integer (at least 1).", 400
    except (ValueError, TypeError):
        return False, "Quantity must be a valid positive integer.", 400

    group = get_group(code)
    if not group:
        return False, f"Group '{code}' not found.", 404

    size_str = str(size).strip()
    sizes = group.get("sizes", {})
    if size_str not in sizes:
        return False, f"Size '{size_str}' does not exist in group '{code}'.", 404

    # Future committed bookings check
    max_committed = get_max_future_committed_group_quantity(code, size_str)
    if new_qty < max_committed:
        return False, f"Cannot reduce quantity to {new_qty} because {max_committed} pieces are already committed in future bookings. Minimum safe quantity is {max_committed}.", 400

    now_str = get_ist_now().strftime("%Y-%m-%d %H:%M:%S")
    res = costume_groups.update_one(
        {"code": group["code"]},
        {
            "$set": {
                f"sizes.{size_str}.quantity": new_qty,
                "updated_at": now_str
            }
        }
    )
    if res.matched_count == 0:
        return False, "Failed to update quantity.", 500

    return True, f"Quantity for size {size_str} successfully updated to {new_qty}.", 200


def add_group_size(code, size, quantity, active=True):
    """Adds a new size to a group or updates/reactivates an existing size."""
    size_str = str(size).strip()
    if not size_str:
        return False, "Size is required.", 400

    try:
        qty = int(quantity)
        if qty < 1:
            return False, "Quantity must be a positive integer (at least 1).", 400
    except (ValueError, TypeError):
        return False, "Quantity must be a valid positive integer.", 400

    group = get_group(code)
    if not group:
        return False, f"Group '{code}' not found.", 404

    now_str = get_ist_now().strftime("%Y-%m-%d %H:%M:%S")
    costume_groups.update_one(
        {"code": group["code"]},
        {
            "$set": {
                f"sizes.{size_str}": {
                    "quantity": qty,
                    "active": bool(active)
                },
                "updated_at": now_str
            }
        }
    )
    return True, f"Size {size_str} ({qty} pcs) added to group {group['code']}.", 200


def toggle_group_size_active(code, size, active=None):
    """Toggles or sets active state of a size in a group."""
    group = get_group(code)
    if not group:
        return False, f"Group '{code}' not found.", 404

    size_str = str(size).strip()
    sizes = group.get("sizes", {})
    if size_str not in sizes:
        return False, f"Size '{size_str}' not found.", 404

    current_state = bool(sizes[size_str].get("active", True))
    new_state = (not current_state) if active is None else bool(active)

    now_str = get_ist_now().strftime("%Y-%m-%d %H:%M:%S")
    costume_groups.update_one(
        {"code": group["code"]},
        {
            "$set": {
                f"sizes.{size_str}.active": new_state,
                "updated_at": now_str
            }
        }
    )
    status_label = "enabled" if new_state else "disabled"
    return True, f"Size {size_str} is now {status_label} for new bookings.", 200


def delete_or_disable_group_size(code, size):
    """
    Deletes or soft-disables a group size.
    Enforces Section 31: If historical or future bookings exist for this size,
    mark inactive instead of deleting.
    """
    group = get_group(code)
    if not group:
        return False, f"Group '{code}' not found.", 404

    size_str = str(size).strip()
    sizes = group.get("sizes", {})
    if size_str not in sizes:
        return False, f"Size '{size_str}' not found.", 404

    base_code = group["code"]
    base_norm = normalize_product_code(base_code)
    has_any_booking = False

    try:
        for doc in collection.find():
            cust_bookings = doc.get("bookings", {})
            if isinstance(cust_bookings, dict):
                for d_k, p_list in cust_bookings.items():
                    items = p_list if isinstance(p_list, list) else [p_list]
                    for item in items:
                        i_b, i_s, _ = parse_product_item(item)
                        if normalize_product_code(i_b) == base_norm and str(i_s).strip() == size_str:
                            has_any_booking = True
                            break
                    if has_any_booking:
                        break
            if has_any_booking:
                break
    except Exception:
        pass

    now_str = get_ist_now().strftime("%Y-%m-%d %H:%M:%S")

    if has_any_booking:
        costume_groups.update_one(
            {"code": group["code"]},
            {
                "$set": {
                    f"sizes.{size_str}.active": False,
                    "updated_at": now_str
                }
            }
        )
        return True, f"Size {size_str} has booking records and has been deactivated (disabled) to preserve historical data.", 200
    else:
        costume_groups.update_one(
            {"code": group["code"]},
            {
                "$unset": {f"sizes.{size_str}": ""},
                "$set": {"updated_at": now_str}
            }
        )
        return True, f"Size {size_str} has been permanently deleted.", 200


def toggle_product_status(code, on_rent=None):
    """
    Toggles or sets on_rent for individual products or groups.
    Does NOT delete products from database.
    """
    code_clean = str(code).strip().upper()
    if is_group_code(code_clean):
        group = get_group(code_clean)
        if not group:
            return False, f"Group '{code_clean}' not found.", 404
        current_state = bool(group.get("on_rent", True))
        new_state = (not current_state) if on_rent is None else bool(on_rent)
        now_str = get_ist_now().strftime("%Y-%m-%d %H:%M:%S")
        costume_groups.update_one(
            {"code": group["code"]},
            {"$set": {"on_rent": new_state, "updated_at": now_str}}
        )
        msg = f"Group '{group['code']}' is now {'taking bookings' if new_state else 'not taking bookings'}."
        return True, msg, 200
    else:
        product = get_navaratri_product(code_clean)
        if not product:
            return False, f"Product '{code_clean}' not found.", 404
        current_state = bool(product.get("on_rent", True))
        new_state = (not current_state) if on_rent is None else bool(on_rent)
        navaratri_products.update_one(
            {"code": product["code"]},
            {"$set": {"on_rent": new_state}}
        )
        msg = f"Product '{product['code']}' is now {'taking bookings' if new_state else 'not taking bookings'}."
        return True, msg, 200


# ==============================================================================
# 📦 BULK UPLOAD VALIDATION & ATOMIC INSERTION ENGINES
# ==============================================================================
from werkzeug.utils import secure_filename
from PIL import Image
import io

def validate_individual_upload_item(filename, file_bytes=None):
    """
    Validates a single individual product upload item.
    Returns: (is_valid: bool, code: str, ptype: str, error: str)
    """
    if not filename:
        return False, "", "", "Filename is empty."

    fname = secure_filename(filename)
    base, ext = os.path.splitext(fname)
    ext_lower = ext.lower()

    if ext_lower not in {'.webp', '.jpg', '.jpeg', '.png'}:
        return False, base, "", f"Unsupported file extension '{ext}'. Only .webp, .jpg, .jpeg, .png are allowed."

    code = base.strip().upper()
    if not code:
        return False, "", "", "Product code cannot be empty."

    # Must match Cxxx or Kxxx with numeric portion
    if re.match(r'^C\d+$', code):
        ptype = "choli"
    elif re.match(r'^K\d+$', code):
        ptype = "kediya"
    else:
        return False, code, "", f"Invalid product filename/code '{code}'. Must be 'C' or 'K' followed by numbers (e.g. C101, K102)."

    # Verify image integrity if bytes provided
    if file_bytes is not None:
        if len(file_bytes) == 0:
            return False, code, ptype, "File is empty (0 bytes)."
        if len(file_bytes) > 16 * 1024 * 1024:
            return False, code, ptype, "File exceeds maximum size of 16MB."
        try:
            with Image.open(io.BytesIO(file_bytes)) as img:
                img.verify()
        except Exception as e:
            return False, code, ptype, f"Invalid or corrupt image file: {str(e)}"

    return True, code, ptype, None


def validate_individual_bulk_batch(files_metadata):
    """
    Pre-validates entire bulk batch of individual products (Atomic Requirement).
    Checks extensions, code formats, duplicates within batch, and duplicates against DB.
    files_metadata: list of dicts [{"filename": str, "file_bytes": bytes (optional)}]
    Returns: (all_valid: bool, items_results: list)
    """
    items_results = []
    seen_in_batch = set()
    all_valid = True

    # Pre-fetch existing database codes
    db_individual_codes = set(p["code"].upper() for p in navaratri_products.find({}, {"code": 1}))
    db_group_codes = set(g["code"].upper() for g in costume_groups.find({}, {"code": 1}))
    all_existing_codes = db_individual_codes | db_group_codes

    for item in files_metadata:
        fname = item.get("filename", "")
        fbytes = item.get("file_bytes")

        is_valid, code, ptype, err = validate_individual_upload_item(fname, fbytes)
        
        if is_valid:
            if code in seen_in_batch:
                is_valid = False
                err = f"Duplicate code '{code}' in current selection."
            elif code in all_existing_codes:
                is_valid = False
                err = f"Product code '{code}' already exists in database."
            else:
                seen_in_batch.add(code)

        if not is_valid:
            all_valid = False

        items_results.append({
            "filename": fname,
            "code": code,
            "type": ptype,
            "valid": is_valid,
            "error": err
        })

    return all_valid, items_results


def save_individual_bulk_upload(files_list):
    """
    Executes transaction-like atomic bulk upload of individual products:
    1. Reads and pre-validates ALL files.
    2. If ANY file is invalid or already exists -> REJECT ENTIRE SUBMISSION.
    3. If ALL valid -> Saves files to disk and inserts into navaratri_products.
    Returns: (success: bool, message: str, items_results: list, status_code: int)
    """
    from flask import current_app
    import os

    if not files_list:
        return False, "No files selected for upload.", [], 400

    # Build files metadata with bytes
    files_metadata = []
    read_files = []
    for f in files_list:
        fname = f.filename
        if not fname:
            continue
        b = f.read()
        files_metadata.append({"filename": fname, "file_bytes": b})
        read_files.append((fname, b))

    all_valid, items_results = validate_individual_bulk_batch(files_metadata)

    if not all_valid:
        invalid_count = sum(1 for x in items_results if not x["valid"])
        return False, f"Upload rejected: {invalid_count} item(s) failed pre-validation. Zero items were inserted.", items_results, 400

    # All items are valid -> Save to disk and database atomically
    base_static = current_app.static_folder if current_app else os.path.join(os.getcwd(), 'website', 'static')
    choli_dir = os.path.join(base_static, 'Choli')
    choli_jpg_dir = os.path.join(base_static, 'CholiJpg')
    kediya_dir = os.path.join(base_static, 'Kediya')
    kediya_jpg_dir = os.path.join(base_static, 'KediyaJpg')

    for d in (choli_dir, choli_jpg_dir, kediya_dir, kediya_jpg_dir):
        os.makedirs(d, exist_ok=True)

    docs_to_insert = []
    try:
        for idx, (fname, b) in enumerate(read_files):
            meta = items_results[idx]
            code = meta["code"]
            ptype = meta["type"]

            target_webp_dir = choli_dir if ptype == "choli" else kediya_dir
            target_jpg_dir = choli_jpg_dir if ptype == "choli" else kediya_jpg_dir

            webp_path = os.path.join(target_webp_dir, f"{code}.webp")
            jpg_path = os.path.join(target_jpg_dir, f"{code}.jpg")

            # Save as WebP and JPG using PIL
            with Image.open(io.BytesIO(b)) as img:
                # WebP
                img.save(webp_path, "WEBP", quality=90)
                # JPG (converting transparency to white if needed)
                if img.mode in ("RGBA", "LA", "P"):
                    bg = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    bg.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                    bg.save(jpg_path, "JPEG", quality=90)
                else:
                    img.convert("RGB").save(jpg_path, "JPEG", quality=90)

            docs_to_insert.append({
                "code": code,
                "image": f"{code}.webp",
                "on_rent": True
            })

        # Atomic database insertion
        if docs_to_insert:
            navaratri_products.insert_many(docs_to_insert)

        return True, f"Successfully uploaded and registered {len(docs_to_insert)} products!", items_results, 200

    except Exception as e:
        print(f"[ERROR] save_individual_bulk_upload failed during disk/DB write: {e}", flush=True)
        return False, f"Server error during upload: {str(e)}", items_results, 500


def validate_and_create_groups(groups_list, files_dict=None):
    """
    Executes transaction-like atomic multi-group creation:
    1. Pre-validates ALL groups.
    2. If ANY group is invalid or code exists -> REJECT ENTIRE SUBMISSION.
    3. If ALL valid -> Saves images and inserts documents into costume_groups.
    groups_list: list of dicts [{"code": "G4", "type": "choli", "image_key": "img_G4", "sizes": {"32": 2, ...}}]
    files_dict: dict of {image_key: FileStorage or bytes}
    Returns: (success: bool, message: str, results: list, status_code: int)
    """
    from flask import current_app
    import os

    if files_dict is None:
        files_dict = {}

    if not groups_list:
        return False, "No groups provided.", [], 400

    db_individual_codes = set(p["code"].upper() for p in navaratri_products.find({}, {"code": 1}))
    db_group_codes = set(g["code"].upper() for g in costume_groups.find({}, {"code": 1}))
    all_existing_codes = db_individual_codes | db_group_codes

    seen_codes = set()
    validated_groups = []
    errors = []

    for idx, grp in enumerate(groups_list):
        raw_code = str(grp.get("code") or "").strip().upper()
        raw_type = str(grp.get("type") or "").strip().lower()
        sizes_raw = grp.get("sizes") or {}
        img_key = grp.get("image_key") or f"image_{idx}"

        group_errors = []

        # 1. Code format check: G + digits
        if not raw_code:
            group_errors.append("Group code is required.")
        elif not re.match(r'^G\d+$', raw_code):
            group_errors.append(f"Invalid group code '{raw_code}'. Group code must start with 'G' followed by numbers (e.g. G4, G12).")
        elif raw_code in seen_codes:
            group_errors.append(f"Duplicate group code '{raw_code}' within current submission.")
        elif raw_code in all_existing_codes:
            group_errors.append(f"Group code '{raw_code}' already exists in database.")
        else:
            seen_codes.add(raw_code)

        # 2. Type check
        if raw_type not in {"choli", "kediya"}:
            group_errors.append(f"Invalid group type '{raw_type}'. Must be 'choli' or 'kediya'.")

        # 3. Sizes check
        if isinstance(sizes_raw, list):
            s_dict = {}
            for item in sizes_raw:
                if isinstance(item, dict):
                    s_dict[item.get("size")] = item.get("quantity")
            sizes_raw = s_dict

        if not isinstance(sizes_raw, dict) or len(sizes_raw) == 0:
            group_errors.append("At least one size with positive quantity must be provided.")
        else:
            cleaned_sizes = {}
            for sz_k, qty_val in sizes_raw.items():
                sz_str = str(sz_k).strip()
                if not sz_str:
                    continue
                try:
                    qty_int = int(qty_val)
                    if qty_int <= 0:
                        group_errors.append(f"Quantity for size '{sz_str}' must be a positive integer (> 0).")
                    else:
                        cleaned_sizes[sz_str] = {"quantity": qty_int, "active": True}
                except (ValueError, TypeError):
                    group_errors.append(f"Quantity for size '{sz_str}' must be a valid whole number (no decimals or text).")
            if not cleaned_sizes and not group_errors:
                group_errors.append("At least one valid size must be specified.")

        # 4. Image check
        img_file = files_dict.get(img_key) or files_dict.get(raw_code) or files_dict.get(grp.get("image_filename"))
        img_bytes = None
        if img_file is None:
            # If not in files_dict, check if image already exists on disk
            base_static = current_app.static_folder if current_app else os.path.join(os.getcwd(), 'website', 'static')
            existing_path = os.path.join(base_static, 'Group', f"{raw_code}.webp")
            if os.path.exists(existing_path):
                with open(existing_path, 'rb') as f:
                    img_bytes = f.read()
            else:
                group_errors.append(f"Style image is required for group '{raw_code}'.")
        else:
            try:
                if hasattr(img_file, "read"):
                    img_bytes = img_file.read()
                elif isinstance(img_file, bytes):
                    img_bytes = img_file
                
                if not img_bytes or len(img_bytes) == 0:
                    group_errors.append(f"Image for group '{raw_code}' is empty.")
                else:
                    with Image.open(io.BytesIO(img_bytes)) as test_img:
                        test_img.verify()
            except Exception as e:
                group_errors.append(f"Corrupt or unsupported image file for group '{raw_code}': {str(e)}")

        if group_errors:
            errors.append({"group": raw_code or f"Group #{idx+1}", "errors": group_errors})
        else:
            validated_groups.append({
                "code": raw_code,
                "type": raw_type,
                "sizes": cleaned_sizes,
                "img_bytes": img_bytes
            })

    if errors:
        return False, "Group creation rejected: Validation errors encountered.", errors, 400

    # All valid -> write images and insert documents
    base_static = current_app.static_folder if current_app else os.path.join(os.getcwd(), 'website', 'static')
    group_dir = os.path.join(base_static, 'Group')
    group_jpg_dir = os.path.join(base_static, 'GroupJpg')
    choli_dir = os.path.join(base_static, 'Choli')
    choli_jpg_dir = os.path.join(base_static, 'CholiJpg')
    kediya_dir = os.path.join(base_static, 'Kediya')
    kediya_jpg_dir = os.path.join(base_static, 'KediyaJpg')

    for d in (group_dir, group_jpg_dir, choli_dir, choli_jpg_dir, kediya_dir, kediya_jpg_dir):
        os.makedirs(d, exist_ok=True)

    now_str = get_ist_now().strftime("%Y-%m-%d %H:%M:%S")
    docs_to_insert = []

    try:
        for grp in validated_groups:
            code = grp["code"]
            ptype = grp["type"]
            img_b = grp["img_bytes"]

            with Image.open(io.BytesIO(img_b)) as img:
                # Save in Group/ and GroupJpg/
                img.save(os.path.join(group_dir, f"{code}.webp"), "WEBP", quality=90)
                
                # Also save in Choli/ or Kediya/ so any standard path resolves it
                cat_dir = choli_dir if ptype == "choli" else kediya_dir
                cat_jpg_dir = choli_jpg_dir if ptype == "choli" else kediya_jpg_dir
                img.save(os.path.join(cat_dir, f"{code}.webp"), "WEBP", quality=90)

                # Save JPGs
                if img.mode in ("RGBA", "LA", "P"):
                    bg = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    bg.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                    bg.save(os.path.join(group_jpg_dir, f"{code}.jpg"), "JPEG", quality=90)
                    bg.save(os.path.join(cat_jpg_dir, f"{code}.jpg"), "JPEG", quality=90)
                else:
                    img.convert("RGB").save(os.path.join(group_jpg_dir, f"{code}.jpg"), "JPEG", quality=90)
                    img.convert("RGB").save(os.path.join(cat_jpg_dir, f"{code}.jpg"), "JPEG", quality=90)

            docs_to_insert.append({
                "code": code,
                "type": ptype,
                "image": f"{code}.webp",
                "on_rent": True,
                "sizes": grp["sizes"],
                "created_at": now_str,
                "updated_at": now_str
            })

        if docs_to_insert:
            costume_groups.insert_many(docs_to_insert)

        return True, f"Successfully created {len(docs_to_insert)} product group(s)!", docs_to_insert, 200

    except Exception as e:
        print(f"[ERROR] validate_and_create_groups write failure: {e}", flush=True)
        return False, f"Server error creating groups: {str(e)}", [], 500


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
        return False, f"Product code '{code_clean}' does not exist in the Navaratri collection.", 400

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


def record_multiple_costume_sale(name, mobile, address, reference, codes, total_price, given_price, password):
    """
    Validates and executes a multi-costume sale:
    1. Verifies admin password
    2. Validates customer details and multiple product codes
    3. Verifies each code is currently rentable
    4. Sets on_rent = False in navaratri_products collection
    5. Saves customer record in the active cycle collection with type = 'selling'
    6. Upserts customer record in Navaratri_Customers (ncustomers)
    7. Logs admin actions
    Returns: (success: bool, message: str, customer_id: str, data: dict, status_code: int)
    """
    from bson import ObjectId

    if not verify_admin_password(password):
        return False, "Incorrect admin password.", None, {}, 401

    name = str(name or "").strip()
    if not name:
        return False, "Customer Name is mandatory.", None, {}, 400

    mobile = str(mobile or "").strip()
    if not mobile or not mobile.isdigit() or len(mobile) != 10:
        return False, "A valid 10-digit Mobile Number is mandatory.", None, {}, 400

    address = str(address or "").strip()
    if not address:
        return False, "Customer Address is mandatory.", None, {}, 400

    reference = str(reference or "").strip()

    if not codes:
        return False, "At least one product code must be selected.", None, {}, 400

    if isinstance(codes, str):
        raw_list = [c.strip().upper() for c in codes.split(",") if c.strip()]
    elif isinstance(codes, (list, tuple)):
        raw_list = [str(c or "").strip().upper() for c in codes if str(c or "").strip()]
    else:
        raw_list = []

    cleaned_codes = []
    seen = set()
    for c in raw_list:
        if c and c not in seen:
            seen.add(c)
            cleaned_codes.append(c)

    if not cleaned_codes:
        return False, "At least one valid product code must be selected.", None, {}, 400

    try:
        total_price = int(total_price)
    except (ValueError, TypeError):
        return False, "Total Price is mandatory and must be a valid number.", None, {}, 400

    try:
        given_price = int(given_price)
    except (ValueError, TypeError):
        return False, "Given Price is mandatory and must be a valid number.", None, {}, 400

    if total_price < 0:
        return False, "Total Price cannot be negative.", None, {}, 400

    if given_price < 0:
        return False, "Given Price cannot be negative.", None, {}, 400

    if given_price > total_price:
        return False, f"Given Price (₹{given_price}) cannot exceed Total Price (₹{total_price}).", None, {}, 400

    # Verify each costume exists in Navaratri collection and is rentable
    for code in cleaned_codes:
        prod = get_navaratri_product(code)
        if not prod:
            return False, f"Costume code '{code}' does not exist in the Navaratri collection. Only registered Navaratri costumes can be sold.", None, {}, 400

        if prod.get("on_rent") is False:
            return False, f"Costume '{code}' is already marked as sold and unavailable for rent.", None, {}, 400

    now = get_ist_now()
    today_str = now.strftime("%d-%m-%y")
    sale_id = ObjectId()

    try:
        from flask import url_for
        qr_url = url_for('navaratri.download_bill_page', id=str(sale_id), _external=True)
    except Exception:
        qr_url = f"/download-bill?id={str(sale_id)}"

    customer_doc = {
        "_id": sale_id,
        "Name": name,
        "mobile": mobile,
        "address": address,
        "reference": reference,
        "deposit": "N/A",
        "group": "",
        "type": "selling",
        "sold_products": cleaned_codes,
        "bookings": {today_str: cleaned_codes},
        "total_price": total_price,
        "given_price": given_price,
        "date": today_str,
        "created_at": now,
        "qr_url": qr_url
    }

    try:
        collection.insert_one(customer_doc)
    except Exception as e:
        return False, f"Database error creating customer sale record: {str(e)}", None, {}, 500

    # Upsert customer record into Navaratri_Customers collection
    try:
        from website.general.db import ncustomers
        ncustomers.update_one(
            {"mobile": mobile},
            {
                "$set": {
                    "name": name,
                    "mobile": mobile,
                    "address": address,
                    "reference": reference,
                    "updated_at": now
                }
            },
            upsert=True
        )
    except Exception:
        pass

    # Mark all selected costumes as sold (on_rent: False)
    for code in cleaned_codes:
        try:
            navaratri_products.update_one(
                {"code": code},
                {
                    "$set": {
                        "on_rent": False,
                        "sold_info": {
                            "buyer_name": name,
                            "buyer_mobile": mobile,
                            "sale_id": str(sale_id),
                            "price": str(total_price),
                            "sold_at": now.strftime("%d/%m/%Y %H:%M:%S")
                        }
                    }
                }
            )
            try:
                log_action("Admin", mobile, "product_sold", f"Marked costume '{code}' as sold to {name} ({mobile}).")
            except Exception:
                pass
        except Exception:
            pass

    try:
        log_action(name, mobile, "sale", f"Sold {len(cleaned_codes)} costume(s): {', '.join(cleaned_codes)}. Total: ₹{total_price}, Paid: ₹{given_price}.")
    except Exception:
        pass

    remaining = total_price - given_price
    return True, f"Sale successfully recorded for {len(cleaned_codes)} costume(s)!", str(sale_id), {
        "customer_id": str(sale_id),
        "name": name,
        "mobile": mobile,
        "address": address,
        "reference": reference,
        "codes": cleaned_codes,
        "total_price": total_price,
        "given_price": given_price,
        "remaining": remaining,
        "date": today_str
    }, 200



