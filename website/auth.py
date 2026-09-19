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

