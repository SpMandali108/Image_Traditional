import json
import os

from flask import Blueprint, render_template, request, redirect, send_from_directory, url_for, session, jsonify
from datetime import datetime
from bson.objectid import ObjectId
import re
from flask import current_app, render_template, abort
from werkzeug.utils import secure_filename
from website.fancy.fcycle import (
    get_all_cycles,
    get_selected_cycle,
    get_active_cycle
)
from website.navaratri.ncycle import (
    get_all_cycles as get_all_nav_cycles,
    get_selected_cycle as get_selected_nav_cycle,
    get_active_cycle as get_active_nav_cycle
)

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

    cycles = get_all_cycles()

    selected_cycle = get_selected_cycle()

    active_cycle = get_active_cycle()

    return render_template(
        "fancy/fancy_admin.html",
        cycles=cycles,
        selected_cycle=selected_cycle,
        active_cycle=active_cycle
    )

@general.route('/navaratri_admin')
def navaratri_admin():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))
    
    cycles = get_all_nav_cycles()
    selected_cycle = get_selected_nav_cycle()
    active_cycle = get_active_nav_cycle()
    
    return render_template(
        "general/navaratri_admin.html",
        cycles=cycles,
        selected_cycle=selected_cycle,
        active_cycle=active_cycle
    )


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

    # Load unique descriptions
    desc_path = os.path.join(current_app.root_path, 'static', 'fancy_descriptions.json')
    descriptions = {}
    if os.path.exists(desc_path):
        try:
            with open(desc_path, 'r', encoding='utf-8') as df:
                descriptions = json.load(df)
        except Exception:
            pass

    # Build list of (filename, clean_display_name) tuples
    images = []
    for f in sorted(raw_images):
        stem = os.path.splitext(f)[0]
        # Replace underscores and hyphens with spaces to separate words
        clean = stem.replace('_', ' ').replace('-', ' ')
        # Remove any numeric and special characters (keeping only letters and spaces)
        clean = re.sub(r'[^a-zA-Z ]', '', clean)
        # Collapse multiple spaces and strip
        clean = re.sub(r'\s+', ' ', clean).strip().title()
        
        # Match using subcategory/filename
        key = f"{sub}/{f}"
        desc = descriptions.get(key, f"A premium quality stage-wear costume representing {clean}, designed with comfortable fabrics and vibrant colors to make your child shine on stage.")
        
        images.append({'file': f, 'name': clean, 'desc': desc})

    return render_template(
        'general/fancy_gallery.html',
        sub=sub,
        images=images
    )
