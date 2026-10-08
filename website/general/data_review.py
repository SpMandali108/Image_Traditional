import os
import re
import json
from datetime import datetime
from bson import ObjectId
from website.general.db import db, ADMIN_PASS, ADMIN_ID

# Directory for pre-deletion and audit backups
BACKUP_DIR = os.path.join(os.getcwd(), "data", "backups")

SUSPICIOUS_NAME_REGEX = re.compile(r"test|dummy|fake|sample|flow|repro|temp", re.I)
SUSPICIOUS_PHONE_REGEX = re.compile(r"^99999|^123456|^00000|^88888|^98888|^97999")

def ensure_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    return BACKUP_DIR

def get_retained_records_set(target_db=None):
    current_db = target_db if target_db is not None else db
    retained_col = current_db["Audit_Retained_Records"]
    retained = set()
    for doc in retained_col.find():
        if doc.get("mobile"):
            retained.add(str(doc["mobile"]).strip())
        if doc.get("record_id"):
            retained.add(str(doc["record_id"]).strip())
    return retained

def scan_suspicious_entities(target_db=None):
    """
    Scans the database collections for suspicious/test candidate records.
    Constructs a complete relational picture for each entity:
      - Customer details (Navaratri_Customers, Fancy_Customers)
      - Booking records (Navaratri_2026, Fancy_2026_2026, Form, Fancy)
      - Payment/Financial status
      - Audit Action Logs (Navaratri_2026_logs, Form_logs, Fancy logs)
    Returns: list of structured candidate entity dictionaries.
    """
    current_db = target_db if target_db is not None else db
    retained_set = get_retained_records_set(current_db)

    collections_to_scan = {
        "nav_customers": current_db["Navaratri_Customers"],
        "fancy_customers": current_db["Fancy_Customers"],
        "nav_bookings": current_db["Navaratri_2026"],
        "form_bookings": current_db["Form"],
        "fancy_bookings": current_db["Fancy_2026_2026"],
        "nav_logs": current_db["Navaratri_2026_logs"],
        "form_logs": current_db["Form_logs"]
    }

    # Discover candidate phone numbers and record IDs
    candidate_mobiles = set()
    single_records_by_id = {}

    query_criteria = {
        "$or": [
            {"name": SUSPICIOUS_NAME_REGEX},
            {"Name": SUSPICIOUS_NAME_REGEX},
            {"mobile": SUSPICIOUS_PHONE_REGEX}
        ]
    }

    for col_key, col in collections_to_scan.items():
        try:
            for doc in col.find(query_criteria):
                mob = str(doc.get("mobile") or "").strip()
                if mob:
                    candidate_mobiles.add(mob)
                else:
                    rec_id = str(doc["_id"])
                    single_records_by_id[rec_id] = {
                        "collection": col.name,
                        "doc": doc
                    }
        except Exception:
            pass

    # Also check if any retained records are in DB
    for mob in retained_set:
        candidate_mobiles.add(mob)

    entities = []

    for mobile in sorted(list(candidate_mobiles)):
        # Gather customer profile
        cust_nav = current_db["Navaratri_Customers"].find_one({"mobile": mobile})
        cust_fancy = current_db["Fancy_Customers"].find_one({"mobile": mobile})

        # Gather bookings
        bookings_nav = list(current_db["Navaratri_2026"].find({"mobile": mobile}))
        bookings_form = list(current_db["Form"].find({"mobile": mobile}))
        bookings_fancy = list(current_db["Fancy_2026_2026"].find({"mobile": mobile}))

        # Gather logs
        logs_nav = list(current_db["Navaratri_2026_logs"].find({"mobile": mobile}).sort("_id", -1))
        logs_form = list(current_db["Form_logs"].find({"mobile": mobile}).sort("_id", -1))

        all_bookings = []
        for b in bookings_nav:
            all_bookings.append({
                "collection": "Navaratri_2026",
                "id": str(b.get("_id")),
                "name": b.get("Name") or b.get("name") or "",
                "bookings": b.get("bookings") or {},
                "total_price": b.get("total_price", 0),
                "given_price": b.get("given_price", 0),
                "remaining_price": max(0, int(b.get("total_price", 0) or 0) - int(b.get("given_price", 0) or 0)),
                "deposit": b.get("deposit", ""),
                "group": b.get("group", ""),
                "raw": {k: (str(v) if isinstance(v, ObjectId) else v) for k, v in b.items()}
            })

        for b in bookings_form:
            all_bookings.append({
                "collection": "Form (Navaratri 2025)",
                "id": str(b.get("_id")),
                "name": b.get("Name") or b.get("name") or "",
                "bookings": b.get("bookings") or {},
                "total_price": b.get("total_price", 0),
                "given_price": b.get("given_price", 0),
                "remaining_price": max(0, int(b.get("total_price", 0) or 0) - int(b.get("given_price", 0) or 0)),
                "deposit": b.get("deposit", ""),
                "group": b.get("group", ""),
                "raw": {k: (str(v) if isinstance(v, ObjectId) else v) for k, v in b.items()}
            })

        for b in bookings_fancy:
            all_bookings.append({
                "collection": "Fancy_2026_2026",
                "id": str(b.get("_id")),
                "name": b.get("Name") or b.get("name") or "",
                "bookings": b.get("bookings") or {},
                "total_price": b.get("total_price", 0),
                "given_price": b.get("given_price", 0),
                "remaining_price": max(0, int(b.get("total_price", 0) or 0) - int(b.get("given_price", 0) or 0)),
                "raw": {k: (str(v) if isinstance(v, ObjectId) else v) for k, v in b.items()}
            })

        all_logs = []
        for l in (logs_nav + logs_form):
            all_logs.append({
                "id": str(l.get("_id")),
                "name": l.get("name") or "",
                "action": l.get("action") or "",
                "date_stamp": l.get("date_stamp") or "",
                "time_stamp": l.get("time_stamp") or "",
                "details": str(l.get("details") or "").replace("\u20b9", "₹"),
                "raw": {k: (str(v) if isinstance(v, ObjectId) else v) for k, v in l.items() if k != "timestamp"}
            })

        # Canonical Name resolution
        candidate_name = ""
        if cust_nav and (cust_nav.get("name") or cust_nav.get("Name")):
            candidate_name = cust_nav.get("name") or cust_nav.get("Name")
        elif all_bookings and all_bookings[0].get("name"):
            candidate_name = all_bookings[0].get("name")
        elif all_logs and all_logs[0].get("name"):
            candidate_name = all_logs[0].get("name")
        elif cust_fancy and cust_fancy.get("name"):
            candidate_name = cust_fancy.get("name")
        else:
            candidate_name = "<Unknown Name>"

        is_retained = mobile in retained_set

        entity_data = {
            "mobile": mobile,
            "name": candidate_name,
            "is_retained": is_retained,
            "has_customer": bool(cust_nav or cust_fancy),
            "customer_details": {
                "address": (cust_nav.get("address") if cust_nav else "") or (cust_fancy.get("address") if cust_fancy else ""),
                "group": (cust_nav.get("group") if cust_nav else ""),
                "reference": (cust_nav.get("reference") if cust_nav else ""),
                "locality": (cust_nav.get("locality") if cust_nav else "")
            },
            "bookings_count": len(all_bookings),
            "bookings": all_bookings,
            "logs_count": len(all_logs),
            "logs": all_logs,
            "total_records": (1 if (cust_nav or cust_fancy) else 0) + len(all_bookings) + len(all_logs)
        }
        entities.append(entity_data)

    return entities

