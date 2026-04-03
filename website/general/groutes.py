import json
import os

from flask import Blueprint, render_template, request, redirect, send_from_directory, url_for, session, jsonify
from datetime import datetime
from bson.objectid import ObjectId
import re
from flask import current_app, render_template, abort
from werkzeug.utils import secure_filename

general = Blueprint('general',__name__)

@general.route("/choli")
def choli():
    with open('choli.json') as f:
        products = json.load(f)
    return render_template("general/choli.html", products=products)

@general.route("/kediya")
def kediya():
    with open('kediya.json') as f:
        products = json.load(f)
    return render_template("general/kediya.html", products=products)

@general.route("/sitemap.xml")
def sitemap():
    return send_from_directory('static', 'sitemap.xml', mimetype='application/xml')


@general.route('/robots.txt')
def robots():
    return "Sitemap: https://image-traditional.onrender.com/sitemap.xml", 200, {'Content-Type': 'text/plain'}


@general.route('/fancy_admin')
def fancy_admin():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))
    return render_template("fancy/fancy_admin.html")

@general.route('/navaratri_admin')
def navaratri_admin():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))
    return render_template("general/navaratri_admin.html")


@general.route('/catalogue/fancy/')
def catalogue():

    # Map subfolder name → icon filename
    icon_map = {
        "Bhagwan":            "bhagwan.png",
        "Mataji":             "mataji.png",
        "Profession":         "Proffesion.png",
        "Freedom Fighter":    "Freedom Fighter.png",
        "Regional":           "Regional.png",
        "Wild Animals":       "Wild Animal.png",
        "Domestic Animals":   "Domestic Animal.png",
        "Water Animals":      "Water Animal.png",
        "Insects":            "Insect.png",
        "Birds":              "Bird.png",
        "Fruits":             "fruit.png",
        "Vegetables":         "vegetable.png",
        "Halloween":          "Halloween.png",
        "Cartoon":            "Cartoon.png",
        "Superhero":          "Superhero.png",
        "International":      "International.png",
        "Flexi":              "Flex.png",
        "Nature":             "Nature.png",
        "Tiranga":            "Tiranga.png",
        "Others":             "Other.png"    
        
    }

    subfolders = list(icon_map.keys())

    return render_template(
        'fancy/fancy_subcategories.html',
        subfolders=subfolders,
        icon_map=icon_map,
    )


@general.route('/catalogue/fancy/<sub>/')
def fancy_sub(sub):
    sub = secure_filename(sub)
    BASE_DIR = os.path.join(current_app.root_path, 'static', 'Products')
    folder_path = os.path.join(BASE_DIR, 'Fancy', sub)

    if not os.path.exists(folder_path):
        abort(404)

    raw_images = [
        f for f in os.listdir(folder_path)
        if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))
    ]

    # Build list of (filename, clean_display_name) tuples
    images = []
    for f in sorted(raw_images):
        stem = os.path.splitext(f)[0]          # "bhagwan1"
        clean = re.sub(r'\d+$', '', stem)      # "bhagwan"
        clean = clean.replace('_', ' ').replace('-', ' ').strip().title()  # "Bhagwan"
        images.append({'file': f, 'name': clean})

    return render_template(
        'general/fancy_gallery.html',
        sub=sub,
        images=images
    )
