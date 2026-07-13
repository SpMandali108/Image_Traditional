import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

mongo_uri = os.environ.get("client")
if not mongo_uri:
    print("Error: client environment variable not found in .env")
    exit(1)

try:
    print(f"Connecting to MongoDB...")
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    # Trigger connection
    client.admin.command('ping')
    print("Ping success! Connected to MongoDB Atlas.")
    
    db = client.get_database("Image_Traditional")
    print(f"Using database: {db.name}")
    
    collections = db.list_collection_names()
    print("Collections found:", collections)
    
    for name in collections:
        count = db[name].count_documents({})
        print(f"  Collection '{name}': {count} documents")
        
except Exception as e:
    print(f"Connection failed: {e}")
