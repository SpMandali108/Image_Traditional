import csv
import io
import os

from bson import ObjectId
from flask import Blueprint, Response, current_app, render_template, request, redirect, send_file, url_for, session, flash, jsonify
from datetime import datetime
from fpdf import FPDF
import qrcode
from werkzeug.local import LocalProxy

from .nmodels import *
from ..general.db import *
from .nservices import *
from website.navaratri.ncycle import (
    get_active_cycle,
    get_selected_cycle,
    get_all_cycles,
    set_selected_cycle,
    create_cycle,
    end_cycle,
    reactivate_cycle,
    get_selected_collection,
    is_selected_cycle_locked,
    navaratri_cycles
)

collection = LocalProxy(lambda: get_selected_collection())

navaratri = Blueprint('navaratri', __name__)

# ------------------ BOOK ------------------

@navaratri.route('/book', methods=['GET', 'POST'])
def book():
    if not session.get('logged_in'):
        return redirect(url_for('navaratri.login'))

    if request.method == 'POST':
        if is_selected_cycle_locked():
            flash("❌ Selected cycle is locked.", "error")
            return redirect(request.referrer or url_for("navaratri.dashboard_summary"))
        Name = request.form.get('name')
        mobile = request.form.get('mobile')
        given_price = request.form.get('given_price')
        price = request.form.get('price')
        address = request.form.get('address')
        deposit = request.form.get('deposit')
        group = request.form.get('group')
        reference = request.form.get('reference')

        dates = request.form.getlist('date')
        products_inputs = request.form.getlist('product')

        # Convert prices safely
        try:
            given_price_val = int(given_price) if given_price else 0
        except:
            given_price_val = 0
        try:
            total_price = int(price) if price else 0
        except:
            total_price = 0

        # Normalize dates and create bookings data
        bookings_data = []
        for date, prod_str in zip(dates, products_inputs):
            prod_list = [p.strip() for p in prod_str.split(',') if p.strip()]
            try:
                formatted_date = datetime.strptime(date, "%Y-%m-%d").strftime("%d-%m-%y")
            except:
                formatted_date = date
            bookings_data.append({"date": formatted_date, "products": prod_list})

        # -------------------- Conflict check --------------------
        for booking in bookings_data:
            date = booking['date']
            has_conflict, conflicts = check_booking_conflict(date, booking['products'])

            if has_conflict:
                conflict_msg = f"❌ Booking Failed! These products are already booked on {date}:\n"
                for conflict in conflicts:
                    conflict_msg += f"• '{conflict['product']}' by {conflict['customer_name']} ({conflict['customer_mobile']})\n"
                flash(conflict_msg, "error")
                return redirect(url_for('navaratri.book'))

        # -------------------- Insert / Update customer --------------------
        customer = collection.find_one({"mobile": mobile})

        if customer:
            # Existing customer → merge bookings
            bookings = customer.get('bookings', {})
            for booking_item in bookings_data:
                date = booking_item['date']
                new_prods = booking_item['products']
                if date in bookings:
                    bookings[date] = list(set(bookings[date] + new_prods))
                else:
                    bookings[date] = new_prods

            updated_total = customer.get('total_price', 0) + total_price
            updated_given = customer.get('given_price', 0) + given_price_val

            collection.update_one(
                {"_id": customer['_id']},
                {"$set": {
                    "bookings": bookings,
                    "total_price": updated_total,
                    "given_price": updated_given,
                }}
            )
        else:
            # New customer
            bookings = {}
            for b in bookings_data:
                date = b['date']
                if date in bookings:
                    bookings[date] = list(set(bookings[date] + b['products']))
                else:
                    bookings[date] = b['products']
            new_customer = {
                "Name": Name,
                "mobile": mobile,
                "address": address,
                "deposit": deposit,
                "group": group,
                "reference": reference,
                "bookings": bookings,
                "given_price": given_price_val,
                "total_price": total_price
            }
            collection.insert_one(new_customer)

        # Upsert customer record into Navaratri_Customers collection
        ncustomers.update_one(
            {"mobile": mobile},
            {
                "$set": {
                    "name": Name,
                    "mobile": mobile,
                    "address": address,
                    "group": group,
                    "reference": reference,
                    "updated_at": datetime.now()
                }
            },
            upsert=True
        )

        # Find the customer to get the generated ObjectId
        cust_record = collection.find_one({"mobile": mobile})

        # -------------------- Generate QR URL --------------------
        qr_url = url_for('navaratri.download_bill_page', id=str(cust_record["_id"]), _external=True)

        collection.update_one(
            {"_id": cust_record["_id"]},
            {"$set": {"qr_url": qr_url}}
        )

        try:
            details_list = [f"{b['date']}: {b['products']}" for b in bookings_data]
            details = f"Booked products: {', '.join(details_list)}. Total: ₹{total_price}, Paid: ₹{given_price_val}."
            log_action(Name, mobile, "book", details)
        except Exception:
            pass

        flash("✅ Booking successful!", "success")
        return redirect(url_for('navaratri.QR', mobile=mobile))

    return render_template("navaratri/book.html")

@navaratri.route("/listing",methods=['GET', 'POST'])
def listing():
    if not session.get('logged_in'):
        return redirect(url_for('navaratri.login'))
    return redirect(url_for('navaratri.navaratri_booking'))

@navaratri.route('/calendar', methods=['GET', 'POST'])
def calendar():
    if not session.get('logged_in'):
        return redirect(url_for('navaratri.login'))

    date = request.args.get('date') or request.form.get('date')
    bookings_on_date = []

    # Gather all booked dates for highlights
    booked_dates = set()
    try:
        for doc in collection.find():
            bookings = doc.get("bookings", {})
            for date_key in bookings.keys():
                if date_key not in ("given_price", "total_price"):
                    try:
                        date_obj = datetime.strptime(date_key, "%d-%m-%y")
                        booked_dates.add(date_obj.strftime("%Y-%m-%d"))
                    except ValueError:
                        pass
    except Exception as e:
        current_app.logger.error(f"Error gathering booked dates: {e}")

    selected_date_obj = None
    if date:
        try:
            # Convert YYYY-MM-DD → Date object
            selected_date_obj = datetime.strptime(date, "%Y-%m-%d")
            formatted_date = selected_date_obj.strftime("%d-%m-%y")
        except ValueError:
            try:
                selected_date_obj = datetime.strptime(date, "%d-%m-%y")
                formatted_date = date
            except ValueError:
                selected_date_obj = None
                formatted_date = date

        if selected_date_obj:
            from datetime import timedelta
            yesterday_date_str = (selected_date_obj - timedelta(days=1)).strftime("%d-%m-%y")
            tomorrow_date_str = (selected_date_obj + timedelta(days=1)).strftime("%d-%m-%y")
            
            # Fetch bookings for yesterday and tomorrow to map back-to-back rentals
            yesterday_customers = list(collection.find({f"bookings.{yesterday_date_str}": {"$exists": True}}))
            tomorrow_customers = list(collection.find({f"bookings.{tomorrow_date_str}": {"$exists": True}}))
            
            yesterday_map = {}
            for yc in yesterday_customers:
                y_prods = yc.get("bookings", {}).get(yesterday_date_str, [])
                for yp in y_prods:
                    yesterday_map[yp] = {
                        "name": yc.get("Name", "Unknown"),
                        "mobile": yc.get("mobile", ""),
                        "id": str(yc["_id"])
                    }
                    
            tomorrow_map = {}
            for tc in tomorrow_customers:
                t_prods = tc.get("bookings", {}).get(tomorrow_date_str, [])
                for tp in t_prods:
                    tomorrow_map[tp] = {
                        "name": tc.get("Name", "Unknown"),
                        "mobile": tc.get("mobile", ""),
                        "id": str(tc["_id"])
                    }
            
            # Fetch current day's bookings
            customers = collection.find({f"bookings.{formatted_date}": {"$exists": True}})
            for c in customers:
                prods = c["bookings"].get(formatted_date, [])
                prods_details = []
                for p in prods:
                    prods_details.append({
                        "code": p,
                        "yesterday": yesterday_map.get(p),
                        "tomorrow": tomorrow_map.get(p)
                    })
                
                entry = {
                    "id": str(c["_id"]),
                    "Name": c.get("Name"),
                    "mobile": c.get("mobile"),
                    "address": c.get("address", ""),
                    "deposit": c.get("deposit", "Not provided"),
                    "group": c.get("group", ""),
                    "reference": c.get("reference", ""),
                    "products": prods_details,
                    "total_price": c.get("total_price", 0),
                    "given_price": c.get("given_price", 0),
                    "remaining": c.get("total_price", 0) - c.get("given_price", 0)
                }
                bookings_on_date.append(entry)

    iso_date = selected_date_obj.strftime("%Y-%m-%d") if selected_date_obj else ""
    return render_template(
        "navaratri/calendar.html",
        date=date,
        iso_date=iso_date,
        bookings=bookings_on_date,
        booked_dates=list(booked_dates)
    )

@navaratri.route('/modify', methods=['GET', 'POST'])
def modify():
    if not session.get('logged_in'):
        return redirect(url_for('navaratri.login'))

    if request.method == 'POST':
        if is_selected_cycle_locked():
            flash("❌ Selected cycle is locked.", "error")
            return redirect(request.referrer or url_for("navaratri.dashboard_summary"))
        mobile = request.form.get('mobile')
        date_input = request.form.get('date')  # from <input type="date"> (YYYY-MM-DD)
        old_products_str = request.form.get('old_products')
        new_products_str = request.form.get('new_products')
        price_diff_str = request.form.get('price_diff')

        # Convert date → DD-MM-YY
        try:
            date_obj = datetime.strptime(date_input, "%Y-%m-%d")
            date = date_obj.strftime("%d-%m-%y")
        except ValueError:
            date = date_input  # fallback (in case already stored in correct format)

        customer = collection.find_one({"mobile": mobile})
        if not customer:
            flash("❌ No customer found with that mobile number.", "error")
            return redirect(url_for('navaratri.modify'))

        bookings = customer.get('bookings', {})
        if date not in bookings:
            flash(f"❌ No bookings exist for {date}.", "error")
            return redirect(url_for('navaratri.modify'))

        old_products = [p.strip() for p in old_products_str.split(',')] if old_products_str else []
        new_products = [p.strip() for p in new_products_str.split(',')] if new_products_str else []

        if not old_products:
            flash("❌ Please specify at least one existing product to replace.", "error")
            return redirect(url_for('navaratri.modify'))

        current = set(bookings[date])
        if not set(old_products).issubset(current):
            flash("❌ One or more products to remove aren't in the current booking.", "error")
            return redirect(url_for('navaratri.modify'))

        if set(old_products) == set(new_products):
            flash("❌ New products must differ from the ones being replaced.", "error")
            return redirect(url_for('navaratri.modify'))

        if new_products:
            has_conflict, conflicts = check_booking_conflict(date, new_products, exclude_mobile=mobile)
            if has_conflict:
                conflict_msg = f"❌ Cannot update! These products are already booked on {date}:\n"
                for conflict in conflicts:
                    conflict_msg += f"• '{conflict['product']}' by {conflict['customer_name']} ({conflict['customer_mobile']})\n"
                flash(conflict_msg, "error")
                return redirect(url_for('navaratri.modify'))

        # Update booking
        updated = [p for p in bookings[date] if p not in old_products]
        updated.extend(new_products)
        bookings[date] = updated

        try:
            price_diff = int(price_diff_str) if price_diff_str else 0
        except ValueError:
            flash("❌ Price difference must be a valid number.", "error")
            return redirect(url_for('navaratri.modify'))

        new_total_price = max(0, customer.get('total_price', 0) + price_diff)

        collection.update_one(
            {"mobile": mobile},
            {"$set": {
                "bookings": bookings,
                "total_price": new_total_price
            }}
        )

        try:
            log_action(customer.get("Name"), mobile, "edit", f"Modified booking on {date}. Replaced products {old_products} with {new_products}. Price difference: ₹{price_diff}. New total: ₹{new_total_price}.")
        except Exception:
            pass

        flash(f"✅ Booking updated for {mobile} on {date}!", "success")
        return redirect(url_for('navaratri.modify'))

    return render_template("navaratri/modify.html")

