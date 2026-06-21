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
    get_active_collection,
    get_selected_collection,
    is_selected_cycle_locked
)

fancy = Blueprint('fancy', __name__)

ADMIN_ID = os.environ.get("ADMIN_ID")
ADMIN_PASS = os.environ.get("ADMIN_PASS")

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

        print("DATA =", data)

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
        print("ERROR:", e)
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

    # -----------------------------
    # MOST RENTED COSTUMES
    # -----------------------------
    costume_counter = Counter()

    for b in current_bookings:

        costume = b.get('costume')

        if costume:
            costume_counter[costume] += 1

    top_costumes = sorted(
        costume_counter.items(),
        key=lambda x: x[1],
        reverse=True
    )[:20]

    # -----------------------------
    # TOP SCHOOLS
    # -----------------------------
    school_counter = Counter()

    for b in current_bookings:

        school = b.get('school')

        if school:
            school_counter[school] += 1

    top_school = sorted(
        school_counter.items(),
        key=lambda x: x[1],
        reverse=True
    )[:20]

    # -----------------------------
    # ALL-TIME CUSTOMER DATA
    # -----------------------------
    all_bookings = []

    for cycle in get_all_cycles():

        cycle_collection = db[
            cycle["collection_name"]
        ]

        all_bookings.extend(
            list(
                cycle_collection.find()
            )
        )

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
    # CURRENT SELECTED CYCLE INFO
    # -----------------------------
    selected_cycle = get_selected_cycle()

    return render_template(
        'fancy/fancy_dashboard.html',
        total_bookings=total_bookings_count,
        total_revenue=total_revenue,
        returned_count=returned_count,
        taken_count=taken_count,
        not_returned=not_returned,
        top_costumes=top_costumes,
        top_school=top_school,
        top_20_customers=top_20_customers,
        selected_cycle=selected_cycle
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
        costume = b.get('costume')

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

@fancy.route("/fancy_cycles/end/<cycle_id>")
def end_fancy_cycle_route(cycle_id):

    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    end_cycle(cycle_id)

    return redirect(
        url_for("fancy.fancy_cycles_page")
    )
@fancy.route("/fancy_cycles/select/<cycle_id>")
def select_fancy_cycle_id(cycle_id):

    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    set_selected_cycle(cycle_id)

    return redirect(
        url_for("fancy.fancy_dashboard")
    )

@fancy.route(
    "/fancy_cycles/select",
    methods=["POST"]
)
def select_fancy_cycle():

    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    cycle_id = request.form.get("cycle_id")

    set_selected_cycle(cycle_id)

    return redirect("/fancy_admin")

@fancy.route("/fancy_cycles/start", methods=["POST"])
def start_cycle():

    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    active = get_active_cycle()

    if active:
        return "End current cycle first"

    name = request.form.get("name")
    collection_name = request.form.get("collection_name")

    

    create_cycle(
        name,
        collection_name
    )

    return redirect("/fancy_admin")

@fancy.route("/fancy_cycles/end")
def end_current_cycle():

    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    cycle = get_active_cycle()

    if cycle:
        end_cycle(
            str(cycle["_id"])
        )

    return redirect("/fancy_admin")


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