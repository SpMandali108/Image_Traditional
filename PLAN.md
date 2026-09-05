# Architectural Blueprint & Upgrade Plan: Fancy Dress Rental BI Dashboard

> **Status:** Proposal & Architectural Plan  
> **Target Environment:** Flask 3.1.1 / MongoDB Atlas (`Image_Traditional`) / Python 3.12 / Chart.js / Google Gemini API (`gemini-3.6-flash`)  
> **Key Constraint:** Strict adherence to existing visual design system, glassmorphic dark theme, non-destructive data handling, and 100% PII privacy (zero mobile numbers or customer addresses sent to LLM).

---

## 1. Current Architecture Analysis

### 1.1 Overview & Application Ecosystem
The Fancy Dress module is part of the **Image Traditional** rental management web application (Flask). It handles rental bookings for school events, cultural festivals, fancy dress competitions, and annual functions across Ahmedabad and Gujarat.

### 1.2 Frontend Architecture
* **Template Engine:** Jinja2 rendering `website/templates/fancy/fancy_dashboard.html` extending `general/base.html`.
* **Visual Theme & Design System:**
  * Dark Glassmorphic Aesthetic: Root background `--bg-dark: #080b11`, panel background `rgba(17, 24, 39, 0.7)` with `backdrop-filter: blur(12px)`.
  * Borders & Glow: Subdued borders `rgba(255, 255, 255, 0.08)` and active/hover glow `rgba(139, 92, 246, 0.35)`.
  * Color Palette: Neon Blue (`#3b82f6`), Neon Purple (`#8b5cf6`), Neon Pink (`#ec4899`), Neon Emerald (`#10b981`), Neon Amber (`#f59e0b`), Neon Rose (`#f43f5e`), Cyan (`#06b6d4`), Teal (`#14b8a6`).
  * Typography: Google Font `'Plus Jakarta Sans'`, weights 300 to 800.
  * UI Components: `card-glass` hovering cards, pill tab navigation (`.tabs-navigation`), rank circle badges (`.rank-circle`), status countdown badges, and modal overlays.
* **Charting Library:** Chart.js (v4 via CDN). Currently initializes:
  1. `timelineChart`: Line chart for daily booking counts.
  2. `costumesChart`: Vertical bar chart for top 10 costume revenues.
  3. `schoolsChart`: Horizontal bar chart for top 10 school revenues.
  4. `dayOfWeekChart`: Vertical bar chart for pickup counts by weekday.
  5. `monthlyRevenueChart`: Vertical bar chart for revenue across calendar months.
  6. `categoryRevenueChart`: Doughnut chart with cutout `65%` for revenue share across broad categories.
* **Client-side Interactivity:** Real-time JavaScript table filters (`filterTable`, `filterModalTable`), tab switcher (`switchTab`), and modal popup (`openEventModal`).

### 1.3 Backend Architecture & Request Flow
* **Framework:** Flask 3.1.1 Blueprint `fancy` registered in `website/__init__.py`.
* **Route Controller:** `website/fancy/froutes.py` (route `@fancy.route('/fancy_dashboard')` lines 381–827).
* **Cycle Management:** `website/fancy/fcycle.py` manages cycle creation, activation, closure, and selection in session (`session["fancy_cycle_id"]`).
* **Database Connection:** `website/general/db.py` exposes PyMongo `MongoClient` connected to Atlas database `Image_Traditional`.
* **Execution Flow:**
  1. User accesses `/fancy_dashboard` (optionally with `?cycle_id=...`).
  2. Cycle is verified via `get_selected_cycle()`.
  3. Collection is resolved via `get_selected_collection()`.
  4. Documents are loaded into memory: `current_bookings = list(collection.find())`.
  5. Basic Python `Counter` and dictionary aggregations are computed on raw in-memory lists.
  6. Template `fancy/fancy_dashboard.html` is rendered with serialized data injected into inline JavaScript.

### 1.4 Database Schema & Collections
| Collection Name | Purpose | Document Count | Key Fields |
| :--- | :--- | :--- | :--- |
| `fancy_cycles` | Metadata for rental seasons/cycles | 3 cycles | `_id`, `name`, `collection_name`, `start_date`, `end_date`, `status`, `edit_override` |
| `Fancy_2026_2026` | Current Active Cycle Bookings | 422 records | `_id`, `name`, `mobile`, `address`, `school`, `start_date`, `end_date`, `price`, `costume`, `details`, `taken`, `returned`, `timestamp` |
| `Fancy_2025_2026` | Previous Cycle Bookings (Closed) | 361 records | Same as above |
| `Fancy` | Historical Cycle 2025 (Closed) | 355 records | Same as above (older legacy records) |
| `Costume_Category_Master` | Standard Master Categories | 30 categories | `_id`, `name` |
| `School_Master` | Registered Schools Directory | 124 schools | `_id`, `name` |
| `Fancy_Inventory` | Physical Garment Inventory | 145 items | `_id`, `name`, `color`, `category`, `sizes` (dict of size: qty) |
| `Fancy_Customers` | Global Customer Master | 909 profiles | `_id`, `mobile`, `name`, `address`, `school`, `locality` |
| `chat_cache` | Legacy Q&A cache | 525 entries | `query`, `answer`, `category` |

