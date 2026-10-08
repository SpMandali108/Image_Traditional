import re
from datetime import datetime
from pymongo import UpdateOne

def normalize_mobile(raw_mobile):
    """
    Extracts the clean 10-digit mobile number from any input format
    (e.g., '+91 98765 43210', '09876543210', 9876543210).
    """
    if not raw_mobile:
        return ""
    digits = re.sub(r'\D', '', str(raw_mobile).strip())
    if len(digits) == 12 and digits.startswith('91'):
        return digits[2:]
    elif len(digits) == 11 and digits.startswith('0'):
        return digits[1:]
    elif len(digits) > 10:
        return digits[-10:]
    return digits


def build_flexible_mobile_query(mobile):
    """
    Builds a flexible MongoDB query matching 10-digit mobile, +91, 91, 0, and int formats.
    """
    m = normalize_mobile(mobile)
    if not m:
        return {"mobile": mobile}
    return {
        "$or": [
            {"mobile": m},
            {"mobile": f"91{m}"},
            {"mobile": f"+91{m}"},
            {"mobile": f"0{m}"},
            {"mobile": int(m) if m.isdigit() else m}
        ]
    }


def sync_all_navaratri_customers(target_db=None):
    """
    Unites all customer records across all Navaratri cycles (past and present)
    into the centralized Navaratri_Customers database using high-performance bulk operations.
    Guarantees that regardless of which cycle is selected or created,
    the customer database remains 100% united and all-inclusive.
    """
    from website.general.db import db as default_db
    database = target_db if target_db is not None else default_db

    cycle_collections = []
    try:
        cycles_col = database["navaratri_cycles"]
        for c in cycles_col.find().sort("created_at", 1):
            col_name = c.get("collection_name")
            if col_name and col_name in database.list_collection_names() and col_name not in cycle_collections:
                cycle_collections.append(col_name)
    except Exception as e:
        print(f"[CUSTOMER SYNC NOTICE] navaratri_cycles query: {e}", flush=True)

    if "Form" in database.list_collection_names() and "Form" not in cycle_collections:
        cycle_collections.insert(0, "Form")
    if "Navaratri_2026" in database.list_collection_names() and "Navaratri_2026" not in cycle_collections:
        cycle_collections.append("Navaratri_2026")

    from website.general.utils import resolve_customer_locality
    active_localities = []
    try:
        from website.navaratri.nroutes import KNOWN_LOCALITIES
        active_localities = list(KNOWN_LOCALITIES)
    except Exception:
        pass

    try:
        for cloc in database["Custom_Localities"].find():
            cname = cloc.get("name")
            if cname and cname not in active_localities:
                active_localities.insert(0, cname)
    except Exception:
        pass

    ncust_col = database["Navaratri_Customers"]

    # Pre-fetch existing customers in 1 single network call
    existing_map = {}
    try:
        for doc in ncust_col.find():
            m = normalize_mobile(doc.get("mobile"))
            if m:
                existing_map[m] = doc
    except Exception as e:
        print(f"[CUSTOMER SYNC ERROR] Fetching existing Navaratri_Customers: {e}", flush=True)

    merged_customers = {}

    for col_name in cycle_collections:
        try:
            col = database[col_name]
            for doc in col.find():
                m = normalize_mobile(doc.get("mobile"))
                if len(m) == 10:
                    name = (doc.get("Name") or doc.get("name") or "").strip()
                    addr = (doc.get("address") or "").strip()
                    grp = (doc.get("group") or "").strip()
                    ref = (doc.get("reference") or "").strip()
                    dep = (doc.get("deposit") or "").strip()
                    updated = doc.get("updated_at") or doc.get("created_at") or datetime.utcnow()

                    if m not in merged_customers:
                        merged_customers[m] = {
                            "mobile": m,
                            "name": name,
                            "address": addr,
                            "group": grp,
                            "reference": ref,
                            "deposit": dep,
                            "updated_at": updated
                        }
                    else:
                        cust = merged_customers[m]
                        if name: cust["name"] = name
                        if addr: cust["address"] = addr
                        if grp: cust["group"] = grp
                        if ref: cust["reference"] = ref
                        if dep: cust["deposit"] = dep
                        if updated: cust["updated_at"] = updated
        except Exception as e:
            print(f"[CUSTOMER SYNC ERROR] Reading collection '{col_name}': {e}", flush=True)

    bulk_ops = []
    for m, cdata in merged_customers.items():
        existing = existing_map.get(m)
        upd = {
            "mobile": m,
            "updated_at": cdata.get("updated_at") or datetime.utcnow()
        }

        name = cdata.get("name") or (existing.get("name") if existing else "")
        if name: upd["name"] = name

        addr = cdata.get("address") or (existing.get("address") if existing else "")
        if addr: upd["address"] = addr

        grp = cdata.get("group") or (existing.get("group") if existing else "")
        if grp: upd["group"] = grp

        ref = cdata.get("reference") or (existing.get("reference") if existing else "")
        if ref: upd["reference"] = ref

        dep = cdata.get("deposit") or (existing.get("deposit") if existing else "")
        if dep: upd["deposit"] = dep

        # Preserve existing verified locality or resolve
        if existing and existing.get("locality"):
            upd["locality"] = existing.get("locality")
        elif addr and active_localities:
            mapped_loc = resolve_customer_locality({"address": addr}, active_localities)
            if mapped_loc:
                upd["locality"] = mapped_loc

        # Only execute update if new customer or fields changed
        needs_update = False
        if not existing:
            needs_update = True
        else:
            for k, v in upd.items():
                if k != "updated_at" and existing.get(k) != v:
                    needs_update = True
                    break

        if needs_update:
            bulk_ops.append(UpdateOne({"mobile": m}, {"$set": upd}, upsert=True))

    if bulk_ops:
        try:
            res = ncust_col.bulk_write(bulk_ops, ordered=False)
            return res.upserted_count + res.modified_count
        except Exception as e:
            print(f"[CUSTOMER SYNC ERROR] Bulk write Navaratri_Customers: {e}", flush=True)
            return 0
    return 0


