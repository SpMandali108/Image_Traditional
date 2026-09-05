"""
fnormalizer.py - Normalization engine for Fancy Dress bookings.
Parses freeform details, extracts multipliers (*), splits bundled items (+),
cleans embedded damage/price tags, maps variants to canonical product names,
resolves categories against Costume_Category_Master, and cleans school affiliations.
"""

import re
from datetime import datetime

# Authoritative aliases for product variants -> Canonical Product Name
PRODUCT_ALIAS_MAP = {
    # Freedom Fighters
    "jhanshi ki rani": "Rani Laxmibai",
    "rani laxmi bai": "Rani Laxmibai",
    "rani laxmibai": "Rani Laxmibai",
    "subhash chandra bose": "Subhash Chandra Bose",
    "subhas chandra bose": "Subhash Chandra Bose",
    "subhash chandra bose dress": "Subhash Chandra Bose",
    "subhas chandra bose dress": "Subhash Chandra Bose",
    "baal gangadhar tilak": "Bal Gangadhar Tilak",
    "bal gangadhar tilak": "Bal Gangadhar Tilak",
    "gandhi": "Mahatma Gandhi",
    "mahatma gandhi": "Mahatma Gandhi",
    "bhagat singh": "Bhagat Singh",
    "bhagat sinh": "Bhagat Singh",
    "bhagat singh dress": "Bhagat Singh",
    "captain laxmi": "Captain Lakshmi Sahgal",
    "captain lakshmi": "Captain Lakshmi Sahgal",
    "sardar patel": "Sardar Vallabhbhai Patel",
    "sardar vallabhbhai patel": "Sardar Vallabhbhai Patel",
    "laal bahadur shashtri": "Lal Bahadur Shastri",
    "lal bahadur shastri": "Lal Bahadur Shastri",
    "rajguru": "Rajguru",
    "bharat mata": "Bharat Mata",

    # Mythological & Gods / Bhagwan
    "krishna": "Krishna",
    "krishna dress": "Krishna",
    "krishna bhagwan": "Krishna",
    "bal krishna": "Krishna",
    "krishna (yellow)": "Krishna",
    "krishna (new rama yellow)": "Krishna",
    "new krishna heavy": "Krishna",
    "radhaji": "Radha",
    "radharani": "Radha",
    "radha": "Radha",
    "radha dress": "Radha",
    "sudama dress": "Sudama",
    "sudama": "Sudama",
    "ganeshji": "Ganeshji",
    "ganesh": "Ganeshji",
    "ganpati": "Ganeshji",
    "shivji": "Shankar / Shivji",
    "shankarji": "Shankar / Shivji",
    "shankar dress": "Shankar / Shivji",
    "shankar dress heavy": "Shankar / Shivji",
    "shankar bhagwan dress": "Shankar / Shivji",
    "ram": "Lord Ram",
    "shree ram": "Lord Ram",
    "laxman": "Laxman",
    "sita mata": "Sita Mata",
    "sita": "Sita Mata",
    "parvati mata": "Parvati Mata",
    "parvati": "Parvati Mata",
    "vishnu bhagwan": "Lord Vishnu",
    "vishnu": "Lord Vishnu",
    "laxmi mata": "Laxmi Mata",
    "mahakali mata": "Mahakali Mata",
    "ganga maa": "Ganga Mata",
    "suryadev": "Suryadev",
    "indradev": "Indradev",
    "bramhaji": "Brahmaji",
    "kartikey": "Kartikeya",
    "narsinh mehta": "Narsinh Mehta",
    "raja harishchandra": "Raja Harishchandra",
    "tarabai": "Tarabai",
    "balram": "Balram",

    # Profession
    "doctor": "Doctor",
    "doctor dress": "Doctor",
    "police": "Police",
    "police dress": "Police",
    "army": "Army",
    "army dress": "Army",
    "army (bsf)": "Army",
    "navy": "Navy",
    "navy dress": "Navy",
    "teacher": "Teacher",
    "advocate": "Advocate / Lawyer",
    "lawyer": "Advocate / Lawyer",
    "chef": "Chef",
    "astronaut": "Astronaut",
    "air hostess": "Air Hostess",

    # Regional / Traditional
    "south boy": "South Indian (Boy)",
    "south girl": "South Indian (Girl)",
    "marathi saree": "Marathi Saree",
    "punjabi dress": "Punjabi Dress",
    "rajashthani dress": "Rajasthani Dress",
    "rajasthani dress": "Rajasthani Dress",
    "bhangra rumal": "Bhangra Rumal",

    # Animals / Birds / Nature
    "tiger dress": "Tiger",
    "tiger": "Tiger",
    "lion dress": "Lion",
    "lion": "Lion",
    "nandi dress": "Nandi",
    "tree dress": "Tree",
    "mango dress": "Mango",
    "apple dress": "Apple",
    "watermelon dress": "Watermelon",
    "blue fish": "Blue Fish",
    "nemo fish": "Nemo Fish",
    "sheshnag": "Sheshnag",

    # Cartoon / Superhero / Characters
    "doraemon": "Doraemon",
    "batman": "Batman",
    "chhota bheem": "Chhota Bheem",
    "vampire": "Vampire",
    "guruji dress": "Guruji / Sage",
    "sadhu dress": "Sadhu",
    "sadhu": "Sadhu",
    "leader girl": "Leader (Girl)",
    "graduation cap": "Graduation Robe & Cap",
}

