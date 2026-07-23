import json
from typing import Counter
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify,flash
from datetime import datetime, timedelta
from bson.objectid import ObjectId
import os

from .fservices import *
from .fmodels import *
from ..general.db import *

from website.fancy.fcycle import fancy_cycles

from website.fancy.fcycle import (
    get_active_cycle,
    get_selected_cycle_id,
    get_all_cycles,
    get_cycle_by_id,
    get_selected_cycle,
    is_selected_cycle_locked,
    set_selected_cycle,
    create_cycle,
    end_cycle,
    reactivate_cycle,
    get_active_collection,
    get_selected_collection
)

fancy = Blueprint('fancy', __name__)

# ------------------ MAIN ------------------


@fancy.route('/fancy', methods=['GET', 'POST'])
def fbook():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        data = request.get_json(silent=True)

        if is_selected_cycle_locked():
            return jsonify({
        "error": "Cycle is locked"
    }), 403

        if not data:
            return jsonify({"error": "Invalid JSON"}), 400

        # Normalize keys
        data = {k.lower(): v for k, v in data.items()}

        mobile = str(data.get('mobile', '')).strip()
        if not mobile or len(mobile) != 10:
            return jsonify({"error": "Invalid mobile"}), 400

        collection = get_selected_collection()
        school = data.get('school', '').strip().title()
        costume = data.get('costume', '').strip().title()

        booking_data = {
    'name': data.get('name', '').strip().title(),
    'mobile': mobile,
    'address': data.get('address', '').strip().title(),
    'school': data.get('school', '').strip().title(),
    'start_date': data.get('start_date', ''),
    'end_date': data.get('end_date', ''),
    'price': float(data.get('price', 0)),
    'costume': data.get('costume', '').strip().title(),
    'details': data.get('details', '').strip(),
    'timestamp': datetime.utcnow()
}

        customer_data = {
            'name': booking_data['name'],
            'mobile': mobile,
            'address': booking_data['address'],
            'school': booking_data['school'],
            'updated_at': datetime.utcnow()
        }

        fcustomers.update_one(
            {'mobile': mobile},
            {
                '$set': customer_data,
                '$setOnInsert': {'created_at': datetime.utcnow()}
            },
            upsert=True
        )

        # Add school to School_Master if new
        if school:
            db.School_Master.update_one(
                {"name": school},
                {"$setOnInsert": {"name": school}},
                upsert=True
            )

        # Add costume category to Costume_Category_Master if new
        if costume:
            db.Costume_Category_Master.update_one(
                {"name": costume},
                {"$setOnInsert": {"name": costume}},
                upsert=True
            )

        collection.insert_one(booking_data)

        return jsonify({'status': 'success'}), 200

    # ✅ GET request — data is NOT used here
    schools = sorted(
    [x["name"] for x in db.School_Master.find({}, {"name": 1})]
)

    costumes = sorted(
        [x["name"] for x in db.Costume_Category_Master.find({}, {"name": 1})]
    )

    return render_template(
        "fancy/fancy.html",
        schools=schools,
        costumes=costumes
    )

@fancy.route("/fancy_listing",methods=['GET','POST'])
def flisting():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))
    
    collection = get_selected_collection()
    fbookings = list(collection.find())

    return render_template("fancy/fancy_listing.html",fbookings = fbookings)





@fancy.route('/delete_booking/<id>', methods=['POST'])
def delete_booking(id):

    if not session.get('logged_in'):
        return jsonify(success=False)

    collection = get_selected_collection()

    collection.delete_one({
        '_id': ObjectId(id)
    })

    return jsonify(success=True)

@fancy.route('/update_booking', methods=['POST'])
def update_booking():

    try:
        data = request.json

        current_app.logger.info(f"DATA = {data}")

        collection = get_selected_collection()

        collection.update_one(
    {'_id': ObjectId(data['id'])},
    {
        '$set': {
            'name': data['name'],
            'mobile': data['mobile'],
            'address': data['address'],
            'school': data['school'],
            'costume': data['costume'],
            'details': data['details'],
            'price': int(float(data['price'])),
            'start_date': data['start_date'],
            'end_date': data['end_date']
        }
    }
)

        return jsonify(success=True)

    except Exception as e:
        current_app.logger.error(f"ERROR: {e}")
        return jsonify(success=False, message=str(e))

@fancy.route("/get_customer")
def get_customer():
    mobile = request.args.get("mobile")

    customer = fcustomers.find_one(
        {"mobile": mobile},     # lowercase mobile
        {"_id": 0}
    )

    if customer:
        return jsonify({"exists": True, "data": customer})

    return jsonify({"exists": False})

