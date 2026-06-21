import os
import sys
from datetime import datetime
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from website.general.db import db

def run_migration():
    ncustomers = db["Navaratri_Customers"]
    navaratri_cycles = db["navaratri_cycles"]
    
    print("Fetching cycles...")
    cycles = list(navaratri_cycles.find())
    print(f"Found {len(cycles)} cycles.")
    
    migrated_count = 0
    
    for cycle in cycles:
        coll_name = cycle.get("collection_name")
        if not coll_name:
            continue
        print(f"\nMigrating from collection: {coll_name}")
        coll = db[coll_name]
        
        try:
            bookings = list(coll.find())
            print(f"Found {len(bookings)} bookings in {coll_name}")
            
            for b in bookings:
                m = b.get("mobile")
                if m:
                    # Update customer record
                    ncustomers.update_one(
                        {"mobile": m},
                        {
                            "$set": {
                                "name": b.get("Name") or b.get("name"),
                                "mobile": m,
                                "address": b.get("address", ""),
                                "group": b.get("group", ""),
                                "reference": b.get("reference", ""),
                                "updated_at": datetime.now()
                            }
                        },
                        upsert=True
                    )
                    migrated_count += 1
                    print(f"Updated customer {m} (Name: {b.get('Name')}, Group: {b.get('group')}, Reference: {b.get('reference')})")
        except Exception as e:
            print(f"Error migrating from {coll_name}: {e}")
            
    print(f"\nMigration completed. Processed {migrated_count} records.")

if __name__ == "__main__":
    run_migration()
