import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
client = MongoClient(os.environ.get("client"), tls=True, tlsAllowInvalidCertificates=True)
db = client["Image_Traditional"]

mobiles = ['1234567890', '9799988889', '9876543210', '9888800001', '9988776655', '9999900001', '9999900002', '9999988887', '9999988888']

for m in mobiles:
    nc = db.Navaratri_Customers.find_one({"mobile": m})
    fc = db.Fancy_Customers.find_one({"mobile": m})
    n2026 = db.Navaratri_2026.find_one({"mobile": m})
    form = db.Form.find_one({"mobile": m})
    nlogs = db.Navaratri_2026_logs.count_documents({"mobile": m})
    flogs = db.Form_logs.count_documents({"mobile": m})
    
    name = (nc.get('name') if nc else '') or (n2026.get('Name') if n2026 else '') or (form.get('Name') if form else '') or (fc.get('name') if fc else '')
    print(f"Mobile {m} | Name: '{name}'")
    print(f"  Navaratri_Customers: {bool(nc)} | Fancy_Customers: {bool(fc)}")
    print(f"  Navaratri_2026 booking: {bool(n2026)} (bookings: {n2026.get('bookings') if n2026 else None})")
    print(f"  Form booking: {bool(form)} (bookings: {form.get('bookings') if form else None})")
    print(f"  Navaratri_2026 logs: {nlogs} | Form logs: {flogs}")