@fancy.route('/fancy_calendar', methods=['GET', 'POST'])
def fancy_calendar():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    today = datetime.now().date()
    selected_date = request.args.get('date')

    # ---------- HANDLE TAKEN / RETURNED ----------
    if request.method == 'POST':

        actions_raw = request.form.get('actions')

        if not actions_raw:
            return jsonify(success=False)

        actions = json.loads(actions_raw)

        for act in actions:

            bid = act['bookingId']
            field = act['field']
            cycle_id = act.get('cycleId')

            if not cycle_id:
                continue

            cycle = get_cycle_by_id(cycle_id)

            if not cycle:
                continue

            collection = db[
                cycle['collection_name']
            ]

            collection.update_one(
                {'_id': ObjectId(bid)},
                {'$set': {field: True}}
            )

        return jsonify(success=True)

    # ---------- FETCH ALL BOOKINGS ----------
    all_bookings = []

    for cycle in get_all_cycles():

        collection = db[
            cycle['collection_name']
        ]

        for b in collection.find():

            b['season'] = cycle['name']
            b['cycle_id'] = str(cycle['_id'])

            # Normalize dates
            for k in ['start_date', 'end_date']:

                v = b.get(k)

                if isinstance(v, datetime):

                    b[k] = v.strftime('%d-%m-%Y')

                elif isinstance(v, str):

                    formats = [
                        '%Y-%m-%d',
                        '%d-%m-%Y',
                        '%d-%m-%y'
                    ]

                    for fmt in formats:
                        try:
                            b[k] = datetime.strptime(
                                v,
                                fmt
                            ).strftime('%d-%m-%Y')
                            break
                        except:
                            pass

            all_bookings.append(b)

    # ---------- CALENDAR HIGHLIGHT DATES ----------
    booked_dates = set()

    for b in all_bookings:

        try:

            sd = datetime.strptime(
                b['start_date'],
                '%d-%m-%Y'
            ).date()

            ed = datetime.strptime(
                b['end_date'],
                '%d-%m-%Y'
            ).date()

            cur = sd

            while cur <= ed:

                booked_dates.add(
                    cur.strftime('%Y-%m-%d')
                )

                cur += timedelta(days=1)

        except:
            pass

    # ---------- BOOKINGS FOR SELECTED DATE ----------
    day_bookings = []

    if selected_date:

        sel = datetime.strptime(
            selected_date,
            '%Y-%m-%d'
        ).date()

        for b in all_bookings:

            try:

                sd = datetime.strptime(
                    b['start_date'],
                    '%d-%m-%Y'
                ).date()

                ed = datetime.strptime(
                    b['end_date'],
                    '%d-%m-%Y'
                ).date()

                if sd <= sel <= ed:
                    day_bookings.append(b)

            except:
                pass

    # ---------- UPCOMING & NOT RETURNED ----------
    upcoming = []
    not_returned = []

    for b in all_bookings:

        try:

            ed = datetime.strptime(
                b['end_date'],
                '%d-%m-%Y'
            ).date()

            if ed >= today:

                upcoming.append(b)

            elif ed < today and not b.get('returned'):

                not_returned.append(b)

        except:
            pass

    return render_template(
        'fancy/fancy_calendar.html',
        booked_dates=list(booked_dates),
        day_bookings=day_bookings,
        upcoming=upcoming,
        not_returned=not_returned,
        selected_date=selected_date,
        today=today.strftime('%Y-%m-%d')
    )

