# fservices.py

from collections import Counter
from .fmodels import *

def get_fancy_dashboard_data():
    bookings = get_all_fancy_bookings()

    total_bookings = len(bookings)
    total_revenue = sum(b.get("price", 0) for b in bookings)

    returned_count = sum(1 for b in bookings if b.get("returned"))
    taken_count = sum(1 for b in bookings if b.get("taken"))
    not_returned = sum(
        1 for b in bookings if b.get("taken") and not b.get("returned")
    )

    costume_counter = Counter()
    school_counter = Counter()

    for b in bookings:
        if b.get("costume"):
            costume_counter[b["costume"]] += 1
        if b.get("school"):
            school_counter[b["school"]] += 1

    return {
        "total_bookings": total_bookings,
        "total_revenue": total_revenue,
        "returned_count": returned_count,
        "taken_count": taken_count,
        "not_returned": not_returned,
        "top_costumes": sorted(costume_counter.items(), key=lambda x: x[1], reverse=True),
        "top_school": sorted(school_counter.items(), key=lambda x: x[1], reverse=True),
    }   

def format_date_safe(date):
    from datetime import datetime

    if isinstance(date, datetime):
        return date.strftime("%d-%m-%Y")

    if isinstance(date, str):
        try:
            return datetime.strptime(date, "%Y-%m-%d").strftime("%d-%m-%Y")
        except:
            return date

    return date

def get_fancy_profile_data(mobile, fancy_collection, fancy_2024_2025):
    from datetime import datetime

    all_bookings = []

    for col, season in [
        (fancy_2024_2025, "2024-2025"),
        (fancy_collection, "2025-2026"),
    ]:
        bookings = list(col.find({"mobile": mobile}))

        for b in bookings:
            b["season"] = season
            b["start_date"] = format_date_safe(b.get("start_date"))
            b["end_date"] = format_date_safe(b.get("end_date"))

        all_bookings.extend(bookings)

    all_bookings.sort(
        key=lambda x: x.get("timestamp", datetime.min),
        reverse=True
    )

    total_spent = sum(b.get("price", 0) for b in all_bookings)

    return all_bookings, total_spent

def get_fancy_profile_data(mobile, fancy_collection, fancy_2024_2025):
    from datetime import datetime

    all_bookings = []

    for col, season in [
        (fancy_2024_2025, "2024-2025"),
        (fancy_collection, "2025-2026"),
    ]:
        bookings = list(col.find({"mobile": mobile}))

        for b in bookings:
            b["season"] = season
            b["start_date"] = format_date_safe(b.get("start_date"))
            b["end_date"] = format_date_safe(b.get("end_date"))

        all_bookings.extend(bookings)

    all_bookings.sort(
        key=lambda x: x.get("timestamp", datetime.min),
        reverse=True
    )

    total_spent = sum(b.get("price", 0) for b in all_bookings)

    return all_bookings, total_spent

def get_calendar_data(all_bookings, selected_date):
    from datetime import datetime, timedelta

    booked_dates = set()
    today = datetime.now().date()

    for b in all_bookings:
        try:
            sd = datetime.strptime(b['start_date'], '%d-%m-%Y').date()
            ed = datetime.strptime(b['end_date'], '%d-%m-%Y').date()

            cur = sd
            while cur <= ed:
                booked_dates.add(cur.strftime('%Y-%m-%d'))
                cur += timedelta(days=1)
        except:
            pass

    day_bookings = []
    if selected_date:
        sel = datetime.strptime(selected_date, '%Y-%m-%d').date()

        for b in all_bookings:
            try:
                sd = datetime.strptime(b['start_date'], '%d-%m-%Y').date()
                ed = datetime.strptime(b['end_date'], '%d-%m-%Y').date()

                if sd <= sel <= ed:
                    day_bookings.append(b)
            except:
                pass

    return booked_dates, day_bookings, today