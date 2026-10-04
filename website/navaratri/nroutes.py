import csv
import io
import os
import re

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

        with booking_lock:
            # -------------------- Rental Status Validation --------------------
            for booking in bookings_data:
                for p in booking['products']:
                    base_code, size, qty = parse_product_item(p)
                    is_avail, err_reason = is_product_available_for_rent(
                        code=base_code, size=size, requested_qty=qty, date=booking['date']
                    )
                    if not is_avail:
                        flash(f"❌ Booking Failed! {err_reason}", "error")
                        return redirect(url_for('navaratri.book'))

            # -------------------- Conflict check --------------------
            for booking in bookings_data:
                date = booking['date']
                has_conflict, conflicts = check_booking_conflict(date, booking['products'])

                if has_conflict:
                    conflict_msg = f"❌ Booking Failed! Conflict on {date}:\n"
                    for conflict in conflicts:
                        reason = conflict.get('reason')
                        if reason:
                            conflict_msg += f"• {conflict['product']}: {reason}\n"
                        else:
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
                    curr = list(bookings.get(date, []))
                    for np in new_prods:
                        base_c, size, _ = parse_product_item(np)
                        grp = get_group(base_c) if is_group_code(base_c) else None
                        if grp and size:
                            curr.append(np)
                        else:
                            norm_np = normalize_product_code(np)
                            if not any(normalize_product_code(x) == norm_np for x in curr):
                                curr.append(np)
                    bookings[date] = curr

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
                    curr = list(bookings.get(date, []))
                    for np in b['products']:
                        base_c, size, _ = parse_product_item(np)
                        grp = get_group(base_c) if is_group_code(base_c) else None
                        if grp and size:
                            curr.append(np)
                        else:
                            norm_np = normalize_product_code(np)
                            if not any(normalize_product_code(x) == norm_np for x in curr):
                                curr.append(np)
                    bookings[date] = curr
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
            for p in new_products:
                is_avail, err_reason = is_product_available_for_rent(p)
                if not is_avail:
                    flash(f"❌ Cannot update: {err_reason}", "error")
                    return redirect(url_for('navaratri.modify'))

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

# ------------------ API: Live Availability Check (Harden Protected) ------------------
@navaratri.route('/api/check-product', methods=['GET', 'POST'])
@navaratri.route('/api/check-availability', methods=['GET', 'POST'])
def api_check_product():
    # 1. Thread-safe sliding window rate limiting (40 req/min per IP)
    from website.general.security import (
        validate_product_code, 
        validate_booking_date, 
        availability_rate_limiter, 
        get_client_ip
    )
    
    client_ip = get_client_ip(request)
    allowed, remaining, retry_after = availability_rate_limiter.is_allowed(client_ip)
    if not allowed:
        current_app.logger.warning(f"[SECURITY ALERT] Rate limit exceeded on availability API by IP {client_ip}")
        resp = jsonify({
            "available": False, 
            "error": "Too many requests. Please wait a moment before checking again."
        })
        resp.headers["Retry-After"] = str(retry_after)
        return resp, 429

    # 2. Request payload size protection (Max 10 KB)
    if request.content_length and request.content_length > 10 * 1024:
        return jsonify({"available": False, "error": "Request payload exceeds allowed limit."}), 413

    # 3. Parameter extraction and strict schema verification
    is_admin = bool(session.get('logged_in'))
    raw_product_code = None
    raw_date = None
    raw_exclude_mobile = None

    if request.method == 'POST':
        if not request.is_json:
            return jsonify({"available": False, "error": "Request body must be valid application/json."}), 400
        
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"available": False, "error": "JSON payload must be an object."}), 400

        # Whitelist permitted keys - reject unexpected/NoSQL operator keys
        allowed_keys = {"product_code", "date"}
        if is_admin:
            allowed_keys.add("exclude_mobile")
        extra_keys = set(data.keys()) - allowed_keys
        if extra_keys:
            current_app.logger.warning(f"[SECURITY ALERT] Unexpected payload keys {extra_keys} from IP {client_ip}")
            return jsonify({"available": False, "error": "Unexpected fields present in request payload."}), 400

        raw_product_code = data.get("product_code")
        raw_date = data.get("date")
        raw_exclude_mobile = data.get("exclude_mobile") if is_admin else None
    else:
        # GET request: extract from query string
        raw_product_code = request.args.get("product_code")
        raw_date = request.args.get("date")
        raw_exclude_mobile = request.args.get("exclude_mobile") if is_admin else None

    # 4. Strict Type, Length, Format & Injection Validation
    val_code_ok, product_code, err_code = validate_product_code(raw_product_code)
    if not val_code_ok:
        return jsonify({"available": False, "error": err_code}), 400

    val_date_ok, dt_obj, norm_date_yyyy, date_str, err_date = validate_booking_date(raw_date)
    if not val_date_ok:
        return jsonify({"available": False, "error": err_date}), 400

    # 5. Safe Normalized Server-Side Query Construction
    base_code, embedded_size, _ = parse_product_item(product_code)
    req_size = request.args.get('size') or embedded_size
    norm_base = normalize_product_code(base_code)
    if not norm_base:
        return jsonify({"available": False, "error": f"Invalid product code '{product_code}'"}), 400

    try:
        group = get_group(norm_base) if is_group_code(norm_base) else None
        if group:
            if not group.get("on_rent", True):
                return jsonify({
                    "available": False,
                    "is_group": True,
                    "product_code": norm_base,
                    "reason": f"Group '{norm_base}' is currently not taking new bookings."
                })

            if req_size:
                sz_str = str(req_size).strip()
                sizes = group.get("sizes", {})
                if sz_str not in sizes or not sizes[sz_str].get("active", True):
                    return jsonify({
                        "available": False,
                        "is_group": True,
                        "product_code": norm_base,
                        "size": sz_str,
                        "reason": f"Size '{sz_str}' is currently not available for group '{norm_base}'."
                    })
                
                avail_qty, master_qty, booked_qty = get_available_group_quantity(
                    norm_base, sz_str, date_str, exclude_mobile=raw_exclude_mobile if is_admin else None
                )
                if avail_qty <= 0:
                    return jsonify({
                        "available": False,
                        "is_group": True,
                        "product_code": norm_base,
                        "size": sz_str,
                        "available_quantity": 0,
                        "master_quantity": master_qty,
                        "booked_quantity": booked_qty,
                        "reason": f"Size {sz_str} is fully booked on {date_str} (0/{master_qty} available)."
                    })
                else:
                    return jsonify({
                        "available": True,
                        "is_group": True,
                        "product_code": norm_base,
                        "size": sz_str,
                        "available_quantity": avail_qty,
                        "master_quantity": master_qty,
                        "booked_quantity": booked_qty,
                        "reason": f"{avail_qty} piece(s) available on {date_str}."
                    })
            else:
                # No specific size passed -> return full breakdown for the date
                sizes_breakdown = get_group_size_availability(
                    norm_base, date=date_str, exclude_mobile=raw_exclude_mobile if is_admin else None
                )
                has_any_avail = any(s["available"] > 0 for s in sizes_breakdown.values() if s.get("active"))
                return jsonify({
                    "available": has_any_avail,
                    "is_group": True,
                    "product_code": norm_base,
                    "type": group.get("type", "choli"),
                    "sizes": sizes_breakdown,
                    "reason": "Available for rent" if has_any_avail else f"All sizes booked on {date_str}"
                })
        else:
            # Individual product check
            is_avail, err_reason = is_product_available_for_rent(norm_base, date=date_str)
            prod_doc = get_navaratri_product(norm_base)
            prod_img = prod_doc.get("image") if prod_doc else None

            if not is_avail:
                resp = {
                    "available": False,
                    "is_group": False,
                    "reason": err_reason or "Not available for rent",
                    "product_code": norm_base
                }
                if is_admin:
                    resp["customer"] = "Sold / Not for Rent"
                    resp["error"] = err_reason
                return jsonify(resp)

            has_conflict, conflicts = check_booking_conflict(
                date_str, 
                [norm_base], 
                exclude_mobile=raw_exclude_mobile if is_admin else None
            )
            if has_conflict:
                conflict = conflicts[0]
                cust_name = conflict.get('customer_name', 'Unknown')
                resp = {
                    "available": False,
                    "is_group": False,
                    "reason": f"Booked by {cust_name}" if is_admin else "Already booked for this date",
                    "product_code": norm_base
                }
                if is_admin:
                    resp["customer"] = cust_name
                return jsonify(resp)
            else:
                resp = {
                    "available": True,
                    "is_group": False,
                    "product_code": norm_base,
                    "reason": "Available for rent"
                }
                if prod_img:
                    resp["image"] = prod_img
                return jsonify(resp)

    except Exception as e:
        current_app.logger.error(f"[SECURITY/ERROR] Error checking product availability for '{norm_base}' on '{date_str}': {e}", exc_info=True)
        return jsonify({
            "available": False,
            "error": "A temporary service error occurred while checking availability. Please try again."
        }), 500

