import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from website.general.db import db
from website.general.utils import format_log_timestamp

def migrate():
    log_cols = [c for c in db.list_collection_names() if 'logs' in c.lower()]
    print('Found log collections:', log_cols)

    for c in log_cols:
        col = db[c]
        count = 0
        for doc in col.find():
            ts = doc.get('timestamp')
            old_d = doc.get('date_stamp', '')
            old_t = doc.get('time_stamp', '')
            d_str, t_str, _ = format_log_timestamp(ts, old_d, old_t)

            if d_str != old_d or t_str != old_t:
                col.update_one(
                    {'_id': doc['_id']},
                    {'$set': {'date_stamp': d_str, 'time_stamp': t_str}}
                )
                count += 1
                print(f"  Updated log: old=({old_d}, {old_t}) -> new=({d_str}, {t_str})")
        print(f"Collection {c}: Updated {count} documents")

if __name__ == "__main__":
    migrate()