@fancy.route('/fancy_dashboard')
def fancy_dashboard():

    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    # -----------------------------
    # CYCLE SELECTOR HANDLE
    # -----------------------------
    cycle_id = request.args.get('cycle_id')
    if cycle_id:
        set_selected_cycle(cycle_id)

    # -----------------------------
    # SELECTED CYCLE DATA
    # -----------------------------
    collection = get_selected_collection()

    current_bookings = list(
        collection.find()
    )

    total_bookings_count = len(
        current_bookings
    )

    total_revenue = sum(
        b.get('price', 0)
        for b in current_bookings
    )

    returned_count = sum(
        1
        for b in current_bookings
        if b.get('returned')
    )

    taken_count = sum(
        1
        for b in current_bookings
        if b.get('taken')
    )

    not_returned = sum(
        1
        for b in current_bookings
        if b.get('taken')
        and not b.get('returned')
    )

    awaiting_pickup = total_bookings_count - returned_count - not_returned
    avg_revenue = total_revenue / total_bookings_count if total_bookings_count > 0 else 0

    # -----------------------------
    # MOST RENTED COSTUMES & SCHOOLS
    # -----------------------------
    costume_counter = Counter()
    school_counter = Counter()

    for b in current_bookings:
        costume = b.get('details')
        school = b.get('school')
        if costume:
            costume_counter[costume.strip().title()] += 1
        if school:
            school_counter[school.strip().title()] += 1

    top_costumes = sorted(
        costume_counter.items(),
        key=lambda x: x[1],
        reverse=True
    )[:20]

    top_school = sorted(
        school_counter.items(),
        key=lambda x: x[1],
        reverse=True
    )[:20]

    # -----------------------------
    # INVENTORY CATEGORY MAPPING & SALES LEADERS
    # -----------------------------
    inventory_products = list(finventory.find())
    
    # 1. Map costume names to categories
    costume_to_category = {}
    category_stock = {}
    total_stock = 0

    for p in inventory_products:
        name = p.get("name", "").strip().title()
        cat = p.get("category", "General").strip().title()
        if name:
            costume_to_category[name] = cat
        
        # Calculate stock per category
        sizes = p.get("sizes", {})
        qty = 0
        if isinstance(sizes, dict):
            qty = sum(int(q) for q in sizes.values() if str(q).isdigit() or isinstance(q, (int, float)))
        category_stock[cat] = category_stock.get(cat, 0) + qty
        total_stock += qty

    # 2. Group bookings and revenue by category (costume field holds the category name in bookings schema)
    category_bookings = {}
    category_revenue = {}
    for b in current_bookings:
        cat = b.get("costume", "General").strip().title()
        price = b.get("price", 0)
        
        category_bookings[cat] = category_bookings.get(cat, 0) + 1
        category_revenue[cat] = category_revenue.get(cat, 0) + price

    # 3. Calculate Best Category and Best Product highlights (excluding catch-alls like Other & General)
    category_bookings_sorted = sorted(category_bookings.items(), key=lambda x: x[1], reverse=True)
    category_revenue_sorted = sorted(category_revenue.items(), key=lambda x: x[1], reverse=True)

    filtered_bookings = [item for item in category_bookings_sorted if item[0] not in ["Other", "General"]]
    filtered_revenue = [item for item in category_revenue_sorted if item[0] not in ["Other", "General"]]
    
    best_category_by_bookings = filtered_bookings[0][0] if filtered_bookings else (category_bookings_sorted[0][0] if category_bookings_sorted else "None")
    best_category_bookings_count = filtered_bookings[0][1] if filtered_bookings else (category_bookings_sorted[0][1] if category_bookings_sorted else 0)
    
    best_category_by_revenue = filtered_revenue[0][0] if filtered_revenue else (category_revenue_sorted[0][0] if category_revenue_sorted else "None")
    best_category_revenue_val = filtered_revenue[0][1] if filtered_revenue else (category_revenue_sorted[0][1] if category_revenue_sorted else 0)

    # Best Products
    best_product_by_bookings = top_costumes[0][0] if top_costumes else "None"
    best_product_bookings_count = top_costumes[0][1] if top_costumes else 0

    # 4. Calculate Average Rental Duration (days) per Category
    def safe_parse_date(d):
        if not d:
            return None
        if isinstance(d, datetime):
            return d.date()
        if isinstance(d, str):
            for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d-%m-%y"]:
                try:
                    return datetime.strptime(d.strip(), fmt).date()
                except ValueError:
                    continue
        return None

    category_durations = {}
    category_duration_counts = {}
    total_duration_days = 0
    duration_bookings_count = 0

    for b in current_bookings:
        costume = b.get("costume", "").strip().title()
        cat = costume_to_category.get(costume, "Other")
        sd = safe_parse_date(b.get("start_date"))
        ed = safe_parse_date(b.get("end_date"))
        if sd and ed and ed >= sd:
            duration = (ed - sd).days + 1
            category_durations[cat] = category_durations.get(cat, 0) + duration
            category_duration_counts[cat] = category_duration_counts.get(cat, 0) + 1
            total_duration_days += duration
            duration_bookings_count += 1

    avg_durations_by_category = []
    for cat, total_dur in category_durations.items():
        cnt = category_duration_counts[cat]
        avg_dur = round(total_dur / cnt, 1) if cnt > 0 else 0
        avg_durations_by_category.append({
            "category": cat,
            "avg_duration": avg_dur
        })
    avg_durations_by_category.sort(key=lambda x: x["avg_duration"], reverse=True)
    overall_avg_duration = round(total_duration_days / duration_bookings_count, 1) if duration_bookings_count > 0 else 0

    # 5. Day of Week Demand Analysis
    today = datetime.now().date()
    day_of_week_counts = {
        "Monday": 0, "Tuesday": 0, "Wednesday": 0, "Thursday": 0, "Friday": 0, "Saturday": 0, "Sunday": 0
    }
    days_list = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    for b in current_bookings:
        sd = safe_parse_date(b.get("start_date"))
        if sd:
            day_name = days_list[sd.weekday()]
            day_of_week_counts[day_name] += 1
    day_of_week_data = [{"day": d, "count": day_of_week_counts[d]} for d in days_list]

    # 6. Monthly Revenue Performance Analysis
    months_list = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    monthly_revenue = {m: 0 for m in months_list}
    for b in current_bookings:
        sd = safe_parse_date(b.get("start_date"))
        if sd:
            m_name = months_list[sd.month - 1]
            monthly_revenue[m_name] += b.get("price", 0)
    monthly_revenue_data = [{"month": m, "revenue": monthly_revenue[m]} for m in months_list]

    # 7. Active Customers count
    active_customers = len({b.get("mobile") for b in current_bookings if b.get("mobile")})

    # -----------------------------
    # ALL-TIME CUSTOMER DATA & CYCLES
    # -----------------------------
    all_bookings = []
    for cycle in get_all_cycles():
        cycle_collection = db[cycle["collection_name"]]
        cycle_bookings = list(cycle_collection.find())
        for b in cycle_bookings:
            b["season"] = cycle["name"]
        all_bookings.extend(cycle_bookings)

    customer_totals = {}
    for b in all_bookings:
        mobile = b.get('mobile')
        name = b.get('name', 'Unknown')
        price = b.get('price', 0)

        if not mobile:
            continue

        if mobile not in customer_totals:
            customer_totals[mobile] = {
                'name': name,
                'mobile': mobile,
                'total_amount': 0,
                'total_bookings': 0
            }
        customer_totals[mobile]['total_amount'] += price
        customer_totals[mobile]['total_bookings'] += 1

    top_20_customers = sorted(
        customer_totals.values(),
        key=lambda x: x['total_amount'],
        reverse=True
    )[:20]

    # -----------------------------
    # ADVANCED GRAPH METRICS & REVENUE BREAKDOWNS
    # -----------------------------
    school_stats_dict = {}
    costume_stats_dict = {}
    for b in current_bookings:
        school = b.get('school', 'Unknown').strip().title()
        costume = b.get('details', 'Unknown').strip().title()
        price = b.get('price', 0)
        
        if school:
            if school not in school_stats_dict:
                school_stats_dict[school] = {"bookings": 0, "revenue": 0}
            school_stats_dict[school]["bookings"] += 1
            school_stats_dict[school]["revenue"] += price
            
        if costume:
            if costume not in costume_stats_dict:
                costume_stats_dict[costume] = {"bookings": 0, "revenue": 0}
            costume_stats_dict[costume]["bookings"] += 1
            costume_stats_dict[costume]["revenue"] += price

    top_schools_by_revenue = sorted(
        [{"name": k, "bookings": v["bookings"], "revenue": v["revenue"]} for k, v in school_stats_dict.items()],
        key=lambda x: x["revenue"],
        reverse=True
    )[:10]

    top_costumes_by_revenue = sorted(
        [{"name": k, "bookings": v["bookings"], "revenue": v["revenue"]} for k, v in costume_stats_dict.items()],
        key=lambda x: x["revenue"],
        reverse=True
    )[:10]

    # -----------------------------
    # BOOKINGS TIMELINE (DATE NORMALIZATION)
    # -----------------------------
    bookings_by_date_dict = {}
    for b in current_bookings:
        sd = b.get("start_date")
        date_str = None
        if isinstance(sd, datetime):
            date_str = sd.strftime("%d-%m-%Y")
        elif isinstance(sd, str) and sd.strip():
            for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d-%m-%y"]:
                try:
                    date_str = datetime.strptime(sd.strip(), fmt).strftime("%d-%m-%Y")
                    break
                except ValueError:
                    continue
        if date_str:
            bookings_by_date_dict[date_str] = bookings_by_date_dict.get(date_str, 0) + 1

    sorted_date_items = []
    for date_str, count in bookings_by_date_dict.items():
        parsed_date = None
        for fmt in ["%d-%m-%Y", "%Y-%m-%d"]:
            try:
                parsed_date = datetime.strptime(date_str, fmt).date()
                break
            except ValueError:
                continue
        if not parsed_date:
            parsed_date = datetime.min.date()
        sorted_date_items.append((parsed_date, date_str, count))

    sorted_date_items.sort(key=lambda x: x[0])
    bookings_by_date = [{"date": item[1], "count": item[2]} for item in sorted_date_items]

    # -----------------------------
    # INDIAN EVENT FORECAST CALENDAR (PREDICTIVE AI)
    # -----------------------------
    # MM-DD map of Indian holidays and events
    indian_events = [
        {"id": "republic_day", "name": "Republic Day", "month": 1, "day": 26, "category": "Freedom Fighters / Regional", "description": "National parade & school acts. High demand for Gandhi, Nehru, Bhagat Singh, Subhas Chandra Bose, and army/police uniforms."},
        {"id": "independence_day", "name": "Independence Day", "month": 8, "day": 15, "category": "Freedom Fighters / National Heroes", "description": "Independence Day assemblies. Highest demand for historic freedom fighter attire (Rani Laxmibai, Bhagat Singh, Gandhi, Nehru)."},
        {"id": "gandhi_jayanti", "name": "Gandhi Jayanti", "month": 10, "day": 2, "category": "Freedom Fighters / Khadi Attire", "description": "Birth anniversary of Mahatma Gandhi. High demand for dhotis, bald wigs, spectacles, and Nehru caps."},
        {"id": "teachers_day", "name": "Teachers' Day", "month": 9, "day": 5, "category": "Professional / Formal Costumes", "description": "Teachers' Day plays and roleplays. Demand for formal blazers, sarees, doctor, lawyer, and corporate uniforms."},
        {"id": "childrens_day", "name": "Children's Day", "month": 11, "day": 14, "category": "Cartoon Characters / Animals / Nehru", "description": "Children's Day events. High demand for cartoon characters (Doraemon, Mickey Mouse), animal onesies, and Chacha Nehru jackets."},
        {"id": "christmas", "name": "Christmas Conciliates", "month": 12, "day": 25, "category": "Christmas / Angels / Santa Claus", "description": "School Christmas concerts. High demand for Santa Claus outfits, Elf costumes, Angel wings, and Shepherd robes."},
        {"id": "janmashtami", "name": "Krishna Janmashtami (typical Aug/Sep)", "month": 8, "day": 24, "category": "Mythological (Krishna/Radha)", "description": "Krishna tableaus and dahi handi. Peak demand for Bal Krishna crown, flute, peacock feather, and Radha lehengas."},
        {"id": "navaratri", "name": "Navaratri Festival (typical Oct)", "month": 10, "day": 12, "category": "Chaniya Choli / Kediyu", "description": "9 days of Garba. Huge demand for heavily-embroidered Chaniya Cholis, Kediyus, turbans, and oxidized ornaments."}
    ]

    import datetime as dt
    today_dt = datetime.now()

    forecast_calendar = []
    for ev in indian_events:
        year = today_dt.year
        ev_date = dt.datetime(year, ev["month"], ev["day"])
        # If passed in current year, target next year
        if ev_date.date() < today_dt.date():
            ev_date = dt.datetime(year + 1, ev["month"], ev["day"])
            
        countdown = (ev_date.date() - today_dt.date()).days
        
        # Calculate historical bookings spike count and gather details in a ±3 days window around this event
        matching_bookings = []
        event_categories = Counter()
        event_costumes = Counter()
        for b in all_bookings:
            sd = safe_parse_date(b.get("start_date"))
            if sd:
                try:
                    ev_date_by_year = dt.date(sd.year, ev["month"], ev["day"])
                except ValueError:
                    ev_date_by_year = dt.date(sd.year, ev["month"], ev["day"] - 1)
                
                diff = (sd - ev_date_by_year).days
                if -3 <= diff <= 3:
                    costume = b.get("costume", "Unknown").strip().title()
                    cat = costume_to_category.get(costume, "General").strip().title()
                    
                    event_categories[cat] += 1
                    event_costumes[costume] += 1
                    
                    matching_bookings.append({
                        "name": b.get("name", "Unknown"),
                        "mobile": b.get("mobile", ""),
                        "costume": costume,
                        "date": sd.strftime("%d-%m-%Y"),
                        "price": b.get("price", 0),
                        "season": b.get("season", "Historical")
                    })
                    
        matching_bookings.sort(key=lambda x: x["date"], reverse=True)

        # Dynamic recommendations based on actual historical bookings during the ±3 days event window
        top_cats = [c for c, count in event_categories.most_common(2)]
        top_dresses = [f"{d} ({count})" for d, count in event_costumes.most_common(5)]
        
        dynamic_category = ", ".join(top_cats) if top_cats else "General"
        dynamic_desc = f"Top rented costumes: {', '.join(top_dresses)}" if top_dresses else "No historical records for this date window."
        
        # Calculate dynamic stock availability and deficit for the categories associated with this event
        total_available_stock = 0
        for cat in top_cats:
            total_available_stock += category_stock.get(cat, 0)
        
        deficit = max(0, len(matching_bookings) - total_available_stock)
        
        forecast_calendar.append({
            "id": ev["id"],
            "name": ev["name"],
            "date": ev_date.strftime("%d-%m-%Y"),
            "countdown": countdown,
            "category": dynamic_category,
            "description": dynamic_desc,
            "spike_count": len(matching_bookings),
            "bookings": matching_bookings,  # Send all records to show everything!
            "total_stock": total_available_stock,
            "deficit": deficit,
            "status": "Critical Deficit" if deficit > 5 else "Moderate Shortage" if deficit > 0 else "Stock Adequate"
        })
        
    # Sort events by proximity (countdown ascending)
    forecast_calendar.sort(key=lambda x: x["countdown"])

    # -----------------------------
    # STRATEGIC INSIGHTS / BEST PERFORMERS
    # -----------------------------
    highest_rev_costume = top_costumes_by_revenue[0]["name"] if top_costumes_by_revenue else "None"
    highest_rev_val = top_costumes_by_revenue[0]["revenue"] if top_costumes_by_revenue else 0
    highest_rev_school = top_schools_by_revenue[0]["name"] if top_schools_by_revenue else "None"
    highest_rev_school_val = top_schools_by_revenue[0]["revenue"] if top_schools_by_revenue else 0

    strategic_insights = {
        "best_category_by_bookings": f"{best_category_by_bookings} ({best_category_bookings_count} rentals)",
        "best_category_by_revenue": f"{best_category_by_revenue} (₹{best_category_revenue_val})",
        "best_product_by_bookings": f"{best_product_by_bookings} ({best_product_bookings_count} rentals)",
        "best_product_by_revenue": f"{highest_rev_costume} (₹{highest_rev_val})",
        "overall_avg_duration": f"{overall_avg_duration} days",
        "anchor_school": f"{highest_rev_school} (₹{highest_rev_school_val})"
    }

    category_revenue_list = sorted(
        [{"name": k, "revenue": v, "bookings": category_bookings.get(k, 0)} for k, v in category_revenue.items()],
        key=lambda x: x["revenue"],
        reverse=True
    )

    # CURRENT SELECTED CYCLE INFO
    selected_cycle = get_selected_cycle()
    all_cycles = get_all_cycles()

    return render_template(
        'fancy/fancy_dashboard.html',
        total_bookings=total_bookings_count,
        total_revenue=total_revenue,
        returned_count=returned_count,
        taken_count=taken_count,
        not_returned=not_returned,
        awaiting_pickup=awaiting_pickup,
        avg_revenue=avg_revenue,
        top_costumes=top_costumes,
        top_school=top_school,
        top_20_customers=top_20_customers,
        selected_cycle=selected_cycle,
        all_cycles=all_cycles,
        bookings_by_date=bookings_by_date,
        top_schools_by_revenue=top_schools_by_revenue,
        top_costumes_by_revenue=top_costumes_by_revenue,
        total_stock=total_stock,
        avg_durations_by_category=avg_durations_by_category,
        strategic_insights=strategic_insights,
        day_of_week_data=day_of_week_data,
        active_customers=active_customers,
        monthly_revenue_data=monthly_revenue_data,
        forecast_calendar=forecast_calendar,
        category_revenue_list=category_revenue_list
    )