# ------------------ API: Product Code Suggestion ------------------
@navaratri.route('/api/suggest-products', methods=['GET'])
def api_suggest_products():
    if not session.get('logged_in'):
        return jsonify([]), 401
    try:
        # Load active individual products
        nav_prods = list(navaratri_products.find({"on_rent": True}, {"code": 1, "_id": 0}))
        ind_codes = [p["code"] for p in nav_prods if p.get("code")]
        
        # Load active groups
        group_prods = list(costume_groups.find({"on_rent": True}, {"code": 1, "_id": 0}))
        grp_codes = [g["code"] for g in group_prods if g.get("code")]

        all_codes = sorted(list(set(ind_codes + grp_codes)), key=natural_sort_key)
        return jsonify(all_codes)
    except Exception as e:
        current_app.logger.error(f"Error in api_suggest_products: {e}", exc_info=True)
        return jsonify({"error": "Failed to load product suggestions."}), 500

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
                
            curr = list(formatted_bookings.get(formatted_date, []))
            for np in prods:
                base_c, size, _ = parse_product_item(np)
                grp = get_group(base_c) if is_group_code(base_c) else None
                if grp and size:
                    curr.append(np)
                else:
                    norm_np = normalize_product_code(np)
                    if not any(normalize_product_code(x) == norm_np for x in curr):
                        curr.append(np)
            formatted_bookings[formatted_date] = curr

    with booking_lock:
        # Validate rental status for all booked products
        for date_str, products_list in formatted_bookings.items():
            for p in products_list:
                base_c, size, qty = parse_product_item(p)
                is_avail, err_reason = is_product_available_for_rent(
                    code=base_c, size=size, requested_qty=qty, date=date_str
                )
                if not is_avail:
                    return jsonify({"success": False, "message": f"❌ Booking Rejected: {err_reason}"}), 400

        # Run conflict checks for the bookings (excluding this customer)
        for date_str, products_list in formatted_bookings.items():
            has_conflict, conflicts = check_booking_conflict(date_str, products_list, exclude_mobile=mobile)
            if has_conflict:
                conflict_msg = f"❌ Conflict: Following product(s) are already booked on {date_str}:<br>"
                for conflict in conflicts:
                    reason = conflict.get('reason')
                    if reason:
                        conflict_msg += f"• {conflict['product']}: {reason}<br>"
                    else:
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
        current_app.logger.error(f"Error updating payment for customer {customer_id}: {e}", exc_info=True)
        return jsonify({"success": False, "message": "A database error occurred while updating payment. Please try again."}), 500

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

    is_avail, err_reason = is_product_available_for_rent(new_product)
    if not is_avail:
        return jsonify({"success": False, "message": f"❌ Cannot reassign: {err_reason}"}), 400

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

    is_avail, err_reason = is_product_available_for_rent(product)
    if not is_avail:
        return jsonify({"success": False, "message": f"❌ Cannot book: {err_reason}"}), 400

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

        # Check rental status
        is_avail, err_reason = is_product_available_for_rent(product)
        if not is_avail:
            flash(f"❌ {err_reason}", "error")
            return redirect(url_for('navaratri.check'))

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
    total_collection_trad = sum(safe_int(b.get('total_price')) for b in traditional_data) 
    total_given_trad = sum(safe_int(b.get('given_price')) for b in traditional_data)
    total_rem_trad = total_collection_trad - total_given_trad
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
    db_cholis = get_active_individual_products("choli")
    db_kediyas = get_active_individual_products("kediya")
    choli_all_set = {p["code"] for p in db_cholis}
    kediya_all_set = {p["code"] for p in db_kediyas}
    total_choli_stock = len(choli_all_set) if choli_all_set else 150
    total_kediya_stock = len(kediya_all_set) if kediya_all_set else 173
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
            "total_choli_stock": total_choli_stock,
            "total_kediya_stock": total_kediya_stock,
            "choli_codes": sorted(list(choli_all_set), key=lambda x: int(x[1:]) if x[1:].isdigit() else 0),
            "kediya_codes": sorted(list(kediya_all_set), key=lambda x: int(x[1:]) if x[1:].isdigit() else 0),
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
    
    
def parse_booking_date(date_str):
    if not date_str:
        return datetime.max
    clean_str = str(date_str).split('[')[0].strip()
    for fmt in (
        "%d-%m-%y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y",
        "%d-%b-%Y", "%d-%b-%y", "%d %b %Y", "%d %B %Y"
    ):
        try:
            return datetime.strptime(clean_str, fmt)
        except ValueError:
            pass
    try:
        from dateutil import parser
        return parser.parse(clean_str, dayfirst=True)
    except Exception:
        return datetime.max


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
    is_sale = (customer.get('type') == 'selling')

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
            inv_title = "Costume Sale Invoice" if is_sale else "Rental Booking Invoice"
            self.cell(55, 5, inv_title, align='R', ln=1)
            
            self.set_xy(140, 23)
            self.cell(55, 5, f"Date: {datetime.now().strftime('%d-%b-%Y')}", align='R', ln=1)
            
            # Space below header banner
            self.ln(25)

        def footer(self):
            self.set_y(-15)
            self.set_font('helvetica', 'I', 8)
            self.set_text_color(148, 163, 184)
            footer_txt = 'Image Traditional Sale Receipt' if is_sale else 'Image Traditional Rental Receipt'
            self.cell(0, 10, f'Page {self.page_no()}/{{nb}} | {footer_txt}', align='C')

    pdf = PDF('P', 'mm', 'A4')
    pdf.alias_nb_pages()

    # Register Unicode Gujarati font
    font_reg = os.path.join(current_app.root_path, "static", "fonts", "NotoSansGujarati-Regular.ttf")
    font_bold = os.path.join(current_app.root_path, "static", "fonts", "NotoSansGujarati-Bold.ttf")
    if not os.path.exists(font_reg) and os.path.exists(r"C:\Windows\Fonts\shruti.ttf"):
        font_reg = r"C:\Windows\Fonts\shruti.ttf"
        font_bold = r"C:\Windows\Fonts\shrutib.ttf"
    if os.path.exists(font_reg):
        pdf.add_font("NotoSansGujarati", "", font_reg)
        if os.path.exists(font_bold):
            pdf.add_font("NotoSansGujarati", "B", font_bold)
        else:
            pdf.add_font("NotoSansGujarati", "B", font_reg)
        try:
            pdf.set_text_shaping(True)
        except Exception:
            pass

    pdf.add_page()

    # ------- Customer Details Heading -------
    pdf.set_y(46)
    pdf.set_font('helvetica', 'B', 11)
    pdf.set_text_color(15, 23, 42)  # Dark slate
    pdf.cell(0, 8, "CUSTOMER & SALE DETAILS" if is_sale else "CUSTOMER & BOOKING DETAILS", ln=1)
    
    # Gold separator line
    pdf.set_draw_color(212, 175, 55)
    pdf.set_line_width(0.5)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(4)

    # ------- Two-Column Customer Details Grid -------
    def render_row(label1, val1, label2, val2):
        y_start = pdf.get_y()
        val_font = 'helvetica'
        val_font_size = 9.5
        line_h = 4.6

        # Col 1: X from 15 to 110 (width 95)
        pdf.set_xy(15, y_start)
        pdf.set_font('helvetica', 'B', 9)
        pdf.set_text_color(100, 116, 139)  # Muted slate
        lbl1_str = str(label1).strip() + ":"
        lbl1_w = 32
        pdf.cell(lbl1_w, line_h, sanitize_latin1(lbl1_str), border=0)

        v1_x = 15 + lbl1_w
        v1_w = 110 - v1_x  # 63 mm
        pdf.set_xy(v1_x, y_start)
        pdf.set_font(val_font, '', val_font_size)
        pdf.set_text_color(15, 23, 42)
        pdf.multi_cell(v1_w, line_h, sanitize_latin1(str(val1)), border=0, align='L')
        col1_bottom = pdf.get_y()

        # Col 2: X from 110 to 195 (width 85)
        pdf.set_xy(110, y_start)
        pdf.set_font('helvetica', 'B', 9)
        pdf.set_text_color(100, 116, 139)
        lbl2_str = str(label2).strip() + ":"
        lbl2_w = 22
        pdf.cell(lbl2_w, line_h, sanitize_latin1(lbl2_str), border=0)

        v2_x = 110 + lbl2_w
        v2_w = 195 - v2_x  # 63 mm
        pdf.set_xy(v2_x, y_start)
        pdf.set_font(val_font, '', val_font_size)
        pdf.set_text_color(15, 23, 42)
        pdf.multi_cell(v2_w, line_h, sanitize_latin1(str(val2)), border=0, align='L')
        col2_bottom = pdf.get_y()

        next_y = max(col1_bottom, col2_bottom) + 1.8
        pdf.set_y(next_y)

    if is_sale:
        render_row("Customer Name", customer.get("Name", "N/A"), "Reference", customer.get("reference") or "Direct Sale")
        render_row("Mobile Number", customer.get("mobile", "N/A"), "Sale Date", customer.get("date") or datetime.now().strftime("%d-%m-%y"))
        render_row("Customer Address", customer.get("address", "N/A"), "Invoice Type", "Costume Purchase")
    else:
        render_row("Customer Name", customer.get("Name", "N/A"), "Group Name", customer.get("group", "N/A"))
        render_row("Mobile Number", customer.get("mobile", "N/A"), "Reference", customer.get("reference", "N/A"))
        render_row("Security Deposit", customer.get('deposit', 'N/A'), "Address", customer.get("address", "N/A"))
    
    pdf.ln(1.5)

    def print_table_header():
        pdf.set_font('helvetica', 'B', 10)
        pdf.set_text_color(255, 255, 255)  # White
        pdf.set_fill_color(10, 17, 32)      # Navy
        pdf.set_draw_color(10, 17, 32)      # Navy
        pdf.set_x(15)
        pdf.cell(15, 9, "Sr.", border=1, align="C", fill=True)
        pdf.cell(50, 9, "Product Code", border=1, align="C", fill=True)
        pdf.cell(60, 9, "Product Preview", border=1, align="C", fill=True)
        pdf.cell(55, 9, "Sale Date" if is_sale else "Booking Date", border=1, align="C", fill=True)
        pdf.ln()

    # ------- Items Table Heading -------
    pdf.set_font('helvetica', 'B', 11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 8, "PURCHASED COSTUMES & ITEMS" if is_sale else "RENTAL ITEMS", ln=1)
    
    # Gold separator line
    pdf.set_draw_color(212, 175, 55)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(3.5)

    print_table_header()

    # ------- Table Rows -------
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(15, 23, 42)
    pdf.set_draw_color(226, 232, 240)  # Soft grey borders
    
    sr = 1
    bookings = customer.get("bookings", {})
    if not bookings and customer.get("sold_products"):
        s_date = customer.get("date") or datetime.now().strftime("%d-%m-%y")
        bookings = {s_date: customer.get("sold_products", [])}

    # Show bookings in ascending order of date (earliest date first)
    sorted_bookings = sorted(bookings.items(), key=lambda item: parse_booking_date(item[0]))

    for date, codes in sorted_bookings:
        for code in codes:
            if pdf.get_y() + 25 > 272:
                pdf.add_page()
                pdf.set_y(48)
                print_table_header()
                pdf.set_font("helvetica", "", 10)
                pdf.set_text_color(15, 23, 42)
                pdf.set_draw_color(226, 232, 240)

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

            pdf.cell(55, 25, str(date), border=1, align="C")
            pdf.ln()

            sr += 1

    # ------- Totals Card Section -------
    if pdf.get_y() + 28 > 272:
        pdf.add_page()
        pdf.set_y(48)

    pdf.ln(4)
    totals_start_x = 115
    
    total_price = customer.get("total_price", 0)
    given_price = customer.get("given_price", 0)
    remaining = total_price - given_price

    # Row: Total Price
    pdf.set_x(totals_start_x)
    pdf.set_font("helvetica", "B", 9.5)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(45, 5.5, "Total Amount:", align="R")
    pdf.set_font("helvetica", "B", 10.5)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(35, 5.5, f"Rs. {total_price}", align="R", ln=1)

    # Row: Given Price
    pdf.set_x(totals_start_x)
    pdf.set_font("helvetica", "B", 9.5)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(45, 5.5, "Amount Paid:", align="R")
    pdf.set_font("helvetica", "B", 10.5)
    pdf.set_text_color(16, 185, 129)  # Success Green
    pdf.cell(35, 5.5, f"Rs. {given_price}", align="R", ln=1)

    # Divider line
    pdf.set_draw_color(226, 232, 240)
    pdf.line(totals_start_x, pdf.get_y() + 1, 195, pdf.get_y() + 1)
    pdf.ln(2.0)

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

    card_y = pdf.get_y()
    pdf.rect(totals_start_x, card_y, 80, 8.0, 'DF')
    pdf.set_xy(totals_start_x, card_y + 1.0)
    pdf.set_font("helvetica", "B", 9.5)
    pdf.cell(45, 6, "Balance Due:", align="R")
    pdf.set_font("helvetica", "B", 11.5)
    pdf.cell(30, 6, f"Rs. {remaining}", align="R")

    # ------- Terms & Conditions (Bilingual) -------
    gap_after_payment = 6.0
    candidate_tc_y = card_y + 8.0 + gap_after_payment

    if is_sale:
        guj_terms = [
            "1. વેચેલ કપડાં / સામાનનું વેચાણ આખરી છે. કોઈપણ સંજોગોમાં માલ પરત કે રિફંડ મળશે નહીં.",
            "2. માલ લેતી વખતે બરાબર તપાસીને લેવો. પાછળથી કોઈ પણ ફરિયાદ માન્ય રહેશે નહીં.",
            "3. બાકી રકમ નક્કી કરેલ સમયમર્યાદામાં પૂરેપૂરી ચૂકવવાની રહેશે."
        ]
        eng_terms = [
            "1. All costume sales are final. Sold items are strictly non-refundable and non-returnable.",
            "2. Please inspect the items carefully at the time of purchase. No complaints accepted later.",
            "3. Any remaining balance must be cleared as per the agreed payment terms."
        ]
    else:
        guj_terms = [
            "1. ચણિયાચોળી/કેડિયાનું એડવાન્સ બુકિંગ ટોકન એમાઉન્ટ આપી બુક કરાવવાનું રહેશે અને બાકીની પૂરી રકમ નવરાત્રી પહેલા જમા કરાવવાની રહેશે, તો જ તમારું બુકિંગ માન્ય રહેશે.",
            "2. ભાડું એક દિવસ / રાત્રી માટે જ રહેશે. વધારે સમય માટે અલગથી ભાડું ચૂકવવાનું રહેશે.",
            "3. બુકિંગ સમયે ડિપોઝિટ / ઓળખાણ ફરજિયાત રહેશે.",
            "4. વરસાદ કે અન્ય કોઈપણ કારણોસર બુકિંગ કેન્સલ થશે નહીં અને કોઈપણ પ્રકારનું રિફંડ મળશે નહીં તેમજ બુકિંગ અન્ય કોઈપણ દિવસે ટ્રાન્સફર થશે નહીં.",
            "5. વસ્તુ લેવા આવો ત્યારે બરાબર તપાસીને જોઈને જ લઈ જવી. પાછળથી કોઈ તકરાર ચાલશે નહીં.",
            "6. કપડું ફાટી ગયું હશે અથવા કોઈ ઓર્નામેન્ટ્સ ખોવાઈ ગયું હશે તો તેની પૂરેપૂરી નુકસાની ગ્રાહકે આપવાની રહેશે.",
            "7. ગરબા થઈ ગયા પછી આપના ભીના કપડાં પંખા નીચે હવામાં સુકાઈ જાય પછી જ થેલીમાં પેક કરી લાવવાં.",
            "8. ચણિયાચોળી/કેડિયું જમા કરાવવાનો સમય સવારે 9 થી 12 અને ચણિયાચોળી/કેડિયું લઈ જવાનો સમય બપોરે 2 થી 7 રહેશે.",
            "9. ડિપોઝિટ રિફંડેબલ છે."
        ]
        eng_terms = [
            "1. Chaniya Choli/Kediya must be booked in advance by paying a token amount. The remaining full amount must be paid before Navratri; only then will your booking be considered valid.",
            "2. The rental is valid for one day/night only. Additional charges will apply for extra time.",
            "3. A security deposit / valid identification is mandatory at the time of booking.",
            "4. Bookings cannot be cancelled due to rain or any other reason. No refund of any kind will be provided, and the booking cannot be transferred to any other date.",
            "5. Please inspect the items carefully before taking them. No complaints or disputes will be accepted later.",
            "6. If the clothes are torn or any ornaments/accessories are lost, the customer will be responsible for paying the full cost of the damage/loss.",
            "7. After the Garba event, wet clothes must be properly air-dried under a fan before packing them back into the bag.",
            "8. The return time for Chaniya Choli/Kediya is from 9:00 AM to 12:00 PM, and the collection time for Chaniya Choli/Kediya is from 2:00 PM to 7:00 PM.",
            "9. The security deposit is refundable."
        ]

    guj_font = "NotoSansGujarati" if "notosansgujarati" in pdf.fonts else "helvetica"
    tc_font_size = 7.5
    line_h = 3.5
    point_gap = 1.0
    safe_bottom = 273.0

    col_w = 87.0
    col1_x = 15.0
    col2_x = 108.0

    # Calculate required height for complete T&C
    pdf.set_font(guj_font, "", tc_font_size)
    guj_lines = sum(len(pdf.multi_cell(col_w, line_h, pt, dry_run=True, output="LINES")) for pt in guj_terms)
    guj_req_h = 6.0 + (guj_lines * line_h) + (len(guj_terms) * point_gap)

    pdf.set_font("helvetica", "", tc_font_size)
    eng_lines = sum(len(pdf.multi_cell(col_w, line_h, pt, dry_run=True, output="LINES")) for pt in eng_terms)
    eng_req_h = 6.0 + (eng_lines * line_h) + (len(eng_terms) * point_gap)

    req_tc_height = max(guj_req_h, eng_req_h)
    remaining_height = safe_bottom - candidate_tc_y

    # Decision logic:
    # calculate remaining page height -> remaining_height
    # calculate required T&C height   -> req_tc_height
    # required height <= remaining height?
    #   YES -> T&C on current page
    #   NO  -> new page -> T&C
    if req_tc_height <= remaining_height:
        tc_y = candidate_tc_y
    else:
        pdf.add_page()
        tc_y = 48.0

    # Render Two-Column Bilingual Terms & Conditions
    # 1. Column 1: Gujarati
    pdf.set_xy(col1_x, tc_y)
    pdf.set_font(guj_font, "B", 9)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(col_w, 5.0, "નિયમો અને શરતો :-")

    curr_guj_y = tc_y + 6.0
    pdf.set_font(guj_font, "", tc_font_size)
    pdf.set_text_color(51, 65, 85)
    for pt in guj_terms:
        pdf.set_xy(col1_x, curr_guj_y)
        pdf.multi_cell(col_w, line_h, pt, align="L")
        curr_guj_y = pdf.get_y() + point_gap

    # 2. Column 2: English
    pdf.set_xy(col2_x, tc_y)
    pdf.set_font("helvetica", "B", 9)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(col_w, 5.0, "Terms & Conditions")

    curr_eng_y = tc_y + 6.0
    pdf.set_font("helvetica", "", tc_font_size)
    pdf.set_text_color(51, 65, 85)
    for pt in eng_terms:
        pdf.set_xy(col2_x, curr_eng_y)
        pdf.multi_cell(col_w, line_h, pt, align="L")
        curr_eng_y = pdf.get_y() + point_gap

    # Output PDF as bytes
    pdf_output = pdf.output()
    if isinstance(pdf_output, (bytes, bytearray)):
        pdf_bytes = bytes(pdf_output)
    else:
        pdf_bytes = pdf_output.encode("latin1")

    pdf_buffer = io.BytesIO(pdf_bytes)
    pdf_buffer.seek(0)

    filename = f"{customer.get('Name', 'customer')}_Sale_Invoice.pdf" if is_sale else f"{customer.get('Name', 'customer')}_Profile.pdf"

    try:
        log_type = "sale_bill_download" if is_sale else "bill_download"
        log_desc = f"Downloaded costume sale invoice: {filename}." if is_sale else f"Downloaded rental booking bill/invoice: {filename}."
        log_action(customer.get("Name"), customer.get("mobile"), log_type, log_desc)
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