### 1.5 Cycle Definition (Authoritative Analysis)
A **cycle** in this system represents an isolated fiscal/seasonal booking period:
1. Every cycle document in `fancy_cycles` specifies its own dedicated MongoDB collection via `collection_name`.
2. The current active cycle is:
   * **Name:** `Summer 2026 to Diwali 2026`
   * **Collection:** `Fancy_2026_2026`
   * **Cycle ID:** `6a240d9903b108da609c936d`
   * **Status:** `active`
   * **Span:** `06-06-26` onwards (currently contains 422 bookings dated June 2026 through September 2026).
3. Past cycles are:
   * `Fancy_2025_2026`: `Diwali 2025 to Summer 2026` (361 bookings, closed).
   * `Fancy`: `Summer 2025 to Diwali 2025` (355 bookings, closed).
4. **Data Isolation Rule:** When analyzing the "current cycle", queries must query strictly the collection returned by `get_selected_collection()`. Historical multi-cycle data is used only for longitudinal trends and festival back-testing.

### 1.6 Current AI & Festival Forecasting Implementation
* **Existing AI Code:** The repository currently has `GEMINI_API_KEY` configured in `.env`, and the official SDK `google-genai` is installed and verified working with model `gemini-3.6-flash`. However, the current dashboard code does **not** call the Gemini API during execution.
* **Existing Forecast Implementation:** `froutes.py` lines 685–770 use a hardcoded list of 8 Indian cultural events (`republic_day`, `independence_day`, `gandhi_jayanti`, `teachers_day`, `childrens_day`, `christmas`, `janmashtami`, `navaratri`). It searches historical bookings within a $\pm 3$ day buffer, calculates an inventory deficit against `Fancy_Inventory`, and renders a static table. No generative reasoning, anomaly detection, or LLM-driven demand synthesis currently occurs.

---

## 2. Current Problems Discovered

### 2.1 Product & Quantity Data Inconsistencies
Direct inspection of `Fancy_2026_2026` revealed critical data flaws:
1. **Freeform String Contamination in `details`:**
   * Staff enters freeform text for `details` while booking: e.g., `'Ganeshji (500 + 100(Damage)) + Rani Laxmibai (500)'`, `'Doctor Dress * 2 (Damage - 100)'`, `'Bhangra Rumal *  8 Pair'`.
   * The current dashboard simply aggregates `b.get('details', '').strip().title()`. Consequently, `'Doctor Dress * 2 (Damage - 100)'` is treated as a distinct product from `'Doctor'` and `'Doctor Dress'`.
2. **Bundled Multi-Product Bookings in a Single Field:**
   * 28 bookings in the active cycle contain multiple distinct costumes bundled together using `+` or `,`.
   * Extreme example found in active cycle: `'Sainik * 2 , Suryadev , Indradev , Bramhaji , Shankarji , Sadhu * 2 , Ganga Maa , Raja * 2 , Rajkumar * 3 , Weapons , Horse Dress'`. Currently, the system counts this entire 16-item bundle as 1 booking of 1 single product!
   * Another example: `'Raja Harishchandra + Tarabai (Ornaments)'` (₹700) where neither king nor queen gets individual product credit.
3. **Uncounted Units Rented:**
   * Quantities marked with `* 2`, `* 3`, `* 8 Pair` are completely ignored by the existing dashboard. A booking of 8 pairs of Bhangra Rumals is counted as 1 unit.
4. **Embedded Price Adjustments & Damage Notes:**
   * Staff writes price breakdowns and damage penalties into the product string: e.g., `'Doctor (Damage 250)'`, `'Doctor (Damage 100)'`, `'Krishna (250 + 50 (Lost))'`.
5. **Variant Naming (Same Product, Multiple Labels):**
   * *Krishna:* `'Krishna'` (66), `'Krishna Dress'` (8), `'Krishna (Yellow)'`, `'Krishna Pink 28'`, `'New Krishna Heavy'`, `'Bal Krishna'`.
   * *Rani Laxmibai:* `'Jhanshi Ki Rani'` (15), `'Rani Laxmi Bai'` (2), `'Rani Laxmibai (500)'`, `'Jhanshi Ki Rani * 2'`.
   * *Subhash Chandra Bose:* `'Subhash Chandra Bose'` (14), `'Subhash Chandra Bose Dress'`, `'Subhas Chandra Bose'`.
   * *Doctor:* `'Doctor'` (11), `'Doctor Dress'` (2), `'Doctor Dress * 2 (Damage - 100)'`.
   * *Police:* `'Police'` (6), `'Police Dress'` (4).
6. **Missing Product Details:**
   * 5 records have empty or blank `details` strings.

### 2.2 Category Inconsistencies
1. **Booking Schema Role Reversal:**
   * In `Fancy_2026_2026`, the MongoDB field `costume` actually stores the **Category** (e.g., `Bhagwan`, `Profession`, `Freedom Fighter`), while `details` stores the product name.
   * In earlier legacy cycles (`Fancy`), `costume` sometimes stored the costume name (`Apple Dress`) and `details` stored customer reference notes (`Reference = Mahisagar Dairy`).