from io import BytesIO
from flask import send_file
from openpyxl import Workbook

@fancy.route('/download_dashboard_excel')
def download_dashboard_excel():

    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    collection = get_selected_collection()

    current_bookings = list(collection.find())

    total_bookings_count = len(current_bookings)

    total_revenue = sum(
        b.get('price', 0)
        for b in current_bookings
    )

    returned_count = sum(
        1
        for b in current_bookings
        if b.get('returned')
    )

    taken_count = sum(
        1
        for b in current_bookings
        if b.get('taken')
    )

    not_returned = sum(
        1
        for b in current_bookings
        if b.get('taken') and not b.get('returned')
    )

    # Top Costumes
    costume_counter = Counter()

    for b in current_bookings:
        costume = b.get('details')

        if costume:
            costume_counter[costume] += 1

    top_costumes = sorted(
        costume_counter.items(),
        key=lambda x: x[1],
        reverse=True
    )

    # Top Schools
    school_counter = Counter()

    for b in current_bookings:
        school = b.get('school')

        if school:
            school_counter[school] += 1

    top_schools = sorted(
        school_counter.items(),
        key=lambda x: x[1],
        reverse=True
    )

    # Top Customers
    all_bookings = []

    for cycle in get_all_cycles():

        cycle_collection = db[
            cycle["collection_name"]
        ]

        all_bookings.extend(
            list(cycle_collection.find())
        )

    customer_totals = {}

    for b in all_bookings:

        mobile = b.get('mobile')

        if not mobile:
            continue

        if mobile not in customer_totals:

            customer_totals[mobile] = {
                'name': b.get('name', ''),
                'mobile': mobile,
                'total_amount': 0,
                'total_bookings': 0
            }

        customer_totals[mobile]['total_amount'] += b.get('price', 0)
        customer_totals['mobile'] if False else None
        customer_totals[mobile]['total_bookings'] += 1

    top_customers = sorted(
        customer_totals.values(),
        key=lambda x: x['total_amount'],
        reverse=True
    )[:50]

    wb = Workbook()

    # Summary Sheet
    ws = wb.active
    ws.title = "Summary"

    ws.append(["Metric", "Value"])
    ws.append(["Total Bookings", total_bookings_count])
    ws.append(["Total Revenue", total_revenue])
    ws.append(["Returned", returned_count])
    ws.append(["Taken", taken_count])
    ws.append(["Not Returned", not_returned])

    # Costumes Sheet
    ws2 = wb.create_sheet("Top Costumes")
    ws2.append(["Costume", "Bookings"])

    for costume, count in top_costumes:
        ws2.append([costume, count])

    # Schools Sheet
    ws3 = wb.create_sheet("Top Schools")
    ws3.append(["School", "Bookings"])

    for school, count in top_schools:
        ws3.append([school, count])

    # Customers Sheet
    ws4 = wb.create_sheet("Top Customers")
    ws4.append([
        "Name",
        "Mobile",
        "Total Amount",
        "Total Bookings"
    ])

    for customer in top_customers:
        ws4.append([
            customer["name"],
            customer["mobile"],
            customer["total_amount"],
            customer["total_bookings"]
        ])

    # All Bookings Sheet
    ws5 = wb.create_sheet("All Bookings")

    ws5.append([
        "Name",
        "Mobile",
        "Address",
        "School",
        "Start Date",
        "End Date",
        "Price",
        "Costume",
        "Details"
    ])

    for booking in current_bookings:
        ws5.append([
            booking.get("name", ""),
            booking.get("mobile", ""),
            booking.get("address", ""),
            booking.get("school", ""),
            booking.get("start_date", ""),
            booking.get("end_date", ""),
            booking.get("price", 0),
            booking.get("costume", ""),
            booking.get("details", "")
        ])

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="dashboard_report.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@fancy.route("/fancy_inventory", methods=["GET", "POST"])
def fancy_inventory():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))
    if request.method == "POST":
        name = request.form.get("name")
        color = request.form.get("color")
        category = request.form.get("category")

        size_names = request.form.getlist("size_name[]")
        size_qtys = request.form.getlist("size_qty[]")

        sizes = {}
        for s, q in zip(size_names, size_qtys):
            if s.strip() and q.strip():
                sizes[s.strip()] = int(q)

        finventory.insert_one({
            "name": name,
            "color": color,
            "category": category,
            "sizes": sizes
        })

        return redirect(url_for("fancy.fancy_inventory"))

    products = list(finventory.find())
    return render_template("fancy/fancy_inventory.html", products=products)