# Authoritative Category Map for Canonical Products
PRODUCT_CATEGORY_MAP = {
    "Krishna": "Bhagwan",
    "Radha": "Bhagwan",
    "Sudama": "Bhagwan",
    "Ganeshji": "Bhagwan",
    "Shankar / Shivji": "Bhagwan",
    "Lord Ram": "Bhagwan",
    "Laxman": "Bhagwan",
    "Lord Vishnu": "Bhagwan",
    "Balram": "Bhagwan",
    "Suryadev": "Bhagwan",
    "Indradev": "Bhagwan",
    "Brahmaji": "Bhagwan",
    "Kartikeya": "Bhagwan",
    "Parvati Mata": "Mataji",
    "Sita Mata": "Mataji",
    "Laxmi Mata": "Mataji",
    "Mahakali Mata": "Mataji",
    "Ganga Mata": "Mataji",
    "Rani Laxmibai": "Freedom Fighter",
    "Subhash Chandra Bose": "Freedom Fighter",
    "Bal Gangadhar Tilak": "Freedom Fighter",
    "Mahatma Gandhi": "Freedom Fighter",
    "Bhagat Singh": "Freedom Fighter",
    "Captain Lakshmi Sahgal": "Freedom Fighter",
    "Sardar Vallabhbhai Patel": "Freedom Fighter",
    "Lal Bahadur Shastri": "Freedom Fighter",
    "Rajguru": "Freedom Fighter",
    "Bharat Mata": "Freedom Fighter",
    "Doctor": "Profession",
    "Police": "Profession",
    "Army": "Profession",
    "Navy": "Profession",
    "Teacher": "Profession",
    "Advocate / Lawyer": "Profession",
    "Chef": "Profession",
    "Astronaut": "Profession",
    "Air Hostess": "Profession",
    "South Indian (Boy)": "Regional",
    "South Indian (Girl)": "Regional",
    "Marathi Saree": "Regional",
    "Punjabi Dress": "Regional",
    "Rajasthani Dress": "Regional",
    "Bhangra Rumal": "Regional",
    "Tiger": "Wild Animal",
    "Lion": "Wild Animal",
    "Nandi": "Domestic Animal",
    "Blue Fish": "Water Animal",
    "Nemo Fish": "Water Animal",
    "Tree": "Nature",
    "Mango": "Fruit",
    "Apple": "Fruit",
    "Watermelon": "Fruit",
    "Doraemon": "Cartoon",
    "Batman": "Super Hero",
    "Chhota Bheem": "Cartoon",
    "Vampire": "Haloween",
    "Narsinh Mehta": "Historical Character",
    "Raja Harishchandra": "Historical Character",
    "Tarabai": "Historical Character",
    "Guruji / Sage": "Historical Character",
    "Sadhu": "Historical Character",
    "Leader (Girl)": "National Character",
    "Graduation Robe & Cap": "Properties",
    "Dhoti": "Properties",
    "Mukut": "Properties",
    "Talwar": "Properties",
    "Tiranga Jabbha": "Tiranga",
    "Tiranga Dupatta": "Tiranga",
}