@navaratri.route('/pay_remaining', methods=['GET', 'POST'])
def pay_remaining():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    customer = None
    mobile = request.args.get('mobile')  # case 1: GET ?mobile=xxxx

    if request.method == 'POST':  # case 2: POST form
        
        if is_selected_cycle_locked():
            flash("❌ Selected cycle is locked.", "error")
            return redirect(
                request.referrer or
                url_for("navaratri.dashboard_summary")
            )

        mobile = request.form.get('mobile')
        pay_amount = request.form.get('pay_amount')

        # Validate payment
        try:
            pay_amount_val = int(pay_amount)
            if pay_amount_val <= 0:
                flash("⚠️ Payment amount must be positive.", "error")
                return redirect(url_for('navaratri.pay_remaining', mobile=mobile))
        except:
            flash("⚠️ Invalid payment amount.", "error")
            return redirect(url_for('navaratri.pay_remaining', mobile=mobile))

        customer = collection.find_one({"mobile": mobile})
        if not customer:
            flash("⚠️ Customer not found.", "error")
            return redirect(url_for('navaratri.pay_remaining'))

        total_price = customer.get('total_price', 0)
        given_price = customer.get('given_price', 0)
        remaining = total_price - given_price

        if pay_amount_val > remaining:
            flash(f"❌ Payment exceeds remaining balance of {remaining}", "error")
            return redirect(url_for('navaratri.pay_remaining', mobile=mobile))

        # Update DB
        new_given_price = given_price + pay_amount_val
        collection.update_one(
            {"_id": customer['_id']},
            {"$set": {"given_price": new_given_price}}
        )

        # -------------------- Generate QR URL --------------------
        qr_url = url_for('navaratri.download_bill_page', id=str(customer["_id"]), _external=True)
        collection.update_one(
            {"_id": customer["_id"]},
            {"$set": {"qr_url": qr_url}}
        )

        try:
            log_action(customer.get("Name"), mobile, "payment", f"Paid remaining amount: ₹{pay_amount_val}. New given price: ₹{new_given_price} of total ₹{total_price}.")
        except Exception:
            pass

        return redirect(url_for('navaratri.QR', mobile=mobile))

    # If GET or error → fetch customer for prefilled form
    if mobile:
        customer = collection.find_one({"mobile": mobile})

    return render_template("navaratri/pay_remaining.html", customer=customer)


@navaratri.route('/delete', methods=['GET', 'POST'])
def delete():
    if not session.get('logged_in'):
        return redirect(url_for('navaratri.login'))

    if request.method == 'POST':
        if is_selected_cycle_locked():
            flash("❌ Selected cycle is locked.", "error")
            return redirect(
            request.referrer or
            url_for("navaratri.dashboard_summary")
        )
        mobile = request.form.get('mobile', "").strip()
        date_input = request.form.get('date', "").strip()
        product = request.form.get('product', "").strip()
        price_diff_str = request.form.get('price_diff', "").strip()

        # ✅ Validate Mobile
        if not mobile.isdigit() or len(mobile) != 10:
            flash("❌ Invalid mobile number. Please enter a 10-digit number.", "error")
            return redirect(url_for('navaratri.delete'))

        # ✅ Convert Date Format (YYYY-MM-DD → DD-MM-YY)
        try:
            date_obj = datetime.strptime(date_input, "%Y-%m-%d")
            date = date_obj.strftime("%d-%m-%y")
        except ValueError:
            flash("❌ Invalid date format.", "error")
            return redirect(url_for('navaratri.delete'))

        # ✅ Validate Price Difference
        try:
            price_diff = int(price_diff_str)
            if price_diff <= 0:
                raise ValueError
        except ValueError:
            flash("❌ Price difference must be a positive number.", "error")
            return redirect(url_for('navaratri.delete'))

        # ✅ Validate Product
        if not product:
            flash("❌ Product name cannot be empty.", "error")
            return redirect(url_for('navaratri.delete'))

        # 🔎 Fetch Customer
        customer = collection.find_one({"mobile": mobile})
        if not customer:
            flash(f"❌ No customer found with mobile number {mobile}.", "error")
            return redirect(url_for('navaratri.delete'))

        bookings = customer.get('bookings', {})
        products_for_date = bookings.get(date)

        if not products_for_date:
            flash(f"❌ No bookings found for {date}.", "error")
            return redirect(url_for('navaratri.delete'))

        # Normalize stored product list
        if isinstance(products_for_date, str):
            products_for_date = [p.strip() for p in products_for_date.split(',')]

        if product not in products_for_date:
            flash(f"❌ Product '{product}' not found in bookings on {date}.", "error")
            return redirect(url_for('navaratri.delete'))

        # 🔄 Remove product
        products_for_date.remove(product)
        if products_for_date:
            bookings[date] = products_for_date
        else:
            bookings.pop(date)

        # 💰 Update Prices
        existing_price = customer.get('total_price', 0)
        new_price = max(0, existing_price - price_diff)

        collection.update_one(
            {"_id": customer['_id']},
            {"$set": {
                "bookings": bookings,
                "total_price": new_price
            }}
        )

        try:
            log_action(customer.get("Name"), mobile, "delete", f"Deleted product '{product}' on {date}. Reduced price by ₹{price_diff}. New total: ₹{new_price}.")
        except Exception:
            pass

        flash(f"✅ Product '{product}' removed from booking on {date}. Price reduced by {price_diff}.", "success")
        return redirect(url_for('navaratri.delete'))

    return render_template("navaratri/delete.html")

@navaratri.route('/navaratri_booking', methods=['GET', 'POST'])
@navaratri.route('/navaratri_booking/<customer_id>', methods=['GET'])
def navaratri_booking(customer_id=None):
    if not session.get('logged_in'):
        return redirect(url_for('navaratri.login'))
    customer = None
    error = None

    # Case 1: from clickable card → GET ?mobile=xxxx
    mobile = request.args.get('mobile')

    # Case 2: from search form → POST
    if request.method == 'POST':
        mobile = request.form.get('mobile')

    if customer_id:
        try:
            customer = collection.find_one({"_id": ObjectId(customer_id)})
            if not customer:
                error = "Customer not found by ID"
        except Exception as e:
            error = f"Invalid customer ID: {str(e)}"
    elif mobile:
        customer = collection.find_one({"mobile": mobile})
        if not customer:
            error = "Customer not found"

    if customer:
        customer['remaining'] = customer.get('total_price', 0) - customer.get('given_price', 0)

    bookings = list(collection.find())
    for b in bookings:
        b['remaining'] = b.get('total_price', 0) - b.get('given_price', 0)

    return render_template("navaratri/navaratri_booking.html", customer=customer, error=error, bookings=bookings)

# Redirect legacy /profile URLs to /navaratri_booking
@navaratri.route('/profile', methods=['GET', 'POST'])
@navaratri.route('/profile/<customer_id>', methods=['GET'])
def profile(customer_id=None):
    mobile = request.args.get('mobile') or (request.form.get('mobile') if request.method == 'POST' else None)
    if customer_id:
        return redirect(url_for('navaratri.navaratri_booking', customer_id=customer_id))
    elif mobile:
        return redirect(url_for('navaratri.navaratri_booking', mobile=mobile))
    return redirect(url_for('navaratri.navaratri_booking'))

# ------------------ API: Live Availability Check ------------------
@navaratri.route('/api/check-product', methods=['GET'])
def api_check_product():
    if not session.get('logged_in'):
        return jsonify({"available": False, "error": "Unauthorized"}), 401
        
    product_code = request.args.get('product_code', '').strip().upper()
    date_input = request.args.get('date', '').strip()
    exclude_mobile = request.args.get('exclude_mobile', '').strip()
    
    if not product_code or not date_input:
        return jsonify({"available": False, "error": "Product code and date are required"}), 400
        
    date_str = date_input
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d-%m-%y"):
        try:
            date_obj = datetime.strptime(date_input, fmt)
            date_str = date_obj.strftime("%d-%m-%y")
            break
        except ValueError:
            pass
        
    has_conflict, conflicts = check_booking_conflict(date_str, [product_code], exclude_mobile=exclude_mobile or None)
    if has_conflict:
        conflict = conflicts[0]
        return jsonify({
            "available": False,
            "customer": conflict.get('customer_name', 'Unknown')
        })
    else:
        return jsonify({"available": True})

# ------------------ API: Product Code Suggestion ------------------
@navaratri.route('/api/suggest-products', methods=['GET'])
def api_suggest_products():
    if not session.get('logged_in'):
        return jsonify([]), 401
    try:
        all_products = list(products.find({}, {"_id": 1}))
        codes = [p["_id"] for p in all_products]
        if not codes:
            # Fallback if Storage collection has no entries yet
            codes = [f'C{i}' for i in range(1, 151)] + [f'K{i}' for i in range(1, 174)]
        return jsonify(sorted(list(set(codes))))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ------------------ API: Unified Save/Update Profile ------------------
