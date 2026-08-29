# 🗺️ Customer Concentration Map & Geolocation System Documentation

**Image Traditional** — Rental Management System (Navaratri Collection & Fancy Dress Rentals)

---

## 📌 Executive Summary

The **Customer Concentration Map & Geolocation System** is an end-to-end spatial analytics, address parsing, and geocoding feature integrated into the Image Traditional rental management application. 

It enables business owners and administrators to:
1. **Visualize Customer Density**: Interactive dark-themed maps displaying customer concentrations across Ahmedabad localities and Gujarat towns.
2. **Interactive Filtering**: Filter customer records in real-time by clicking map circles or locality cards.
3. **Smart Address Parsing**: Intelligent resolution algorithm with anti-false-positive regex to parse unstructured address text into verified localities.
4. **Unified Address Resolver Dashboard (`/address_manager`)**: Dedicated administrative portal to inspect, verify, and geocode unmapped customer addresses.
5. **Dynamic Locality Management**: Add and maintain custom localities and GPS coordinates stored in MongoDB without code changes.

---

## 🏗️ Architectural Overview

```mermaid
flowchart TD
    subgraph DataSources["1. Data Sources"]
        N[Navaratri Customers DB\n<code>ncustomers</code>]
        F[Fancy Dress Customers DB\n<code>fcustomers</code>]
        CL[Custom Localities DB\n<code>custom_localities</code>]
        MTRX[Hardcoded Matrices\n<code>GUJARAT_TOWNS_MATRIX</code>\n<code>AREA_COORDINATES</code>]
    end

    subgraph BackendEngine["2. Backend Processing Engine"]
        RL[Locality Resolver\n<code>website/general/utils.py</code>\n<code>resolve_customer_locality()</code>]
        BF[Suffix & Regex Filter\n<code>BUILDING_SUFFIX_REGEX</code>]
        AGG[Locality Aggregator & Math\nCounts & Percentage Share]
    end

    subgraph Endpoints["3. Routes & Endpoints"]
        NC["/navaratri-customers"]
        FC["/fancy-customers"]
        AM["/address_manager"]
        API1["POST /api/update_customer_address"]
        API2["POST /api/add_custom_locality"]
    end

    subgraph Frontend["4. Frontend Presentation"]
        LMAP[Leaflet.js Interactive Dark Map\nCartoDB Dark Matter Tiles]
        CIRC[Proportional Density Circles\n<code>L.circle</code> with Gold Glow]
        TABLE[Real-time Filtered Customer Table]
        RES[Unified Address Resolver GUI]
    end

    N --> RL
    F --> RL
    CL --> RL
    MTRX --> RL
    RL --> BF
    BF --> AGG
    AGG --> NC
    AGG --> FC
    AGG --> AM
    NC --> LMAP
    FC --> LMAP
    AM --> RES
    LMAP --> CIRC
    CIRC -->|Click to Filter| TABLE
    RES -->|Resolve & Save| API1
    RES -->|Add Custom Locality| API2
    API1 --> N
    API1 --> F
    API1 --> CL
    API2 --> CL
```

---

## 🧩 Core Components

### 1. Smart Locality Resolution Engine (`website/general/utils.py`)

Customer addresses entered during bookings often contain free-form text with society names, landmarks, or typos (e.g., *"Flat 402, Anand Apartment, Vastral, Ahmedabad"*). 

The `resolve_customer_locality(customer, active_localities)` function accurately identifies the true geographic locality while eliminating false positives.

#### 🛡️ Anti-False-Positive Society Detection
In Gujarat, many housing societies and apartment complexes are named after towns (e.g., *Anand Apartment*, *Surat Complex*, *Patan Society*). A standard substring search would incorrectly match the customer to the town of *Anand* instead of *Vastral*.

