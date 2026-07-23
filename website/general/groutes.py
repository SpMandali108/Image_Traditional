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


# ------------------ Page: Unified Address Resolver & Geocoding Manager ------------------
@general.route("/address_manager")
def address_manager():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    from website.general.db import ncustomers, fcustomers, custom_localities
    from website.navaratri.nroutes import KNOWN_LOCALITIES

    merged_localities = list(KNOWN_LOCALITIES)
    try:
        for cloc in custom_localities.find():
            cname = cloc.get("name")
            if cname and cname not in merged_localities:
                merged_localities.insert(0, cname)
    except Exception:
        pass

    n_custs = list(ncustomers.find().sort("updated_at", -1))
    f_custs = list(fcustomers.find().sort("updated_at", -1))

    unmapped_navaratri = []
    for c in n_custs:
        raw_addr = (c.get("address") or "").replace('\r', ' ').replace('\n', ' ').strip()
        c['address'] = raw_addr
        found = False
        if raw_addr and raw_addr != "-":
            al = raw_addr.lower()
            for loc in merged_localities:
                if loc.lower() in al:
                    found = True
                    break
        if not found:
            c['_id_str'] = str(c['_id'])
            c['system'] = 'Navaratri'
            unmapped_navaratri.append(c)

    unmapped_fancy = []
    for c in f_custs:
        raw_addr = (c.get("address") or "").replace('\r', ' ').replace('\n', ' ').strip()
        c['address'] = raw_addr
        found = False
        if raw_addr and raw_addr != "-":
            al = raw_addr.lower()
            for loc in merged_localities:
                if loc.lower() in al:
                    found = True
                    break
        if not found:
            c['_id_str'] = str(c['_id'])
            c['system'] = 'Fancy Dress'
            unmapped_fancy.append(c)

    all_unmapped = unmapped_navaratri + unmapped_fancy

    return render_template(
        "general/address_manager.html",
        unmapped_customers=all_unmapped,
        navaratri_count=len(unmapped_navaratri),
        fancy_count=len(unmapped_fancy),
        known_localities=merged_localities
    )


GUJARAT_TOWNS_MATRIX = {
    'patan': [23.8493, 72.1266], 'palanpur': [24.1724, 72.4346], 'unjha': [23.8043, 72.3942],
    'visnagar': [23.6961, 72.5484], 'mehsana': [23.5880, 72.3693], 'kalol': [23.2393, 72.4962],
    'chhatral': [23.2800, 72.4500], 'kadi': [23.3000, 72.3300], 'dehgam': [23.1670, 72.8120],
    'himmatnagar': [23.5979, 72.9698], 'himatnagar': [23.5979, 72.9698], 'modasa': [23.4667, 73.3000],
    'idar': [23.8340, 73.0030], 'deesa': [24.2587, 72.1804], 'disa': [24.2587, 72.1804],
    'radhanpur': [23.8333, 71.6000], 'siddhpur': [23.9167, 72.3833], 'sidhpur': [23.9167, 72.3833],
    'chanasma': [23.7170, 72.1150], 'gandhinagar': [23.2156, 72.6369], 'nadiad': [22.6916, 72.8634],
    'anand': [22.5645, 72.9289], 'bakrol': [22.5480, 72.9350], 'vadtal': [22.5920, 72.8880],
    'petlad': [22.4748, 72.8020], 'khambhat': [22.3131, 72.6192], 'vadodara': [22.3072, 73.1812],
    'baroda': [22.3072, 73.1812], 'bharuch': [21.7051, 72.9959], 'ankleshwar': [21.6264, 73.0152],
    'surat': [21.1702, 72.8311], 'navsari': [20.9467, 72.9520], 'valsad': [20.6100, 72.9300],
    'vapi': [20.3719, 72.9044], 'godhra': [22.7758, 73.6149], 'dahod': [22.8378, 74.2565],
    'halol': [22.5024, 73.4735], 'rajkot': [22.3039, 70.8022], 'morbi': [22.8173, 70.8368],
    'gondal': [21.9619, 70.7932], 'bhavnagar': [21.7645, 72.1519], 'botad': [22.1700, 71.6700],
    'amreli': [21.6032, 71.2221], 'junagadh': [21.5222, 70.4579], 'veraval': [20.9000, 70.3700],
    'porbandar': [21.6417, 69.6292], 'jamnagar': [22.4707, 70.0577], 'bhuj': [23.2420, 69.6669],
    'gandhidham': [23.0753, 70.1337], 'anjar': [23.1132, 70.0270], 'mandvi': [22.8354, 69.3563],
    'sanand': [22.9910, 72.3810], 'dholka': [22.7200, 72.4700], 'bavla': [22.8300, 72.3600],
    'aslali': [22.9210, 72.6010], 'bareja': [22.8850, 72.6050], 'changodar': [22.9230, 72.4410],
    'kheda': [22.7500, 72.6800], 'vastral': [23.0041, 72.6617], 'maninagar': [22.9976, 72.6009],
    'khokhra': [22.9983, 72.6167], 'isanpur': [22.9731, 72.5976], 'amraiwadi': [23.0039, 72.6288],
    'vatva': [22.9554, 72.6240], 'lambha': [22.9238, 72.5843], 'odhav': [23.0232, 72.6698],
    'hatkeshwar': [23.0012, 72.6225], 'ctm': [22.9908, 72.6321], 'nikol': [23.0483, 72.6717],
    'ramol': [22.9840, 72.6582], 'narol': [22.9634, 72.5891], 'bapunagar': [23.0371, 72.6231],
    'saraspur': [23.0298, 72.6080], 'asarwa': [23.0494, 72.6033], 'shahibaug': [23.0560, 72.5925],
    'naroda': [23.0725, 72.6656], 'rakhial': [23.0180, 72.6210], 'navrangpura': [23.0366, 72.5611],
    'satellite': [23.0300, 72.5176], 'satelite': [23.0300, 72.5176], 'vastrapur': [23.0350, 72.5293],
    'bodakdev': [23.0410, 72.5115], 'thaltej': [23.0500, 72.5070], 'sola': [23.0680, 72.5180],
    'gota': [23.0970, 72.5310], 'ghatlodia': [23.0682, 72.5358], 'ghatlodiya': [23.0682, 72.5358],
    'naranpura': [23.0520, 72.5530], 'paldi': [23.0120, 72.5620], 'vasna': [22.9980, 72.5520],
    'ranip': [23.0800, 72.5710], 'sabarmati': [23.0845, 72.5802], 'chandkheda': [23.1114, 72.5835],
    'saijpur': [23.0640, 72.6280], 'jivraj park': [23.0010, 72.5410], 'bopal': [23.0300, 72.4640]
}