@navaratri.route('/navaratri_booking/update', methods=['POST'])
@navaratri.route('/profile/update', methods=['POST'])
def profile_update():
    if not session.get('logged_in'):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    if is_selected_cycle_locked():
        return jsonify({"success": False, "message": "❌ Selected cycle is locked."}), 403
        
    data = request.json or request.form
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400
        
    customer_id = data.get('customer_id')
    name = data.get('name', '').strip()
    mobile = data.get('mobile', '').strip()
    address = data.get('address', '').strip()
    deposit = data.get('deposit', '').strip()
    group = data.get('group', '').strip()
    reference = data.get('reference', '').strip()
    
    try:
        total_price = int(data.get('total_price', 0))
    except:
        total_price = 0
        
    try:
        given_price = int(data.get('given_price', 0))
    except:
        given_price = 0
        
    bookings_raw = data.get('bookings', [])
    
    if not name or not mobile:
        return jsonify({"success": False, "message": "Name and Mobile are required."}), 400
        
    if not mobile.isdigit() or len(mobile) != 10:
        return jsonify({"success": False, "message": "Mobile number must be a 10-digit number."}), 400
        
    # Check mobile conflicts
    if customer_id and customer_id != 'new':
        existing = collection.find_one({"mobile": mobile})
        if existing and str(existing['_id']) != customer_id:
            return jsonify({"success": False, "message": f"Mobile number {mobile} is already registered to another customer ({existing.get('Name')})."}), 400
    else:
        existing = collection.find_one({"mobile": mobile})
        if existing:
            return jsonify({"success": False, "message": f"Mobile number {mobile} is already registered to customer {existing.get('Name')}."}), 400

    # Process and clean bookings
    formatted_bookings = {}
    
    if isinstance(bookings_raw, list):
        for item in bookings_raw:
            date = item.get('date', '').strip()
            prods = item.get('products', [])
            if isinstance(prods, str):
                prods = [p.strip().upper() for p in prods.split(',') if p.strip()]
            else:
                prods = [p.strip().upper() for p in prods if p.strip()]
                
            if not date or not prods:
                continue
                
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
                formatted_date = date_obj.strftime("%d-%m-%y")
            except ValueError:
                formatted_date = date
                
            if formatted_date in formatted_bookings:
                formatted_bookings[formatted_date] = list(set(formatted_bookings[formatted_date] + prods))
            else:
                formatted_bookings[formatted_date] = prods

    # Run conflict checks for the bookings (excluding this customer)
    for date_str, products_list in formatted_bookings.items():
        has_conflict, conflicts = check_booking_conflict(date_str, products_list, exclude_mobile=mobile)
        if has_conflict:
            conflict_msg = f"❌ Conflict: Following product(s) are already booked on {date_str}:<br>"
            for conflict in conflicts:
                conflict_msg += f"• '{conflict['product']}' by {conflict['customer_name']} ({conflict['customer_mobile']})<br>"
            return jsonify({"success": False, "message": conflict_msg}), 400

    if customer_id and customer_id != 'new':
        ret_id = customer_id
    else:
        ret_id = str(ObjectId())

    qr_url = url_for('navaratri.download_bill_page', id=ret_id, _external=True)
    
    customer_data = {
        "Name": name,
        "mobile": mobile,
        "address": address,
        "deposit": deposit,
        "group": group,
        "reference": reference,
        "bookings": formatted_bookings,
        "given_price": given_price,
        "total_price": total_price,
        "qr_url": qr_url
    }
    
    existing_cust = None
    if customer_id and customer_id != 'new':
        try:
            existing_cust = collection.find_one({"_id": ObjectId(customer_id)})
        except:
            pass

    if customer_id and customer_id != 'new':
        collection.update_one(
            {"_id": ObjectId(customer_id)},
            {"$set": customer_data}
        )
        message = "✅ Customer profile updated successfully!"
    else:
        customer_data["_id"] = ObjectId(ret_id)
        collection.insert_one(customer_data)
        message = "✅ Customer profile created successfully!"
        ret_id = str(ret_id)

    # Upsert customer record into Navaratri_Customers collection
    ncustomers.update_one(
        {"mobile": mobile},
        {
            "$set": {
                "name": name,
                "mobile": mobile,
                "address": address,
                "group": group,
                "reference": reference,
                "updated_at": datetime.now()
            }
        },
        upsert=True
    )

    try:
        if customer_id and customer_id != 'new':
            if existing_cust:
                changes = []
                for label, key in [("Name", "Name"), ("Mobile", "mobile"), ("Address", "address"), ("Deposit", "deposit"), ("Group", "group"), ("Reference", "reference")]:
                    old_v = existing_cust.get(key, "")
                    new_v = customer_data.get(key, "")
                    if str(old_v).strip() != str(new_v).strip():
                        changes.append(f"{label}: '{old_v}' -> '{new_v}'")
                
                if existing_cust.get("total_price", 0) != total_price:
                    changes.append(f"Total Price: ₹{existing_cust.get('total_price', 0)} -> ₹{total_price}")
                if existing_cust.get("given_price", 0) != given_price:
                    changes.append(f"Paid Amount: ₹{existing_cust.get('given_price', 0)} -> ₹{given_price}")
                
                old_books = existing_cust.get("bookings", {})
                all_dates = set(old_books.keys()) | set(formatted_bookings.keys())
                book_changes = []
                for d in all_dates:
                    old_p = old_books.get(d, [])
                    new_p = formatted_bookings.get(d, [])
                    if set(old_p) != set(new_p):
                        added = set(new_p) - set(old_p)
                        removed = set(old_p) - set(new_p)
                        parts = []
                        if added:
                            parts.append(f"added {list(added)}")
                        if removed:
                            parts.append(f"removed {list(removed)}")
                        book_changes.append(f"on {d} ({' and '.join(parts)})")
                
                if book_changes:
                    changes.append(f"Bookings: {', '.join(book_changes)}")
                
                if changes:
                    details = f"Updated customer details: {'; '.join(changes)}."
                else:
                    details = "Updated customer profile (no value changes detected)."
            else:
                details = f"Updated customer profile via profile page. Total: ₹{total_price}, Given: ₹{given_price}. Bookings: {formatted_bookings}."
            log_action(name, mobile, "edit", details)
        else:
            log_action(name, mobile, "book", f"Created customer profile. Total: ₹{total_price}, Given: ₹{given_price}. Bookings: {formatted_bookings}.")
    except Exception:
        pass
        
    is_new = (customer_id == 'new' or not customer_id or not existing_cust)
    return jsonify({
        "success": True,
        "message": message,
        "customer_id": ret_id,
        "mobile": mobile,
        "name": name,
        "total_price": total_price,
        "given_price": given_price,
        "remaining": max(0, total_price - given_price),
        "qr_url": qr_url,
        "is_new": is_new
    })