@fancy.route("/fancy_inventory/update/<id>", methods=["POST"])
def update_fancy_inventory(id):
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))
    name = request.form.get("name")
    color = request.form.get("color")
    category = request.form.get("category")

    size_names = request.form.getlist("size_name[]")
    size_qtys = request.form.getlist("size_qty[]")

    sizes = {}
    for s, q in zip(size_names, size_qtys):
        if s.strip() and q.strip():
            sizes[s.strip()] = int(q)

    finventory.update_one(
        {"_id": ObjectId(id)},
        {"$set": {
            "name": name,
            "color": color,
            "category": category,
            "sizes": sizes
        }}
    )

    return redirect(url_for("fancy.fancy_inventory"))


@fancy.route("/fancy_inventory/delete/<id>", methods=["POST"])
def delete_fancy_inventory(id):
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))
    finventory.delete_one({"_id": ObjectId(id)})
    return redirect(url_for("fancy.fancy_inventory"))

@fancy.route('/fancy_profile')
def fancy_profile():

    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    mobile = request.args.get('mobile')

    if not mobile:
        return "Mobile number missing", 400

    # Customer master
    customer = fcustomers.find_one({
        "mobile": mobile
    })

    if not customer:
        return "Customer not found", 404

    all_bookings = []

    # ---------- FETCH FROM ALL CYCLES ----------
    for cycle in get_all_cycles():

        collection = db[
            cycle["collection_name"]
        ]

        bookings = list(
            collection.find({
                "mobile": mobile
            })
        )

        for b in bookings:

            b["season"] = cycle["name"]
            b["cycle_id"] = str(
                cycle["_id"]
            )

            # Normalize start_date
            sd = b.get("start_date")

            if isinstance(sd, datetime):

                b["start_date"] = sd.strftime(
                    "%d-%m-%Y"
                )

            elif isinstance(sd, str):

                formats = [
                    "%Y-%m-%d",
                    "%d-%m-%Y",
                    "%d-%m-%y"
                ]

                for fmt in formats:
                    try:
                        b["start_date"] = (
                            datetime.strptime(
                                sd,
                                fmt
                            ).strftime(
                                "%d-%m-%Y"
                            )
                        )
                        break
                    except:
                        pass

            # Normalize end_date
            ed = b.get("end_date")

            if isinstance(ed, datetime):

                b["end_date"] = ed.strftime(
                    "%d-%m-%Y"
                )

            elif isinstance(ed, str):

                formats = [
                    "%Y-%m-%d",
                    "%d-%m-%Y",
                    "%d-%m-%y"
                ]

                for fmt in formats:
                    try:
                        b["end_date"] = (
                            datetime.strptime(
                                ed,
                                fmt
                            ).strftime(
                                "%d-%m-%Y"
                            )
                        )
                        break
                    except:
                        pass

        all_bookings.extend(bookings)

    # ---------- SORT LATEST FIRST ----------
    all_bookings.sort(
        key=lambda x: x.get(
            "timestamp",
            datetime.min
        ),
        reverse=True
    )

    total_spent = sum(
        b.get("price", 0)
        for b in all_bookings
    )

    return render_template(
        "fancy/fancy_profile.html",
        customer=customer,
        bookings=all_bookings,
        total_spent=total_spent
    )