@navaratri.route("/export-calendar-pdf", methods=["GET", "POST"])
def export_calendar_pdf():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    date = (request.args.get("date") or request.form.get("date") or "").strip()
    if not date:
        return "No date provided", 400

    try:
        from datetime import timedelta
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%d-%m-%y")
        formatted_date_display = date_obj.strftime("%d-%b-%Y")
        full_date_display = date_obj.strftime("%d %B %Y (%A)")
    except ValueError:
        try:
            date_obj = datetime.strptime(date, "%d-%m-%y")
            formatted_date = date
            formatted_date_display = date_obj.strftime("%d-%b-%Y")
            full_date_display = date_obj.strftime("%d %B %Y (%A)")
        except ValueError:
            return "Invalid date format. Expected YYYY-MM-DD", 400

    # Calculate yesterday's and tomorrow's date strings
    from datetime import timedelta
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

    # Collect rows
    rows = []
    for c in customers:
        products = c.get("bookings", {}).get(formatted_date, [])
        for product in products:
            y_info = yesterday_map.get(product)
            t_info = tomorrow_map.get(product)
            rows.append({
                "name": c.get("Name", "N/A"),
                "mobile": c.get("mobile", "N/A"),
                "product": product,
                "yesterday": f"{y_info['name']} ({y_info['mobile']})" if y_info else None,
                "tomorrow": f"{t_info['name']} ({t_info['mobile']})" if t_info else None,
            })

    class CalendarPDF(FPDF):
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
            self.cell(0, 10, 'IMAGE TRADITIONAL')
            
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
            self.cell(55, 5, "Prakash Mandali: 9428610384", align='R')
            
            self.set_text_color(241, 245, 249)
            self.set_font('helvetica', '', 9)
            self.set_xy(140, 17)
            self.cell(55, 5, "Daily Bookings Schedule", align='R')
            
            self.set_xy(140, 23)
            self.cell(55, 5, f"Date: {formatted_date_display}", align='R')
            
            self.ln(25)

        def footer(self):
            self.set_y(-15)
            self.set_font('helvetica', 'I', 8)
            self.set_text_color(148, 163, 184)
            self.cell(0, 10, f'Page {self.page_no()}/{{nb}} | Image Traditional Daily Bookings Schedule', align='C')

    pdf = CalendarPDF('P', 'mm', 'A4')
    pdf.alias_nb_pages()

    # Register Unicode Gujarati font
    font_reg = os.path.join(current_app.root_path, "static", "fonts", "NotoSansGujarati-Regular.ttf")
    font_bold = os.path.join(current_app.root_path, "static", "fonts", "NotoSansGujarati-Bold.ttf")
    if not os.path.exists(font_reg) and os.path.exists(r"C:\Windows\Fonts\shruti.ttf"):
        font_reg = r"C:\Windows\Fonts\shruti.ttf"
        font_bold = r"C:\Windows\Fonts\shrutib.ttf"
    if os.path.exists(font_reg):
        pdf.add_font("NotoSansGujarati", "", font_reg)
        pdf.add_font("NotoSansGujarati", "B", font_bold if os.path.exists(font_bold) else font_reg)
        try:
            pdf.set_text_shaping(True)
        except Exception:
            pass

    has_guj_font = "notosansgujarati" in pdf.fonts

    def is_gujarati(text):
        return any('\u0a80' <= ch <= '\u0aff' for ch in str(text))

    def set_smart_font(text, style='', size=8):
        if is_gujarati(text) and has_guj_font:
            pdf.set_font("NotoSansGujarati", style, size)
        else:
            pdf.set_font("helvetica", style, size)

    def draw_table_header():
        pdf.set_font("helvetica", "B", 8.5)
        pdf.set_text_color(255, 255, 255)
        pdf.set_fill_color(10, 17, 32)
        pdf.set_draw_color(10, 17, 32)

        pdf.set_x(15)
        pdf.cell(8, 8, "Sr.", border=1, align="C", fill=True)
        pdf.cell(36, 8, "Customer Name", border=1, align="C", fill=True)
        pdf.cell(24, 8, "Mobile", border=1, align="C", fill=True)
        pdf.cell(16, 8, "Product", border=1, align="C", fill=True)
        pdf.cell(48, 8, "Booked Yesterday (Handover)", border=1, align="C", fill=True)
        pdf.cell(48, 8, "Booked Tomorrow (Next)", border=1, align="C", fill=True)
        pdf.ln()

    pdf.add_page()
    pdf.set_y(46)

    # Title
    pdf.set_font('helvetica', 'B', 11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 7, "DAILY BOOKINGS & HANDOVER SCHEDULE")
    pdf.ln(7)

    # Gold separator line
    pdf.set_draw_color(212, 175, 55)
    pdf.set_line_width(0.5)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(3.5)

    # KPI summary bar
    b2b_count = sum(1 for r in rows if r.get('yesterday'))
    total_count = len(rows)

    kpi_y = pdf.get_y()
    pdf.set_fill_color(248, 250, 252)
    pdf.set_draw_color(226, 232, 240)
    pdf.set_line_width(0.3)
    pdf.rect(15, kpi_y, 180, 9, 'DF')

    # Date
    pdf.set_xy(18, kpi_y + 2)
    pdf.set_font('helvetica', 'B', 8.5)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(24, 5, "Schedule Date: ")
    pdf.set_font('helvetica', 'B', 9)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(50, 5, full_date_display)

    # Total Costumes
    pdf.set_xy(95, kpi_y + 2)
    pdf.set_font('helvetica', 'B', 8.5)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(28, 5, "Total Costumes: ")
    pdf.set_font('helvetica', 'B', 9)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(18, 5, str(total_count))

    # B2B Handovers
    pdf.set_xy(145, kpi_y + 2)
    pdf.set_font('helvetica', 'B', 8.5)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(26, 5, "B2B Handovers: ")
    pdf.set_font('helvetica', 'B', 9)
    if b2b_count > 0:
        pdf.set_text_color(220, 38, 38)
    else:
        pdf.set_text_color(16, 185, 129)
    pdf.cell(20, 5, f"{b2b_count} item(s)")

    pdf.set_y(kpi_y + 12)

    # Draw Table
    draw_table_header()

    if not rows:
        pdf.set_x(15)
        pdf.set_font('helvetica', 'I', 9)
        pdf.set_text_color(148, 163, 184)
        pdf.cell(180, 14, "No costume bookings scheduled for this date.", border=1, align="C")
    else:
        for idx, r in enumerate(rows):
            # Check for page overflow
            if pdf.get_y() + 8.5 > 270:
                pdf.add_page()
                pdf.set_y(46)
                draw_table_header()

            bg_fill = (idx % 2 == 1)
            pdf.set_x(15)
            if bg_fill:
                pdf.set_fill_color(248, 250, 252)
            else:
                pdf.set_fill_color(255, 255, 255)
            pdf.set_draw_color(226, 232, 240)

            # 1. Sr. (8mm)
            pdf.set_font('helvetica', '', 8)
            pdf.set_text_color(100, 116, 139)
            pdf.cell(8, 7.5, str(idx + 1), border=1, align="C", fill=True)

            # 2. Customer Name (36mm)
            name = str(r.get('name', 'N/A'))
            set_smart_font(name, style='B' if not is_gujarati(name) else '', size=8)
            pdf.set_text_color(15, 23, 42)
            while pdf.get_string_width('  ' + name) > 34 and len(name) > 3:
                name = name[:-2] + '..'
            pdf.cell(36, 7.5, '  ' + name, border=1, align="L", fill=True)

            # 3. Mobile (24mm)
            pdf.set_font('helvetica', '', 8)
            pdf.set_text_color(51, 65, 85)
            pdf.cell(24, 7.5, str(r.get('mobile', 'N/A')), border=1, align="C", fill=True)

            # 4. Product Code (16mm)
            pdf.set_font('helvetica', 'B', 8.5)
            pdf.set_text_color(10, 17, 32)
            pdf.cell(16, 7.5, str(r.get('product', '-')), border=1, align="C", fill=True)

            # 5. Booked Yesterday (48mm)
            y_info = r.get('yesterday')
            if y_info:
                set_smart_font(y_info, size=7.5)
                pdf.set_text_color(185, 28, 28)  # Alert Red
                y_text = str(y_info)
                while pdf.get_string_width('  ' + y_text) > 46 and len(y_text) > 3:
                    y_text = y_text[:-2] + '..'
                pdf.cell(48, 7.5, '  ' + y_text, border=1, align="L", fill=True)
            else:
                pdf.set_font('helvetica', '', 7.5)
                pdf.set_text_color(21, 128, 61)  # Success Green
                pdf.cell(48, 7.5, '  In shop - ready', border=1, align="L", fill=True)

            # 6. Booked Tomorrow (48mm)
            t_info = r.get('tomorrow')
            if t_info:
                set_smart_font(t_info, size=7.5)
                pdf.set_text_color(29, 78, 216)  # Info Blue
                t_text = str(t_info)
                while pdf.get_string_width('  ' + t_text) > 46 and len(t_text) > 3:
                    t_text = t_text[:-2] + '..'
                pdf.cell(48, 7.5, '  ' + t_text, border=1, align="L", fill=True)
            else:
                pdf.set_font('helvetica', '', 7.5)
                pdf.set_text_color(148, 163, 184)  # Muted slate
                pdf.cell(48, 7.5, '  -', border=1, align="L", fill=True)

            pdf.ln()

        # Operational Note
        pdf.ln(3)
        if pdf.get_y() + 10 <= 270:
            pdf.set_x(15)
            pdf.set_font('helvetica', 'I', 7.5)
            pdf.set_text_color(100, 116, 139)
            pdf.cell(180, 5, "* Note: Costumes with Back-to-Back (B2B) handovers must be checked and sanitized immediately upon return.")

    pdf_output = pdf.output()
    if isinstance(pdf_output, (bytes, bytearray)):
        pdf_bytes = bytes(pdf_output)
    else:
        pdf_bytes = pdf_output.encode("latin1")

    pdf_buffer = io.BytesIO(pdf_bytes)
    pdf_buffer.seek(0)

    filename = f"Bookings_{date}.pdf"
    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
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
                if isinstance(customer.get("bookings"), dict):
                    customer["bookings"] = dict(sorted(customer["bookings"].items(), key=lambda item: parse_booking_date(item[0])))
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
        {"$match": {"bookingsArr.v": {"$regex": f"^{re.escape(code.strip().upper())}(\\b|\\-|$)", "$options": "i"}}}, 
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

    # build image path dynamically
    code_upper = code.strip().upper()
    if code_upper.startswith("K"):
        image_url = url_for("static", filename=f"Kediya/{code_upper}.webp")
    elif code_upper.startswith("C"):
        image_url = url_for("static", filename=f"Choli/{code_upper}.webp")
    elif code_upper.startswith("G"):
        image_url = url_for("static", filename=f"Group/{code_upper}.webp")
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