# ------------------ API: Add Payment to Customer ------------------
@navaratri.route('/navaratri_booking/add-payment', methods=['POST'])
@navaratri.route('/profile/add-payment', methods=['POST'])
def profile_add_payment():
    if not session.get('logged_in'):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    if is_selected_cycle_locked():
        return jsonify({"success": False, "message": "❌ Selected cycle is locked."}), 403

    data = request.json or {}
    customer_id = data.get('customer_id')
    try:
        amount = int(data.get('amount', 0))
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid payment amount."}), 400

    if not customer_id:
        return jsonify({"success": False, "message": "Customer ID is required."}), 400
    if amount <= 0:
        return jsonify({"success": False, "message": "Payment amount must be greater than zero."}), 400

    try:
        customer = collection.find_one({"_id": ObjectId(customer_id)})
        if not customer:
            return jsonify({"success": False, "message": "Customer not found."}), 404

        total_price = customer.get('total_price', 0)
        given_price = customer.get('given_price', 0)
        remaining = total_price - given_price

        if amount > remaining:
            return jsonify({"success": False, "message": f"Payment amount exceeds remaining balance of ₹{remaining}."}), 400

        new_given_price = given_price + amount
        collection.update_one(
            {"_id": ObjectId(customer_id)},
            {"$set": {"given_price": new_given_price}}
        )

        try:
            log_action(customer.get("Name"), customer.get("mobile"), "payment", f"Added payment of ₹{amount} via profile page. New given price: ₹{new_given_price} of total ₹{total_price}.")
        except Exception:
            pass

        return jsonify({
            "success": True,
            "message": f"Successfully added payment of ₹{amount}.",
            "new_given_price": new_given_price,
            "new_remaining": total_price - new_given_price
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Error updating payment: {str(e)}"}), 500

# ------------------ API: Product Reassignment ------------------
@navaratri.route('/navaratri_booking/reassign', methods=['POST'])
@navaratri.route('/profile/reassign', methods=['POST'])
def profile_reassign():
    if not session.get('logged_in'):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    if is_selected_cycle_locked():
        return jsonify({"success": False, "message": "Selected cycle is locked"}), 403
        
    data = request.json or request.form
    customer_id = data.get('customer_id')
    old_date = data.get('old_date', '').strip()
    old_product = data.get('old_product', '').strip().upper()
    new_date = data.get('new_date', '').strip()
    new_product = data.get('new_product', '').strip().upper()
    price_diff_str = data.get('price_diff', '0').strip()
    
    if not customer_id or not old_date or not old_product or not new_date or not new_product:
        return jsonify({"success": False, "message": "Missing required fields"}), 400
        
    try:
        old_date_formatted = datetime.strptime(old_date, "%Y-%m-%d").strftime("%d-%m-%y") if '-' in old_date and len(old_date) == 10 else old_date
    except:
        old_date_formatted = old_date
        
    try:
        new_date_formatted = datetime.strptime(new_date, "%Y-%m-%d").strftime("%d-%m-%y") if '-' in new_date and len(new_date) == 10 else new_date
    except:
        new_date_formatted = new_date
        
    customer = collection.find_one({"_id": ObjectId(customer_id)})
    if not customer:
        return jsonify({"success": False, "message": "Customer not found"}), 404
        
    bookings = customer.get('bookings', {})
    
    if old_date_formatted not in bookings or old_product not in bookings[old_date_formatted]:
        return jsonify({"success": False, "message": f"Product '{old_product}' not found in bookings on {old_date_formatted}"}), 400
        
    has_conflict, conflicts = check_booking_conflict(new_date_formatted, [new_product], exclude_mobile=customer.get('mobile'))
    if has_conflict:
        conflict = conflicts[0]
        return jsonify({"success": False, "message": f"❌ Conflict: Product '{new_product}' is already booked on {new_date_formatted} by {conflict['customer_name']}."}), 400
        
    bookings[old_date_formatted].remove(old_product)
    if not bookings[old_date_formatted]:
        bookings.pop(old_date_formatted)
        
    if new_date_formatted in bookings:
        bookings[new_date_formatted] = list(set(bookings[new_date_formatted] + [new_product]))
    else:
        bookings[new_date_formatted] = [new_product]
        
    try:
        price_diff = int(price_diff_str)
    except:
        price_diff = 0
    new_total = max(0, customer.get('total_price', 0) + price_diff)
    
    collection.update_one(
        {"_id": ObjectId(customer_id)},
        {"$set": {"bookings": bookings, "total_price": new_total}}
    )

    try:
        log_action(customer.get("Name"), customer.get("mobile"), "edit", f"Reassigned product from '{old_product}' on {old_date_formatted} to '{new_product}' on {new_date_formatted}. Price difference: ₹{price_diff_str}. New total: ₹{new_total}.")
    except Exception:
        pass

    return jsonify({"success": True, "message": "✅ Product reassigned successfully!"})

# ------------------ API: Add Single Booking Row ------------------
@navaratri.route('/navaratri_booking/add-booking', methods=['POST'])
@navaratri.route('/profile/add-booking', methods=['POST'])
def profile_add_booking():
    if not session.get('logged_in'):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    if is_selected_cycle_locked():
        return jsonify({"success": False, "message": "Selected cycle is locked"}), 403
        
    data = request.json or request.form
    customer_id = data.get('customer_id')
    date_input = data.get('date', '').strip()
    product = data.get('product', '').strip().upper()
    price_diff_str = data.get('price_diff', '0').strip()
    
    if not customer_id or not date_input or not product:
        return jsonify({"success": False, "message": "Missing required fields"}), 400
        
    try:
        date_formatted = datetime.strptime(date_input, "%Y-%m-%d").strftime("%d-%m-%y") if '-' in date_input and len(date_input) == 10 else date_input
    except:
        date_formatted = date_input
        
    customer = collection.find_one({"_id": ObjectId(customer_id)})
    if not customer:
        return jsonify({"success": False, "message": "Customer not found"}), 404
        
    has_conflict, conflicts = check_booking_conflict(date_formatted, [product], exclude_mobile=customer.get('mobile'))
    if has_conflict:
        conflict = conflicts[0]
        return jsonify({"success": False, "message": f"❌ Conflict: Product '{product}' is already booked on {date_formatted} by {conflict['customer_name']}."}), 400
        
    bookings = customer.get('bookings', {})
    if date_formatted in bookings:
        bookings[date_formatted] = list(set(bookings[date_formatted] + [product]))
    else:
        bookings[date_formatted] = [product]
        
    try:
        price_diff = int(price_diff_str)
    except:
        price_diff = 0
    new_total = customer.get('total_price', 0) + price_diff
    
    collection.update_one(
        {"_id": ObjectId(customer_id)},
        {"$set": {"bookings": bookings, "total_price": new_total}}
    )

    try:
        log_action(customer.get("Name"), customer.get("mobile"), "book", f"Added booking of product '{product}' on {date_formatted} via profile page. Price difference: ₹{price_diff_str}. New total: ₹{new_total}.")
    except Exception:
        pass

    return jsonify({"success": True, "message": "✅ Booking added successfully!"})

# ------------------ API: Delete Single Booking Row ------------------
@navaratri.route('/navaratri_booking/delete-booking', methods=['POST'])
@navaratri.route('/profile/delete-booking', methods=['POST'])
def profile_delete_booking():
    if not session.get('logged_in'):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    if is_selected_cycle_locked():
        return jsonify({"success": False, "message": "Selected cycle is locked"}), 403
        
    data = request.json or request.form
    customer_id = data.get('customer_id')
    date_input = data.get('date', '').strip()
    product = data.get('product', '').strip().upper()
    price_diff_str = data.get('price_diff', '0').strip()
    
    if not customer_id or not date_input or not product:
        return jsonify({"success": False, "message": "Missing required fields"}), 400
        
    try:
        date_formatted = datetime.strptime(date_input, "%Y-%m-%d").strftime("%d-%m-%y") if '-' in date_input and len(date_input) == 10 else date_input
    except:
        date_formatted = date_input
        
    customer = collection.find_one({"_id": ObjectId(customer_id)})
    if not customer:
        return jsonify({"success": False, "message": "Customer not found"}), 404
        
    bookings = customer.get('bookings', {})
    if date_formatted not in bookings or product not in bookings[date_formatted]:
        return jsonify({"success": False, "message": f"Booking not found for {product} on {date_formatted}"}), 400
        
    bookings[date_formatted].remove(product)
    if not bookings[date_formatted]:
        bookings.pop(date_formatted)
        
    try:
        price_diff = int(price_diff_str)
    except:
        price_diff = 0
    new_total = max(0, customer.get('total_price', 0) - price_diff)
    
    collection.update_one(
        {"_id": ObjectId(customer_id)},
        {"$set": {"bookings": bookings, "total_price": new_total}}
    )

    try:
        log_action(customer.get("Name"), customer.get("mobile"), "delete", f"Deleted booking row of product '{product}' on {date_formatted} via profile page. Price reduced by ₹{price_diff_str}. New total: ₹{new_total}.")
    except Exception:
        pass

    return jsonify({"success": True, "message": "✅ Booking row deleted successfully!"})

# ------------------ API: Delete Entire Customer (Password Protected) ------------------
@navaratri.route('/navaratri_booking/delete-customer', methods=['POST'])
@navaratri.route('/profile/delete-customer', methods=['POST'])
def profile_delete_customer():
    if not session.get('logged_in'):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    if is_selected_cycle_locked():
        return jsonify({"success": False, "message": "❌ Selected cycle is locked."}), 403

    data = request.json or request.form
    customer_id = data.get('customer_id')
    mobile = data.get('mobile', '').strip()
    entered_pass = data.get('password', '').strip()

    if not entered_pass:
        return jsonify({"success": False, "message": "Admin password is required."}), 400

    if entered_pass != ADMIN_PASS:
        return jsonify({"success": False, "message": "Incorrect admin password."}), 400

    if not customer_id and not mobile:
        return jsonify({"success": False, "message": "Customer ID or mobile is required."}), 400

    customer = None
    if customer_id and customer_id != 'new':
        try:
            customer = collection.find_one({"_id": ObjectId(customer_id)})
        except Exception:
            pass

    if not customer and mobile:
        customer = collection.find_one({"mobile": mobile})

    if not customer:
        return jsonify({"success": False, "message": "Customer not found."}), 404

    cust_name = customer.get("Name", "Unknown")
    cust_mobile = customer.get("mobile", "")

    # 1. Delete document from active cycle collection ONLY (removes booking from current cycle)
    collection.delete_one({"_id": customer["_id"]})

    # Note: Customer record in Navaratri_Customers is PRESERVED intact.

    try:
        log_action(cust_name, cust_mobile, "delete_customer", f"Removed cycle booking for '{cust_name}' ({cust_mobile}). Universal customer profile preserved.")
    except Exception:
        pass

    return jsonify({"success": True, "message": f"✅ Booking record for '{cust_name}' removed from current cycle!"})

@navaratri.route('/check', methods=['GET', 'POST'])
def check():
    if not session.get('logged_in'):
        return redirect(url_for('navaratri.login'))
    
    if request.method == 'POST':
        date = request.form.get('date')  # Example: "2025-08-29"
        product = request.form.get('product').strip().replace('k', 'K').replace('c', 'C')
        
        if not date or not product:
            flash("❌ Please provide both date and product name.", "error")
            return redirect(url_for('navaratri.check'))
        
        # ✅ Convert YYYY-MM-DD → DD-MM-YY
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%d-%m-%y")
        except ValueError:
            # If already in DD-MM-YY
            formatted_date = date

        current_app.logger.debug(f"DEBUG check: input = {date} formatted = {formatted_date}")

        # ✅ Pass converted date to your conflict checker
        has_conflict, conflicts = check_booking_conflict(formatted_date, [product])
        
        if has_conflict:
            conflict = conflicts[0]
            flash(f"❌ Product '{product}' is not available on {date}. "
                  f"Already booked by {conflict['customer_name']} ({conflict['customer_mobile']}).", "error")
        else:
            flash(f"✅ Good news! Product '{product}' is available on {date}.", "success")
        
        return redirect(url_for('navaratri.check'))
    
    return render_template("navaratri/check.html")

    
# Helper functions to extract detailed analytics for the modern dashboard
def get_navaratri_analytics(traditional_data):
    def safe_int(val):
        try:
            return int(float(str(val).strip()))
        except (ValueError, TypeError, AttributeError):
            return 0

    total_customers_trad = len(traditional_data)
    total_collection_trad = sum(safe_int(b.get('total_price')) for b in traditional_data) + 29500
    total_given_trad = sum(safe_int(b.get('given_price')) for b in traditional_data)
    total_rem_trad = total_collection_trad - total_given_trad - 29500
    avg_trad = total_collection_trad / total_customers_trad if total_customers_trad > 0 else 0

    best_c, best_c_count, best_k, best_k_count = find_best_products_by_letter(traditional_data)
    highest_booking_person, highest_booking_value = find_highest_booking_customer(traditional_data)

    # Detailed statistics
    product_counts = {}
    choli_counts = {}
    kediya_counts = {}
    total_items_rented = 0

    for customer in traditional_data:
        bookings = customer.get("bookings", {})
        if not isinstance(bookings, dict):
            continue
        for date, products in bookings.items():
            if isinstance(products, list):
                for p in products:
                    if isinstance(p, str) and p.strip():
                        code = p.strip().upper()
                        product_counts[code] = product_counts.get(code, 0) + 1
                        total_items_rented += 1
                        if code.startswith('C'):
                            choli_counts[code] = choli_counts.get(code, 0) + 1
                        elif code.startswith('K'):
                            kediya_counts[code] = kediya_counts.get(code, 0) + 1

    top_cholis = sorted(choli_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    top_kediyas = sorted(kediya_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    top_products = sorted(product_counts.items(), key=lambda x: x[1], reverse=True)[:15]

    # Aggregating bookings by date
    bookings_by_date_dict = {}
    for customer in traditional_data:
        bookings = customer.get("bookings", {})
        if not isinstance(bookings, dict):
            continue
        for raw_date, products in bookings.items():
            if not isinstance(products, list) or not products:
                continue
            # Remove anything like ][][ or spaces
            clean_date = raw_date.split('[')[0].strip()
            if clean_date:
                bookings_by_date_dict[clean_date] = bookings_by_date_dict.get(clean_date, 0) + len(products)

    # Sort dates chronologically
    sorted_date_items = []
    for date_str, count in bookings_by_date_dict.items():
        parsed_date = None
        for fmt in ["%d-%m-%y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                break
            except:
                continue
        if not parsed_date:
            parsed_date = datetime.min
        sorted_date_items.append((parsed_date, date_str, count))

    sorted_date_items.sort(key=lambda x: x[0])
    bookings_by_date = [{"date": item[1], "count": item[2]} for item in sorted_date_items]

    # Payment Statuses
    fully_paid = 0
    partially_paid = 0
    unpaid = 0
    for customer in traditional_data:
        tot = safe_int(customer.get('total_price'))
        giv = safe_int(customer.get('given_price'))
        if tot == 0:
            continue
        if giv >= tot:
            fully_paid += 1
        elif giv > 0:
            partially_paid += 1
        else:
            unpaid += 1

    payment_status = {
        "fully_paid": fully_paid,
        "partially_paid": partially_paid,
        "unpaid": unpaid
    }

    # Top Customers & Top Debtors
    top_customers = []
    for customer in traditional_data:
        tot = safe_int(customer.get('total_price'))
        giv = safe_int(customer.get('given_price'))
        rem = tot - giv
        
        item_count = 0
        bookings = customer.get("bookings", {})
        if isinstance(bookings, dict):
            for products in bookings.values():
                if isinstance(products, list):
                    item_count += len(products)

        top_customers.append({
            "id": str(customer.get("_id")),
            "name": customer.get("Name") or customer.get("name") or "Unknown",
            "mobile": customer.get("mobile") or "",
            "address": customer.get("address") or "",
            "total_price": tot,
            "given_price": giv,
            "remaining": rem,
            "item_count": item_count
        })

    top_customers.sort(key=lambda x: x['total_price'], reverse=True)
    top_debtors = [c for c in top_customers if c['remaining'] > 0]
    top_debtors.sort(key=lambda x: x['remaining'], reverse=True)

    # Group & Reference Analysis
    group_revenue = {}
    reference_revenue = {}
    for customer in traditional_data:
        tot = safe_int(customer.get('total_price'))
        group = customer.get('group', '-').strip()
        ref = customer.get('reference', 'Self').strip()
        if not group or group == '':
            group = '-'
        if not ref or ref == '':
            ref = 'Self'
        group_revenue[group] = group_revenue.get(group, 0) + tot
        reference_revenue[ref] = reference_revenue.get(ref, 0) + tot

    sorted_groups = sorted(group_revenue.items(), key=lambda x: x[1], reverse=True)[:10]
    sorted_references = sorted(reference_revenue.items(), key=lambda x: x[1], reverse=True)[:10]

    # ── Product-Centric Analytical AI ──
    # A. Stock Utilization & Capacity Analytics
    total_choli_stock = 150
    total_kediya_stock = 173
    total_stock = total_choli_stock + total_kediya_stock
    
    rented_codes = set(product_counts.keys())
    rented_cholis = {code for code in rented_codes if code.startswith('C')}
    rented_kediyas = {code for code in rented_codes if code.startswith('K')}
    
    utilization_choli_pct = round((len(rented_cholis) / total_choli_stock) * 100, 1) if total_choli_stock > 0 else 0
    utilization_kediya_pct = round((len(rented_kediyas) / total_kediya_stock) * 100, 1) if total_kediya_stock > 0 else 0
    overall_utilization_pct = round((len(rented_codes) / total_stock) * 100, 1) if total_stock > 0 else 0
    
    # B. Wear and Tear Heuristics (Since products are unique, track usage levels)
    wear_tear_alerts = []
    for code, count in top_products:
        if count >= 3:
            wear_tear_alerts.append({
                "code": code,
                "rentals": count,
                "util_level": "High" if count >= 4 else "Medium",
                "action": "Inspect fabric integrity. Consider maintenance or retirement. Replace with a new unique design to keep catalog fresh." if count >= 4 else "Perform standard fabric care, starching and button checks."
            })
            
    # C. Cross-Selling Style Pairings (Items booked together on same date/account)
    associations = {}
    for customer in traditional_data:
        bookings = customer.get("bookings", {})
        if not isinstance(bookings, dict):
            continue
        for date, products in bookings.items():
            if not isinstance(products, list) or len(products) < 2:
                continue
            cholis = [p.upper().strip() for p in products if isinstance(p, str) and p.strip().upper().startswith('C')]
            kediyas = [p.upper().strip() for p in products if isinstance(p, str) and p.strip().upper().startswith('K')]
            for c in cholis:
                for k in kediyas:
                    pair = (c, k)
                    associations[pair] = associations.get(pair, 0) + 1
                    
    style_pairings = []
    sorted_pairs = sorted(associations.items(), key=lambda x: x[1], reverse=True)[:10]
    for pair, count in sorted_pairs:
        style_pairings.append({
            "choli": pair[0],
            "kediya": pair[1],
            "count": count,
            "suggestion": "Highly associated pair. Recommend displaying together in catalog as a pre-matched style."
        })

    # D. Catalog Showcase Rotations (Identify idle unique garments)
    choli_all_set = {f"C{i}" for i in range(1, 151)}
    kediya_all_set = {f"K{i}" for i in range(1, 174)}
    unbooked_cholis = list(choli_all_set - rented_cholis)
    unbooked_kediyas = list(kediya_all_set - rented_kediyas)
    unbooked_cholis.sort(key=lambda x: int(x[1:]) if x[1:].isdigit() else 0)
    unbooked_kediyas.sort(key=lambda x: int(x[1:]) if x[1:].isdigit() else 0)
    
    catalog_rotations = []
    for code in unbooked_cholis[:4]:
        catalog_rotations.append({
            "code": code,
            "type": "Choli",
            "reason": "Idle this cycle (0 bookings).",
            "action": "Rotate to homepage featured slider or display at entrance window."
        })
    for code in unbooked_kediyas[:4]:
        catalog_rotations.append({
            "code": code,
            "type": "Kediya",
            "reason": "Idle this cycle (0 bookings).",
            "action": "Reposition in catalog list header or display as outfit alternative."
        })

    return {
        "total_customers_trad": total_customers_trad,
        "total_collection_trad": total_collection_trad,
        "total_given_trad": total_given_trad,
        "total_rem_trad": total_rem_trad,
        "avg_trad": avg_trad,
        "best_c": best_c,
        "best_c_count": best_c_count,
        "best_k": best_k,
        "best_k_count": best_k_count,
        "highest_booking_person": highest_booking_person,
        "highest_booking_value": highest_booking_value,
        "total_items_rented": total_items_rented,
        "choli_count": sum(c for _, c in choli_counts.items()),
        "kediya_count": sum(c for _, c in kediya_counts.items()),
        "top_cholis": top_cholis,
        "top_kediyas": top_kediyas,
        "top_products": top_products,
        "bookings_by_date": bookings_by_date,
        "payment_status": payment_status,
        "top_customers": top_customers[:15],
        "top_debtors": top_debtors[:15],
        "top_groups": sorted_groups,
        "top_references": sorted_references,
        
        "utilization": {
            "choli_pct": utilization_choli_pct,
            "kediya_pct": utilization_kediya_pct,
            "overall_pct": overall_utilization_pct,
            "total_stock": total_stock,
            "rented_unique": len(rented_codes),
            "product_counts": product_counts
        },
        "wear_tear_alerts": wear_tear_alerts,
        "style_pairings": style_pairings,
        "catalog_rotations": catalog_rotations
    }

def get_fancy_analytics(fancy_data):
    total_bookings = len(fancy_data)
    total_revenue = sum(
        int(b.get('price') or 0) for b in fancy_data if isinstance(b.get('price'), (int, float, str))
    )
    avg_revenue = total_revenue / total_bookings if total_bookings > 0 else 0

    returned_count = sum(1 for b in fancy_data if b.get("returned"))
    taken_count = sum(1 for b in fancy_data if b.get("taken"))
    not_returned = sum(
        1 for b in fancy_data if b.get("taken") and not b.get("returned")
    )

    costume_counter = {}
    school_counter = {}
    bookings_by_date_dict = {}

    for b in fancy_data:
        costume = b.get("costume")
        school = b.get("school")
        
        if costume:
            costume_counter[costume] = costume_counter.get(costume, 0) + 1
        if school:
            school_counter[school] = school_counter.get(school, 0) + 1

        # Aggregating bookings by start date
        raw_date = b.get("start_date")
        if raw_date:
            if isinstance(raw_date, datetime):
                date_str = raw_date.strftime("%d-%m-%Y")
            else:
                date_str = str(raw_date).strip()
            bookings_by_date_dict[date_str] = bookings_by_date_dict.get(date_str, 0) + 1

    # Sort dates chronologically
    sorted_date_items = []
    for date_str, count in bookings_by_date_dict.items():
        parsed_date = None
        for fmt in ["%d-%m-%Y", "%Y-%m-%d", "%d-%m-%y", "%d/%m/%Y"]:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                break
            except:
                continue
        if not parsed_date:
            parsed_date = datetime.min
        sorted_date_items.append((parsed_date, date_str, count))

    sorted_date_items.sort(key=lambda x: x[0])
    bookings_by_date = [{"date": item[1], "count": item[2]} for item in sorted_date_items]

    top_costumes = sorted(costume_counter.items(), key=lambda x: x[1], reverse=True)[:10]
    top_school = sorted(school_counter.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "total_customers_fancy": total_bookings,
        "total_collection_fancy": total_revenue,
        "avg_fancy": avg_revenue,
        "returned_count_fancy": returned_count,
        "taken_count_fancy": taken_count,
        "not_returned_fancy": not_returned,
        "top_costumes_fancy": top_costumes,
        "top_school_fancy": top_school,
        "bookings_by_date_fancy": bookings_by_date
    }


@navaratri.route('/dashboard')
def dashboard_summary():
    if not session.get('logged_in'):
        return redirect(url_for('navaratri.login'))

    selected_cycle = get_selected_cycle()

    try:
        try:
            collection.find_one()
            fancy_collection.find_one()
        except NameError as e:
            return f"Error: Database collections not properly defined - {e}"
        except Exception as e:
            return f"Error: Database connection failed - {e}"

        traditional_data = list(collection.find())
        trad_analytics = get_navaratri_analytics(traditional_data)

        fancy_data = list(fancy_collection.find())
        fancy_analytics = get_fancy_analytics(fancy_data)

        combined_collection = trad_analytics.get("total_collection_trad", 0) + fancy_analytics.get("total_collection_fancy", 0)

        # Merge all data into one context
        context = {
            "selected_cycle": selected_cycle,
            "combined_collection": combined_collection,
            "has_error": False
        }
        context.update(trad_analytics)
        context.update(fancy_analytics)

        return render_template('navaratri/total.html', **context)

    except Exception as e:
        import traceback
        traceback.print_exc()

        return render_template(
            'navaratri/total.html',
            selected_cycle=selected_cycle,
            total_customers_trad=0,
            total_collection_trad=0,
            total_given_trad=0,
            total_rem_trad=0,
            best_c="Error",
            best_c_count=0,
            best_k="Error",
            best_k_count=0,
            highest_booking_person="Error",
            highest_booking_value=0,
            avg_trad=0,
            total_customers_fancy=0,
            total_collection_fancy=0,
            avg_fancy=0,
            combined_collection=0,
            has_error=True,
            error_message=str(e)
        )
    
    
@navaratri.route('/download-customer', methods=['GET', 'POST'])
def download_customer():
    cust_id = request.form.get('id') or request.args.get('id')
    mobile = request.form.get('mobile') or request.args.get('mobile')
    if not cust_id and not mobile and request.is_json:
        data = request.get_json(silent=True) or {}
        cust_id = data.get('id')
        mobile = data.get('mobile')
        
    if mobile:
        mobile = str(mobile).strip()
    if cust_id:
        cust_id = str(cust_id).strip()
    
    customer = None
    if cust_id:
        try:
            customer = collection.find_one({"_id": ObjectId(cust_id)})
        except Exception:
            pass
            
    if not customer and mobile:
        customer = collection.find_one({"mobile": mobile})
        
    if not customer:
        return "Customer not found", 404

    # Remaining price
    customer['remaining'] = customer.get('total_price', 0) - customer.get('given_price', 0)

    class PDF(FPDF):
        def header(self):
            # Background navy banner
            self.set_fill_color(10, 17, 32)  # #0a1120 Premium navy
            self.rect(0, 0, 210, 42, 'F')
            
            # Shop Logo
            logo_path = os.path.join(current_app.root_path, "static", "Home_Img", "favicon.png")
            if os.path.exists(logo_path):
                self.image(logo_path, 15, 10, 22)
            
            # Title
            self.set_text_color(212, 175, 55)  # Gold #d4af37
            self.set_font('helvetica', 'B', 22)
            self.set_xy(42, 10)
            self.cell(0, 10, 'IMAGE TRADITIONAL', ln=1)
            
            # Address info (white text)
            self.set_text_color(241, 245, 249)
            self.set_font('helvetica', '', 9)
            self.set_xy(42, 20)
            self.multi_cell(
                95, 4.5,
                "Nr. Laxminarayan Bus-stand, Opp Prarabdh Soc.\n"
                "Maninagar(E), Ahmedabad-08",
                align='L'
            )
            
            # Owner & Meta Details (Right Side)
            self.set_text_color(212, 175, 55)  # Gold
            self.set_font('helvetica', 'B', 10)
            self.set_xy(140, 11)
            self.cell(55, 5, "Prakash Mandali: 9428610384", align='R', ln=1)
            
            self.set_text_color(241, 245, 249)
            self.set_font('helvetica', '', 9)
            self.set_xy(140, 17)
            self.cell(55, 5, "Rental Booking Invoice", align='R', ln=1)
            
            self.set_xy(140, 23)
            self.cell(55, 5, f"Date: {datetime.now().strftime('%d-%b-%Y')}", align='R', ln=1)
            
            # Space below header banner
            self.ln(25)

        def footer(self):
            self.set_y(-15)
            self.set_font('helvetica', 'I', 8)
            self.set_text_color(148, 163, 184)
            self.cell(0, 10, f'Page {self.page_no()}/{{nb}} | Image Traditional Rental Receipt', align='C')

    pdf = PDF('P', 'mm', 'A4')
    pdf.alias_nb_pages()
    pdf.add_page()

    # ------- Customer Details Heading -------
    pdf.set_y(46)
    pdf.set_font('helvetica', 'B', 11)
    pdf.set_text_color(15, 23, 42)  # Dark slate
    pdf.cell(0, 8, "CUSTOMER & BOOKING DETAILS", ln=1)
    
    # Gold separator line
    pdf.set_draw_color(212, 175, 55)
    pdf.set_line_width(0.5)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(4)

    # ------- Two-Column Customer Details Grid -------
    def render_row(label1, val1, label2, val2):
        y = pdf.get_y()
        # Col 1 Label
        pdf.set_xy(15, y)
        pdf.set_font('helvetica', 'B', 9)
        pdf.set_text_color(100, 116, 139)  # Muted slate
        pdf.cell(32, 6, sanitize_latin1(label1) + ":", border=0)
        # Col 1 Value
        pdf.set_font('helvetica', '', 9.5)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(63, 6, sanitize_latin1(str(val1)), border=0)
        
        # Col 2 Label
        pdf.set_font('helvetica', 'B', 9)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(28, 6, sanitize_latin1(label2) + ":", border=0)
        # Col 2 Value
        pdf.set_font('helvetica', '', 9.5)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(57, 6, sanitize_latin1(str(val2)), border=0)
        pdf.ln(7.5)

    render_row("Customer Name", customer.get("Name", "N/A"), "Group Name", customer.get("group", "N/A"))
    render_row("Mobile Number", customer.get("mobile", "N/A"), "Reference", customer.get("reference", "N/A"))
    render_row("Security Deposit", customer.get('deposit', 'N/A'), "Address", customer.get("address", "N/A"))
    
    pdf.ln(2)

    # ------- Items Table Heading -------
    pdf.set_font('helvetica', 'B', 11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 8, "RENTAL ITEMS", ln=1)
    
    # Gold separator line
    pdf.set_draw_color(212, 175, 55)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(4)

    # ------- Table Header -------
    pdf.set_font('helvetica', 'B', 10)
    pdf.set_text_color(255, 255, 255)  # White
    pdf.set_fill_color(10, 17, 32)      # Navy
    pdf.set_draw_color(10, 17, 32)      # Navy
    
    pdf.set_x(15)
    pdf.cell(15, 9, "Sr.", border=1, align="C", fill=True)
    pdf.cell(50, 9, "Product Code", border=1, align="C", fill=True)
    pdf.cell(60, 9, "Product Preview", border=1, align="C", fill=True)
    pdf.cell(55, 9, "Booking Date", border=1, align="C", fill=True)
    pdf.ln()

    # ------- Table Rows -------
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(15, 23, 42)
    pdf.set_draw_color(226, 232, 240)  # Soft grey borders
    
    sr = 1
    bookings = customer.get("bookings", {})

    for date, codes in bookings.items():
        for code in codes:
            pdf.set_x(15)
            # Row height 25 to fit image
            pdf.cell(15, 25, str(sr), border=1, align="C")
            pdf.cell(50, 25, f"  {code}", border=1, align="L")

            # Image Cell
            x = pdf.get_x()
            y = pdf.get_y()
            pdf.cell(60, 25, "", border=1)

            img_path = None
            if code.startswith("K"):
                img_path = os.path.join(current_app.static_folder, "KediyaJpg", f"{code}.jpg")
            elif code.startswith("C"):
                img_path = os.path.join(current_app.static_folder, "CholiJpg", f"{code}.jpg")
            elif code.startswith("G"):
                img_path = os.path.join(current_app.static_folder, "GroupJpg", f"{code}.jpg")

            if img_path and os.path.exists(img_path):
                # Center image inside cell: Cell width 60, height 25. Image width 36, height 21
                pdf.image(img_path, x + 12, y + 2, 36, 21)
            else:
                curr_y = pdf.get_y()
                pdf.set_xy(x, y + 10)
                pdf.set_font("helvetica", "I", 8.5)
                pdf.set_text_color(148, 163, 184)
                pdf.cell(60, 5, "No Preview Available", border=0, align="C")
                pdf.set_font("helvetica", "", 10)
                pdf.set_text_color(15, 23, 42)
                pdf.set_xy(x + 60, y)

            pdf.cell(55, 25, date, border=1, align="C")
            pdf.ln()

            sr += 1

    # ------- Totals Card Section -------
    pdf.ln(5)
    totals_start_x = 115
    
    total_price = customer.get("total_price", 0)
    given_price = customer.get("given_price", 0)
    remaining = total_price - given_price

    # Row: Total Price
    pdf.set_x(totals_start_x)
    pdf.set_font("helvetica", "B", 9.5)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(45, 6, "Total Amount:", align="R")
    pdf.set_font("helvetica", "B", 10.5)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(35, 6, f"Rs. {total_price}", align="R", ln=1)

    # Row: Given Price
    pdf.set_x(totals_start_x)
    pdf.set_font("helvetica", "B", 9.5)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(45, 6, "Amount Paid:", align="R")
    pdf.set_font("helvetica", "B", 10.5)
    pdf.set_text_color(16, 185, 129)  # Success Green
    pdf.cell(35, 6, f"Rs. {given_price}", align="R", ln=1)

    # Divider line
    pdf.set_draw_color(226, 232, 240)
    pdf.line(totals_start_x, pdf.get_y() + 1, 195, pdf.get_y() + 1)
    pdf.ln(2.5)

    # Row: Remaining (Balance Due Box)
    pdf.set_x(totals_start_x)
    if remaining > 0:
        pdf.set_fill_color(254, 242, 242)  # Light Red background
        pdf.set_draw_color(239, 68, 68)    # Red border
        pdf.set_text_color(220, 38, 38)    # Red text
    else:
        pdf.set_fill_color(240, 253, 250)  # Light Green background
        pdf.set_draw_color(16, 185, 129)   # Green border
        pdf.set_text_color(13, 148, 136)   # Teal text

    y = pdf.get_y()
    pdf.rect(totals_start_x, y, 80, 8.5, 'DF')
    pdf.set_xy(totals_start_x, y + 1.25)
    pdf.set_font("helvetica", "B", 9.5)
    pdf.cell(45, 6, "Balance Due:", align="R")
    pdf.set_font("helvetica", "B", 11.5)
    pdf.cell(30, 6, f"Rs. {remaining}", align="R")
    pdf.ln(13)

    # ------- Terms & Conditions -------
    pdf.set_x(15)
    pdf.set_font("helvetica", "B", 8.5)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 4, "Terms & Conditions:", ln=1)
    
    pdf.set_font("helvetica", "", 7.5)
    pdf.set_text_color(148, 163, 184)
    pdf.set_x(15)
    pdf.multi_cell(
        180, 3.5,
        "1. Please verify the condition of all rental items before leaving the shop.\n"
        "2. Rental items must be returned on the scheduled return date. Delayed returns may incur penalty fees.\n"
        "3. The security deposit is fully refundable upon returning all items without damage.\n"
        "4. Thank you for choosing Image Traditional!",
        align="L"
    )

    # Output PDF as bytes
    pdf_output = pdf.output(dest="S")
    if isinstance(pdf_output, str):
        pdf_bytes = pdf_output.encode("latin1")
    else:
        pdf_bytes = bytes(pdf_output)

    pdf_buffer = io.BytesIO(pdf_bytes)
    pdf_buffer.seek(0)

    filename = f"{customer.get('Name', 'customer')}_Profile.pdf"

    try:
        log_action(customer.get("Name"), customer.get("mobile"), "bill_download", f"Downloaded rental booking bill/invoice: {filename}.")
    except Exception:
        pass

    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf"
    )


@navaratri.route('/search', methods=['GET', 'POST'])
def search():
    query = None
    normal_results = []
    fancy_results = []

    if not session.get('logged_in'):
        return redirect(url_for('navaratri.login'))

    if request.method == 'POST':
        query = request.form.get('search')

        # --------------------------
        # Normal Collection Search
        # --------------------------
        normal_matches = collection.find({
            "$or": [
                {"Name": {"$regex": query, "$options": "i"}},
                {"mobile": {"$regex": query, "$options": "i"}},
                {"address": {"$regex": query, "$options": "i"}},
                {"group": {"$regex": query, "$options": "i"}},
                {"reference": {"$regex": query, "$options": "i"}},
                {"bookings": {"$exists": True}}
            ]
        })

        for c in normal_matches:
            bookings = c.get("bookings", {})
            total_price = bookings.get("total_price", c.get("total_price", ""))
            given_price = bookings.get("given_price", c.get("given_price", ""))

            for date_key, products in bookings.items():
                if date_key in ["total_price", "given_price"]:
                    continue
                if isinstance(products, list):
                    for product in products:
                        if query.lower() in str(product).lower() \
                           or query.lower() in c.get("Name", "").lower() \
                           or query.lower() in c.get("mobile", "").lower() \
                           or query.lower() in c.get("address", "").lower() \
                           or query.lower() in c.get("group", "").lower() \
                           or query.lower() in c.get("reference", "").lower():
                            normal_results.append({
                                "name": c.get("Name", "N/A"),
                                "mobile": c.get("mobile", "N/A"),
                                "address": c.get("address", "N/A"),
                                "group": c.get("group", "N/A"),
                                "reference": c.get("reference", "N/A"),
                                "product_code": product,
                                "date": date_key,
                                "total_price": total_price,
                                "given_price": given_price
                            })

        # --------------------------
        # Fancy Collection Search
        # --------------------------
        fancy_matches = fancy_collection.find({
            "$or": [
                {"name": {"$regex": query, "$options": "i"}},
                {"mobile": {"$regex": query, "$options": "i"}},
                {"address": {"$regex": query, "$options": "i"}},
                {"Address": {"$regex": query, "$options": "i"}},  # handle capital A
                {"costume": {"$regex": query, "$options": "i"}},
                {"details": {"$regex": query, "$options": "i"}},
            ]
        })

        for f in fancy_matches:
            fancy_results.append({
                "name": f.get("name", "N/A"),
                "mobile": f.get("mobile", "N/A"),
                "address": f.get("address") or f.get("Address", "N/A"),
                "costume": f.get("costume", "N/A"),
                "details": f.get("details", "N/A"),
                "start_date": f.get("start_date", "N/A"),
                "end_date": f.get("end_date", "N/A"),
                "price": f.get("price", "N/A"),
            })

    return render_template("navaratri/search.html", query=query,
                           normal_results=normal_results,
                           fancy_results=fancy_results)

@navaratri.route("/export_bookings")
def export_bookings():
    if not session.get('logged_in'):
        return redirect(url_for('navaratri.login'))
    docs = list(collection.find())

    # Collect all unique booking dates (keys in bookings except prices)
    date_keys = set()
    for doc in docs:
        bookings = doc.get("bookings", {})
        for key in bookings.keys():
            if key not in ("given_price", "total_price"):
                date_keys.add(key)
    date_keys = sorted(date_keys)

    # Collect all other top-level keys except '_id' and 'bookings'
    other_keys = set()
    for doc in docs:
        for key in doc.keys():
            if key not in ("_id", "bookings"):
                other_keys.add(key)
    other_keys = sorted(other_keys)

    # Prepare CSV fieldnames (other keys + booking dates)
    fieldnames = other_keys + date_keys

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for doc in docs:
        row = {}

        # Add other top-level fields
        for key in other_keys:
            value = doc.get(key, "")
            # Convert complex types to string
            if isinstance(value, (dict, list)):
                value = str(value)
            row[key] = value

        # Add booking dates with product lists
        bookings = doc.get("bookings", {})
        for date in date_keys:
            products = bookings.get(date, [])
            if isinstance(products, list):
                row[date] = ", ".join(str(p) for p in products)
            else:
                row[date] = ""

        writer.writerow(row)

    output.seek(0)
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=bookings_export.csv"}
    )


@navaratri.route("/export-calendar-bookings")
def export_calendar_bookings():
    if not session.get('logged_in'):
        return redirect(url_for('navaratri.login'))

    date = request.args.get("date", "").strip()
    if not date:
        return "No date provided", 400

    try:
        from datetime import timedelta
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%d-%m-%y")
    except ValueError:
        return "Invalid date format. Expected YYYY-MM-DD", 400

    # Calculate yesterday's and tomorrow's date strings
    yesterday_obj = date_obj - timedelta(days=1)
    yesterday_date_str = yesterday_obj.strftime("%d-%m-%y")
    
    tomorrow_obj = date_obj + timedelta(days=1)
    tomorrow_date_str = tomorrow_obj.strftime("%d-%m-%y")

    # Query MongoDB for bookings on formatted_date, yesterday, and tomorrow
    customers = list(collection.find({f"bookings.{formatted_date}": {"$exists": True}}))
    yesterday_customers = list(collection.find({f"bookings.{yesterday_date_str}": {"$exists": True}}))
    tomorrow_customers = list(collection.find({f"bookings.{tomorrow_date_str}": {"$exists": True}}))
    
    # Map product codes to yesterday's renter details
    yesterday_map = {}
    for yc in yesterday_customers:
        y_prods = yc.get("bookings", {}).get(yesterday_date_str, [])
        for yp in y_prods:
            yesterday_map[yp] = {
                "name": yc.get("Name", "Unknown"),
                "mobile": yc.get("mobile", "N/A")
            }
            
    # Map product codes to tomorrow's renter details
    tomorrow_map = {}
    for tc in tomorrow_customers:
        t_prods = tc.get("bookings", {}).get(tomorrow_date_str, [])
        for tp in t_prods:
            tomorrow_map[tp] = {
                "name": tc.get("Name", "Unknown"),
                "mobile": tc.get("mobile", "N/A")
            }

    # Prepare CSV fieldnames matching the web dashboard
    fieldnames = [
        "Customer Name", 
        "Customer Mobile", 
        "Product Code", 
        "Booked Yesterday", 
        "Booked Tomorrow"
    ]

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for c in customers:
        products = c.get("bookings", {}).get(formatted_date, [])
        for product in products:
            y_info = yesterday_map.get(product)
            t_info = tomorrow_map.get(product)

            row = {
                "Customer Name": c.get("Name", "N/A"),
                "Customer Mobile": c.get("mobile", "N/A"),
                "Product Code": product,
                "Booked Yesterday": f"{y_info['name']} - {y_info['mobile']}" if y_info else "",
                "Booked Tomorrow": f"{t_info['name']} - {t_info['mobile']}" if t_info else ""
            }
            writer.writerow(row)

    output.seek(0)
    filename = f"Bookings_{date}.csv"

    # Return CSV file response
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )


@navaratri.route("/download-bill", methods=["GET", "POST"])
def download_bill_page():
    cust_id = request.args.get("id", "") or request.form.get("id", "")
    customer = None
    mobile = ""
    
    if cust_id:
        try:
            customer = collection.find_one({"_id": ObjectId(cust_id)})
            if customer:
                mobile = customer.get("mobile", "")
        except Exception:
            pass
            
    return render_template("navaratri/download_bill.html", id=cust_id, mobile=mobile, customer=customer)


@navaratri.route("/api/send-whatsapp-auto", methods=["POST"])
def send_whatsapp_auto_route():
    data = request.get_json(silent=True) or {}
    cust_id = data.get("id") or request.form.get("id")
    mobile = data.get("mobile") or request.form.get("mobile")

    customer = None
    if cust_id:
        try:
            customer = collection.find_one({"_id": ObjectId(cust_id)})
        except Exception:
            pass
    if not customer and mobile:
        customer = collection.find_one({"mobile": mobile})

    if not customer:
        return jsonify({"success": False, "message": "Customer not found"}), 404

    target_mobile = customer.get("mobile")
    customer_name = customer.get("Name", "Customer")
    
    # Build public external PDF invoice download link
    pdf_url = url_for('navaratri.download_customer', id=str(customer["_id"]), _external=True)

    from website.general.utils import send_whatsapp_pdf_cloud_api
    ok, response_data = send_whatsapp_pdf_cloud_api(target_mobile, pdf_url, customer_name)

    if ok:
        return jsonify({"success": True, "message": f"PDF invoice sent automatically to WhatsApp (+91 {target_mobile})!"})
    else:
        return jsonify({"success": False, "message": f"Meta WhatsApp API: {response_data}"}), 400

@navaratri.route("/generate-qr/<mobile>")
def generate_qr(mobile):
    customer = collection.find_one({"mobile": mobile})
    if not customer:
        return "Customer not found", 404

    # Generate QR URL with customer's database ID for security/privacy
    qr_url = url_for('navaratri.download_bill_page', id=str(customer["_id"]), _external=True)

    qr_img = qrcode.make(qr_url)
    buf = io.BytesIO()
    qr_img.save(buf, format="PNG")
    buf.seek(0)

    return send_file(buf, mimetype="image/png")

@navaratri.route("/QR/<mobile>")
def QR(mobile):
    customer = collection.find_one({"mobile": mobile})
    if not customer:
        flash("Customer not found", "warning")
        return redirect(url_for("navaratri.book"))

    qr_url = customer.get("qr_url")
    return render_template("navaratri/QR.html", customer=customer, qr_url=qr_url)

@navaratri.route('/payment_success')
def payment_success():
    if not session.get('logged_in'):
        return redirect(url_for('navaratri.login'))

    mobile = request.args.get('mobile')
    customer = collection.find_one({"mobile": mobile}) if mobile else None

    if not customer:
        flash("⚠️ Customer not found.", "error")
        return redirect(url_for('navaratri.navaratri_booking'))

    return render_template("navaratri/payment_success.html", customer=customer)





# Save product status to 'products' collection
@navaratri.route("/update_status", methods=["POST"])
def update_status():

    if is_selected_cycle_locked():
        return jsonify({
            "success": False,
            "message": "Selected cycle is locked"
        }), 403

    data = request.json
    product_code = data.get("product_code")
    status = data.get("status")

    
    if product_code and status:
        products_collection.update_one(
            {"product_code": product_code},  # if exists
            {"$set": {"status": status}},    # update status
            upsert=True                       # insert if not exists
        )
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Invalid data"}), 400

# Retrieve all product statuses
@navaratri.route("/get_statuses", methods=["GET"])
def get_statuses():
    statuses = products_collection.find({}, {"_id": 0})
    return jsonify({item["product_code"]: item["status"] for item in statuses})

# Clear all product statuses
@navaratri.route("/clear_statuses", methods=["POST"])
def clear_statuses():

    if is_selected_cycle_locked():
        return jsonify({
            "success": False,
            "message": "Selected cycle is locked"
        }), 403

    products_collection.delete_many({})
    return jsonify({"success": True})

@navaratri.route("/code/<code>")
def code_detail(code):
    if not session.get('logged_in'):
        return redirect(url_for('navaratri.login'))

    pipeline = [
        {"$project": {
            "Name": 1,
            "mobile": 1,
            "address": 1,
            "deposit": 1,
            "group": 1,
            "reference": 1,
            "given_price": 1,
            "total_price": 1,
            "bookingsArr": {"$objectToArray": "$bookings"}  # convert object to array
        }},
        {"$unwind": "$bookingsArr"},
        {"$match": {"bookingsArr.v": {"$in": [code]}}}, 
        {"$project": {
            "dateStr": "$bookingsArr.k",
            "day": {"$toInt": {"$substr": ["$bookingsArr.k", 0, 2]}},
            "month": {"$toInt": {"$substr": ["$bookingsArr.k", 3, 2]}},
            "year": {"$toInt": {"$concat": ["20", {"$substr": ["$bookingsArr.k", 6, 2]}]}},
            "user": {
                "id": {"$toString": "$_id"},
                "Name": "$Name",
                "mobile": "$mobile",
                "address": "$address",
                "group": "$group",
                "reference": "$reference",
                "deposit": "$deposit"
            },
            "given_price": "$given_price",
            "total_price": "$total_price"
        }},
        {"$group": {
            "_id": "$dateStr",
            "year": {"$first": "$year"},
            "month": {"$first": "$month"},
            "day": {"$first": "$day"},
            "bookings": {"$push": {
                "user": "$user",
                "given_price": "$given_price",
                "total_price": "$total_price"
            }}
        }}
    ]

    results = list(collection.aggregate(pipeline))

    # Sort in Python by year, month, day
    results.sort(key=lambda r: (r["year"], r["month"], r["day"]))

    # Prepare for template
    bookings_by_date = [{"date": r["_id"], "bookings": r["bookings"]} for r in results]

    # build image path (static/images/c1.jpg, k1.jpg etc.)
    if code.startswith("K"):
        image_url = url_for("static", filename=f"Kediya/{code}.webp")
    elif code.startswith("C"):
        image_url = url_for("static", filename=f"Choli/{code}.webp")
    else:
        image_url = None

    # Dynamic JSON Output handler for AJAX Costume Explorer
    if request.args.get('json') == 'true' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            "success": True,
            "code": code,
            "image_url": image_url,
            "bookings_by_date": bookings_by_date
        })

    if not results:
        return render_template("navaratri/no_booking.html", code=code)

    return render_template(
        "navaratri/code.html",
        code=code,
        image_url=image_url,
        bookings_by_date=bookings_by_date
    )