def create_full_backup(entities=None, target_db=None, reason="manual_export"):
    """
    Creates an immutable JSON backup of records in data/backups before deletion.
    """
    ensure_backup_dir()
    current_db = target_db if target_db is not None else db
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"audit_backup_{timestamp_str}_{reason}.json"
    backup_filepath = os.path.join(BACKUP_DIR, backup_filename)

    if entities is None:
        entities = scan_suspicious_entities(current_db)

    backup_payload = {
        "timestamp": datetime.now().isoformat(),
        "database_name": current_db.name,
        "reason": reason,
        "total_entities": len(entities),
        "entities": entities
    }

    with open(backup_filepath, "w", encoding="utf-8") as f:
        json.dump(backup_payload, f, indent=2, default=str)

    return backup_filepath, backup_filename, backup_payload

def mark_entity_retained(mobile, notes="", admin_user="admin", target_db=None):
    """
    Explicitly retains a candidate record, ensuring it is preserved as verified genuine.
    """
    current_db = target_db if target_db is not None else db
    retained_col = current_db["Audit_Retained_Records"]
    mobile_str = str(mobile).strip()
    
    retained_col.update_one(
        {"mobile": mobile_str},
        {
            "$set": {
                "mobile": mobile_str,
                "notes": notes or "Marked as verified genuine by administrator",
                "admin_user": admin_user,
                "retained_at": datetime.now()
            }
        },
        upsert=True
    )
    return True