# ------------------ AVAILABLE PRODUCTS (Database-Driven) ------------------
@navaratri.route('/available', methods=['GET', 'POST'])
def available():
    if not session.get('logged_in'):
        return redirect(url_for('navaratri.login'))

    date = None
    filter_val = "all"   # default filter
    remaining_c = []
    remaining_k = []
    remaining_g = []

    # Dynamically fetch active products from database
    active_c = get_active_individual_products("choli")
    active_k = get_active_individual_products("kediya")
    active_g = get_active_group_products()

    if request.method == 'POST':
        date = request.form.get('date')              # YYYY-MM-DD from form
        filter_val = request.form.get('filter', 'all')

        if date:
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
                formatted_date = date_obj.strftime("%d-%m-%y")
            except Exception:
                formatted_date = date

            # Collect booked individual codes for that date
            booked_ind = set()
            for doc in collection.find({}):
                bookings = doc.get("bookings", {})
                if not isinstance(bookings, dict):
                    continue
                if formatted_date in bookings:
                    value = bookings.get(formatted_date, [])
                    if isinstance(value, str):
                        items = [p.strip() for p in value.split(',') if p.strip()]
                    elif isinstance(value, list):
                        items = value
                    else:
                        items = []

                    for p in items:
                        if not isinstance(p, str):
                            continue
                        base_c = parse_product_item(p)[0]
                        if not is_group_code(base_c):
                            booked_ind.add(normalize_product_code(base_c))

            remaining_c = [p for p in active_c if normalize_product_code(p.get("code", "")) not in booked_ind]
            remaining_k = [p for p in active_k if normalize_product_code(p.get("code", "")) not in booked_ind]

            # Calculate date-specific group availability
            for grp in active_g:
                g_code = grp["code"]
                sizes_avail = get_group_size_availability(g_code, date=formatted_date)
                has_avail = any(s["available"] > 0 for s in sizes_avail.values() if s.get("active"))
                if has_avail:
                    grp_copy = dict(grp)
                    grp_copy["size_info"] = sizes_avail
                    remaining_g.append(grp_copy)

    return render_template(
        "navaratri/available.html",
        date=date,
        remaining_c=remaining_c,
        remaining_k=remaining_k,
        remaining_g=remaining_g,
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

def _search_storage(search_type, query):
    query = (query or '').strip()
    if not query:
        return []

    if search_type == 'product':
        reg = f"^{re.escape(query)}"
        raw_products = list(products.find({"_id": {"$regex": reg, "$options": "i"}}))

        all_bags_list = list(bags.find())
        bag_map = {str(b['_id']): b for b in all_bags_list}

        q_upper = query.upper()
        exact_matches = []
        prefix_matches = []

        for p in raw_products:
            p_code = str(p.get('_id', ''))
            if not p_code.upper().startswith(q_upper):
                continue

            b_id = str(p.get('bag_id', ''))
            bag = bag_map.get(b_id)
            if not bag and ObjectId.is_valid(b_id):
                bag = bags.find_one({"_id": ObjectId(b_id)})
                if bag:
                    bag_map[b_id] = bag

            p['bag_name'] = bag.get('name', 'Unknown') if bag else 'Unknown'
            p['bag_description'] = bag.get('description', 'No description') if bag else 'No description'
            p['is_exact'] = (p_code.upper() == q_upper)

            if p['is_exact']:
                exact_matches.append(p)
            else:
                prefix_matches.append(p)

        def sort_key(item):
            code = str(item['_id'])
            m = re.match(r'^([A-Za-z]+)(\d+)$', code)
            if m:
                return (m.group(1).upper(), int(m.group(2)), code)
            return (code.upper(), 0, code)

        prefix_matches.sort(key=sort_key)
        return exact_matches + prefix_matches

    elif search_type == 'bag':
        bag = bags.find_one({"name": {"$regex": f"^{re.escape(query)}$", "$options": "i"}})
        if not bag:
            bag = bags.find_one({"name": {"$regex": f"^{re.escape(query)}", "$options": "i"}})
        if bag:
            bag_id_str = str(bag['_id'])
            return list(products.find({"bag_id": bag_id_str}))
        return []

    return []


@navaratri.route('/api/storage-search')
def api_storage_search():
    if not session.get('logged_in'):
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    search_type = request.args.get('search_type', 'product')
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify({"success": True, "query": "", "search_type": search_type, "total": 0, "results": []})

    results = _search_storage(search_type, query)

    serialized = []
    for item in results:
        serialized.append({
            "_id": str(item.get('_id', '')),
            "bag_id": str(item.get('bag_id', '')),
            "bag_name": str(item.get('bag_name', 'Unknown')),
            "bag_description": str(item.get('bag_description', 'No description')),
            "is_exact": bool(item.get('is_exact', False))
        })

    return jsonify({
        "success": True,
        "query": query,
        "search_type": search_type,
        "total": len(serialized),
        "results": serialized
    })


@navaratri.route('/Storage', methods=['GET', 'POST'])
def Storage():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    # Check for AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.args.get('ajax'):
        search_type = request.args.get('search_type') or request.form.get('search_type', 'product')
        query = (request.args.get('query') or request.form.get('query', '')).strip()
        if not query:
            return jsonify({"success": True, "query": "", "search_type": search_type, "total": 0, "results": []})
        results = _search_storage(search_type, query)
        serialized = []
        for item in results:
            serialized.append({
                "_id": str(item.get('_id', '')),
                "bag_id": str(item.get('bag_id', '')),
                "bag_name": str(item.get('bag_name', 'Unknown')),
                "bag_description": str(item.get('bag_description', 'No description')),
                "is_exact": bool(item.get('is_exact', False))
            })
        return jsonify({
            "success": True,
            "query": query,
            "search_type": search_type,
            "total": len(serialized),
            "results": serialized
        })

    result = None
    search_type = 'product'
    query = ''
    searched = False

    if request.method == 'POST':
        search_type = request.form.get('search_type', 'product')
        query = request.form.get('query', '').strip()
        if query:
            searched = True
            result = _search_storage(search_type, query)

    all_bags = list(bags.find())

    # Generate available codes (for checkboxes)
    db_ind_codes = [p["code"] for p in costumes.find({}, {"code": 1})]
    db_grp_codes = [g["code"] for g in costume_groups.find({}, {"code": 1})]
    all_codes = sorted(db_ind_codes + db_grp_codes, key=lambda x: (x[0], int(x[1:]) if x[1:].isdigit() else 9999))
    if not all_codes:
        all_codes = [f'C{i}' for i in range(1, 151)] + [f'K{i}' for i in range(1, 174)]
    used_codes = [p['_id'] for p in products.find({}, {"_id": 1})]
    available_codes = [c for c in all_codes if c not in used_codes]

    return render_template(
        'navaratri/Storage.html',
        result=result,
        search_type=search_type,
        query=query,
        searched=searched,
        bags=all_bags,
        available_codes=available_codes
    )


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
    "Lambha", "Dehgam", "Patan", "Palanpur", "Unjha", "Visnagar", "Mehsana", "Kalol", "Chhatral", "Kadi", "Himmatnagar", "Gandhinagar",
    "Nadiad", "Anand", "Bakrol", "Vadtal", "Vadodara", "Surat", "Rajkot", "Kheda", "Sanand", "Dholka", "Bavla",
    "Aslali", "Bareja", "Changodar", "Moraiya",
    "Nava Vadaj", "Vadaj", "Jay Hind", "Arbuda Nagar", "Haridarshan", "Hathijan", "Vivekanand Nagar",
    "Saijpur Bogha", "Saijpur", "Jivraj Park", "South Bopal", "Bopal", "Ghatlodiya", "Gordhanwadi", "Maniyasa", "Laxminarayan",
    "Jashodanagar", "Jashoda Nagar", "Bhadwat Nagar", "Prahlad Nagar", "Prahladnagar", "Prerna Tirth", "Satelite",
    "New Maninagar", "New Vatva", "Shahwadi", "Motipura", "Sureliya", "Khodiyar Nagar", "Rajendra Park", "Saheed Circle", "Aman Nagar",
    "Vastral", "Maninagar", "Khokhra", "Isanpur", "Amraiwadi", "Ghodasar",
    "Vatva", "Odhav", "Hatkeshwar", "CTM", "Nikol", "Ramol", "Narol",
    "Bapunagar", "Saraspur", "Asarwa", "Shahibaug", "Naroda", "Rakhial",
    "Sarangpur", "Kalupur", "Astodia", "Raipur", "Lal Darwaja", "Geeta Mandir",
    "Shahpur", "Dani Limda", "Navrangpura", "Satellite", "Vastrapur", "Bodakdev",
    "Thaltej", "Sola", "Gota", "Ghatlodia", "Naranpura", "Paldi", "Vasna",
    "Ranip", "Sabarmati", "Chandkheda"
]