@navaratri.route("/dashboard_listing",methods=['GET', 'POST'])
def dashboard_listing():
    if not session.get('logged_in'):
        return redirect(url_for('navaratri.login'))

    bookings = list(collection.find())
    for b in bookings:
        b['remaining'] = b.get('total_price', 0) - b.get('given_price', 0)

    return render_template("navaratri/dashboard_listing.html", bookings=bookings)
# Add/replace this route in your blueprint (navaratri)
@navaratri.route('/available', methods=['GET', 'POST'])
def available():
    # require login (same pattern as your other routes)
    if not session.get('logged_in'):
        return redirect(url_for('navaratri.login'))

    date = None
    filter_val = "all"   # default filter
    remaining_c = []
    remaining_k = []

    # Generate inventory codes (no image filenames here; template builds .webp path)
    all_c = [{"code": f"C{i}"} for i in range(1, 151)]
    all_k = [{"code": f"K{i}"} for i in range(1, 174)]

    if request.method == 'POST':
        date = request.form.get('date')              # YYYY-MM-DD from form
        filter_val = request.form.get('filter', 'all')

        if date:
            # convert date to your DB key format (DD-MM-YY). fallback to raw if parse fails
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
                formatted_date = date_obj.strftime("%d-%m-%y")
            except Exception:
                formatted_date = date

            # Collect booked codes for that date (safe check, handles list or comma-string)
            booked = set()
            for doc in collection.find({}):
                bookings = doc.get("bookings", {})
                if not isinstance(bookings, dict):
                    continue
                if formatted_date in bookings:
                    value = bookings.get(formatted_date, [])
                    # normalize: could be list or string like "C1,C2"
                    if isinstance(value, str):
                        items = [p.strip() for p in value.split(',') if p.strip()]
                    elif isinstance(value, list):
                        items = value
                    else:
                        items = []

                    for p in items:
                        if not isinstance(p, str):
                            continue
                        booked.add(p.strip().upper())

            # Debug prints (check server console)
            current_app.logger.debug(f"[DEBUG] Booked on {formatted_date} => {len(booked)} items: {sorted(booked)[:50]}")

            # Build remaining lists (exclude booked codes)
            remaining_c = [p for p in all_c if p["code"].upper() not in booked]
            remaining_k = [p for p in all_k if p["code"].upper() not in booked]

    # Render template and pass filter to make radio sticky
    return render_template(
        "navaratri/available.html",
        date=date,
        remaining_c=remaining_c,
        remaining_k=remaining_k,
        filter=filter_val
    )

