import sys
import os

# Adjust path to import from website
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from website.general.db import db

def main():
    print("Database connected. Collections:")
    print(db.list_collection_names())
    
    # Check cycles
    cycles = list(db["navaratri_cycles"].find())
    print("\nNavaratri Cycles:")
    for c in cycles:
        print(c)
        
    # Check Form
    form_count = db["Form"].count_documents({})
    print(f"\nForm documents count: {form_count}")
    if form_count > 0:
        print("Sample Form document:")
        print(db["Form"].find_one())

if __name__ == "__main__":
    main()