@general.route("/api/update_customer_address", methods=["POST"])
def update_customer_address():
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    from website.general.db import ncustomers, fcustomers, custom_localities

    data = request.get_json() or {}
    cust_id = data.get("cust_id")
    system = data.get("system")
    assigned_locality = (data.get("locality") or "").strip()
    new_address = (data.get("new_address") or "").strip()

    if not cust_id or not system:
        return jsonify({"status": "error", "message": "Missing required fields"}), 400

    try:
        col = ncustomers if system.lower() == 'navaratri' else fcustomers
        query = {"$or": [{"_id": ObjectId(cust_id)}, {"_id": cust_id}]} if ObjectId.is_valid(cust_id) else {"_id": cust_id}
        doc = col.find_one(query)

        if not doc:
            return jsonify({"status": "error", "message": "Customer record not found"}), 444

        existing_addr = (doc.get("address") or "").strip()
        existing_orig = doc.get("original_address") or existing_addr

        # Determine real street address and assigned locality
        final_street_addr = new_address if new_address else existing_addr
        final_locality = assigned_locality

        # If locality not explicitly passed, auto-detect from address string
        if not final_locality:
            addr_lower = final_street_addr.lower()
            for town, coords in GUJARAT_TOWNS_MATRIX.items():
                if town in addr_lower:
                    final_locality = town.title()
                    break

        # Register custom locality in Custom_Localities if needed
        if final_locality:
            coords = GUJARAT_TOWNS_MATRIX.get(final_locality.lower(), [23.0225, 72.5714])
            try:
                custom_localities.update_one(
                    {"name": final_locality},
                    {"$set": {"name": final_locality, "lat": float(coords[0]), "lng": float(coords[1]), "created_at": datetime.now()}},
                    upsert=True
                )
            except Exception:
                pass

        upd = {
            "locality": final_locality,
            "address": final_street_addr,
            "original_address": existing_orig,
            "updated_at": datetime.now()
        }

        col.update_one(query, {"$set": upd})

        return jsonify({
            "status": "success",
            "message": f"Saved locality '{final_locality}' and preserved real address for customer in {system}!",
            "cust_id": cust_id,
            "locality": final_locality,
            "address": final_street_addr
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@general.route("/api/add_custom_locality", methods=["POST"])
def add_custom_locality():
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    from website.general.db import custom_localities

    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    lat = data.get("lat")
    lng = data.get("lng")

    if not name or lat is None or lng is None:
        return jsonify({"status": "error", "message": "Locality Name, Latitude, and Longitude are required."}), 400

    try:
        lat = float(lat)
        lng = float(lng)
    except ValueError:
        return jsonify({"status": "error", "message": "Latitude and Longitude must be valid decimal numbers."}), 400

    try:
        custom_localities.update_one(
            {"name": name},
            {"$set": {"name": name, "lat": lat, "lng": lng, "created_at": datetime.now()}},
            upsert=True
        )

        return jsonify({
            "status": "success",
            "message": f"Successfully created new custom locality '{name}' at [{lat}, {lng}]!",
            "locality": {"name": name, "lat": lat, "lng": lng}
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