# Known School Aliases -> Canonical School Name
SCHOOL_ALIAS_MAP = {
    "jay somanth school": "Jay Somnath",
    "jay somnath school": "Jay Somnath",
    "jay somnath": "Jay Somnath",
    "vedant": "Vedant International",
    "vedant international": "Vedant International",
    "seventh day adventist": "Seventh Day Adventist",
    "seventh day": "Seventh Day Adventist",
    "ssgits": "SSGITS",
    "ssgit": "SSGITS",
    "muktajivan school": "Muktajivan School",
    "muktajivan": "Muktajivan School",
    "nelson": "Nelson School",
    "nelson school": "Nelson School",
    "euro kids": "EuroKids",
    "eurokids": "EuroKids",
    "durga school": "Durga School",
    "doon school": "Doon School",
    "bright school": "Bright School",
    "podar jumbo": "Podar Jumbo Kids",
    "podar jumbo kids": "Podar Jumbo Kids",
    "little millenium": "Little Millennium",
    "divine gurukulam": "Divine Gurukulam",
    "divine buds": "Divine Buds",
    "fairy land school maninagar": "Fairy Land School Maninagar",
}

# Known accessories to attribute to primary outfit when bundled
ACCESSORY_KEYWORDS = {
    "ornaments", "talwar", "mukut", "pagh", "jata", "teeth", "horn", "stick",
    "beard", "mask", "khesh", "much", "moustache", "weapons", "wings", "cap",
    "dupatta", "ghunghroo", "kundal"
}


def clean_school_name(raw_school):
    """
    Normalizes school name, resolving aliases and filtering walk-in markers.
    Returns (cleaned_name: str, is_walkin: bool)
    """
    if not raw_school:
        return "Walk-in Customer", True

    cleaned = str(raw_school).strip().lower()
    if cleaned in ["none", "not available", "na", "n/a", "unknown", "office", "-", ""]:
        return "Walk-in Customer", True

    canonical = SCHOOL_ALIAS_MAP.get(cleaned)
    if canonical:
        return canonical, False

    # Return Title Cased school name
    return str(raw_school).strip().title(), False