The engine resolves this with the `BUILDING_SUFFIX_REGEX`:
```python
BUILDING_SUFFIX_REGEX = re.compile(
    r'^\s*(apartment|apartments|flat|flats|society|soc|villa|villas|complex|'
    r'tower|towers|bhuvan|house|enclave|residency|plaza|arcade|heights|'
    r'row\s*house|scheme|bungalow|bungalows|apt|apts)\b',
    re.IGNORECASE
)
```

#### ⚙️ Resolution Hierarchy:
1. **Explicit Locality Field**: Checks `customer.get("locality")` first.
   - Exact case-insensitive match against active localities.
   - Word boundary regex matching with **longest match first** (`sorted(active_localities, key=len, reverse=True)`).
   - Validates that the match is not immediately followed by a building suffix.
2. **Address Text Fallback**: Scans `customer.get("address")` for active locality names using word boundaries (`\b<locality>\b`), skipping building prefixes.
3. **Returns `None`** if no verified locality is resolved, placing the customer in the `/address_manager` unmapped queue.

---

### 2. Interactive Map Visualizer (Leaflet.js + CartoDB)

Both the **Navaratri Customer Directory** ([`website/templates/navaratri/navaratri_customers.html`](file:///F:/Shashwat_Mandali/Coding%20Script/Image-Traditional/Rental_Mandagement_Flask_App_Image_Traditional/Rental_Mandagement_Flask_App_Image_Traditional/website/templates/navaratri/navaratri_customers.html)) and **Fancy Dress Directory** ([`website/templates/fancy/fancy_customers.html`](file:///F:/Shashwat_Mandali/Coding%20Script/Image-Traditional/Rental_Mandagement_Flask_App_Image_Traditional/Rental_Mandagement_Flask_App_Image_Traditional/website/templates/fancy/fancy_customers.html)) feature full Leaflet.js map widgets.

#### Key Features:
- **Dark Theme Map Tiles**: Rendered via CartoDB Dark Matter:
  `https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png`
- **Dynamic Density Circles**: Circle radius scales proportionally based on customer density:
  $$\text{radius} = \max(200, \text{count} \times 35)$$
- **Gold Glow Theme**: Matches Image Traditional's aesthetic with `#d4af37` border and translucent fill.
- **Rich Popup Cards**: Hovering or clicking a circle displays:
  - 📍 Locality Name
  - 👥 Total Registered Customers
  - 📊 Percentage Share of Mapped Base
- **Smooth Fly-to Animation**: Clicking a locality triggers `map.flyTo([lat, lng], 14, { animate: true, duration: 1.2 })`.
- **Synchronized Directory Filtering**: Filters table rows and mobile cards instantly to display only customers from that locality.
- **Active Filter Banner**: Displays a gold banner with a "Clear Map Filter" button to reset the view and restore `map.fitBounds()`.

---

### 3. Unified Address Resolver Dashboard (`/address_manager`)

Accessible to logged-in administrators at `/address_manager`, this portal provides a workflow to clean and geocode unstructured customer data.

#### Dashboard Capabilities:
- **Live Unmapped Counters**: Top KPI cards showing the total unmapped queue, partitioned by Navaratri and Fancy Dress.
- **System Tabs & Live Search**: Filter the queue by "All", "Navaratri", or "Fancy Dress", with client-side real-time search across Name, Mobile, and Address.
- **Autocomplete Datalist**: Suggestions drawn from all verified system localities plus custom-added localities.
- **Real-Time Address Separation**: Splits building/street address into `address` and town/area into `locality`.
- **Direct Save & Instant Row Removal**: Resolves the record via AJAX, updates MongoDB, triggers an emerald success flash, and slides the row off the queue.
- **Quick Customer Profile Modal**:
  - Direct WhatsApp chat link (`https://wa.me/91XXXXXXXXXX`)
  - Direct telephone call link (`tel:XXXXXXXXXX`)
  - Associated details (Schools for Fancy Dress, Groups/References for Navaratri)
  - Shortcut to jump to full customer history in directories

---

### 4. Custom Localities & Dynamic GPS Storage

In addition to the predefined Ahmedabad and Gujarat coordinates, the application supports dynamic runtime localities stored in MongoDB.

#### MongoDB Collection: `Custom_Localities`
```json
{
  "_id": ObjectId("..."),
  "name": "Nikol Gam",
  "lat": 23.0512,
  "lng": 72.6781,
  "created_at": ISODate("2026-08-15T12:00:00Z")
}
```

When building map data or rendering the address resolver, `groutes.py`, `froutes.py`, and `nroutes.py` merge hardcoded coordinates with records from `custom_localities`, ensuring newly added areas appear on the map without code changes.

---

## 🌐 API Reference

### 1. Update Customer Address & Geocode
Saves verified locality and street address for a customer.

- **URL**: `/api/update_customer_address`
- **Method**: `POST`
- **Auth Required**: Yes (`session['logged_in']`)
- **Content-Type**: `application/json`

#### Request Payload:
```json
{
  "cust_id": "64f1a2b3c4d5e6f7a8b9c0d1",
  "system": "Navaratri",
  "locality": "Vastral",
  "new_address": "Flat 204, Radha Krishna Complex"
}
```

#### Response:
```json
{
  "status": "success",
  "message": "Saved locality 'Vastral' and preserved real address for customer in Navaratri!",
  "cust_id": "64f1a2b3c4d5e6f7a8b9c0d1",
  "locality": "Vastral",
  "address": "Flat 204, Radha Krishna Complex"
}
```

---

### 2. Add Custom Locality
Registers a new locality and its geographic coordinates.

- **URL**: `/api/add_custom_locality`
- **Method**: `POST`
- **Auth Required**: Yes (`session['logged_in']`)
- **Content-Type**: `application/json`

#### Request Payload:
```json
{
  "name": "South Bopal",
  "lat": 23.0300,
  "lng": 72.4640
}
```

#### Response:
```json
{
  "status": "success",
  "message": "Successfully created new custom locality 'South Bopal' at [23.0300, 72.4640]!",
  "locality": {
    "name": "South Bopal",
    "lat": "23.0300",
    "lng": "72.4640"
  }
}
```

---

## 🗺️ Geographic Coverage Matrix

The system includes built-in coordinates for over 50 localities and cities across Ahmedabad and Gujarat:

| Zone / Region | Key Covered Localities |
| :--- | :--- |
| **East Ahmedabad** | Vastral, Maninagar, Khokhra, Isanpur, Amraiwadi, Ghodasar, Vatva, Odhav, Hatkeshwar, CTM, Nikol, Ramol, Narol, Bapunagar, Saraspur, Asarwa, Naroda, Rakhial |
| **West Ahmedabad** | Navrangpura, Satellite, Vastrapur, Bodakdev, Thaltej, Sola, Gota, Ghatlodia, Naranpura, Paldi, Vasna, Jivraj Park, Bopal, South Bopal |
| **Central / North Ahmedabad** | Shahpur, Dani Limda, Sarangpur, Kalupur, Astodia, Raipur, Lal Darwaja, Geeta Mandir, Shahibaug, Ranip, Sabarmati, Chandkheda, Nava Vadaj |
| **Surrounding Ahmedabad Hubs** | Aslali, Bareja, Changodar, Moraiya, Sanand, Dholka, Bavla, Dehgam, Kalol, Chhatral, Kadi |
| **Major Gujarat Cities & Towns** | Gandhinagar, Nadiad, Anand, Vadodara, Surat, Rajkot, Mehsana, Visnagar, Unjha, Siddhpur, Patan, Palanpur, Himmatnagar, Modasa, Idar, Deesa, Bharuch, Ankleshwar, Navsari, Valsad, Vapi, Godhra, Dahod, Morbi, Gondal, Bhavnagar, Junagadh, Jamnagar, Bhuj, Gandhidham |

---

## 📁 Source File Map

| File Path | Description |
| :--- | :--- |
| [`website/general/utils.py`](file:///F:/Shashwat_Mandali/Coding%20Script/Image-Traditional/Rental_Mandagement_Flask_App_Image_Traditional/Rental_Mandagement_Flask_App_Image_Traditional/website/general/utils.py) | Contains `resolve_customer_locality()` and `BUILDING_SUFFIX_REGEX`. |
| [`website/general/groutes.py`](file:///F:/Shashwat_Mandali/Coding%20Script/Image-Traditional/Rental_Mandagement_Flask_App_Image_Traditional/Rental_Mandagement_Flask_App_Image_Traditional/website/general/groutes.py) | Handles `/address_manager`, `/api/update_customer_address`, `/api/add_custom_locality`, and `GUJARAT_TOWNS_MATRIX`. |
| [`website/templates/general/address_manager.html`](file:///F:/Shashwat_Mandali/Coding%20Script/Image-Traditional/Rental_Mandagement_Flask_App_Image_Traditional/Rental_Mandagement_Flask_App_Image_Traditional/website/templates/general/address_manager.html) | Unified Address Resolver UI with customer analysis modal & quick geocoding. |
| [`website/navaratri/nroutes.py`](file:///F:/Shashwat_Mandali/Coding%20Script/Image-Traditional/Rental_Mandagement_Flask_App_Image_Traditional/Rental_Mandagement_Flask_App_Image_Traditional/website/navaratri/nroutes.py) | Navaratri customer directory route, `KNOWN_LOCALITIES`, `AREA_COORDINATES`, and map data packaging. |
| [`website/templates/navaratri/navaratri_customers.html`](file:///F:/Shashwat_Mandali/Coding%20Script/Image-Traditional/Rental_Mandagement_Flask_App_Image_Traditional/Rental_Mandagement_Flask_App_Image_Traditional/website/templates/navaratri/navaratri_customers.html) | Navaratri Leaflet.js interactive dark map with circle overlays & sidebar filters. |
| [`website/fancy/froutes.py`](file:///F:/Shashwat_Mandali/Coding%20Script/Image-Traditional/Rental_Mandagement_Flask_App_Image_Traditional/Rental_Mandagement_Flask_App_Image_Traditional/website/fancy/froutes.py) | Fancy dress customer directory route, `KNOWN_LOCALITIES_FANCY`, `AREA_COORDINATES_FANCY`, and map data packaging. |
| [`website/templates/fancy/fancy_customers.html`](file:///F:/Shashwat_Mandali/Coding%20Script/Image-Traditional/Rental_Mandagement_Flask_App_Image_Traditional/Rental_Mandagement_Flask_App_Image_Traditional/website/templates/fancy/fancy_customers.html) | Fancy dress Leaflet.js interactive dark map with responsive cards and filter sync. |

---

## 💡 Best Practices & Maintenance

1. **Adding New Localities**:
   - For frequent or permanent localities, add them to `KNOWN_LOCALITIES` in `nroutes.py` and `froutes.py` with coordinates in `AREA_COORDINATES` and `GUJARAT_TOWNS_MATRIX`.
   - For ad-hoc or client-specific localities, use the `/address_manager` UI to create dynamic custom localities without server restart.
2. **Preventing Suffix Overlaps**:
   - If new building nomenclature is commonly used by customers (e.g. *Nagar*, *Bhavan*, *Vatika*), verify that regex boundary checks in `BUILDING_SUFFIX_REGEX` in [`utils.py`](file:///F:/Shashwat_Mandali/Coding%20Script/Image-Traditional/Rental_Mandagement_Flask_App_Image_Traditional/Rental_Mandagement_Flask_App_Image_Traditional/website/general/utils.py) continue to cleanly separate building identifiers from town names.
3. **Database Indexing**:
   - Ensure `ncustomers` and `fcustomers` collections have indexes on `locality`, `address`, and `updated_at` for optimal performance during large-scale aggregations.
