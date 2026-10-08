# =========================
# STANDARD LIBRARIES
# =========================
import os
import io
import csv
import json
from datetime import datetime, timedelta
from collections import Counter


# =========================
# THIRD PARTY LIBRARIES
# =========================
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, jsonify, send_file, send_from_directory,
    current_app, Response, make_response
)
from pymongo import MongoClient
from bson.objectid import ObjectId
from dotenv import load_dotenv
from fpdf import FPDF
import qrcode


# =========================
# FLASK APP / DB SETUP
# =========================
auth = Blueprint("auth", __name__)

from .general.db import (
    db, collection, fancy_2024_2025, fancy_collection,
    products_collection, bags, products, fcustomers, finventory,
    ADMIN_ID, ADMIN_PASS
)

@auth.route('/admin')
def admin():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))
    resp = make_response(render_template("general/admin.html"))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    return resp


@auth.route('/admin/data-review')
def admin_data_review():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))
    from .general.data_review import scan_suspicious_entities
    candidates = scan_suspicious_entities()
    
    total_candidates = len(candidates)
    total_customers = sum(1 for c in candidates if c.get('has_customer'))
    total_bookings = sum(c.get('bookings_count', 0) for c in candidates)
    total_logs = sum(c.get('logs_count', 0) for c in candidates)
    total_retained = sum(1 for c in candidates if c.get('is_retained'))

    resp = make_response(render_template(
        "general/admin_data_review.html",
        candidates=candidates,
        stats={
            "total_candidates": total_candidates,
            "total_customers": total_customers,
            "total_bookings": total_bookings,
            "total_logs": total_logs,
            "total_retained": total_retained
        }
    ))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    return resp


@auth.route('/admin/data-review/export', methods=['GET', 'POST'])
def admin_data_review_export():
    if not session.get('logged_in'):
        if request.is_json or request.args.get('format') == 'json' or request.headers.get('Accept') == 'application/json':
            return jsonify({"success": False, "error": "Unauthorized: Administrator login required."}), 401
        return redirect(url_for('auth.login'))
    from .general.data_review import create_full_backup
    filepath, filename, payload = create_full_backup(reason="admin_manual_export")
    if request.args.get('format') == 'json' or request.headers.get('Accept') == 'application/json':
        return jsonify({
            "success": True,
            "backup_file": filepath,
            "filename": filename,
            "total_entities": payload.get("total_entities")
        })
    return send_file(filepath, as_attachment=True, download_name=filename, mimetype="application/json")


@auth.route('/admin/data-review/retain', methods=['POST'])
def admin_data_review_retain():
    if not session.get('logged_in'):
        if request.is_json:
            return jsonify({"success": False, "error": "Unauthorized: Administrator login required."}), 401
        return redirect(url_for('auth.login'))
    from .general.data_review import mark_entity_retained
    mobile = request.form.get('mobile') or (request.json and request.json.get('mobile'))
    notes = request.form.get('notes') or (request.json and request.json.get('notes')) or "Certified genuine by administrator"
    if not mobile:
        flash("Mobile number is required to mark as retained.", "error")
        return redirect(url_for('auth.admin_data_review'))
    mark_entity_retained(mobile, notes=notes)
    flash(f"🛡️ Record for mobile {mobile} has been intentionally marked as RETAINED / GENUINE.", "success")
    if request.is_json:
        return jsonify({"success": True, "message": f"Entity {mobile} retained successfully."})
    return redirect(url_for('auth.admin_data_review'))


@auth.route('/admin/data-review/unretain', methods=['POST'])
def admin_data_review_unretain():
    if not session.get('logged_in'):
        if request.is_json:
            return jsonify({"success": False, "error": "Unauthorized: Administrator login required."}), 401
        return redirect(url_for('auth.login'))
    from .general.data_review import unmark_entity_retained
    mobile = request.form.get('mobile') or (request.json and request.json.get('mobile'))
    if not mobile:
        flash("Mobile number is required.", "error")
        return redirect(url_for('auth.admin_data_review'))
    unmark_entity_retained(mobile)
    flash(f"ℹ️ Retention flag removed for mobile {mobile}.", "info")
    if request.is_json:
        return jsonify({"success": True, "message": f"Retention removed for {mobile}."})
    return redirect(url_for('auth.admin_data_review'))


@auth.route('/admin/data-review/delete', methods=['POST'])
def admin_data_review_delete():
    if not session.get('logged_in'):
        if request.is_json:
            return jsonify({"success": False, "error": "Unauthorized: Administrator login required."}), 401
        return redirect(url_for('auth.login'))
    from .general.data_review import safe_delete_candidate_entity
    
    mobile = request.form.get('mobile') or (request.json and request.json.get('mobile'))
    password = request.form.get('admin_password') or (request.json and request.json.get('admin_password'))
    
    if not mobile or not password:
        msg = "Both mobile number and administrator password are required for confirmed deletion."
        if request.is_json:
            return jsonify({"success": False, "error": msg}), 400
        flash(f"❌ {msg}", "error")
        return redirect(url_for('auth.admin_data_review'))

    result = safe_delete_candidate_entity(mobile, password)
    if not result.get("success"):
        err = result.get("error", "Deletion failed.")
        if request.is_json:
            return jsonify({"success": False, "error": err}), 400
        flash(f"❌ {err}", "error")
        return redirect(url_for('auth.admin_data_review'))

    success_msg = f"✅ Safely removed {result.get('total_deleted')} test document(s) for mobile {mobile}. Immutable backup preserved at: {result.get('backup_filename')}"
    if request.is_json:
        return jsonify(result)
    flash(success_msg, "success")
    return redirect(url_for('auth.admin_data_review'))


@auth.route('/login', methods=['GET', 'POST'])
def login():
    # If already logged in, redirect directly to admin panel
    if session.get('logged_in'):
        return redirect(url_for('auth.admin'))

    if request.method == 'POST':
        entered_id = (request.form.get('id') or '').strip()
        entered_pass = (request.form.get('password') or '').strip()

        # Support configured environment credentials as well as default admin credentials
        valid_id = (entered_id == str(ADMIN_ID).strip()) or (entered_id == "IMGTRADE1008")
        valid_pass = (entered_pass == str(ADMIN_PASS).strip()) or (entered_pass == "212010")

        if valid_id and valid_pass:
            session.permanent = True
            session['logged_in'] = True
            flash("✅ Login successful!", "success")
            return redirect(url_for('auth.admin'))
        else:
            flash("❌ Invalid credentials!", "error")
            resp = make_response(render_template('general/login.html'))
            resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
            resp.headers['Pragma'] = 'no-cache'
            return resp

    resp = make_response(render_template('general/login.html'))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    return resp


@auth.route('/logout')
def logout():
    session.clear()
    flash("🔒 You have been logged out.", "info")
    resp = redirect(url_for('auth.login'))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    return resp

