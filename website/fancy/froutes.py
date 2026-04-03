import json
from typing import Counter
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from datetime import datetime, timedelta
from bson.objectid import ObjectId

from .fservices import *
from .fmodels import *
from ..general.db import *

fancy = Blueprint('fancy', __name__)

# ------------------ MAIN ------------------


@fancy.route('/fancy', methods=['GET', 'POST'])
def fbook():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        data = request.get_json(silent=True)

        if not data:
            return jsonify({"error": "Invalid JSON"}), 400

        # Normalize keys
        data = {k.lower(): v for k, v in data.items()}

        mobile = str(data.get('mobile', '')).strip()
        if not mobile or len(mobile) != 10:
            return jsonify({"error": "Invalid mobile"}), 400

        booking_data = {
            'name': data.get('name', ''),
            'mobile': mobile,
            'address': data.get('address', ''),
            'school': data.get('school', ''),
            'start_date': data.get('start_date', ''),
            'end_date': data.get('end_date', ''),
            'price': float(data.get('price', 0)),
            'costume': data.get('costume', ''),
            'details': data.get('details', ''),
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

        fancy_collection.insert_one(booking_data)

        return jsonify({'status': 'success'}), 200

    # ✅ GET request — data is NOT used here
    return render_template('fancy/fancy.html')


@fancy.route("/fancy_listing",methods=['GET','POST'])
def flisting():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))
    
    fbookings = list(fancy_collection.find())

    return render_template("fancy/fancy_listing.html",fbookings = fbookings)



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
            field = act['field']          # taken / returned
            season = act['season']

            col = fancy_2024_2025 if season == '2024-2025' else fancy_collection

            col.update_one(
                {'_id': ObjectId(bid)},
                {'$set': {field: True}}
            )

    


    # ---------- FETCH ALL BOOKINGS ----------
    all_bookings = []
    for col, season in [
        (fancy_2024_2025, '2024-2025'),
        (fancy_collection, '2025-2026')
    ]:
        for b in col.find():
            b['season'] = season

            # Inline date normalization (DD-MM-YYYY)
            for k in ['start_date', 'end_date']:
                v = b.get(k)
                if isinstance(v, datetime):
                    b[k] = v.strftime('%d-%m-%Y')
                elif isinstance(v, str):
                    try:
                        b[k] = datetime.strptime(v, '%Y-%m-%d').strftime('%d-%m-%Y')
                    except:
                        pass

            all_bookings.append(b)

    # ---------- CALENDAR HIGHLIGHT DATES ----------
    booked_dates = set()
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

    # ---------- BOOKINGS FOR SELECTED DATE ----------
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

    # ---------- UPCOMING & NOT RETURNED ----------
    upcoming = []
    not_returned = []

    for b in all_bookings:
        try:
            ed = datetime.strptime(b['end_date'], '%d-%m-%Y').date()
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
    # CURRENT YEAR DATA (KPIs)
    # -----------------------------
    current_bookings = list(fancy_collection.find())

    total_bookings_count = len(current_bookings)
    total_revenue = sum(b.get('price', 0) for b in current_bookings)

    returned_count = sum(1 for b in current_bookings if b.get('returned'))
    taken_count = sum(1 for b in current_bookings if b.get('taken'))
    not_returned = sum(
        1 for b in current_bookings
        if b.get('taken') and not b.get('returned')
    )

    # -----------------------------
    # MOST RENTED COSTUMES (CURRENT)
    # -----------------------------
    costume_counter = Counter()
    for b in current_bookings:
        if b.get('costume'):
            costume_counter[b['costume']] += 1

    top_costumes = sorted(
        costume_counter.items(),
        key=lambda x: x[1],
        reverse=True
    )

    # -----------------------------
    # TOP SCHOOLS (CURRENT)
    # -----------------------------
    school_counter = Counter()
    for b in current_bookings:
        if b.get('school'):
            school_counter[b['school']] += 1

    top_school = sorted(
        school_counter.items(),
        key=lambda x: x[1],
        reverse=True
    )

    # -----------------------------
    # ALL-TIME CUSTOMER DATA
    # -----------------------------
    old_bookings = list(fancy_2024_2025.find())
    all_bookings = current_bookings + old_bookings

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
                'total_bookings': 0   # number of dresses booked
            }

        customer_totals[mobile]['total_amount'] += price
        customer_totals[mobile]['total_bookings'] += 1

    top_20_customers = sorted(
        customer_totals.values(),
        key=lambda x: x['total_amount'],
        reverse=True
    )[:50]

    return render_template(
        'fancy/fancy_dashboard.html',
        total_bookings=total_bookings_count,
        total_revenue=total_revenue,
        returned_count=returned_count,
        taken_count=taken_count,
        not_returned=not_returned,
        top_costumes=top_costumes,
        top_school=top_school,
        top_20_customers=top_20_customers
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
    customer = fcustomers.find_one({"mobile": mobile})
    if not customer:
        return "Customer not found", 404

    all_bookings = []

    # ---------- Fancy 2024–2025 ----------
    bookings_2425 = list(fancy_2024_2025.find({"mobile": mobile}))
    for b in bookings_2425:
        b["season"] = "2024-2025"

        # INLINE DATE FORMAT (NO FILTER, NO FUNCTION)
        sd = b.get("start_date")
        if isinstance(sd, datetime):
            b["start_date"] = sd.strftime("%d-%m-%Y")
        elif isinstance(sd, str):
            try:
                b["start_date"] = datetime.strptime(sd, "%Y-%m-%d").strftime("%d-%m-%Y")
            except:
                pass

        ed = b.get("end_date")
        if isinstance(ed, datetime):
            b["end_date"] = ed.strftime("%d-%m-%Y")
        elif isinstance(ed, str):
            try:
                b["end_date"] = datetime.strptime(ed, "%Y-%m-%d").strftime("%d-%m-%Y")
            except:
                pass

    all_bookings.extend(bookings_2425)

    # ---------- Fancy 2025–2026 ----------
    bookings_2526 = list(fancy_collection.find({"mobile": mobile}))
    for b in bookings_2526:
        b["season"] = "2025-2026"

        # INLINE DATE FORMAT (NO FILTER, NO FUNCTION)
        sd = b.get("start_date")
        if isinstance(sd, datetime):
            b["start_date"] = sd.strftime("%d-%m-%Y")
        elif isinstance(sd, str):
            try:
                b["start_date"] = datetime.strptime(sd, "%Y-%m-%d").strftime("%d-%m-%Y")
            except:
                pass

        ed = b.get("end_date")
        if isinstance(ed, datetime):
            b["end_date"] = ed.strftime("%d-%m-%Y")
        elif isinstance(ed, str):
            try:
                b["end_date"] = datetime.strptime(ed, "%Y-%m-%d").strftime("%d-%m-%Y")
            except:
                pass

    all_bookings.extend(bookings_2526)

    # Sort latest first (safe even if timestamp missing)
    all_bookings.sort(
        key=lambda x: x.get("timestamp", datetime.min),
        reverse=True
    )

    total_spent = sum(b.get("price", 0) for b in all_bookings)

    return render_template(
        "fancy/fancy_profile.html",
        customer=customer,
        bookings=all_bookings,
        total_spent=total_spent
    )