def sync_all_fancy_customers(target_db=None):
    """
    Unites all customer records across all Fancy cycles into Fancy_Customers using bulk write.
    """
    from website.general.db import db as default_db
    database = target_db if target_db is not None else default_db

    f_collections = []
    try:
        cycles_col = database["fancy_cycles"]
        for c in cycles_col.find().sort("created_at", 1):
            col_name = c.get("collection_name")
            if col_name and col_name in database.list_collection_names() and col_name not in f_collections:
                f_collections.append(col_name)
    except Exception as e:
        print(f"[CUSTOMER SYNC NOTICE] fancy_cycles query: {e}", flush=True)

    for legacy in ["Fancy", "Fancy_2025_2026", "Fancy_2026_2026"]:
        if legacy in database.list_collection_names() and legacy not in f_collections:
            f_collections.append(legacy)

    fcust_col = database["Fancy_Customers"]

    existing_map = {}
    try:
        for doc in fcust_col.find():
            m = normalize_mobile(doc.get("mobile"))
            if m:
                existing_map[m] = doc
    except Exception as e:
        print(f"[CUSTOMER SYNC ERROR] Fetching existing Fancy_Customers: {e}", flush=True)

    merged_customers = {}

    for col_name in f_collections:
        try:
            col = database[col_name]
            for doc in col.find():
                m = normalize_mobile(doc.get("mobile"))
                if len(m) == 10:
                    name = (doc.get("name") or doc.get("Name") or "").strip()
                    addr = (doc.get("address") or "").strip()
                    school = (doc.get("school") or "").strip()
                    updated = doc.get("updated_at") or doc.get("timestamp") or datetime.utcnow()

                    if m not in merged_customers:
                        merged_customers[m] = {
                            "mobile": m,
                            "name": name,
                            "address": addr,
                            "school": school,
                            "updated_at": updated
                        }
                    else:
                        cust = merged_customers[m]
                        if name: cust["name"] = name
                        if addr: cust["address"] = addr
                        if school: cust["school"] = school
                        if updated: cust["updated_at"] = updated
        except Exception as e:
            print(f"[CUSTOMER SYNC ERROR] Reading Fancy collection '{col_name}': {e}", flush=True)

    bulk_ops = []
    for m, cdata in merged_customers.items():
        existing = existing_map.get(m)
        upd = {
            "mobile": m,
            "updated_at": cdata.get("updated_at") or datetime.utcnow()
        }

        name = cdata.get("name") or (existing.get("name") if existing else "")
        if name: upd["name"] = name

        addr = cdata.get("address") or (existing.get("address") if existing else "")
        if addr: upd["address"] = addr

        school = cdata.get("school") or (existing.get("school") if existing else "")
        if school: upd["school"] = school

        if existing and existing.get("locality"):
            upd["locality"] = existing.get("locality")

        needs_update = False
        if not existing:
            needs_update = True
        else:
            for k, v in upd.items():
                if k != "updated_at" and existing.get(k) != v:
                    needs_update = True
                    break

        if needs_update:
            bulk_ops.append(UpdateOne({"mobile": m}, {"$set": upd}, upsert=True))

    if bulk_ops:
        try:
            res = fcust_col.bulk_write(bulk_ops, ordered=False)
            return res.upserted_count + res.modified_count
        except Exception as e:
            print(f"[CUSTOMER SYNC ERROR] Bulk write Fancy_Customers: {e}", flush=True)
            return 0
    return 0


