from datetime import datetime
from flask import session
from bson import ObjectId

from website.general.db import db

navaratri_cycles = db["navaratri_cycles"]


def format_cycle_date(date_value):
    """
    Convert any supported date format to DD-MM-YY
    """

    if date_value is None:
        return "-"

    if isinstance(date_value, datetime):
        return date_value.strftime("%d-%m-%y")

    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%y",
        "%d/%m/%Y",
        "%d-%m-%Y"
    ]

    for fmt in formats:
        try:
            return datetime.strptime(
                str(date_value),
                fmt
            ).strftime("%d-%m-%y")
        except:
            continue

    return str(date_value)


def get_active_cycle():
    """
    Returns active cycle
    """

    return navaratri_cycles.find_one(
        {"status": "active"}
    )


def get_cycle_by_id(cycle_id):
    """
    Returns cycle by ObjectId
    """
    try:
        return navaratri_cycles.find_one(
            {"_id": ObjectId(cycle_id)}
        )
    except:
        return None


def create_cycle(name, collection_name):
    """
    Creates new cycle
    """

    active_cycle = get_active_cycle()

    if active_cycle:
        raise Exception(
            f"Active cycle already exists: {active_cycle['name']}"
        )

    cycle = {
        "name": name,
        "collection_name": collection_name,
        "start_date": datetime.now().strftime("%d-%m-%y"),
        "end_date": None,
        "status": "active",
        "created_at": datetime.utcnow()
    }

    result = navaratri_cycles.insert_one(cycle)

    return result.inserted_id


def end_cycle(cycle_id=None):
    """
    Ends cycle
    """

    cycle = (
        get_cycle_by_id(cycle_id)
        if cycle_id
        else get_active_cycle()
    )

    if not cycle:
        return False

    navaratri_cycles.update_one(
        {"_id": cycle["_id"]},
        {
            "$set": {
                "status": "closed",
                "end_date": datetime.now().strftime("%d-%m-%y"),
                "closed_at": datetime.utcnow()
            }
        }
    )

    return True


def get_all_cycles():
    """
    Returns all cycles
    """

    return list(
        navaratri_cycles.find().sort(
            "created_at",
            -1
        )
    )


def set_selected_cycle(cycle_id):
    """
    Stores selected cycle
    """
    if cycle_id == "default" or not cycle_id:
        session["navaratri_cycle_id"] = "default"
    else:
        session["navaratri_cycle_id"] = str(cycle_id)


def get_selected_cycle():
    """
    Returns selected cycle
    """
    cycle_id = session.get(
        "navaratri_cycle_id"
    )

    if cycle_id == "default":
        return {
            "name": "Navaratri Original Season",
            "collection_name": "Form",
            "status": "active",
            "edit_override": False
        }

    if cycle_id:
        cycle = get_cycle_by_id(
            cycle_id
        )
        if cycle:
            return cycle

    # Fallback to active cycle
    active = get_active_cycle()
    if active:
        return active

    # If no cycles exist in DB at all, return default pointing to original "Form" collection
    return {
        "name": "Navaratri Original Season",
        "collection_name": "Form",
        "status": "active",
        "edit_override": False
    }


def get_selected_cycle_id():
    """
    Returns selected cycle id
    """

    cycle = get_selected_cycle()

    if not cycle or "_id" not in cycle:
        return None

    return str(cycle["_id"])


def get_active_collection():
    """
    Returns Mongo collection
    for active cycle
    """

    cycle = get_active_cycle()

    if not cycle:
        raise Exception(
            "No active cycle found"
        )

    return db[
        cycle["collection_name"]
    ]


def get_selected_collection():
    """
    Returns Mongo collection
    for selected cycle
    """

    cycle = get_selected_cycle()

    if not cycle:
        raise Exception(
            "No cycle selected"
        )

    return db[
        cycle["collection_name"]
    ]


def is_selected_cycle_locked():
    cycle = get_selected_cycle()

    if not cycle:
        return True

    if cycle.get("status") == "active":
        return False

    if cycle.get("edit_override", False):
        return False

    return True