@fancy.route("/fancy_cycles")
def fancy_cycles_page():

    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    cycles = get_all_cycles()

    return render_template(
        "fancy/fancy_cycles.html",
        cycles=cycles
    )

@fancy.route("/fancy_cycles/create", methods=["POST"])
def create_fancy_cycle_route():

    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    name = request.form.get("name")
    collection_name = request.form.get("collection_name")

    create_cycle(
        name,
        collection_name
    )

    return redirect(
        url_for("fancy.fancy_cycles_page")
    )


@fancy.route("/fancy_cycles/select/<cycle_id>", methods=["GET", "POST"])
def select_fancy_cycle_id(cycle_id):
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    set_selected_cycle(cycle_id)
    return redirect("/fancy_admin")


@fancy.route("/fancy_cycles/select", methods=["GET", "POST"])
def select_fancy_cycle():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    cycle_id = request.form.get("cycle_id") or request.args.get("cycle_id")
    if cycle_id:
        set_selected_cycle(cycle_id)

    return redirect("/fancy_admin")

@fancy.route("/fancy_cycles/end", methods=["POST"])
@fancy.route("/fancy_cycles/end/<cycle_id>", methods=["GET", "POST"])
def end_fancy_cycle_route(cycle_id=None):
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    if request.method == "POST":
        target_id = request.form.get("cycle_id") or cycle_id
        password = request.form.get("password")

        if password != ADMIN_PASS:
            flash("❌ Authentication failed: Invalid Admin Password!", "error")
            return redirect(url_for("fancy.fancy_cycles_page"))

        if end_cycle(target_id):
            flash("✅ Active Fancy cycle ended successfully.", "success")
        else:
            flash("❌ Could not end cycle.", "error")
        return redirect(url_for("fancy.fancy_cycles_page"))

    flash("⚠️ Password confirmation required to end a cycle.", "error")
    return redirect(url_for("fancy.fancy_cycles_page"))


