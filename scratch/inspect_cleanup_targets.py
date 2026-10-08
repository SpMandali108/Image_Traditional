import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from collections import Counter
from website.general.db import client, MONGO_DB_PRODUCTION

prod_db = client[MONGO_DB_PRODUCTION]
nav_2026 = prod_db["Navaratri_2026"]
nav_cust = prod_db["Navaratri_Customers"]
nav_logs = prod_db["Navaratri_2026_logs"]
form_col = prod_db["Form"]
form_logs = prod_db["Form_logs"]

print("======================================================================")
print("1. CURRENT ACTIVE CYCLE: Navaratri 2026 (Navaratri_2026)")
print("======================================================================")

# Current cycle bookings
cc_bookings = list(nav_2026.find())
cc_mobiles = set(str(b.get("mobile") or "").strip() for b in cc_bookings if b.get("mobile"))
print(f"Total bookings in Navaratri_2026: {len(cc_bookings)}")
print(f"Unique mobile numbers officially booked in Navaratri_2026: {len(cc_mobiles)}")

# Current cycle customers in Navaratri_Customers
cc_customers = list(nav_cust.find({"mobile": {"$in": list(cc_mobiles)}}))
print(f"Customers in Navaratri_Customers officially registered in Navaratri_2026: {len(cc_customers)}")

# Check if any customer in Navaratri_Customers has multiple bookings in Navaratri_2026
mobile_booking_counts = Counter(str(b.get("mobile") or "").strip() for b in cc_bookings)
multi_booking = {m: c for m, c in mobile_booking_counts.items() if c > 1}
print(f"Customers with multiple bookings in Navaratri_2026: {len(multi_booking)}")

print("\n======================================================================")
print("2. CUSTOMERS NOT IN CURRENT ACTIVE CYCLE")
print("======================================================================")
non_cc_customers = list(nav_cust.find({"mobile": {"$nin": list(cc_mobiles)}}))
print(f"Total customers in Navaratri_Customers NOT registered in Navaratri_2026: {len(non_cc_customers)}")

# Break down who these non_cc_customers are:
form_mobiles = set(str(b.get("mobile") or "").strip() for b in form_col.find() if b.get("mobile"))
in_form_only = [c for c in non_cc_customers if str(c.get("mobile") or "").strip() in form_mobiles]
not_in_any_booking = [c for c in non_cc_customers if str(c.get("mobile") or "").strip() not in form_mobiles]

print(f"  -> Belong to Form (2025 closed cycle): {len(in_form_only)}")
print(f"  -> NOT in Form and NOT in 2026 (No bookings anywhere): {len(not_in_any_booking)}")

print("\nDetails of customers with NO bookings anywhere:")
for c in not_in_any_booking:
    m = c.get("mobile")
    name = c.get("name") or c.get("Name")
    print(f"    Mobile: {m} | Name: {name} | Address: {c.get('address')} | Group: {c.get('group')}")

print("\n======================================================================")
print("3. LOGS IN NAVARATRI 2026 LOGS (Navaratri_2026_logs)")
print("======================================================================")
all_logs = list(nav_logs.find())
print(f"Total logs in Navaratri_2026_logs: {len(all_logs)}")

cc_logs = [l for l in all_logs if str(l.get("mobile") or "").strip() in cc_mobiles]
non_cc_logs = [l for l in all_logs if str(l.get("mobile") or "").strip() not in cc_mobiles]

print(f"Logs matching officially registered 2026 customers: {len(cc_logs)}")
print(f"Logs NOT matching 2026 customers: {len(non_cc_logs)}")

system_logs = [l for l in non_cc_logs if not str(l.get("mobile") or "").strip()]
test_or_other_logs = [l for l in non_cc_logs if str(l.get("mobile") or "").strip()]

print(f"  -> Admin system logs (no customer mobile, e.g. product_sold, product_restored): {len(system_logs)}")
print(f"  -> Logs referencing customer mobiles NOT in 2026: {len(test_or_other_logs)}")

mobile_to_logs = Counter(str(l.get("mobile") or "").strip() for l in test_or_other_logs)
print("\nBreakdown of logs referencing mobiles NOT in 2026:")
for m, count in mobile_to_logs.items():
    sample = [l for l in test_or_other_logs if str(l.get("mobile") or "").strip() == m][0]
    name = sample.get("name")
    action = sample.get("action")
    print(f"    Mobile: {m} (Logs: {count}) | Name: {name} | Sample Action: {action}")

print("\n======================================================================")
print("4. LOGS OF CURRENT-CYCLE CUSTOMERS: ARE THERE TEST LOGS AMONG THEM?")
print("======================================================================")
# Check if any log belonging to a current-cycle customer has test actions or test artifacts
test_actions_in_cc = []
for l in cc_logs:
    action = str(l.get("action") or "").lower()
    details = str(l.get("details") or "").lower()
    name = str(l.get("name") or "").lower()
    if "test" in action or "test" in details or "test" in name or "dummy" in details or "fake" in details:
        test_actions_in_cc.append(l)

print(f"Logs of current-cycle customers containing test indicators: {len(test_actions_in_cc)}")
for l in test_actions_in_cc:
    print(f"    Mobile: {l.get('mobile')} | Name: {l.get('name')} | Action: {l.get('action')} | Details: {l.get('details')}")

print("\n======================================================================")
print("5. FANCY DRESS STATUS CHECK")
print("======================================================================")
fancy_2026 = prod_db["Fancy_2026_2026"]
fancy_cust = prod_db["Fancy_Customers"]
print(f"Fancy_2026_2026 bookings: {fancy_2026.count_documents({})}")
print(f"Fancy_Customers: {fancy_cust.count_documents({})}")