@navaratri.route('/add_bag', methods=['POST'])
def add_bag():
    if not session.get('logged_in'):
        return redirect(url_for('navaratri.login'))
    name = request.form.get('name')
    desc = request.form.get('bag_description', '')
    bags.insert_one({'name': name, 'description': desc})
    return redirect(url_for('navaratri.Storage'))

# -----------------------
# ADD MULTIPLE PRODUCTS
# -----------------------
@navaratri.route('/add_product', methods=['POST'])
def add_product():
    if not session.get('logged_in'):
        return redirect(url_for('navaratri.login'))
    bag_id = request.form['bag_id']
    codes = request.form.getlist('product_codes')  # checkboxes
    custom_code = request.form.get('custom_code', '').strip()

    # Include custom code if provided
    if custom_code:
        codes.append(custom_code)

    for code in codes:
        code = code.strip()
        if code:
            try:
                products.insert_one({
                    "_id": code,
                    "bag_id": str(bag_id)
                })
            except Exception as e:
                current_app.logger.warning(f"Skipping duplicate code: {code}")

    return redirect(url_for('navaratri.Storage'))

@navaratri.route('/Storage', methods=['GET', 'POST'])
def Storage():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))
    result = None
    if request.method == 'POST':
        search_type = request.form['search_type']
        query = request.form['query'].strip()

        if search_type == 'product':
            result = products.find_one({"_id": query})
            if result:
                bag_id = result.get('bag_id')
                bag = bags.find_one({"_id": ObjectId(bag_id)}) if ObjectId.is_valid(bag_id) else bags.find_one({"_id": bag_id})
                if bag:
                    result['bag_name'] = bag.get('name', 'Unknown')
                    result['bag_description'] = bag.get('description', 'No description')
                else:
                    result['bag_name'] = 'Unknown'
                    result['bag_description'] = 'No description'

        elif search_type == 'bag':
            bag = bags.find_one({"name": query})
            if bag:
                bag_id_str = str(bag['_id'])
                result = list(products.find({"bag_id": bag_id_str}))
            else:
                result = []

    all_bags = list(bags.find())

    # Generate available codes (for checkboxes)
    all_codes = [f'C{i}' for i in range(1, 151)] + [f'K{i}' for i in range(1, 174)]
    used_codes = [p['_id'] for p in products.find({}, {"_id": 1})]
    available_codes = [c for c in all_codes if c not in used_codes]

    return render_template('navaratri/Storage.html', result=result, bags=all_bags, available_codes=available_codes)