@fancy.route("/fancy_cycles/reactivate", methods=["POST"])
@fancy.route("/fancy_cycles/reactivate/<cycle_id>", methods=["GET", "POST"])
def reactivate_fancy_cycle_route(cycle_id=None):
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    if request.method == "POST":
        target_id = request.form.get("cycle_id") or cycle_id
        password = request.form.get("password")

        if password != ADMIN_PASS:
            flash("❌ Authentication failed: Invalid Admin Password!", "error")
            return redirect(url_for("fancy.fancy_cycles_page"))

        success, msg = reactivate_cycle(target_id)
        if success:
            flash(msg, "success")
        else:
            flash(f"❌ {msg}", "error")
        return redirect(url_for("fancy.fancy_cycles_page"))

    flash("⚠️ Password confirmation required to reactivate a cycle.", "error")
    return redirect(url_for("fancy.fancy_cycles_page"))


@fancy.route("/fancy_cycles/unlock/<cycle_id>", methods=["POST"])
def unlock_cycle(cycle_id):

    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    entered_id = request.form.get('id')
    entered_pass = request.form.get('password')

    if entered_id != ADMIN_ID or entered_pass != ADMIN_PASS:
        flash("❌ Invalid credentials!", "error")
        return redirect("/fancy_admin")

    fancy_cycles.update_one(
        {"_id": ObjectId(cycle_id)},
        {
            "$set": {
                "edit_override": True
            }
        }
    )

    flash("🔓 Cycle unlocked successfully!", "success")
    return redirect("/fancy_admin")


