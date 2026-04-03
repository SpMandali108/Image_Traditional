# fmodels.py

from ..general.db import fancy_collection, fcustomers, finventory
from bson.objectid import ObjectId


# ------------------ BOOKINGS ------------------

def get_all_fancy_bookings():
    return list(fancy_collection.find())


def insert_fancy_booking(data):
    return fancy_collection.insert_one(data)


# ------------------ CUSTOMERS ------------------

def get_fancy_customer(mobile):
    return fcustomers.find_one({"mobile": mobile})


def upsert_fancy_customer(mobile, data):
    return fcustomers.update_one(
        {"mobile": mobile},
        {
            "$set": data,
            "$setOnInsert": {"created_at": data.get("created_at")}
        },
        upsert=True
    )


# ------------------ INVENTORY ------------------

def get_inventory():
    return list(finventory.find())


def insert_inventory(data):
    return finventory.insert_one(data)


def update_inventory(id, data):
    return finventory.update_one(
        {"_id": ObjectId(id)},
        {"$set": data}
    )


def delete_inventory(id):
    return finventory.delete_one({"_id": ObjectId(id)})