def parse_item_string(item_str):
    """
    Parses a single dress item segment to extract name, multiplier units, and embedded price/damage notes.
    Example: 'Doctor Dress * 2 (Damage - 100)' -> ('Doctor Dress', 2, {'damage': 100})
             'Ganeshji (500 + 100(Damage))'   -> ('Ganeshji', 1, {'price': 500, 'damage': 100})
             'Krishna Yellow 22'               -> ('Krishna Yellow', 1, {'size': '22'})
    """
    raw = item_str.strip()
    if not raw:
        return "", 1, {}

    meta = {}

    # Extract price / damage notes in parentheses
    # e.g. (500), (500 + 100(Damage)), (Damage 100), (Damage - 100), (250 + 50 (Lost))
    paren_matches = re.findall(r'\(([^)]+)\)', raw)
    for p in paren_matches:
        p_clean = p.strip()
        # Check for damage note
        dmg_match = re.search(r'damage\s*[-:]?\s*(\d+)', p_clean, re.I)
        if dmg_match:
            meta["damage"] = float(dmg_match.group(1))
        # Check for explicit standalone price like (500)
        price_match = re.match(r'^\s*(\d+(?:\.\d+)?)\s*$', p_clean)
        if price_match:
            meta["explicit_price"] = float(price_match.group(1))

    # Remove parentheses notes from the working name string
    cleaned_name = re.sub(r'\([^)]*\)', '', raw).strip()

    # Extract explicit multipliers: e.g. * 2, * 8 Pair, * 3
    units = 1
    # Match '* 8 Pair' or '* 2'
    mult_match = re.search(r'[\*xX]\s*(\d+)\s*(?:pair|pairs)?\b', cleaned_name, re.I)
    if mult_match:
        units = int(mult_match.group(1))
        cleaned_name = re.sub(r'[\*xX]\s*\d+\s*(?:pair|pairs)?\b', '', cleaned_name, re.I).strip()

    # Strip trailing size numbers if after a color or product (e.g. 'Krishna Yellow 22' -> size 22)
    size_match = re.search(r'\b(20|22|24|26|28|30|32|34|36|38|40)\s*$', cleaned_name)
    if size_match:
        meta["size"] = size_match.group(1)
        cleaned_name = re.sub(r'\b(20|22|24|26|28|30|32|34|36|38|40)\s*$', '', cleaned_name).strip()

    # Clean leading/trailing punctuation and extra whitespace
    cleaned_name = re.sub(r'^[,\-\+\*]+|[,\-\+\*]+$', '', cleaned_name).strip()
    cleaned_name = re.sub(r'\s+', ' ', cleaned_name)

    return cleaned_name, units, meta


def canonicalize_product_name(raw_name):
    """
    Maps a cleaned dress name to its canonical version.
    """
    if not raw_name:
        return "Miscellaneous Outfit"

    key = raw_name.strip().lower()
    if key in PRODUCT_ALIAS_MAP:
        return PRODUCT_ALIAS_MAP[key]

    # Partial / subphrase matching
    for alias, canon in PRODUCT_ALIAS_MAP.items():
        if alias in key:
            return canon

    # Fallback to Title Case
    return raw_name.strip().title()


def resolve_item_category(canonical_product, booking_category=None):
    """
    Resolves the canonical category for a given product.
    Cross-references authoritative mapping, booking category, and master defaults.
    """
    if canonical_product in PRODUCT_CATEGORY_MAP:
        return PRODUCT_CATEGORY_MAP[canonical_product]

    if booking_category and booking_category.strip():
        cat = booking_category.strip().title()
        if cat not in ["Other", "General", "Mix"]:
            return cat

    return "Miscellaneous"