2. **Singular vs. Plural / Category Mismatch:**
   * `Costume_Category_Master` defines 30 canonical categories (e.g., `Wild Animal`, `Domestic Animal`, `Vegetables`, `Super Hero`).
   * `Fancy_Inventory` contains mismatched pluralizations and composites: `'Domestic Animals'`, `'Wild Animals'`, `'Vegetable'`, `'Superhero'`, `'Cartoon Haloween Profession'`, `'Wild Animals Christmas'`.
3. **Catch-all & Mixed Categories:**
   * Bookings labeled `Mix` or `Other` contain real outfits (e.g., freedom fighters or mythological characters) that are not attributed to their proper category.

### 2.3 School Affiliation Inconsistencies
1. **School Duplication & Typos:**
   * `'Jay Somnath'` (41 bookings) and `'Jay Somanth School'` (17 bookings) are the exact same institution.
   * `'Vedant'` (4 bookings) and `'Vedant International'` (7 bookings) are the same school.
2. **False School Winners:**
   * The 2nd most frequent school entry in the database is `'None'` (45 bookings) and `'Not Available'` (16 bookings).
   * Without filtering, the dashboard currently presents "None" as the top performing school runner-up!

### 2.4 Customer Metrics & Privacy Issues
1. **Flawed Scope of Current Dashboard:**
   * The existing dashboard displays "Top 20 Customers" by aggregating across **all historical cycles**, whereas the requirement mandates identifying the Top Customer for the **current cycle**.
2. **Customer Name Variations for Same Mobile:**
   * 6 mobile numbers have slightly different names across bookings (e.g., `Poonam Shah` vs `Poonam Ben Shah`, `Bhavesh Bhai` vs `Bhavesh Bhai Shah`).
3. **Severe Privacy Risk:**
   * The existing template displays customer mobile numbers in plaintext table cells and links (`<a href="tel:...">`).
   * Sending customer booking dumps directly to Gemini without scrubbing would violate the strict PII prohibition.

### 2.5 Visual & Analytical Limitations
1. **KPI Overload:** The current dashboard displays 8 KPI cards (`Total Bookings`, `Total Revenue`, `Avg Order Value`, `Active Customers`, `Total Inventory Units`, `Returned Outfits`, `Pending Returns`, `Awaiting Pickup`). The user requirements strictly demand **ONLY 4 primary metrics**.
2. **Spike Timeline lacks Anomaly Intelligence:** The velocity timeline displays raw counts without thresholding, anomaly detection, or AI-generated causal explanations.
3. **No Dynamic Drill-Downs:** There is no dedicated interactive drill-down for Category, Product, School, or Customer performance.

---

## 3. Proposed Dashboard Structure (Preserving Existing Theme)

The UI will strictly maintain the existing glassmorphic theme (`--bg-dark: #080b11`, `--panel-bg`, neon accents, card-glass hover effects, and Plus Jakarta Sans typography). The layout is streamlined and organized into logical, high-impact sections.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ TOP HEADER: BI Performance Dashboard | Cycle Selector [Dropdown] | Export Excel Button │
└────────────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────────────┐
│ PRIMARY METRICS GRID (Exactly 4 Cards):                                                │
│  [ Total Bookings ]       [ Total Revenue ]      [ Avg Order Value ]   [ Unique Cust. ]│
│    (Neon Blue)              (Neon Emerald)         (Neon Purple)         (Neon Amber)  │
└────────────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────────────┐
│ TAB NAVIGATION:                                                                        │
│  [ Tab 1: Executive Insights & Trends ]   [ Tab 2: Forecast & Cultural Velocity ]      │
└────────────────────────────────────────────────────────────────────────────────────────┘