def sync_all_customers(target_db=None):
    """
    Unites customer records for both Navaratri and Fancy.
    """
    n_count = sync_all_navaratri_customers(target_db=target_db)
    f_count = sync_all_fancy_customers(target_db=target_db)
    return {"navaratri_synced": n_count, "fancy_synced": f_count}


def lookup_navaratri_customer_autocomplete(raw_mobile, target_db=None, current_cycle_collection=None):
    """
    Centralized, bulletproof customer autocomplete lookup for Navaratri.
    Step 1: Check active cycle collection (to support appending to ongoing bookings & payment calc)
    Step 2: Check united Navaratri_Customers database (for returning customers from ANY cycle)
    Step 3: Fallback across all past Navaratri cycle collections (auto-syncing to united DB)
    Step 4: Cross-system fallback across Fancy_Customers
    """
    from website.general.db import db as default_db
    database = target_db if target_db is not None else default_db

    mobile = normalize_mobile(raw_mobile)
    if not mobile or len(mobile) != 10:
        return {"exists": False}

    mob_query = build_flexible_mobile_query(mobile)

    # 1. Check currently active / selected cycle
    if current_cycle_collection is not None:
        try:
            active_customer = current_cycle_collection.find_one(mob_query)
            if active_customer:
                tot = int(active_customer.get("total_price", 0) or 0)
                giv = int(active_customer.get("given_price", 0) or 0)
                return {
                    "exists": True,
                    "in_cycle": True,
                    "data": {
                        "id": str(active_customer.get("_id")),
                        "name": active_customer.get("Name") or active_customer.get("name", ""),
                        "mobile": mobile,
                        "address": active_customer.get("address", ""),
                        "group": active_customer.get("group", ""),
                        "reference": active_customer.get("reference", ""),
                        "deposit": active_customer.get("deposit", ""),
                        "total_price": tot,
                        "given_price": giv,
                        "remaining": max(0, tot - giv)
                    }
                }
        except Exception as e:
            print(f"[AUTOCOMPLETE LOOKUP NOTICE] Current cycle query: {e}", flush=True)

    # 2. Check united Navaratri_Customers collection
    try:
        ncust_col = database["Navaratri_Customers"]
        customer = ncust_col.find_one(mob_query, {"_id": 0})
        if customer:
            return {
                "exists": True,
                "in_cycle": False,
                "data": {
                    "name": customer.get("name") or customer.get("Name", ""),
                    "mobile": mobile,
                    "address": customer.get("address", ""),
                    "group": customer.get("group", ""),
                    "reference": customer.get("reference", ""),
                    "deposit": customer.get("deposit", "")
                }
            }
    except Exception as e:
        print(f"[AUTOCOMPLETE LOOKUP NOTICE] Navaratri_Customers query: {e}", flush=True)

    # 3. Fallback: Search across all cycle collections in navaratri_cycles
    try:
        cycles_col = database["navaratri_cycles"]
        for c in cycles_col.find():
            c_name = c.get("collection_name")
            if c_name and c_name in database.list_collection_names():
                doc = database[c_name].find_one(mob_query)
                if doc:
                    name = doc.get("Name") or doc.get("name", "")
                    addr = doc.get("address", "")
                    grp = doc.get("group", "")
                    ref = doc.get("reference", "")
                    dep = doc.get("deposit", "")
                    try:
                        database["Navaratri_Customers"].update_one(
                            {"mobile": mobile},
                            {
                                "$set": {
                                    "name": name,
                                    "mobile": mobile,
                                    "address": addr,
                                    "group": grp,
                                    "reference": ref,
                                    "deposit": dep,
                                    "updated_at": datetime.utcnow()
                                }
                            },
                            upsert=True
                        )
                    except Exception:
                        pass
                    return {
                        "exists": True,
                        "in_cycle": False,
                        "data": {
                            "name": name,
                            "mobile": mobile,
                            "address": addr,
                            "group": grp,
                            "reference": ref,
                            "deposit": dep
                        }
                    }
    except Exception as e:
        print(f"[AUTOCOMPLETE LOOKUP NOTICE] Cycles scan fallback: {e}", flush=True)

    # Legacy Form fallback if not in navaratri_cycles
    try:
        if "Form" in database.list_collection_names():
            doc = database["Form"].find_one(mob_query)
            if doc:
                name = doc.get("Name") or doc.get("name", "")
                addr = doc.get("address", "")
                grp = doc.get("group", "")
                ref = doc.get("reference", "")
                dep = doc.get("deposit", "")
                try:
                    database["Navaratri_Customers"].update_one(
                        {"mobile": mobile},
                        {
                            "$set": {
                                "name": name,
                                "mobile": mobile,
                                "address": addr,
                                "group": grp,
                                "reference": ref,
                                "deposit": dep,
                                "updated_at": datetime.utcnow()
                            }
                        },
                        upsert=True
                    )
                except Exception:
                    pass
                return {
                    "exists": True,
                    "in_cycle": False,
                    "data": {
                        "name": name,
                        "mobile": mobile,
                        "address": addr,
                        "group": grp,
                        "reference": ref,
                        "deposit": dep
                    }
                }
    except Exception:
        pass

    # 4. Fallback: Check Fancy_Customers
    try:
        fcust = database["Fancy_Customers"].find_one(mob_query, {"_id": 0})
        if fcust:
            return {
                "exists": True,
                "in_cycle": False,
                "data": {
                    "name": fcust.get("name") or fcust.get("Name", ""),
                    "mobile": mobile,
                    "address": fcust.get("address", ""),
                    "group": "",
                    "reference": ""
                }
            }
    except Exception:
        pass

    return {"exists": False}