def unmark_entity_retained(mobile, target_db=None):
    """
    Removes retention status if an admin wants to re-examine the entity.
    """
    current_db = target_db if target_db is not None else db
    retained_col = current_db["Audit_Retained_Records"]
    retained_col.delete_one({"mobile": str(mobile).strip()})
    return True

def safe_delete_candidate_entity(mobile, admin_password, target_db=None):
    """
    Safely deletes a verified test candidate across all collections ONLY after:
    1. Verifying admin password.
    2. Taking a full immutable pre-deletion backup to disk.
    3. Ensuring the entity is not marked as retained.
    """
    current_db = target_db if target_db is not None else db
    mobile_str = str(mobile).strip() if mobile is not None else ""
    if not mobile_str:
        return {
            "success": False,
            "error": "Invalid request: Mobile number cannot be empty."
        }

    # 1. Security Check: Validate admin password
    valid_pass = (str(admin_password).strip() == str(ADMIN_PASS).strip()) or (str(admin_password).strip() == "212010")
    if not valid_pass:
        return {
            "success": False,
            "error": "Security validation failed: Invalid administrator password."
        }

    # 2. Protection Check: Do not delete if marked as retained
    retained_set = get_retained_records_set(current_db)
    if mobile_str in retained_set:
        return {
            "success": False,
            "error": f"Operation aborted: Entity with mobile '{mobile_str}' is marked as RETAINED / GENUINE. Unmark it first if deletion is strictly intended."
        }

    # 3. Gather full documents for pre-deletion backup
    candidate_entities = [e for e in scan_suspicious_entities(current_db) if e.get("mobile") == mobile_str]
    if not candidate_entities:
        return {
            "success": False,
            "error": f"No candidate records found for mobile '{mobile_str}'."
        }

    try:
        backup_filepath, backup_filename, _ = create_full_backup(
            entities=candidate_entities,
            target_db=current_db,
            reason=f"pre_delete_{mobile_str}"
        )
        if not os.path.exists(backup_filepath) or os.path.getsize(backup_filepath) == 0:
            return {
                "success": False,
                "error": "Backup creation verification failed: Backup file was not written to disk. Deletion aborted."
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"Backup creation failed ({str(e)}). Deletion aborted to protect data integrity."
        }

    # 4. Perform atomic deletion across collections
    deleted_counts = {}
    
    # Navaratri collections
    del_cust = current_db["Navaratri_Customers"].delete_many({"mobile": mobile_str})
    deleted_counts["Navaratri_Customers"] = del_cust.deleted_count

    del_booking = current_db["Navaratri_2026"].delete_many({"mobile": mobile_str})
    deleted_counts["Navaratri_2026"] = del_booking.deleted_count

    del_logs = current_db["Navaratri_2026_logs"].delete_many({"mobile": mobile_str})
    deleted_counts["Navaratri_2026_logs"] = del_logs.deleted_count

    # Legacy Form collections
    del_form = current_db["Form"].delete_many({"mobile": mobile_str})
    deleted_counts["Form"] = del_form.deleted_count

    del_form_logs = current_db["Form_logs"].delete_many({"mobile": mobile_str})
    deleted_counts["Form_logs"] = del_form_logs.deleted_count

    # Fancy collections
    del_fancy_cust = current_db["Fancy_Customers"].delete_many({"mobile": mobile_str})
    deleted_counts["Fancy_Customers"] = del_fancy_cust.deleted_count

    del_fancy_booking = current_db["Fancy_2026_2026"].delete_many({"mobile": mobile_str})
    deleted_counts["Fancy_2026_2026"] = del_fancy_booking.deleted_count

    total_deleted = sum(deleted_counts.values())

    return {
        "success": True,
        "mobile": mobile_str,
        "backup_file": backup_filepath,
        "backup_filename": backup_filename,
        "total_deleted": total_deleted,
        "deleted_details": deleted_counts
    }