AREA_COORDINATES = {
    "Lambha": [22.9238, 72.5843],
    "Dehgam": [23.1670, 72.8120],
    "Patan": [23.8493, 72.1266],
    "Palanpur": [24.1724, 72.4346],
    "Unjha": [23.8043, 72.3942],
    "Visnagar": [23.6961, 72.5484],
    "Mehsana": [23.5880, 72.3693],
    "Kalol": [23.2393, 72.4962],
    "Chhatral": [23.2800, 72.4500],
    "Kadi": [23.3000, 72.3300],
    "Himmatnagar": [23.5979, 72.9698],
    "Gandhinagar": [23.2156, 72.6369],
    "Nadiad": [22.6916, 72.8634],
    "Anand": [22.5645, 72.9289],
    "Bakrol": [22.5480, 72.9350],
    "Vadtal": [22.5920, 72.8880],
    "Vadodara": [22.3072, 73.1812],
    "Surat": [21.1702, 72.8311],
    "Rajkot": [22.3039, 70.8022],
    "Kheda": [22.7500, 72.6800],
    "Sanand": [22.9910, 72.3810],
    "Dholka": [22.7200, 72.4700],
    "Bavla": [22.8300, 72.3600],
    "Aslali": [22.9210, 72.6010],
    "Bareja": [22.8850, 72.6050],
    "Changodar": [22.9230, 72.4410],
    "Moraiya": [22.9150, 72.4350],
    "Nava Vadaj": [23.0640, 72.5690],
    "Vadaj": [23.0640, 72.5690],
    "Jay Hind": [22.9920, 72.5980],
    "Arbuda Nagar": [23.0250, 72.6630],
    "Haridarshan": [23.0450, 72.6680],
    "Hathijan": [22.9280, 72.6390],
    "Vivekanand Nagar": [22.9280, 72.6390],
    "Saijpur Bogha": [23.0640, 72.6280],
    "Saijpur": [23.0640, 72.6280],
    "Jivraj Park": [23.0010, 72.5410],
    "South Bopal": [23.0300, 72.4640],
    "Bopal": [23.0300, 72.4640],
    "Ghatlodiya": [23.0682, 72.5358],
    "Gordhanwadi": [22.9980, 72.5920],
    "Maniyasa": [22.9976, 72.6009],
    "Laxminarayan": [22.9554, 72.6240],
    "Jashodanagar": [22.9850, 72.6250],
    "Jashoda Nagar": [22.9850, 72.6250],
    "Bhadwat Nagar": [22.9910, 72.6080],
    "Prahlad Nagar": [23.0125, 72.5118],
    "Prahladnagar": [23.0125, 72.5118],
    "Prerna Tirth": [23.0300, 72.5176],
    "Satelite": [23.0300, 72.5176],
    "Vastral": [23.0041, 72.6617],
    "Maninagar": [22.9976, 72.6009],
    "New Maninagar": [22.9850, 72.6150],
    "Khokhra": [22.9983, 72.6167],
    "Isanpur": [22.9731, 72.5976],
    "Amraiwadi": [23.0039, 72.6288],
    "Ghodasar": [22.9815, 72.6094],
    "Vatva": [22.9554, 72.6240],
    "New Vatva": [22.9480, 72.6310],
    "Odhav": [23.0232, 72.6698],
    "Hatkeshwar": [23.0012, 72.6225],
    "CTM": [22.9908, 72.6321],
    "Nikol": [23.0483, 72.6717],
    "Ramol": [22.9840, 72.6582],
    "Narol": [22.9634, 72.5891],
    "Shahwadi": [22.9570, 72.5780],
    "Motipura": [22.9610, 72.5820],
    "Sureliya": [23.0010, 72.6510],
    "Khodiyar Nagar": [23.0390, 72.6350],
    "Rajendra Park": [23.0210, 72.6610],
    "Aman Nagar": [23.0240, 72.6650],
    "Saheed Circle": [23.0490, 72.6730],
    "Bapunagar": [23.0371, 72.6231],
    "Saraspur": [23.0298, 72.6080],
    "Asarwa": [23.0494, 72.6033],
    "Shahibaug": [23.0560, 72.5925],
    "Naroda": [23.0725, 72.6656],
    "Rakhial": [23.0180, 72.6210],
    "Sarangpur": [23.0215, 72.5990],
    "Kalupur": [23.0260, 72.5950],
    "Astodia": [23.0170, 72.5910],
    "Raipur": [23.0185, 72.5940],
    "Lal Darwaja": [23.0240, 72.5810],
    "Geeta Mandir": [23.0110, 72.5880],
    "Shahpur": [23.0350, 72.5780],
    "Dani Limda": [22.9950, 72.5810],
    "Navrangpura": [23.0366, 72.5611],
    "Satellite": [23.0300, 72.5176],
    "Vastrapur": [23.0350, 72.5293],
    "Bodakdev": [23.0410, 72.5115],
    "Thaltej": [23.0500, 72.5070],
    "Sola": [23.0680, 72.5180],
    "Gota": [23.0970, 72.5310],
    "Ghatlodia": [23.0682, 72.5358],
    "Naranpura": [23.0520, 72.5530],
    "Paldi": [23.0120, 72.5620],
    "Vasna": [22.9980, 72.5520],
    "Ranip": [23.0800, 72.5710],
    "Sabarmati": [23.0845, 72.5802],
    "Chandkheda": [23.1114, 72.5835]
}