def lookup_fancy_customer_autocomplete(raw_mobile, target_db=None):
    """
    Centralized customer autocomplete lookup for Fancy dress bookings.
    Searches Fancy_Customers first, then fancy cycles, then Navaratri_Customers.
    """
    from website.general.db import db as default_db
    database = target_db if target_db is not None else default_db

    mobile = normalize_mobile(raw_mobile)
    if not mobile or len(mobile) != 10:
        return {"exists": False}

    mob_query = build_flexible_mobile_query(mobile)

    # 1. Fancy_Customers
    try:
        fcust = database["Fancy_Customers"].find_one(mob_query, {"_id": 0})
        if fcust:
            return {"exists": True, "data": fcust}
    except Exception:
        pass

    # 2. Search fancy cycles
    try:
        for c in database["fancy_cycles"].find():
            c_name = c.get("collection_name")
            if c_name and c_name in database.list_collection_names():
                doc = database[c_name].find_one(mob_query)
                if doc:
                    name = doc.get("name") or doc.get("Name", "")
                    addr = doc.get("address", "")
                    school = doc.get("school", "")
                    data = {"mobile": mobile, "name": name, "address": addr, "school": school}
                    try:
                        database["Fancy_Customers"].update_one(
                            {"mobile": mobile},
                            {"$set": {**data, "updated_at": datetime.utcnow()}},
                            upsert=True
                        )
                    except Exception:
                        pass
                    return {"exists": True, "data": data}
    except Exception:
        pass

    # 3. Navaratri_Customers cross-check
    try:
        ncust = database["Navaratri_Customers"].find_one(mob_query, {"_id": 0})
        if ncust:
            return {
                "exists": True,
                "data": {
                    "mobile": mobile,
                    "name": ncust.get("name") or ncust.get("Name", ""),
                    "address": ncust.get("address", ""),
                    "school": ""
                }
            }
    except Exception:
        pass

    return {"exists": False}