@navaratri.route('/export_product_report')
def export_product_report():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    # 1. Get the dictionary of all counts
    #    Example: {'C1': 12, 'K5': 9, 'C10': 5}
    try:
        all_counts = get_all_product_counts()
    except Exception as e:
        return f"Error running get_all_product_counts: {e}"

    # 2. Sort the products by count (most popular first)
    #    This converts the dict to a list of tuples: [('C1', 12), ('K5', 9), ...]
    sorted_products = sorted(all_counts.items(), key=lambda item: item[1], reverse=True)

    # 3. Create an in-memory text buffer
    output = io.StringIO()
    
    # 4. Create a CSV writer object
    writer = csv.writer(output)

    # 5. Write the Header Row
    writer.writerow(['Product_Code', 'Times_Rented'])

    # 6. Write all the data rows
    for product_code, count in sorted_products:
        writer.writerow([product_code, count])

    # 7. Go back to the start of the in-memory file
    output.seek(0)

    # 8. Send the file to the browser as a download
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=product_popularity_report.csv"}
    )


@navaratri.route('/navaratri_dashboard')
def navaratri_dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))
    
    selected_cycle = get_selected_cycle()
    try:
        try:
            collection.find_one()
            fancy_collection.find_one()
        except NameError as e:
            return f"Error: Database collections not properly defined - {e}"
        except Exception as e:
            return f"Error: Database connection failed - {e}"

        traditional_data = list(collection.find())
        trad_analytics = get_navaratri_analytics(traditional_data)

        context = {
            "selected_cycle": selected_cycle,
            "has_error": False
        }
        context.update(trad_analytics)

        return render_template('navaratri/navaratri_dashboard.html', **context)

    except Exception as e:
        import traceback
        traceback.print_exc()

        return render_template(
            'navaratri/navaratri_dashboard.html',
            selected_cycle=selected_cycle,
            total_customers_trad=0,
            total_collection_trad=0,
            total_given_trad=0,
            total_rem_trad=0,
            best_c="Error",
            best_c_count=0,
            best_k="Error",
            best_k_count=0,
            highest_booking_person="Error",
            highest_booking_value=0,
            avg_trad=0,
            has_error=True,
            error_message=str(e)
        )