@navaratri.route("/navaratri-customers")
def navaratri_customers_list():
    if not session.get('logged_in'):
        return redirect('/admin')

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

    # Dynamic Custom Localities Merge
    from website.general.db import custom_localities
    active_localities = list(KNOWN_LOCALITIES)
    active_coords = dict(AREA_COORDINATES)
    try:
        for cloc in custom_localities.find():
            cname = cloc.get("name")
            clat = cloc.get("lat")
            clng = cloc.get("lng")
            if cname and clat is not None and clng is not None:
                if cname not in active_localities:
                    active_localities.insert(0, cname)
                active_coords[cname] = [float(clat), float(clng)]
    except Exception:
        pass

    # Area Strength Analytics & Verified Locality Mapping
    from website.general.utils import resolve_customer_locality

    area_counts = {}
    total_with_addr = 0
    unmapped_count = 0

    for c in all_customers:
        matched_loc = resolve_customer_locality(c, active_localities)
        if matched_loc:
            c["mapped_locality"] = matched_loc
            area_counts[matched_loc] = area_counts.get(matched_loc, 0) + 1
            total_with_addr += 1
        else:
            c["mapped_locality"] = ""
            unmapped_count += 1

    sorted_areas = sorted(area_counts.items(), key=lambda x: x[1], reverse=True)
    top_areas = []
    map_localities = []

    for loc, count in sorted_areas:
        pct = round((count / max(total_with_addr, 1)) * 100, 1)
        item = {"area": loc, "count": count, "percentage": pct}
        if len(top_areas) < 5:
            top_areas.append(item)
        if loc in active_coords:
            item_map = dict(item)
            item_map["lat"] = active_coords[loc][0]
            item_map["lng"] = active_coords[loc][1]
            map_localities.append(item_map)

    # Active Bookings Mobile List
    active_mobiles = set()
    if collection is not None:
        try:
            active_mobiles = set(collection.distinct("mobile"))
        except Exception:
            pass

    id_to_loc = {str(c["_id"]): c.get("mapped_locality", "") for c in all_customers}

    if search:
        customers = list(ncustomers.find(query).sort("updated_at", -1))
        for c in customers:
            c["mapped_locality"] = id_to_loc.get(str(c["_id"]), "")
    else:
        customers = all_customers

    return render_template(
        "navaratri/navaratri_customers.html",
        customers=customers,
        total_count=len(all_customers),
        active_bookers_count=len(active_mobiles),
        total_with_addr=total_with_addr,
        unmapped_count=unmapped_count,
        top_areas=top_areas,
        map_localities=map_localities,
        area_map_data=map_localities,
        search=search
    )


@navaratri.route("/navaratri_logs")
def navaratri_logs():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    from website.general.utils import format_log_timestamp
    selected_cycle = get_selected_cycle()
    logs = []
    if selected_cycle:
        collection_name = selected_cycle.get("collection_name")
        if collection_name:
            logs_col = db[f"{collection_name}_logs"]
            raw_logs = list(logs_col.find().sort("timestamp", -1))
            for log in raw_logs:
                d_str, t_str, sort_ts = format_log_timestamp(
                    log.get("timestamp"),
                    log.get("date_stamp", ""),
                    log.get("time_stamp", "")
                )
                log["date_stamp"] = d_str
                log["time_stamp"] = t_str
                log["sort_ts"] = sort_ts
                logs.append(log)

    return render_template(
        "navaratri/navaratri_logs.html",
        logs=logs,
        selected_cycle=selected_cycle
    )