@fancy.route(
    "/fancy_cycles/lock/<cycle_id>"
)
def lock_cycle(cycle_id):

    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    fancy_cycles.update_one(
        {"_id": ObjectId(cycle_id)},
        {
            "$set": {
                "edit_override": False
            }
        }
    )

    flash("🔒 Cycle locked successfully!", "success")
    return redirect("/fancy_admin")

@fancy.route("/fancy-customers")
def fancy_customers():

    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    search = request.args.get("search", "").strip()

    query = {}

    if search:
        query = {
            "$or": [
                {"name": {"$regex": search, "$options": "i"}},
                {"mobile": {"$regex": search, "$options": "i"}},
                {"school": {"$regex": search, "$options": "i"}},
                {"address": {"$regex": search, "$options": "i"}}
            ]
        }

    customers = list(
        fcustomers.find(query)
        .sort("updated_at", -1)
    )

    return render_template(
        "fancy/fancy_customers.html",
        customers=customers,
        search=search
    )

@fancy.route(
    "/fancy-customer/<customer_id>",
    methods=["GET", "POST"]
)
def fancy_customer(customer_id):

    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    customer = fcustomers.find_one(
        {"_id": ObjectId(customer_id)}
    )

    if not customer:
        return "Customer Not Found"

    if request.method == "POST":

        fcustomers.update_one(
            {"_id": ObjectId(customer_id)},
            {
                "$set": {
                    "name": request.form.get("name"),
                    "mobile": request.form.get("mobile"),
                    "school": request.form.get("school"),
                    "address": request.form.get("address"),
                    "updated_at": datetime.utcnow()
                }
            }
        )

        flash("Customer Updated", "success")

        return redirect(
            url_for("fancy.fancy_customers")
        )

    return render_template(
        "fancy/fancy_customer_edit.html",
        customer=customer
    )

@fancy.route(
    "/fancy-customer/delete/<customer_id>",
    methods=["POST"]
)
def delete_fancy_customer(customer_id):

    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    fcustomers.delete_one(
        {"_id": ObjectId(customer_id)}
    )

    flash("Customer Deleted", "success")

    return redirect(
        url_for("fancy.fancy_customers")
    )