─── TAB 1: EXECUTIVE INSIGHTS & TRENDS ──────────────────────────────────────────────────
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ BEST PERFORMERS SHOWCASE (4 Metric Highlight Cards):                                  │
│  [ Best Category: Units ]   [ Best Category: Rev ]  [ Best Prod: Units ] [ Best Prod: Rev]│
│  [ Top School (Current) ]   [ Top Customer (Cycle) ]                                   │
└────────────────────────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────┬────────────────────────────────────────────┐
│ CHART: Best Products by Revenue           │ CHART: Revenue Share by Category           │
│ (Ranked Horizontal Bar Chart - Clickable) │ (Advanced Doughnut / Polar Area - Clickable│
└───────────────────────────────────────────┴────────────────────────────────────────────┘

┌───────────────────────────────────────────┬────────────────────────────────────────────┐
│ CHART: Weekly Pickup Pattern              │ CHART: Monthly Revenue Trend               │
│ (Day of Week Peak Analysis - Mon to Sun)  │ (Seasonal Trajectory across Cycle Months)  │
└───────────────────────────────────────────┴────────────────────────────────────────────┘

┌───────────────────────────────────────────┬────────────────────────────────────────────┐
│ LEADERBOARDS ROW (Ranked Interactive Tables with Drill-down on Click):                 │
│  [ Top Schools by Revenue (Excl. None) ]      [ Top Products (Units & Revenue) ]      │
└───────────────────────────────────────────┴────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────────────┐
│ DASHBOARD-WIDE AI STRATEGIC INSIGHTS:                                                  │
│  • AI Executive Summary                                                               │
│  • Demand Shifts & Category Concentration Analysis                                     │
│  • Revenue Opportunities & Underperforming Risk Warnings                               │
└────────────────────────────────────────────────────────────────────────────────────────┘

─── TAB 2: FORECAST & CULTURAL VELOCITY ─────────────────────────────────────────────────
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ DAILY RENTAL VELOCITY & SPIKE TIMELINE:                                                │
│  • Line/Area chart tracking daily bookings                                            │
│  • Anomaly markers indicating detected surges (>2.5σ or >15 bookings/day)              │
│  • Interactive Anomaly Inspector: Click any spike to see AI causal analysis            │
└────────────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────────────┐
│ AI-POWERED ADVANCED FESTIVAL DEMAND FORECAST CALENDAR:                                 │
│  • Real-world upcoming Indian festivals (Upcoming date, countdown)                    │
│  • Expected demand level (High / Moderate / Normal)                                   │
│  • Potentially relevant dress categories & top historical costumes                    │
│  • AI Predictive Analysis: Historical booking volume (±3 days) vs current stock        │
│  • Actionable Procurement/Stitching Advice for business owners                         │
└────────────────────────────────────────────────────────────────────────────────────────┘

─── DYNAMIC DRILL-DOWN MODAL OVERLAY (Universal Glassmorphic Drawer/Modal) ─────────────
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ MODAL: [ Category / Product / School / Customer ] Detail View                          │
│  • Entity Title & Type Badge                                                           │
│  • Key Performance KPIs (Total Bookings, Units, Revenue, AOV, Min/Max Booking)         │
│  • Trend Chart (Timeline of bookings for this entity)                                  │
│  • AI Grounded Insights for selected entity (Non-sensitive data only)                  │
│  • Detailed Bookings Breakdown Table                                                   │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Data Normalization Strategy

To ensure deterministic, mathematically accurate analytics, raw booking strings must be normalized into a canonical structure **prior** to running any aggregations.

### 4.1 Canonical Data Model
Every raw booking record $b$ will yield one or more normalized line items:
$$\text{Booking } b \longrightarrow [ \text{Item}_1, \text{Item}_2, \dots, \text{Item}_k ]$$
Where each $\text{Item}$ contains:
* `canonical_product`: Standardized name (e.g., `"Krishna"`, `"Rani Laxmibai"`, `"Doctor"`).
* `canonical_category`: Standardized category mapped to `Costume_Category_Master` (e.g., `"Bhagwan"`, `"Freedom Fighter"`, `"Profession"`).
* `units`: Integer quantity extracted from multiplier expressions (default $1$).
* `allocated_revenue`: Monetary revenue allocated to this specific item.
* `school_clean`: Normalized school name (resolving aliases like `"Jay Somanth School"` $\to$ `"Jay Somnath"`).
* `booking_id`: Reference to parent booking document `_id`.
* `booking_date`: Normalized ISO date (`YYYY-MM-DD`).

### 4.2 Multi-Stage Normalization Pipeline
The normalization engine `website/fancy/fnormalizer.py` will execute a 4-phase deterministic pipeline:

```
[ Raw Booking Details ] 
         │
         ▼
[ Phase 1: Pre-Cleaning & Sanitation ]
  • Strip price tags: "(500 + 100(Damage))" -> damage: 100, item price: 500
  • Strip sizing tokens: "Krishna Yellow 22" -> size: 22, name: "Krishna Yellow"
  • Normalize whitespace, remove stray punctuation
         │
         ▼
[ Phase 2: Bundle Splitting & Extraction ]
  • Split composite bookings on '+' or ',' (e.g., "Ram + Laxman")
  • Extract individual multipliers (e.g., "* 2", "* 8 Pair", "3 pcs")
  • Identify accessories vs primary garments (e.g., "Pagh", "Talwar", "Mukut")
         │
         ▼
[ Phase 3: Canonical Entity Resolution ]
  • Dictionary & Regex Matcher against Fancy_Inventory & Costume_Category_Master
  • Levenshtein / Fuzzy Token Ratio (threshold >= 0.88) to prevent false merging
  • Alias Mapping Table for known variants:
      - 'Jhanshi Ki Rani', 'Rani Laxmi Bai' -> 'Rani Laxmibai'
      - 'Subhas Chandra Bose' -> 'Subhash Chandra Bose'
      - 'Krishna Dress', 'Krishna (Yellow)' -> 'Krishna'
      - 'Jay Somanth School' -> 'Jay Somnath'
         │
         ▼
[ Phase 4: Revenue & Category Allocation ]
  • Distribute parent booking price across split items
  • Map each item to its authoritative category in Costume_Category_Master
         │
         ▼
[ Output: Structured Normalized In-Memory Cache ]
```

### 4.3 Handling Complex Real-World Patterns
1. **Multiplier Handling (`*`):**
   * Pattern: `r'[\*xX]\s*(\d+)'` (e.g., `'Jhanshi Ki Rani * 2'` $\to$ product: `'Rani Laxmibai'`, units: `2`).
   * Pair pattern: `r'[\*xX]?\s*(\d+)\s*(?:pair|pairs)'` (e.g., `'Bhangra Rumal * 8 Pair'` $\to$ product: `'Bhangra Rumal'`, units: `8`).
2. **Bundles with Embedded Prices:**
   * Input: `'Ganeshji (500 + 100(Damage)) + Rani Laxmibai (500)'`, Total booking price = ₹1,100.
   * Extraction: Item 1 = `'Ganeshji'`, units: 1, rev: ₹600. Item 2 = `'Rani Laxmibai'`, units: 1, rev: ₹500.
3. **Bundles without Explicit Item Prices:**
   * Input: `'Ram + Laxman'`, Total booking price = ₹400.
   * Split: Item 1 = `'Ram'` (units: 1, rev: ₹200). Item 2 = `'Laxman'` (units: 1, rev: ₹200).
4. **Primary Outfit + Accessories:**
   * Input: `'Krishna Dress + Heavy Pagh'` or `'Raja Dress + Talwar'`.
   * The accessory (`Heavy Pagh`, `Talwar`) is flagged as an ornament/property, while the primary revenue and category (`Bhagwan` or `Historical Character`) are retained by the main dress.
5. **School Cleaning & Aliasing:**
   * If `school` in `['None', 'Not Available', '', None]`, mark `is_walkin: True` and exclude from school rankings.
   * Group aliases:
     * `{'Jay Somnath', 'Jay Somanth School'} -> 'Jay Somnath'`
     - `{'Vedant', 'Vedant International'} -> 'Vedant International'`
     - `{'Seventh Day Adventist'} -> 'Seventh Day Adventist'`

### 4.4 LLM-Assisted Normalization & Cold-Start Caching
* For rare or ambiguous strings that fail rule-based matching, a one-time LLM classification will run in batch mode during server startup/cache refresh.
* Results are persistently stored in a MongoDB collection `fancy_normalization_cache` (`raw_string` $\to$ `normalized_components`).
* **Zero Run-Time Latency:** Subsequent requests read directly from memory or the MongoDB cache; the LLM is never called repeatedly for previously normalized strings.

---

## 5. Analytics & Data Model Specifications

All metric computations will be deterministic Python functions in `website/fancy/fanalytics.py`.

### 5.1 Primary Dashboard Metrics (Current Cycle Only)
1. **Total Bookings:** Count of unique booking records in `get_selected_collection()`.
   $$\text{Total Bookings} = N = \sum_{b \in \text{CurrentCycle}} 1 \quad (= 422)$$
2. **Total Revenue:** Sum of all booking prices in the current cycle.
   $$\text{Total Revenue} = \sum_{b \in \text{CurrentCycle}} b.\text{price} \quad (= ₹1,34,550.00)$$
3. **Average Order Value (AOV):** Total revenue divided by total bookings.
   $$\text{AOV} = \frac{\text{Total Revenue}}{\text{Total Bookings}} \quad (= ₹318.84)$$
4. **Total Unique Customers:** Count of distinct customer mobile numbers in the current cycle.
   $$\text{Unique Customers} = \big| \{ b.\text{mobile} \mid b \in \text{CurrentCycle} \land b.\text{mobile} \ne \text{None} \} \big| \quad (= 284)$$

### 5.2 Best Performers Definitions (Current Cycle Only)
* **Best Category (Units Rented):** The category whose normalized items sum to the highest total units:
  $$\text{Category}_{\text{max\_units}} = \arg\max_{c} \sum_{i \in c} \text{units}_i \quad (\text{Expected: Bhagwan with } \approx 135\text{ units})$$
* **Best Category (Revenue):** The category generating the highest cumulative revenue:
  $$\text{Category}_{\text{max\_rev}} = \arg\max_{c} \sum_{i \in c} \text{revenue}_i \quad (\text{Expected: Bhagwan})$$
* **Best Product (Units):** The canonical dress design with the highest units rented:
  $$\text{Product}_{\text{max\_units}} = \arg\max_{p} \sum_{i \in p} \text{units}_i \quad (\text{Expected: Krishna with } \approx 82\text{ units})$$
* **Best Product (Revenue):** The canonical dress design generating the most revenue:
  $$\text{Product}_{\text{max\_rev}} = \arg\max_{p} \sum_{i \in p} \text{revenue}_i \quad (\text{Expected: Krishna})$$
* **Top School by Revenue (Current Cycle):**
  * Calculated exclusively for bookings in the current cycle where `school` $\notin \{\text{'None'}, \text{'Not Available'}, \text{''}\}$.
  * School revenue sums all booking prices belonging to each normalized school entity.
  * Expected leader: `Seventh Day Adventist` ($\approx ₹18,450$).
* **Top Customer (Current Cycle):**
  * **Business Definition:** The customer who spent the highest cumulative rental amount in the current cycle (Highest Cycle Customer Value / Revenue Contribution).
  * Tie-breaker: Highest number of bookings in the cycle.
  * Expected leader: `Vishal Bhai Oad` ($₹6,250$, 1 large bulk order) or highest frequency customer `Amit Bhai Bhogte` (4 bookings). Both will be presented: Revenue Leader with booking count and AOV.

### 5.3 Daily Rental Velocity & Anomaly Detection
1. **Daily Aggregation:** Group bookings by `start_date` ($d$) to compute daily volume $V_d$.
2. **Baseline Statistics:** Compute mean ($\mu$) and standard deviation ($\sigma$) of daily bookings across the cycle.
3. **Spike / Anomaly Threshold:**
   $$V_d \ge \mu + 2.0\sigma \quad \text{or} \quad V_d \ge 15 \text{ bookings}$$
4. **Context Gathering for Each Spike:**
   * Spike Date: $d$.
   * Top School: $\arg\max_s \text{count}(s, d)$.
   * Top Category: $\arg\max_c \text{count}(c, d)$.
   * Top Product: $\arg\max_p \text{count}(p, d)$.
   * Proximity to Festivals: Compare $d$ against the cultural calendar (e.g., Aug 13 is 2 days before Independence Day; Sep 02 is 1 day before Janmashtami).
   * Passed to Gemini to generate factual, grounded anomaly explanations.

---

## 6. AI / LLM Architecture & Data Privacy Strategy

### 6.1 Privacy Enforcement: Complete PII Scrubbing
> [!IMPORTANT]
> **Strict Privacy Guarantee:** Customer mobile numbers and addresses are **strictly excluded** from all LLM prompts. 

Data sent to Gemini will undergo an irreversible sanitization step via `sanitize_for_ai()`:
* **Excluded:** `mobile`, `address`, `home_address`, `locality`, `customer_id`, timestamps with exact seconds.
* **Permitted:** `customer_first_name` (optional pseudonymized label like `"Customer A"` or `"Poonam S."`), `canonical_product`, `category`, `units`, `price`, `revenue`, `start_date`, `school_name`, `festival_name`, `days_to_festival`.

```python
# Conceptual sanitization function in website/fancy/fai.py
def sanitize_booking_for_ai(b):
    return {
        "date": b.get("start_date"),
        "category": b.get("canonical_category"),
        "product": b.get("canonical_product"),
        "units": b.get("units", 1),
        "revenue": b.get("allocated_revenue", 0),
        "school": b.get("school_clean") if b.get("school_clean") != "None" else "Private Booking"
    }
```

### 6.2 Model & Client Configuration
* **SDK:** `google.genai` (`from google import genai`).
* **Model:** `gemini-3.6-flash` (tested and verified operational with the existing `GEMINI_API_KEY`).
* **Temperature:** `0.2` for structured analytics and anomaly explanations (preventing hallucination); `0.4` for executive dashboard insights.
* **Response Format:** JSON Schema structured outputs using `response_mime_type="application/json"`.

### 6.3 AI Operational Modules
1. **Anomaly Explainer (`explain_spikes`):**
   * Input: Structured summary of spike dates, volumes, top products, top categories, top schools, and cultural calendar proximity.
   * Output: Clear 2–3 sentence causal explanations based exclusively on provided metrics.
2. **Advanced Cultural Demand Forecaster (`forecast_festival_demand`):**
   * Input: Historical rental spikes ($\pm 3$ days window) across all 3 cycles, current inventory counts from `Fancy_Inventory`, and upcoming Indian festivals.
   * Output: Actionable procurement advisory: expected high-demand categories, dresses with projected deficit, and tailored stocking recommendations.
3. **Executive Dashboard Insights (`generate_dashboard_insights`):**
   * Input: Aggregated metrics (Total Bookings, Revenue, AOV, Top Categories, Top Products, Top Schools, Day-of-Week distribution).
   * Output: Structured insights highlighting top revenue drivers, operational risks, school concentrations, and seasonal opportunities.
4. **Drill-Down Entity Insights (`generate_entity_insights`):**
   * Input: Aggregated performance metrics for a single selected category, product, school, or customer.
   * Output: Tailored 3-bullet business takeaways.

### 6.4 AI Caching & Cost Optimization
* All Gemini responses will be cached in MongoDB collection `fancy_ai_cache` keyed by `(task_type, cycle_id, data_hash)`.
* Cache TTL: 24 hours (or invalidates automatically when new bookings are added).
* Dashboard page loads will retrieve cached insights instantly (0ms latency), with a manual "🔄 Refresh AI Insights" button for on-demand re-generation.

---

## 7. Visualization Plan

| # | Chart Name | Chart Type | Dimensions & Metrics | Interaction | Business Value |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | **Daily Rental Velocity & Spike Timeline** | Smooth Area Line Chart with Scatter Anomaly Points | **X:** Event Start Date<br>**Y:** Bookings Count<br>**Annotations:** Spike Markers (>2.5σ) | Hover for day summary; Click spike marker to open AI anomaly explanation modal. | Identifies peak operational load days, staffing needs, and prep window before festivals. |
| 2 | **Best Products by Revenue** | Horizontal Bar Chart | **X:** Total Revenue (₹)<br>**Y:** Canonical Product Name (Top 12) | Click bar to open Product Drill-Down Modal. | Identifies which specific costumes are primary revenue drivers vs low-return catalog items. |
| 3 | **Category Revenue Share** | Cutout Doughnut Chart (65% cutout) with Legend | **Slices:** Category Name<br>**Values:** Category Total Revenue (₹) & % share | Hover for percentage and total bookings; Click slice to open Category Drill-Down Modal. | Visualizes revenue concentration across costume categories (e.g. Bhagwan vs Profession vs Freedom Fighter). |
| 4 | **Top Schools by Revenue** | Horizontal Stacked/Ranked Bar Chart | **X:** Revenue (₹)<br>**Y:** School Name (Top 10, excluding None/Walk-in) | Click bar to open School Drill-Down Modal. | Identifies key institutional B2B accounts driving repeat bulk bookings for school annual functions. |
| 5 | **Weekly Pick-Up Pattern** | Vertical Bar Chart (Color Gradient by Intensity) | **X:** Day of Week (Mon $\to$ Sun)<br>**Y:** Rental Pickup Count | Tooltip shows % of total weekly pickups. | Optimizes store staffing, ironing schedules, and customer intake logistics on peak pickup days. |
| 6 | **Monthly Revenue Trend** | Vertical Bar Chart / Trend Line | **X:** Months of Active Cycle<br>**Y:** Monthly Revenue (₹) | Tooltip shows monthly growth and booking count. | Tracks seasonal income progression and compares month-over-month performance. |

---

## 8. Drill-Down UX Specifications

When a user clicks on an entity anywhere on the dashboard, a responsive Glassmorphic Drill-Down Modal (`#drilldownModal`) opens dynamically without a full page reload.

### 8.1 Category Drill-Down View
* **Trigger:** Clicking a category in the Best Category card, category chart slice, or leaderboard table.
* **Key Metrics Displayed:**
  * Total Bookings
  * Total Units Rented
  * Total Revenue (₹)
  * Average Booking Value (₹)
  * Highest Booking Value (₹) & Lowest Booking Value (₹)
  * Most Rented Product in this Category
* **Visuals:**
  * Mini-timeline of category bookings across the cycle.
  * Bar list of top costumes belonging to this category.
* **AI Category Insights:**
  * Concise LLM evaluation of demand stability, seasonal peaks, and recommended catalog expansion.

### 8.2 Product Drill-Down View
* **Trigger:** Clicking any dress row or bar in the Best Products chart/table.
* **Key Metrics Displayed:**
  * Total Bookings Count
  * Total Physical Units Rented (accounting for multipliers)
  * Total Revenue Generated (₹)
  * Average Booking Quantity (units/booking)
  * Highest Single Booking (units & ₹)
  * Lowest Single Booking (₹)
* **Visuals:**
  * Rental timeline chart showing product seasonality.
  * Size/variant breakdown (if available from inventory).
* **AI Product Insights:**
  * Commentary on whether demand is event-specific (e.g., Independence Day only) or consistent year-round.

### 8.3 School Drill-Down View
* **Trigger:** Clicking a school row or bar in the School Leaderboard chart/table.
* **Key Metrics Displayed:**
  * Total Bookings Associated
  * Total Outfits Rented
  * Total Revenue Contributed (₹)
  * Average Spend per Booking (₹)
  * Highest Value Booking (₹)
  * Primary Costume Categories ordered by this school
* **Visuals:**
  * Breakdown of categories rented by this school (e.g. 70% Freedom Fighter, 30% Profession).
  * Recent booking orders table.
* **AI School Insights:**
  * Analysis of annual function themes and seasonal ordering cycles for institutional client retention.

### 8.4 Customer Drill-Down View
* **Trigger:** Clicking a customer row in the Top Customer card or table.
* **Privacy Check:** Mobile number and address are displayed in the UI for the shopkeeper's operational use, but are **completely stripped** before generating AI insights.
* **Key Metrics Displayed:**
  * Customer Name & Masked Mobile Display
  * Total Bookings (Current Cycle & All-Time)
  * Total Revenue Contributed (₹)
  * Average Order Value (₹)
  * Favorite / Most Rented Costumes
  * Order History Table with pickup/return status
* **AI Customer Insights:**
  * Rental loyalty pattern analysis, frequency analysis, and VIP retention notes based strictly on non-sensitive rental history.

---

## 9. Performance Strategy

1. **Deterministic Processing in Python / Backend:**
   * 422 bookings take $< 5\text{ ms}$ to process in Python memory. All mathematical counts, sums, rankings, and standard deviations will be computed deterministically without invoking the LLM.
2. **In-Memory Normalization Cache:**
   * Build a lightweight lookup dictionary for distinct `details` strings ($209$ unique strings in the active cycle). Normalized items are calculated once and stored in an LRU/dictionary cache.
3. **Selective LLM Payloads:**
   * Instead of dumping hundreds of raw documents to Gemini, only aggregated summary tables ($< 1.5\text{ KB}$ JSON) are passed.
4. **MongoDB Result Caching for AI Insights (`fancy_ai_cache`):**
   * Expensive Gemini calls are cached by a hash of the underlying data. Page reloads will fetch cached AI insights in $\approx 2\text{ ms}$.
5. **Asynchronous / Lazy Loading for Drill-Downs:**
   * Drill-down analytics and AI entity insights will be fetched on demand via lightweight JSON API endpoints (`/api/fancy/drilldown/...`) so the primary dashboard page loads instantaneously.

---

## 10. Files & Components to Change

> **Reminder:** These files are planned for modification **only after** user review and approval.

| File Path | Nature of Modification | Rationale |
| :--- | :--- | :--- |
| `website/fancy/froutes.py` | Update route handler `fancy_dashboard()`; add API endpoints for drill-downs and AI caching. | Implement 4 primary KPIs, integrate normalization engine, pass normalized data structures to template, handle async drill-down requests. |
| `website/templates/fancy/fancy_dashboard.html` | Update template layout, KPI grid, Chart.js configs, and drill-down modal scripts. | Conform to exact 4 KPI cards, upgrade charts, wire interactive click handlers, embed AI anomaly explainers and festival forecast advisory. |

---

## 11. Files & Components to Create

| File Path | Component Name | Rationale |
| :--- | :--- | :--- |
| `website/fancy/fnormalizer.py` | Data Normalization Engine | Extracts canonical products, quantities (`*`), bundles (`+`), price breakdowns, and maps categories and school aliases. |
| `website/fancy/fanalytics.py` | Deterministic Analytics Engine | Computes cycle KPIs, top performers, day-of-week demand, monthly trajectory, anomaly thresholds, and drill-down metrics. |
| `website/fancy/fai.py` | Gemini LLM Service Module | Integrates `gemini-3.6-flash`, enforces 100% PII stripping, manages prompt templates, and handles MongoDB AI response caching. |

---

## 12. Risks & Ambiguities

1. **Large Multi-Costume Orders with Single Lump-Sum Price:**
   * In records like `'Sainik * 2 , Suryadev , Indradev ...'` (₹1,500 total), individual costume prices are not recorded by the cashier.
   * *Proposed Handling:* Divide the total price evenly across the extracted total units ($₹1,500 / 16 \approx ₹93.75$ per unit) so product revenue rankings remain fair and balanced.
2. **Accessory vs Primary Garment Attribution:**
   * In `'Raja Dress + Talwar'` or `'Krishna Dress + Heavy Pagh'`, Talwar and Pagh are accessories.
   * *Proposed Handling:* Catalog items matching known accessory keywords (`Pagh`, `Mukut`, `Talwar`, `Ornaments`, `Dhoti`, `Dupatta`, `Stick`) when paired with a main costume will have their revenue credited to the primary outfit.
3. **Walk-in Bookings labeled "None" / "Not Available":**
   * 61 bookings lack a school affiliation.
   * *Proposed Handling:* Explicitly filter out `'None'` and `'Not Available'` from the School Leaderboard to prevent a non-school from ranking in the Top 3.
4. **Customer Mobile Reuse across Family Members:**
   * 6 mobile numbers have multiple customer names (e.g. husband/wife).
   * *Proposed Handling:* Group customer records strictly by unique `mobile`, displaying the most recently recorded customer name.

---

## 13. Staged Implementation Order

Once this plan is reviewed and approved, execution will proceed in 4 strictly controlled stages:

* **Stage 1 — Normalization & Analytics Engine (`fnormalizer.py` & `fanalytics.py`):**
  * Implement and unit test canonical parsing of `details`, multiplier extraction (`*`), bundle splitting (`+`), category mapping, and school alias resolution.
  * Verify deterministic calculations against active cycle (`Fancy_2026_2026`).
* **Stage 2 — Gemini Integration & Privacy Sanitization (`fai.py`):**
  * Build the sanitized AI pipeline with `gemini-3.6-flash`.
  * Implement MongoDB caching in `fancy_ai_cache`.
  * Validate that no phone numbers or addresses ever leave the application.
* **Stage 3 — Route Controllers & APIs (`froutes.py`):**
  * Update `/fancy_dashboard` controller to use `fanalytics.py` and `fai.py`.
  * Add drill-down JSON API endpoints (`/api/fancy/drilldown/<type>/<id>`).
  * Update Excel export to reflect canonical normalized items.
* **Stage 4 — Dashboard UI & Advanced Visualizations (`fancy_dashboard.html`):**
  * Update KPI cards to the strict 4 required metrics.
  * Upgrade Chart.js configurations (ranked bar, doughnut, weekly pickup, monthly trend).
  * Build the interactive Anomaly Inspector on the spike timeline.
  * Upgrade the Indian Festival Forecast table with dynamic AI stocking recommendations.
  * Connect interactive click events for Category, Product, School, and Customer drill-down modals.
  * Verify full visual theme preservation.

---
*End of PLAN.md — Awaiting User Review and Approval.*
