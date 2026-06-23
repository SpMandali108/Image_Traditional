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
    current_app, Response
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
    return render_template("general/admin.html")


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        entered_id = request.form.get('id')
        entered_pass = request.form.get('password')

        if entered_id == ADMIN_ID and entered_pass == ADMIN_PASS:
            session['logged_in'] = True
            flash("✅ Login successful!", "success")
            return redirect(url_for('auth.admin'))
        else:
            flash("❌ Invalid credentials!", "error")
            return render_template('general/login.html')
    return render_template('general/login.html')


@auth.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash("🔒 You have been logged out.", "info")
    return redirect(url_for('auth.login'))