def normalize_booking(b):
    """
    Main entry point for normalising a single booking document into canonical line items.
    Returns a list of dicts:
    [{
        'canonical_product': str,
        'canonical_category': str,
        'units': int,
        'allocated_revenue': float,
        'school_clean': str,
        'is_walkin': bool,
        'booking_id': str,
        'booking_date': str (YYYY-MM-DD),
        'customer_name': str,
        'customer_mobile': str
    }, ...]
    """
    booking_id = str(b.get("_id", ""))
    booking_price = float(b.get("price", 0) or 0)
    booking_costume = b.get("costume", "").strip().title()  # Note: costume field holds category in this schema
    raw_details = b.get("details", "").strip()
    raw_school = b.get("school", "")
    customer_name = b.get("name", "Unknown").strip().title()
    customer_mobile = str(b.get("mobile", "")).strip()

    school_clean, is_walkin = clean_school_name(raw_school)

    # Normalize start_date to YYYY-MM-DD
    sd = b.get("start_date")
    date_str = ""
    if isinstance(sd, datetime):
        date_str = sd.strftime("%Y-%m-%d")
    elif isinstance(sd, str) and sd.strip():
        for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d-%m-%y"]:
            try:
                date_str = datetime.strptime(sd.strip(), fmt).strftime("%Y-%m-%d")
                break
            except ValueError:
                continue

    # If details is empty, fallback to costume field
    if not raw_details:
        fallback_product = canonicalize_product_name(booking_costume)
        fallback_cat = resolve_item_category(fallback_product, booking_costume)
        return [{
            "canonical_product": fallback_product,
            "canonical_category": fallback_cat,
            "units": 1,
            "allocated_revenue": booking_price,
            "school_clean": school_clean,
            "is_walkin": is_walkin,
            "booking_id": booking_id,
            "booking_date": date_str,
            "customer_name": customer_name,
            "customer_mobile": customer_mobile
        }]

    # Split bundle strings by '+' or comma (for multi-costume lists)
    segments = []
    if "+" in raw_details:
        segments = [s.strip() for s in raw_details.split("+") if s.strip()]
    elif "," in raw_details and not raw_details.lower().startswith("vampire"):
        # Multiple costumes comma-separated e.g. 'Sainik * 2 , Suryadev , Indradev...'
        segments = [s.strip() for s in raw_details.split(",") if s.strip()]
    else:
        segments = [raw_details]

    # Parse each segment
    parsed_items = []
    for seg in segments:
        pname, units, meta = parse_item_string(seg)
        if not pname:
            continue

        # Check if this segment is purely an accessory (e.g. Talwar, Pagh)
        is_accessory = any(acc in pname.lower() for acc in ACCESSORY_KEYWORDS)
        canon_name = canonicalize_product_name(pname)
        parsed_items.append({
            "raw_name": pname,
            "canonical_product": canon_name,
            "units": max(1, units),
            "meta": meta,
            "is_accessory": is_accessory
        })

    if not parsed_items:
        fallback_product = canonicalize_product_name(booking_costume)
        return [{
            "canonical_product": fallback_product,
            "canonical_category": resolve_item_category(fallback_product, booking_costume),
            "units": 1,
            "allocated_revenue": booking_price,
            "school_clean": school_clean,
            "is_walkin": is_walkin,
            "booking_id": booking_id,
            "booking_date": date_str,
            "customer_name": customer_name,
            "customer_mobile": customer_mobile
        }]

    # Filter out secondary accessories if a primary outfit is present in the bundle
    primary_items = [it for it in parsed_items if not it["is_accessory"]]
    if primary_items:
        active_items = primary_items
    else:
        active_items = parsed_items  # All items were accessories (e.g. Dhoti + Talwar)

    total_units = sum(it["units"] for it in active_items)
    if total_units <= 0:
        total_units = 1

    # Distribute revenue
    # Check if explicit prices were recorded in parentheses
    explicit_sum = sum(it["meta"].get("explicit_price", 0) for it in active_items)
    has_explicit = explicit_sum > 0 and abs(explicit_sum - booking_price) < 100

    results = []
    for it in active_items:
        if has_explicit and it["meta"].get("explicit_price"):
            rev = it["meta"]["explicit_price"] + it["meta"].get("damage", 0)
        else:
            # Distribute proportionally based on unit share
            rev = round((booking_price * it["units"]) / total_units, 2)

        cat = resolve_item_category(it["canonical_product"], booking_costume)

        results.append({
            "canonical_product": it["canonical_product"],
            "canonical_category": cat,
            "units": it["units"],
            "allocated_revenue": rev,
            "school_clean": school_clean,
            "is_walkin": is_walkin,
            "booking_id": booking_id,
            "booking_date": date_str,
            "customer_name": customer_name,
            "customer_mobile": customer_mobile
        })

    return results


def normalize_cycle_bookings(bookings):
    """
    Normalizes all bookings in a cycle.
    Returns:
      items: list of all normalized line items
      summary: audit dictionary
    """
    all_items = []
    for b in bookings:
        line_items = normalize_booking(b)
        all_items.extend(line_items)

    total_units = sum(it["units"] for it in all_items)
    total_rev = sum(it["allocated_revenue"] for it in all_items)

    return all_items, {
        "raw_booking_count": len(bookings),
        "normalized_item_count": len(all_items),
        "total_units": total_units,
        "total_revenue": round(total_rev, 2)
    }