@navaratri.route("/navaratri_cycles")
def navaratri_cycles_page():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    cycles = get_all_cycles()
    return render_template(
    "navaratri/navaratri_cycles.html",
    cycles=cycles
)


@navaratri.route("/navaratri_cycles/create", methods=["POST"])
def create_navaratri_cycle_route():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    name = request.form.get("name")
    collection_name = request.form.get("collection_name")

    create_cycle(
        name,
        collection_name
    )

    return redirect("/navaratri_admin")


@navaratri.route("/navaratri_cycles/select/<cycle_id>", methods=["GET", "POST"])
def select_navaratri_cycle_id(cycle_id):
    if not session.get('logged_in'):
        return redirect(url_for('navaratri.login'))

    set_selected_cycle(cycle_id)
    return redirect("/navaratri_admin")


@navaratri.route("/navaratri_cycles/select", methods=["GET", "POST"])
def select_navaratri_cycle():
    if not session.get('logged_in'):
        return redirect(url_for('navaratri.login'))

    cycle_id = request.form.get("cycle_id") or request.args.get("cycle_id")
    if cycle_id:
        set_selected_cycle(cycle_id)

    return redirect("/navaratri_admin")


@navaratri.route("/navaratri_cycles/end", methods=["POST"])
@navaratri.route("/navaratri_cycles/end/<cycle_id>", methods=["GET", "POST"])
def end_navaratri_cycle_route(cycle_id=None):
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    if request.method == "POST":
        target_id = request.form.get("cycle_id") or cycle_id
        password = request.form.get("password")

        if password != ADMIN_PASS:
            flash("❌ Authentication failed: Invalid Admin Password!", "error")
            return redirect("/navaratri_admin")

        if end_cycle(target_id):
            flash("✅ Active cycle ended successfully.", "success")
        else:
            flash("❌ Could not end cycle.", "error")
        return redirect("/navaratri_admin")

    flash("⚠️ Password confirmation required to end a cycle.", "error")
    return redirect("/navaratri_admin")


@navaratri.route("/navaratri_cycles/reactivate", methods=["POST"])
@navaratri.route("/navaratri_cycles/reactivate/<cycle_id>", methods=["GET", "POST"])
def reactivate_navaratri_cycle_route(cycle_id=None):
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    if request.method == "POST":
        target_id = request.form.get("cycle_id") or cycle_id
        password = request.form.get("password")

        if password != ADMIN_PASS:
            flash("❌ Authentication failed: Invalid Admin Password!", "error")
            return redirect("/navaratri_admin")

        success, msg = reactivate_cycle(target_id)
        if success:
            flash(msg, "success")
        else:
            flash(f"❌ {msg}", "error")
        return redirect("/navaratri_admin")

    flash("⚠️ Password confirmation required to reactivate a cycle.", "error")
    return redirect("/navaratri_admin")


@navaratri.route("/navaratri_cycles/unlock/<cycle_id>", methods=["POST"])
def unlock_cycle(cycle_id):
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    entered_id = request.form.get('id')
    entered_pass = request.form.get('password')

    if entered_id != ADMIN_ID or entered_pass != ADMIN_PASS:
        flash("❌ Invalid credentials!", "error")
        return redirect("/navaratri_admin")

    navaratri_cycles.update_one(
        {"_id": ObjectId(cycle_id)},
        {
            "$set": {
                "edit_override": True
            }
        }
    )

    flash("🔓 Cycle unlocked successfully!", "success")
    return redirect("/navaratri_admin")


@navaratri.route(
    "/navaratri_cycles/lock/<cycle_id>"
)
def lock_cycle(cycle_id):
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    navaratri_cycles.update_one(
        {"_id": ObjectId(cycle_id)},
        {
            "$set": {
                "edit_override": False
            }
        }
    )

    flash("🔒 Cycle locked successfully!", "success")
    return redirect("/navaratri_admin")


# ------------------ API: Get Customer for Autocomplete ------------------
@navaratri.route("/get-navaratri-customer")
def get_navaratri_customer():
    if not session.get('logged_in'):
        return jsonify({"exists": False, "error": "Unauthorized"}), 401
    mobile = request.args.get("mobile", "").strip()
    if not mobile:
        return jsonify({"exists": False})

    # Self-healing migration: Seed from active bookings if empty
    if ncustomers.count_documents({}) == 0:
        try:
            for b in collection.find():
                m = b.get("mobile")
                if m:
                    ncustomers.update_one(
                        {"mobile": m},
                        {
                            "$set": {
                                "name": b.get("Name"),
                                "mobile": m,
                                "address": b.get("address", ""),
                                "group": b.get("group", ""),
                                "reference": b.get("reference", ""),
                                "updated_at": datetime.now()
                            }
                        },
                        upsert=True
                    )
        except Exception as e:
            current_app.logger.error(f"Migration error: {e}")

    # Check if they have a booking in this cycle first
    active_customer = collection.find_one({"mobile": mobile})
    if active_customer:
        return jsonify({
            "exists": True,
            "in_cycle": True,
            "data": {
                "name": active_customer.get("Name") or active_customer.get("name", ""),
                "mobile": active_customer.get("mobile", ""),
                "address": active_customer.get("address", ""),
                "group": active_customer.get("group", ""),
                "reference": active_customer.get("reference", "")
            }
        })

    # Otherwise, fall back to the all-time database
    customer = ncustomers.find_one({"mobile": mobile}, {"_id": 0})
    if customer:
        return jsonify({
            "exists": True,
            "in_cycle": False,
            "data": {
                "name": customer.get("name", ""),
                "mobile": customer.get("mobile", ""),
                "address": customer.get("address", ""),
                "group": customer.get("group", ""),
                "reference": customer.get("reference", "")
            }
        })
    return jsonify({"exists": False})


# ------------------ Page: Navaratri Customers Directory ------------------
KNOWN_LOCALITIES = [
    "Vastral", "Maninagar", "Khokhra", "Isanpur", "Amraiwadi", "Ghodasar",
    "Vatva", "Odhav", "Hatkeshwar", "CTM", "Nikol", "Ramol", "Narol",
    "Bapunagar", "Saraspur", "Asarwa", "Shahibaug", "Satellite", "Vastrapur",
    "Bodakdev", "Navrangpura", "Sabarmati", "Chandkheda", "Ghatlodia"
]


@navaratri.route("/navaratri-customers")
def navaratri_customers_list():
    if not session.get('logged_in'):
        return redirect(url_for('navaratri.login'))

    search = request.args.get("search", "").strip()
    query = {}
    if search:
        query = {
            "$or": [
                {"name": {"$regex": search, "$options": "i"}},
                {"mobile": {"$regex": search, "$options": "i"}},
                {"address": {"$regex": search, "$options": "i"}}
            ]
        }

    all_customers = list(ncustomers.find().sort("updated_at", -1))

    # Area Strength Analytics
    area_counts = {}
    total_with_addr = 0

    for c in all_customers:
        addr = (c.get("address") or "").strip()
        if not addr:
            continue
        total_with_addr += 1
        found = False
        addr_lower = addr.lower()
        for loc in KNOWN_LOCALITIES:
            if loc.lower() in addr_lower:
                area_counts[loc] = area_counts.get(loc, 0) + 1
                found = True
                break
        if not found:
            area_counts["Other Localities"] = area_counts.get("Other Localities", 0) + 1

    sorted_areas = sorted(area_counts.items(), key=lambda x: x[1], reverse=True)
    top_areas = []
    for loc, count in sorted_areas[:5]:
        pct = round((count / max(total_with_addr, 1)) * 100, 1)
        top_areas.append({"area": loc, "count": count, "percentage": pct})

    # Active Bookings Mobile List
    active_mobiles = set()
    if collection is not None:
        try:
            active_mobiles = set(collection.distinct("mobile"))
        except Exception:
            pass

    if search:
        customers = list(ncustomers.find(query).sort("updated_at", -1))
    else:
        customers = all_customers

    return render_template(
        "navaratri/navaratri_customers.html",
        customers=customers,
        total_count=len(all_customers),
        active_bookers_count=len(active_mobiles),
        total_with_addr=total_with_addr,
        top_areas=top_areas,
        search=search
    )


@navaratri.route("/navaratri_logs")
def navaratri_logs():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    selected_cycle = get_selected_cycle()
    logs = []
    if selected_cycle:
        collection_name = selected_cycle.get("collection_name")
        if collection_name:
            logs_col = db[f"{collection_name}_logs"]
            logs = list(logs_col.find().sort("timestamp", -1))

    return render_template(
        "navaratri/navaratri_logs.html",
        logs=logs,
        selected_cycle=selected_cycle
    )


@navaratri.route("/navaratri_logs/api")
def navaratri_logs_api():
    if not session.get('logged_in'):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    selected_cycle = get_selected_cycle()
    logs_data = []
    if selected_cycle:
        collection_name = selected_cycle.get("collection_name")
        if collection_name:
            logs_col = db[f"{collection_name}_logs"]
            raw_logs = list(logs_col.find().sort("timestamp", -1))
            for log in raw_logs:
                logs_data.append({
                    "id": str(log.get("_id", "")),
                    "name": log.get("name", "") or "—",
                    "mobile": log.get("mobile", "") or "—",
                    "action": log.get("action", ""),
                    "details": log.get("details", ""),
                    "date_stamp": log.get("date_stamp", ""),
                    "time_stamp": log.get("time_stamp", "")
                })

    return jsonify({"success": True, "logs": logs_data, "cycle_name": selected_cycle.get("name") if selected_cycle else ""})


@navaratri.route("/navaratri_logs/clear", methods=["POST"])
def clear_navaratri_logs():
    if not session.get('logged_in'):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.json or request.form
    password = data.get("password", "").strip()

    if password != ADMIN_PASS:
        return jsonify({"success": False, "message": "❌ Authentication failed: Invalid Admin Password!"}), 400

    selected_cycle = get_selected_cycle()
    if not selected_cycle:
        return jsonify({"success": False, "message": "No cycle selected."}), 400

    collection_name = selected_cycle.get("collection_name")
    if not collection_name:
        return jsonify({"success": False, "message": "Invalid cycle collection."}), 400

    logs_col = db[f"{collection_name}_logs"]
    logs_col.delete_many({})

    try:
        log_action("Admin", "", "clear_logs", f"Cleared all action logs for cycle '{selected_cycle.get('name')}'.")
    except Exception:
        pass

    return jsonify({"success": True, "message": "✅ All action logs cleared successfully!"})