@navaratri.route("/navaratri_logs/api")
def navaratri_logs_api():
    if not session.get('logged_in'):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    from website.general.utils import format_log_timestamp
    selected_cycle = get_selected_cycle()
    logs_data = []
    if selected_cycle:
        collection_name = selected_cycle.get("collection_name")
        if collection_name:
            logs_col = db[f"{collection_name}_logs"]
            raw_logs = list(logs_col.find().sort("timestamp", -1))
            for log in raw_logs:
                d_str, t_str, sort_ts = format_log_timestamp(
                    log.get("timestamp"),
                    log.get("date_stamp", ""),
                    log.get("time_stamp", "")
                )
                logs_data.append({
                    "id": str(log.get("_id", "")),
                    "name": log.get("name", "") or "—",
                    "mobile": log.get("mobile", "") or "—",
                    "action": log.get("action", ""),
                    "details": log.get("details", ""),
                    "date_stamp": d_str,
                    "time_stamp": t_str,
                    "sort_ts": sort_ts
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


# ==============================================================================
# 🏷️ ADMIN: COSTUME MANAGER (INVENTORY, GROUPS & RENTAL AVAILABILITY)
# ==============================================================================
@navaratri.route("/navaratri_products", methods=["GET"])
@navaratri.route("/navaratri/products", methods=["GET"])
@navaratri.route("/navaratri/costume-manager", methods=["GET"])
@navaratri.route("/costume_manager", methods=["GET"])
@navaratri.route("/costume-manager", methods=["GET"])
def admin_navaratri_products():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    products_list = get_all_navaratri_products()
    groups_list = get_all_costume_groups()

    total_count = len(products_list)
    choli_count = sum(1 for p in products_list if p.get('code', '').upper().startswith('C'))
    kediya_count = sum(1 for p in products_list if p.get('code', '').upper().startswith('K'))
    available_count = sum(1 for p in products_list if p.get('on_rent', True))
    sold_count = total_count - available_count

    group_total_count = len(groups_list)
    group_active_count = sum(1 for g in groups_list if g.get('on_rent', True))

    return render_template(
        "navaratri/products_status.html",
        products=products_list,
        groups=groups_list,
        total_count=total_count,
        choli_count=choli_count,
        kediya_count=kediya_count,
        available_count=available_count,
        sold_count=sold_count,
        group_total_count=group_total_count,
        group_active_count=group_active_count
    )

@navaratri.route("/api/navaratri/verify-password", methods=["POST"])
def api_verify_navaratri_password():
    if not session.get('logged_in'):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.get_json() or {}
    password = str(data.get("password") or "").strip()

    if verify_admin_password(password):
        return jsonify({"success": True, "message": "Password verified."})
    return jsonify({"success": False, "message": "Incorrect password."}), 401

@navaratri.route("/api/navaratri/product-profile/<product_code>", methods=["GET"])
def api_navaratri_product_profile(product_code):
    if not session.get('logged_in'):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    code_clean = str(product_code).strip().upper()
    is_group = is_group_code(code_clean)

    if is_group:
        group_doc = get_group(code_clean)
        if not group_doc:
            return jsonify({"success": False, "message": f"Costume group '{code_clean}' not found in catalog."}), 404
        is_choli = group_doc.get("type") == "choli"
        category_label = f"Group {'Chaniya Choli' if is_choli else 'Traditional Kediya'}"
        image_name = group_doc.get("image", f"{code_clean}.webp")
        image_url = url_for('static', filename=f'GroupJpg/{code_clean}.jpg')
        fallback_url = url_for('static', filename=f'Group/{image_name}')
        on_rent = bool(group_doc.get("on_rent", True))
        sold_info = None
        sizes_data = group_doc.get("sizes", {})
    else:
        product = get_navaratri_product(code_clean)
        if not product:
            try:
                sync_navaratri_products()
                product = get_navaratri_product(code_clean)
            except Exception:
                pass

        if not product:
            return jsonify({"success": False, "message": f"Product '{code_clean}' not found in catalog."}), 404

        is_choli = code_clean.startswith('C')
        category_label = "Chaniya Choli" if is_choli else ("Traditional Kediya" if code_clean.startswith('K') else "Costume")

        # Image URLs
        image_name = product.get("image", "")
        if is_choli:
            image_url = url_for('static', filename=f'CholiJpg/{code_clean}.jpg')
            fallback_url = url_for('static', filename=f'Choli/{image_name}') if image_name else '/static/Home_Img/favicon.png'
        else:
            image_url = url_for('static', filename=f'KediyaJpg/{code_clean}.jpg')
            fallback_url = url_for('static', filename=f'Kediya/{image_name}') if image_name else '/static/Home_Img/favicon.png'
        on_rent = bool(product.get("on_rent", True))
        sold_info = product.get("sold_info")
        sizes_data = None

    # Storage Info
    storage_info = None
    try:
        storage_results = _search_storage('product', code_clean)
        for s in storage_results:
            if s.get('is_exact') or str(s.get('_id', '')).upper() == code_clean:
                storage_info = {
                    "bag_id": s.get("bag_id", ""),
                    "bag_name": s.get("bag_name", "Unknown"),
                    "bag_description": s.get("bag_description", "")
                }
                break
    except Exception:
        pass

    # Bookings search across ONLY the current selected cycle
    selected_cycle = get_selected_cycle()
    selected_cycle_name = selected_cycle.get("name", "Current Cycle") if selected_cycle else "Current Cycle"
    selected_cname = selected_cycle.get("collection_name") if selected_cycle else None

    bookings = []
    existing_collections = set(db.list_collection_names())

    if selected_cname and selected_cname in existing_collections:
        try:
            for doc in db[selected_cname].find():
                cust_bookings = doc.get("bookings", {})
                if not isinstance(cust_bookings, dict):
                    continue
                for d_str, prods in cust_bookings.items():
                    matched = False
                    matched_items = []
                    if isinstance(prods, list):
                        for p in prods:
                            base_c, sz, q = parse_product_item(p)
                            if normalize_product_code(base_c) == normalize_product_code(code_clean):
                                matched = True
                                matched_items.append(p)
                    if matched:
                        total_p = doc.get("total_price", 0) or 0
                        given_p = doc.get("given_price", 0) or 0
                        bookings.append({
                            "date": d_str,
                            "cycle_name": selected_cycle_name,
                            "is_current_cycle": True,
                            "customer_id": str(doc.get("_id", "")),
                            "customer_name": doc.get("Name") or "Unnamed Customer",
                            "customer_mobile": doc.get("mobile") or "",
                            "customer_address": doc.get("address") or "",
                            "customer_deposit": str(doc.get("deposit") or "Not provided"),
                            "customer_reference": doc.get("reference") or "None",
                            "customer_group": doc.get("group") or "None",
                            "customer_total_price": total_p,
                            "customer_given_price": given_p,
                            "customer_remaining": total_p - given_p,
                            "booked_items": matched_items,
                            "all_customer_bookings": cust_bookings
                        })
        except Exception as e:
            current_app.logger.error(f"Error scanning bookings for product {code_clean} in {selected_cname}: {e}")

    def sort_key(b):
        d_str = b.get("date", "")
        for fmt in ("%d-%m-%y", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(d_str, fmt)
            except ValueError:
                pass
        return datetime.min

    bookings.sort(key=sort_key)

    return jsonify({
        "success": True,
        "product": {
            "code": code_clean,
            "is_group": is_group,
            "image_url": image_url,
            "fallback_url": fallback_url,
            "category": category_label,
            "on_rent": on_rent,
            "sold_info": sold_info,
            "sizes": sizes_data,
            "storage": storage_info
        },
        "cycle_name": selected_cycle_name,
        "bookings": bookings,
        "total_bookings": len(bookings)
    })


@navaratri.route("/sell_product", methods=["GET", "POST"])
@navaratri.route("/sell_costume", methods=["GET", "POST"])
@navaratri.route("/navaratri_sell", methods=["GET", "POST"])
def navaratri_sell():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    if request.method == "POST":
        data = request.get_json(silent=True) if request.is_json else request.form
        name = str(data.get("name") or "").strip()
        mobile = str(data.get("mobile") or "").strip()
        address = str(data.get("address") or "").strip()
        reference = str(data.get("reference") or "").strip()
        password = str(data.get("password") or "").strip()
        codes = data.get("codes") or []
        if not codes and data.get("code"):
            codes = [data.get("code")]
        total_price = data.get("total_price", 0)
        given_price = data.get("given_price", 0)

        success, message, sale_id, sale_data, status_code = record_multiple_costume_sale(
            name=name,
            mobile=mobile,
            address=address,
            reference=reference,
            codes=codes,
            total_price=total_price,
            given_price=given_price,
            password=password
        )

        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            bill_url = url_for('navaratri.download_customer', id=sale_id) if sale_id else ""
            bill_page_url = url_for('navaratri.download_bill_page', id=sale_id) if sale_id else ""
            return jsonify({
                "success": success,
                "message": message,
                "customer_id": sale_id,
                "bill_url": bill_url,
                "bill_page_url": bill_page_url,
                "data": sale_data
            }), status_code

        if success and sale_id:
            flash(f"✅ {message}", "success")
            return redirect(url_for('navaratri.download_bill_page', id=sale_id))
        else:
            flash(f"❌ {message}", "danger")
            return redirect(url_for('navaratri.navaratri_sell'))

    products_list = get_all_navaratri_products()
    total_count = len(products_list)
    available_count = sum(1 for p in products_list if p.get('on_rent', True))
    sold_products = [p for p in products_list if not p.get('on_rent', True)]
    sold_count = len(sold_products)
    prefill_code = request.args.get('code', '').strip().upper()

    return render_template(
        "navaratri/sell_costume.html",
        products=products_list,
        total_count=total_count,
        available_count=available_count,
        sold_count=sold_count,
        sold_products=sold_products,
        prefill_code=prefill_code
    )


@navaratri.route("/api/navaratri/sell-costumes", methods=["POST"])
def api_sell_costumes():
    if not session.get('logged_in'):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    name = str(data.get("name") or "").strip()
    mobile = str(data.get("mobile") or "").strip()
    address = str(data.get("address") or "").strip()
    reference = str(data.get("reference") or "").strip()
    password = str(data.get("password") or "").strip()
    codes = data.get("codes") or []
    if not codes and data.get("code"):
        codes = [data.get("code")]
    total_price = data.get("total_price", 0)
    given_price = data.get("given_price", 0)

    success, message, sale_id, sale_data, status_code = record_multiple_costume_sale(
        name=name,
        mobile=mobile,
        address=address,
        reference=reference,
        codes=codes,
        total_price=total_price,
        given_price=given_price,
        password=password
    )

    bill_url = url_for('navaratri.download_customer', id=sale_id) if sale_id else ""
    bill_page_url = url_for('navaratri.download_bill_page', id=sale_id) if sale_id else ""

    return jsonify({
        "success": success,
        "message": message,
        "customer_id": sale_id,
        "bill_url": bill_url,
        "bill_page_url": bill_page_url,
        "data": sale_data
    }), status_code


@navaratri.route("/api/navaratri/product-info/<code>", methods=["GET"])
def api_navaratri_product_info(code):
    if not session.get('logged_in'):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    code_clean = str(code or "").strip().upper()
    if not code_clean:
        return jsonify({"success": False, "message": "Product code is required."}), 400

    product = get_navaratri_product(code_clean)
    if not product:
        return jsonify({
            "success": False,
            "found": False,
            "message": f"Costume code '{code_clean}' does not exist in the Navaratri collection."
        }), 404

    is_choli = code_clean.startswith('C')
    category = "Choli" if is_choli else "Kediya"
    image_filename = product.get("image") or f"{code_clean}.webp"

    jpg_folder = "CholiJpg" if is_choli else "KediyaJpg"
    thumb_url = f"/static/{jpg_folder}/{code_clean}.jpg"
    orig_url = f"/static/{category}/{image_filename}"

    return jsonify({
        "success": True,
        "found": True,
        "code": code_clean,
        "category": category,
        "image": image_filename,
        "thumb_url": thumb_url,
        "orig_url": orig_url,
        "on_rent": product.get("on_rent", True),
        "sold_info": product.get("sold_info")
    })


@navaratri.route("/api/navaratri/sell-product", methods=["POST"])
def api_sell_navaratri_product():
    if not session.get('logged_in'):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.get_json() or {}
    code = str(data.get("code") or "").strip().upper()
    password = str(data.get("password") or "").strip()
    buyer_name = str(data.get("buyer_name") or "").strip() or None
    buyer_mobile = str(data.get("buyer_mobile") or "").strip() or None
    price = str(data.get("price") or "").strip() or None
    notes = str(data.get("notes") or "").strip() or None

    success, message, status_code = sell_navaratri_product(
        code, password, buyer_name=buyer_name, buyer_mobile=buyer_mobile, price=price, notes=notes
    )
    return jsonify({"success": success, "message": message}), status_code

@navaratri.route("/api/navaratri/restore-product", methods=["POST"])
def api_restore_navaratri_product():
    if not session.get('logged_in'):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.get_json() or {}
    code = str(data.get("code") or "").strip().upper()
    password = str(data.get("password") or "").strip()

    success, message, status_code = restore_navaratri_product(code, password)
    return jsonify({"success": success, "message": message}), status_code

@navaratri.route("/api/navaratri/sync-products", methods=["POST"])
def api_sync_navaratri_products():
    if not session.get('logged_in'):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    try:
        total, inserted = sync_navaratri_products()
        return jsonify({
            "success": True,
            "message": f"Successfully synchronized {total} products ({inserted} newly added)."
        })
    except Exception as e:
        return jsonify({"success": False, "message": "Failed to synchronize products."}), 500


# ==============================================================================
# 🛍️ ADMIN: NAVARATRI PRODUCT MANAGEMENT (INDIVIDUAL BULK & GROUPS)
# ==============================================================================
@navaratri.route("/navaratri/admin/products", methods=["GET"])
@navaratri.route("/navaratri_admin/products", methods=["GET"])
def navaratri_admin_products_page():
    if not session.get('logged_in'):
        return redirect(url_for('navaratri.login'))
    return render_template("navaratri/admin_products.html")


@navaratri.route("/api/navaratri/admin/upload-individual", methods=["POST"])
def api_navaratri_admin_upload_individual():
    if not session.get('logged_in'):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    files = request.files.getlist("images")
    if not files:
        files = request.files.getlist("files")
    if not files:
        files = [f for f in request.files.values()]

    if not files or all(not f.filename for f in files):
        return jsonify({"success": False, "message": "No files received for bulk upload."}), 400

    success, message, results, status_code = save_individual_bulk_upload(files)
    return jsonify({
        "success": success,
        "message": message,
        "results": results
    }), status_code


@navaratri.route("/api/navaratri/admin/create-groups", methods=["POST"])
def api_navaratri_admin_create_groups():
    if not session.get('logged_in'):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    import json
    try:
        groups_raw = request.form.get("groups")
        if not groups_raw:
            return jsonify({"success": False, "message": "No group payload received."}), 400

        try:
            groups_list = json.loads(groups_raw)
        except Exception as e:
            return jsonify({"success": False, "message": f"Malformed group JSON payload: {str(e)}"}), 400

        files_dict = request.files.to_dict()
        success, message, results, status_code = validate_and_create_groups(groups_list, files_dict)
        return jsonify({
            "success": success,
            "message": message,
            "results": results
        }), status_code

    except Exception as e:
        current_app.logger.error(f"Error in api_navaratri_admin_create_groups: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500


@navaratri.route("/api/navaratri/group/<group_code>/add-size", methods=["POST"])
def api_navaratri_group_add_size(group_code):
    if not session.get('logged_in'):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.get_json() or {}
    size = data.get("size")
    quantity = data.get("quantity")
    success, message, status_code = add_group_size(group_code, size, quantity)
    return jsonify({"success": success, "message": message}), status_code


@navaratri.route("/api/navaratri/group/<group_code>/update-size", methods=["POST"])
def api_navaratri_group_update_size(group_code):
    if not session.get('logged_in'):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.get_json() or {}
    size = data.get("size")
    quantity = data.get("quantity")
    success, message, status_code = update_group_size_quantity(group_code, size, quantity)
    return jsonify({"success": success, "message": message}), status_code


@navaratri.route("/api/navaratri/group/<group_code>/toggle-size", methods=["POST"])
def api_navaratri_group_toggle_size(group_code):
    if not session.get('logged_in'):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.get_json() or {}
    size = data.get("size")
    active = data.get("active")
    success, message, status_code = toggle_group_size_active(group_code, size, active)
    return jsonify({"success": success, "message": message}), status_code


@navaratri.route("/api/navaratri/group/<group_code>/delete-size", methods=["POST"])
def api_navaratri_group_delete_size(group_code):
    if not session.get('logged_in'):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.get_json() or {}
    size = data.get("size")
    success, message, status_code = delete_or_disable_group_size(group_code, size)
    return jsonify({"success": success, "message": message}), status_code


@navaratri.route("/api/navaratri/toggle-status", methods=["POST"])
def api_navaratri_toggle_status():
    if not session.get('logged_in'):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.get_json() or {}
    code = data.get("code")
    on_rent = data.get("on_rent")
    success, message, status_code = toggle_product_status(code, on_rent)
    return jsonify({"success": success, "message": message}), status_code


@navaratri.route("/navaratri/product-image/<code>", methods=["GET"])
@navaratri.route("/product-image/<code>", methods=["GET"])
def serve_navaratri_product_image(code):
    base_code, _, _ = parse_product_item(code)
    clean_code = normalize_product_code(base_code)
    prefer_jpg = request.args.get("format") == "jpg"

    static_dir = current_app.static_folder or os.path.join(os.getcwd(), 'website', 'static')

    if clean_code.startswith("G"):
        subdirs = ["GroupJpg", "Group"] if prefer_jpg else ["Group", "GroupJpg"]
    elif clean_code.startswith("C"):
        subdirs = ["CholiJpg", "Choli"] if prefer_jpg else ["Choli", "CholiJpg"]
    elif clean_code.startswith("K"):
        subdirs = ["KediyaJpg", "Kediya"] if prefer_jpg else ["Kediya", "KediyaJpg"]
    else:
        subdirs = ["Choli", "Kediya", "Group", "CholiJpg", "KediyaJpg", "GroupJpg"]

    extensions = [".jpg", ".jpeg", ".webp", ".png"] if prefer_jpg else [".webp", ".jpg", ".jpeg", ".png"]

    for sub in subdirs:
        for ext in extensions:
            target = os.path.join(static_dir, sub, f"{clean_code}{ext}")
            if os.path.exists(target):
                mimetype = "image/jpeg" if ext in [".jpg", ".jpeg"] else ("image/webp" if ext == ".webp" else "image/png")
                return send_file(target, mimetype=mimetype, max_age=86400)

    # Fallback to favicon / placeholder
    fallback = os.path.join(static_dir, "Home_Img", "favicon.png")
    if os.path.exists(fallback):
        return send_file(fallback, mimetype="image/png", max_age=86400)

    return Response("Image not found", status=404)

