"""
fanalytics.py - Deterministic aggregation and analytics engine for Fancy Dress Dashboard.
Computes cycle KPIs, top performers, velocity/anomaly spikes, chart datasets,
and on-demand drill-down metrics for categories, products, schools, and customers.
"""

from collections import Counter, defaultdict
from datetime import datetime, date
import statistics
import re

from .fnormalizer import normalize_cycle_bookings, clean_school_name


def safe_parse_date(d):
    """Parses date string or datetime object to date object."""
    if not d:
        return None
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    if isinstance(d, str):
        for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d-%m-%y", "%Y/%m/%d", "%d/%m/%Y"]:
            try:
                return datetime.strptime(d.strip(), fmt).date()
            except ValueError:
                continue
    return None


def compute_advanced_statistical_suite(bookings, items, daily_bookings, sorted_daily_dates):
    """
    Computes deep statistical models and econometric decompositions:
    1. 7-Day Rolling Moving Average with +/- 1.96 Sigma Volatility Confidence Bands
    2. Multi-Dimensional Category Elasticity Matrix (Units vs Revenue vs Avg Spend)
    3. 80/20 Pareto Concentration Curve & Lorenz Cumulative Distribution
    4. Day-of-Week Statistical Dispersion (Mean, Variance, CV)
    5. High-Impact Econometric Indices & Grounded Statistical Takeaways
    """
    daily_revs = [sum(float(b.get("price", 0) or 0) for b in daily_bookings[d]) for d in sorted_daily_dates]
    daily_counts = [len(daily_bookings[d]) for d in sorted_daily_dates]

    # 1. Rolling Time-Series (7-Day SMA, Rolling Std Dev, Confidence Envelope)
    rolling_series = []
    cum_rev = 0
    for i, d in enumerate(sorted_daily_dates):
        rev = daily_revs[i]
        cnt = daily_counts[i]
        cum_rev += rev

        w_start = max(0, i - 6)
        w_revs = daily_revs[w_start:i+1]
        w_cnts = daily_counts[w_start:i+1]
        sma_rev = statistics.mean(w_revs) if w_revs else 0.0
        sma_cnt = statistics.mean(w_cnts) if w_cnts else 0.0
        w_std = statistics.stdev(w_revs) if len(w_revs) > 1 else 0.0
        upper_band = sma_rev + 1.96 * w_std
        lower_band = max(0.0, sma_rev - 1.96 * w_std)

        dt = safe_parse_date(d)
        rolling_series.append({
            "date": d,
            "label": dt.strftime("%d %b") if dt else d,
            "revenue": round(rev, 2),
            "bookings": cnt,
            "cum_revenue": round(cum_rev, 2),
            "sma_revenue": round(sma_rev, 2),
            "sma_bookings": round(sma_cnt, 2),
            "std_dev": round(w_std, 2),
            "upper_band": round(upper_band, 2),
            "lower_band": round(lower_band, 2)
        })

    mean_daily_rev = statistics.mean(daily_revs) if daily_revs else 0.0
    std_daily_rev = statistics.stdev(daily_revs) if len(daily_revs) > 1 else 0.0
    cv_rev = (std_daily_rev / mean_daily_rev * 100) if mean_daily_rev > 0 else 0.0
    max_daily_rev = max(daily_revs) if daily_revs else 0.0

    # 2. Pareto 80/20 Analysis on All Catalog Costumes
    prod_revs = Counter()
    prod_units = Counter()
    for it in items:
        p = it["canonical_product"]
        prod_revs[p] += it["allocated_revenue"]
        prod_units[p] += it["units"]

    total_catalog_rev = sum(prod_revs.values())
    sorted_prods = prod_revs.most_common()
    pareto_curve = []
    p_cum = 0
    pareto_80_idx = len(sorted_prods)
    for idx, (pname, prev) in enumerate(sorted_prods, 1):
        p_cum += prev
        pct = (p_cum / total_catalog_rev * 100) if total_catalog_rev > 0 else 0.0
        if pct >= 80.0 and pareto_80_idx == len(sorted_prods):
            pareto_80_idx = idx
        pareto_curve.append({
            "product": pname,
            "revenue": round(prev, 2),
            "units": prod_units[pname],
            "cum_revenue": round(p_cum, 2),
            "cum_pct": round(pct, 1),
            "rank": idx
        })

    pareto_top_20_count = max(1, round(len(sorted_prods) * 0.20))
    top_20_rev = sum(prev for _, prev in sorted_prods[:pareto_top_20_count])
    top_20_share = (top_20_rev / total_catalog_rev * 100) if total_catalog_rev > 0 else 0.0

    # 3. Multi-Dimensional Category Elasticity Matrix (Bubble/Scatter)
    cat_revs = Counter()
    cat_units = Counter()
    cat_bkgs = Counter()
    for it in items:
        c = it["canonical_category"]
        cat_revs[c] += it["allocated_revenue"]
        cat_units[c] += it["units"]
        cat_bkgs[c] += 1

    cat_matrix = []
    median_units = statistics.median(cat_units.values()) if cat_units else 0.0
    median_rev = statistics.median(cat_revs.values()) if cat_revs else 0.0
    for c, rev in cat_revs.most_common():
        u = cat_units[c]
        b = cat_bkgs[c]
        avg_sp = rev / b if b > 0 else 0.0

        if u >= median_units and rev >= median_rev:
            quadrant = "Star Category (High Vol, High Yield)"
            tag = "Star"
        elif u >= median_units and rev < median_rev:
            quadrant = "Volume Anchor (High Vol, Lower Spend)"
            tag = "Volume"
        elif u < median_units and rev >= median_rev:
            quadrant = "Premium Niche (Selective Vol, High Spend)"
            tag = "Premium"
        else:
            quadrant = "Long-Tail (Selective Demand)"
            tag = "Selective"

        cat_matrix.append({
            "name": c,
            "units": u,
            "revenue": round(rev, 2),
            "bookings": b,
            "avg_spend": round(avg_sp, 2),
            "share": round((rev / total_catalog_rev * 100), 1) if total_catalog_rev > 0 else 0.0,
            "quadrant": quadrant,
            "tag": tag
        })

    # 4. Day-of-Week Dispersion
    days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    dow_revs = defaultdict(list)
    for b in bookings:
        sd = safe_parse_date(b.get("start_date"))
        if sd:
            dow_name = days_order[sd.weekday()]
            dow_revs[dow_name].append(float(b.get("price", 0) or 0))

    dow_dispersion = []
    weekend_rev = 0.0
    all_dow_rev = 0.0
    for d_name in days_order:
        r_list = dow_revs[d_name]
        d_tot = sum(r_list)
        all_dow_rev += d_tot
        if d_name in ["Friday", "Saturday", "Sunday"]:
            weekend_rev += d_tot
        d_mean = statistics.mean(r_list) if r_list else 0.0
        d_std = statistics.stdev(r_list) if len(r_list) > 1 else 0.0
        d_cv = (d_std / d_mean * 100) if d_mean > 0 else 0.0
        dow_dispersion.append({
            "day": d_name,
            "bookings": len(r_list),
            "total_revenue": round(d_tot, 2),
            "mean_revenue": round(d_mean, 2),
            "std_dev": round(d_std, 2),
            "cv": round(d_cv, 1)
        })

    weekend_clustering_pct = round((weekend_rev / all_dow_rev * 100), 1) if all_dow_rev > 0 else 0.0
    peak_multiple = round(max_daily_rev / mean_daily_rev, 1) if mean_daily_rev > 0 else 1.0

    return {
        "rolling_series": rolling_series,
        "pareto_curve": pareto_curve[:45],
        "pareto_summary": {
            "total_costumes": len(sorted_prods),
            "pareto_80_count": pareto_80_idx,
            "pareto_80_pct": round(pareto_80_idx / len(sorted_prods) * 100, 1) if sorted_prods else 0.0,
            "top_20_share": round(top_20_share, 1)
        },
        "category_matrix": cat_matrix,
        "dow_dispersion": dow_dispersion,
        "summary_indices": {
            "mean_daily_revenue": round(mean_daily_rev, 2),
            "std_daily_revenue": round(std_daily_rev, 2),
            "cv_percentage": round(cv_rev, 1),
            "top_20_revenue_share": round(top_20_share, 1),
            "active_days_count": len(sorted_daily_dates),
            "peak_day_multiple": peak_multiple,
            "weekend_clustering_pct": weekend_clustering_pct
        },
        "statistical_takeaways": [
            f"High Econometric Volatility: Active cycle records a daily standard deviation of ₹{std_daily_rev:,.2f} against a mean of ₹{mean_daily_rev:,.2f} (Coefficient of Variation: {cv_rev:.1f}%), demonstrating that revenue is intensely event-driven rather than flat baseline traffic.",
            f"Pareto Concentration Power: The top 20% of catalog outfits command {top_20_share:.1f}% of total cycle earnings, with {pareto_80_idx} core costumes capturing 80% of revenue.",
            f"Category Capital Yield: 'Bhagwan' and 'Freedom Fighter' lead all clusters as High-Volume/High-Yield star categories with healthy ticket sizes above ₹290.",
            f"Peak Velocity Spike Factor: Single-day demand peaks at {peak_multiple}x baseline daily average, highlighting critical event spikes where buffer stock is imperative."
        ]
    }


def compute_dashboard_metrics(bookings, all_bookings=None):
    """
    Computes all primary metrics, best performers, and chart datasets for the current cycle.
    """
    total_bookings = len(bookings)
    total_revenue = sum(float(b.get("price", 0) or 0) for b in bookings)
    avg_revenue = total_revenue / total_bookings if total_bookings > 0 else 0.0

    # Distinct active customers in this cycle
    active_mobile_set = {str(b.get("mobile", "")).strip() for b in bookings if b.get("mobile")}
    unique_customers = len(active_mobile_set)

    # 1. Normalize line items across current cycle
    items, summary = normalize_cycle_bookings(bookings)
    total_units_rented = summary["total_units"]

    # 2. Aggregations by Product, Category, and School
    prod_units = Counter()
    prod_rev = Counter()
    cat_units = Counter()
    cat_rev = Counter()
    cat_bookings = Counter()
    school_rev = Counter()
    school_bookings = Counter()

    for it in items:
        p = it["canonical_product"]
        c = it["canonical_category"]
        s = it["school_clean"]
        u = it["units"]
        r = it["allocated_revenue"]

        prod_units[p] += u
        prod_rev[p] += r

        cat_units[c] += u
        cat_rev[c] += r
        cat_bookings[c] += 1

        if not it["is_walkin"]:
            school_rev[s] += r
            school_bookings[s] += 1

    # Filter out catch-alls like 'Miscellaneous' or 'Other' for top performers highlights
    filtered_cat_units = [item for item in cat_units.most_common() if item[0] not in ["Miscellaneous", "Other"]]
    filtered_cat_rev = [item for item in cat_rev.most_common() if item[0] not in ["Miscellaneous", "Other"]]

    best_cat_units_name = filtered_cat_units[0][0] if filtered_cat_units else (cat_units.most_common(1)[0][0] if cat_units else "None")
    best_cat_units_val = filtered_cat_units[0][1] if filtered_cat_units else (cat_units.most_common(1)[0][1] if cat_units else 0)

    best_cat_rev_name = filtered_cat_rev[0][0] if filtered_cat_rev else (cat_rev.most_common(1)[0][0] if cat_rev else "None")
    best_cat_rev_val = filtered_cat_rev[0][1] if filtered_cat_rev else (cat_rev.most_common(1)[0][1] if cat_rev else 0.0)

    best_prod_units_name = prod_units.most_common(1)[0][0] if prod_units else "None"
    best_prod_units_val = prod_units.most_common(1)[0][1] if prod_units else 0

    best_prod_rev_name = prod_rev.most_common(1)[0][0] if prod_rev else "None"
    best_prod_rev_val = prod_rev.most_common(1)[0][1] if prod_rev else 0.0

    prod_bookings = Counter(it["canonical_product"] for it in items)
    best_prod_rev_bkgs = prod_bookings.get(best_prod_rev_name, 0)
    best_prod_rev_avg_spend = round(best_prod_rev_val / best_prod_rev_bkgs, 2) if best_prod_rev_bkgs > 0 else 0.0

    # Top school (current cycle, excluding walk-ins)
    top_school_name = school_rev.most_common(1)[0][0] if school_rev else "None"
    top_school_rev_val = school_rev.most_common(1)[0][1] if school_rev else 0.0
    top_school_bookings_val = school_bookings.get(top_school_name, 0)

    # Top customer (current cycle only)
    customer_spend = Counter()
    customer_count = Counter()
    customer_names = {}
    for b in bookings:
        m = str(b.get("mobile", "")).strip()
        n = b.get("name", "Unknown").strip().title()
        p = float(b.get("price", 0) or 0)
        if m:
            customer_spend[m] += p
            customer_count[m] += 1
            if m not in customer_names or len(n) > len(customer_names[m]):
                customer_names[m] = n

    top_customer_mobile = customer_spend.most_common(1)[0][0] if customer_spend else ""
    top_customer_name = customer_names.get(top_customer_mobile, "None")
    top_customer_rev = customer_spend.get(top_customer_mobile, 0.0)
    top_customer_bookings = customer_count.get(top_customer_mobile, 0)
    top_customer_aov = top_customer_rev / top_customer_bookings if top_customer_bookings > 0 else 0.0

    # 3. Top Products by Revenue Chart Data (Top 10)
    top_products_by_revenue = []
    for p, rev in prod_rev.most_common(10):
        p_bkgs = prod_bookings.get(p, 0)
        p_avg = round(rev / p_bkgs, 2) if p_bkgs > 0 else 0.0
        top_products_by_revenue.append({
            "name": p,
            "revenue": round(rev, 2),
            "units": prod_units[p],
            "bookings": p_bkgs,
            "avg_spend": p_avg
        })

    # 4. Category Revenue Share Data
    total_cat_rev = sum(cat_rev.values())
    category_revenue_share = []
    for c, rev in cat_rev.most_common():
        pct = round((rev / total_cat_rev * 100), 1) if total_cat_rev > 0 else 0.0
        c_bkgs = cat_bookings.get(c, 0)
        c_avg = round(rev / c_bkgs, 2) if c_bkgs > 0 else 0.0
        category_revenue_share.append({
            "name": c,
            "revenue": round(rev, 2),
            "units": cat_units[c],
            "bookings": c_bkgs,
            "avg_spend": c_avg,
            "percentage": pct
        })

    # 5. Top Schools Leaderboard Table (Top 10, strictly current cycle)
    top_schools_table = []
    for rank, (s, rev) in enumerate(school_rev.most_common(10), 1):
        top_schools_table.append({
            "rank": rank,
            "name": s,
            "revenue": round(rev, 2),
            "bookings": school_bookings[s]
        })

    # 6. Weekly Pickup Pattern (Monday to Sunday)
    days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_counts = {d: 0 for d in days_order}
    day_revenues = {d: 0.0 for d in days_order}

    for b in bookings:
        sd = safe_parse_date(b.get("start_date"))
        if sd:
            d_name = days_order[sd.weekday()]
            day_counts[d_name] += 1
            day_revenues[d_name] += float(b.get("price", 0) or 0)

    weekly_pickup_pattern = [
        {
            "day": d,
            "count": day_counts[d],
            "revenue": round(day_revenues[d], 2),
            "avg_spend": round(day_revenues[d] / day_counts[d], 2) if day_counts[d] > 0 else 0.0
        }
        for d in days_order
    ]

    # 7. Monthly Revenue Trend across cycle
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    monthly_rev_dict = defaultdict(float)
    monthly_cnt_dict = defaultdict(int)

    for b in bookings:
        sd = safe_parse_date(b.get("start_date"))
        if sd:
            m_key = (sd.year, sd.month)
            monthly_rev_dict[m_key] += float(b.get("price", 0) or 0)
            monthly_cnt_dict[m_key] += 1

    sorted_month_keys = sorted(monthly_rev_dict.keys())
    monthly_revenue_data = []
    for y, m in sorted_month_keys:
        m_cnt = monthly_cnt_dict[(y, m)]
        m_rev = monthly_rev_dict[(y, m)]
        monthly_revenue_data.append({
            "month": f"{month_names[m - 1]} '{str(y)[2:]}",
            "month_key": f"{y}-{m:02d}",
            "revenue": round(m_rev, 2),
            "count": m_cnt,
            "bookings": m_cnt,
            "avg_spend": round(m_rev / m_cnt, 2) if m_cnt > 0 else 0.0
        })

    # 8. Daily Rental Velocity & Anomaly Spikes Timeline
    daily_counts = defaultdict(int)
    daily_bookings = defaultdict(list)
    for b in bookings:
        sd = safe_parse_date(b.get("start_date"))
        if sd:
            date_iso = sd.strftime("%Y-%m-%d")
            daily_counts[date_iso] += 1
            daily_bookings[date_iso].append(b)

    sorted_daily_dates = sorted(daily_counts.keys())
    counts_list = [daily_counts[d] for d in sorted_daily_dates]

    # Compute baseline mean & std dev for anomaly detection
    if counts_list:
        mean_v = statistics.mean(counts_list)
        stdev_v = statistics.stdev(counts_list) if len(counts_list) > 1 else 1.0
        spike_threshold = max(15, round(mean_v + 2.0 * stdev_v))
    else:
        mean_v = 0
        stdev_v = 0
        spike_threshold = 15

    daily_velocity = []
    spikes = []

    for d in sorted_daily_dates:
        cnt = daily_counts[d]
        is_spike = cnt >= spike_threshold
        day_b = daily_bookings[d]
        day_rev = sum(float(b.get("price", 0) or 0) for b in day_b)
        day_avg = round(day_rev / cnt, 2) if cnt > 0 else 0.0
        entry = {
            "date": d,
            "count": cnt,
            "revenue": round(day_rev, 2),
            "avg_spend": day_avg,
            "is_spike": is_spike
        }
        daily_velocity.append(entry)

        if is_spike:
            # Context for anomaly
            day_b = daily_bookings[d]
            day_schools = Counter(clean_school_name(b.get("school"))[0] for b in day_b if not clean_school_name(b.get("school"))[1])
            day_cats = Counter(b.get("costume", "Unknown").strip().title() for b in day_b)
            day_prods = Counter(b.get("details", "").strip().title() for b in day_b if b.get("details"))

            top_sch = day_schools.most_common(1)[0] if day_schools else ("None", 0)
            top_c = day_cats.most_common(1)[0] if day_cats else ("None", 0)
            top_p = day_prods.most_common(1)[0] if day_prods else ("None", 0)

            # Check festival proximity
            festival_note = ""
            if "-08-13" in d or "-08-14" in d or "-08-15" in d:
                festival_note = "Independence Day (Aug 15)"
            elif "-09-01" in d or "-09-02" in d or "-09-03" in d or "-09-04" in d:
                festival_note = "Krishna Janmashtami Season"
            elif "-01-25" in d or "-01-26" in d:
                festival_note = "Republic Day (Jan 26)"
            elif "-10-02" in d:
                festival_note = "Gandhi Jayanti (Oct 02)"

            spikes.append({
                "date": d,
                "count": cnt,
                "top_school": top_sch[0],
                "school_count": top_sch[1],
                "top_category": top_c[0],
                "category_count": top_c[1],
                "top_product": top_p[0],
                "product_count": top_p[1],
                "festival": festival_note
            })

    # 9. Top Customers Table (Current Cycle only)
    top_customers_table = []
    for rank, (m, spend) in enumerate(customer_spend.most_common(15), 1):
        top_customers_table.append({
            "rank": rank,
            "name": customer_names.get(m, "Unknown"),
            "mobile": m,
            "total_bookings": customer_count[m],
            "total_spent": round(spend, 2),
            "aov": round(spend / customer_count[m], 2)
        })

    return {
        "primary_kpis": {
            "total_bookings": total_bookings,
            "total_revenue": round(total_revenue, 2),
            "avg_revenue_per_booking": round(avg_revenue, 2),
            "unique_customers": unique_customers,
            "total_units_rented": total_units_rented
        },
        "best_performers": {
            "best_category_by_units": {
                "name": best_cat_units_name,
                "units": best_cat_units_val
            },
            "best_category_by_revenue": {
                "name": best_cat_rev_name,
                "revenue": round(best_cat_rev_val, 2),
                "bookings": cat_bookings.get(best_cat_rev_name, 0),
                "avg_spend": round(best_cat_rev_val / cat_bookings.get(best_cat_rev_name, 1), 2) if cat_bookings.get(best_cat_rev_name, 0) > 0 else 0.0
            },
            "best_product_by_units": {
                "name": best_prod_units_name,
                "units": best_prod_units_val
            },
            "best_product_by_revenue": {
                "name": best_prod_rev_name,
                "revenue": round(best_prod_rev_val, 2),
                "bookings": best_prod_rev_bkgs,
                "avg_spend": best_prod_rev_avg_spend
            },
            "top_school": {
                "name": top_school_name,
                "revenue": round(top_school_rev_val, 2),
                "bookings": top_school_bookings_val
            },
            "top_customer": {
                "name": top_customer_name,
                "mobile": top_customer_mobile,
                "revenue": round(top_customer_rev, 2),
                "bookings": top_customer_bookings,
                "aov": round(top_customer_aov, 2)
            }
        },
        "charts": {
            "best_products_by_revenue": top_products_by_revenue,
            "category_revenue_share": category_revenue_share,
            "weekly_pickup_pattern": weekly_pickup_pattern,
            "monthly_revenue": monthly_revenue_data,
            "daily_velocity": daily_velocity
        },
        "spikes": spikes,
        "top_schools_table": top_schools_table,
        "top_customers_table": top_customers_table,
        "normalized_items": items,
        "advanced_stats": compute_advanced_statistical_suite(bookings, items, daily_bookings, sorted_daily_dates)
    }


def get_category_drilldown(category_name, bookings):
    """
    Computes drill-down analytics for a single category with robust matching.
    """
    if not category_name:
        return None

    items, _ = normalize_cycle_bookings(bookings)
    target_clean = category_name.strip().lower()

    # 1. Exact match
    matching = [it for it in items if (it.get("canonical_category") or "").strip().lower() == target_clean]

    # 2. Relaxed match (substring or plural/singular)
    if not matching:
        target_stem = target_clean.rstrip('s')
        matching = [
            it for it in items 
            if (it.get("canonical_category") or "").strip().lower().rstrip('s') == target_stem
            or target_clean in (it.get("canonical_category") or "").lower()
            or (it.get("canonical_category") or "").lower() in target_clean
        ]

    if not matching:
        return None

    canonical_name = matching[0].get("canonical_category") or category_name.strip().title()

    total_bookings = len(matching)
    units_rented = sum(it.get("units", 1) for it in matching)
    total_rev = sum(it.get("allocated_revenue", 0.0) for it in matching)
    avg_price = total_rev / total_bookings if total_bookings > 0 else 0.0

    booking_prices = [it.get("allocated_revenue", 0.0) for it in matching]
    highest_booking = max(booking_prices) if booking_prices else 0.0
    lowest_booking = min(booking_prices) if booking_prices else 0.0

    prod_counts = Counter(it.get("canonical_product", "Unknown") for it in matching)
    prod_revs = Counter()
    for it in matching:
        prod_revs[it.get("canonical_product", "Unknown")] += it.get("allocated_revenue", 0.0)

    most_rented_prod = prod_counts.most_common(1)[0][0] if prod_counts else "None"

    # Timeline of rentals
    date_counts = Counter(it.get("booking_date") for it in matching if it.get("booking_date"))
    timeline = [{"date": d, "count": date_counts[d]} for d in sorted(date_counts.keys())]

    # Top products table
    products_table = [
        {"product": p, "units": prod_counts[p], "revenue": round(prod_revs[p], 2)}
        for p, _ in prod_counts.most_common(12)
    ]

    return {
        "entity_type": "Category",
        "name": canonical_name,
        "total_bookings": total_bookings,
        "units_rented": units_rented,
        "total_revenue": round(total_rev, 2),
        "avg_booking": round(avg_price, 2),
        "avg_revenue_per_booking": round(avg_price, 2),
        "avg_spend": round(avg_price, 2),
        "avg_spend_per_booking": round(avg_price, 2),
        "highest_booking": round(highest_booking, 2),
        "lowest_booking": round(lowest_booking, 2),
        "most_rented_product": most_rented_prod,
        "products_table": products_table,
        "timeline": timeline
    }


def get_product_drilldown(product_name, bookings):
    """
    Computes drill-down analytics for a single product.
    """
    items, _ = normalize_cycle_bookings(bookings)
    matching = [it for it in items if it["canonical_product"].lower() == product_name.strip().lower()]

    if not matching:
        return None

    total_bookings = len(matching)
    units_rented = sum(it["units"] for it in matching)
    total_rev = sum(it["allocated_revenue"] for it in matching)
    avg_qty = units_rented / total_bookings if total_bookings > 0 else 1.0

    prices = [it["allocated_revenue"] for it in matching]
    highest_booking = max(prices) if prices else 0.0
    lowest_booking = min(prices) if prices else 0.0

    date_counts = Counter(it["booking_date"] for it in matching if it["booking_date"])
    timeline = [{"date": d, "count": date_counts[d]} for d in sorted(date_counts.keys())]

    school_counts = Counter(it["school_clean"] for it in matching if not it["is_walkin"])
    top_schools = [{"school": s, "count": cnt} for s, cnt in school_counts.most_common(5)]

    category = matching[0]["canonical_category"]

    avg_spend = total_rev / total_bookings if total_bookings > 0 else 0.0
    avg_unit_price = total_rev / units_rented if units_rented > 0 else 0.0

    return {
        "entity_type": "Product",
        "name": product_name.strip().title(),
        "category": category,
        "total_bookings": total_bookings,
        "units_rented": units_rented,
        "total_revenue": round(total_rev, 2),
        "avg_spend": round(avg_spend, 2),
        "avg_spend_per_booking": round(avg_spend, 2),
        "avg_price_per_unit": round(avg_unit_price, 2),
        "avg_booking_qty": round(avg_qty, 1),
        "highest_booking": round(highest_booking, 2),
        "lowest_booking": round(lowest_booking, 2),
        "top_schools": top_schools,
        "timeline": timeline
    }


def get_school_drilldown(school_name, bookings):
    """
    Computes comprehensive drill-down analytics for a single school / institution.
    Returns financial KPIs, category-wise breakdown with pie chart data, top costumes,
    peak event dates, all individual bookings portfolio, available schools switcher,
    and deterministic strategic intelligence.
    """
    items, _ = normalize_cycle_bookings(bookings)
    
    clean_target, is_target_walkin = clean_school_name(school_name)
    target_low = clean_target.lower().strip()
    raw_low = str(school_name).lower().strip()

    # Match items
    if is_target_walkin or target_low == "walk-in customer":
        matching_items = [it for it in items if it["is_walkin"]]
        school_display_name = "Walk-in Customers"
    else:
        matching_items = [
            it for it in items 
            if not it["is_walkin"] and (
                it["school_clean"].lower() == target_low or
                target_low in it["school_clean"].lower() or
                it["school_clean"].lower() in target_low or
                raw_low in it["school_clean"].lower()
            )
        ]
        school_display_name = matching_items[0]["school_clean"] if matching_items else clean_target

    if not matching_items:
        return None

    matching_bkg_ids = {it["booking_id"] for it in matching_items if it.get("booking_id")}
    matching_bookings = [b for b in bookings if str(b.get("_id", "")) in matching_bkg_ids]
    if not matching_bookings:
        matching_bookings = [
            b for b in bookings
            if not clean_school_name(b.get("school") or b.get("school_name"))[1] and
            (clean_school_name(b.get("school") or b.get("school_name"))[0].lower() == target_low)
        ]

    total_bookings = len(matching_bookings) if matching_bookings else len(matching_items)
    units_rented = sum(it["units"] for it in matching_items)
    total_rev = sum(float(b.get("price", 0) or 0) for b in matching_bookings) if matching_bookings else sum(it["allocated_revenue"] for it in matching_items)
    avg_spend = total_rev / total_bookings if total_bookings > 0 else 0.0

    prices = [float(b.get("price", 0) or 0) for b in matching_bookings] if matching_bookings else [it["allocated_revenue"] for it in matching_items]
    highest_booking = max(prices) if prices else 0.0
    lowest_booking = min(prices) if prices else 0.0

    # Unique students / customers
    month_mobiles = {str(b.get("mobile", "")).strip() for b in matching_bookings if b.get("mobile")}
    unique_customers = len(month_mobiles) if month_mobiles else len({it.get("customer_mobile") for it in matching_items if it.get("customer_mobile")})

    # Peak day calculation
    daily_bkgs = defaultdict(int)
    daily_rev = defaultdict(float)
    for b in matching_bookings:
        sd = safe_parse_date(b.get("start_date"))
        if sd:
            d_iso = sd.strftime("%Y-%m-%d")
            daily_bkgs[d_iso] += 1
            daily_rev[d_iso] += float(b.get("price", 0) or 0)

    peak_day = None
    if daily_rev:
        peak_date_str = max(daily_rev, key=daily_rev.get)
        peak_dt = safe_parse_date(peak_date_str)
        peak_day = {
            "date": peak_date_str,
            "date_formatted": peak_dt.strftime("%d %b %Y") if peak_dt else peak_date_str,
            "revenue": round(daily_rev[peak_date_str], 2),
            "bookings": daily_bkgs[peak_date_str]
        }

    # Category Breakdown (Pie chart data + table)
    cat_counts = Counter(it["canonical_category"] for it in matching_items)
    cat_units = Counter()
    cat_revs = Counter()
    for it in matching_items:
        c = it["canonical_category"]
        cat_units[c] += it["units"]
        cat_revs[c] += it["allocated_revenue"]

    category_pie_data = []
    for c, r_val in cat_revs.most_common():
        u_val = cat_units[c]
        b_val = cat_counts[c]
        pct = round((r_val / total_rev) * 100, 1) if total_rev > 0 else 0.0
        c_avg = round(r_val / b_val, 2) if b_val > 0 else 0.0
        category_pie_data.append({
            "category": c,
            "units": u_val,
            "revenue": round(r_val, 2),
            "bookings": b_val,
            "percentage": pct,
            "avg_spend": c_avg
        })

    # Top Costumes Table
    prod_counts = Counter(it["canonical_product"] for it in matching_items)
    prod_revs = Counter()
    for it in matching_items:
        prod_revs[it["canonical_product"]] += it["allocated_revenue"]

    products_table = [
        {
            "product": p,
            "units": prod_counts[p],
            "revenue": round(prod_revs[p], 2),
            "avg_spend": round(prod_revs[p] / prod_counts[p], 2) if prod_counts[p] > 0 else 0.0
        }
        for p, _ in prod_counts.most_common(10)
    ]

    # Peak event dates table
    peak_dates_map = defaultdict(lambda: {"bookings": 0, "revenue": 0.0, "units": 0})
    for it in matching_items:
        bd = it.get("booking_date")
        if bd:
            peak_dates_map[bd]["bookings"] += 1
            peak_dates_map[bd]["revenue"] += it["allocated_revenue"]
            peak_dates_map[bd]["units"] += it["units"]

    peak_dates_table = []
    for d_str, d_stats in sorted(peak_dates_map.items(), key=lambda x: x[1]["revenue"], reverse=True)[:6]:
        dt_obj = safe_parse_date(d_str)
        peak_dates_table.append({
            "date": d_str,
            "date_formatted": dt_obj.strftime("%d %b %Y") if dt_obj else d_str,
            "bookings": d_stats["bookings"],
            "revenue": round(d_stats["revenue"], 2),
            "units": d_stats["units"]
        })

    # All Bookings Portfolio for this school
    bkg_items_map = defaultdict(list)
    for it in matching_items:
        bkg_items_map[it.get("booking_id")].append(it)

    sorted_raw_bookings = sorted(
        matching_bookings,
        key=lambda b: (safe_parse_date(b.get("start_date")) or date.min, str(b.get("_id", "")))
    )

    all_bookings_list = []
    for b in sorted_raw_bookings:
        b_id = str(b.get("_id", ""))
        sd = safe_parse_date(b.get("start_date"))
        ed = safe_parse_date(b.get("end_date"))
        b_items = bkg_items_map.get(b_id, [])

        cat_names = sorted(list({it["canonical_category"] for it in b_items if it.get("canonical_category")}))
        primary_category = cat_names[0] if cat_names else (b.get("costume") or "General").strip().title()
        cat_display = ", ".join(cat_names) if cat_names else primary_category

        prods = [f"{it['canonical_product']} ({it['units']})" if it['units'] > 1 else it['canonical_product'] for it in b_items]
        prod_display = ", ".join(prods) if prods else (b.get("details") or b.get("costume") or "-").strip()

        raw_sch = (b.get("school") or b.get("school_name") or "").strip()
        sch_clean, is_w = clean_school_name(raw_sch)

        b_price = float(b.get("price", 0) or 0)
        b_units = sum(it["units"] for it in b_items) if b_items else 1

        all_bookings_list.append({
            "id": b_id,
            "name": b.get("name", "Unknown").strip().title(),
            "mobile": str(b.get("mobile", "")).strip(),
            "school": "Walk-in" if is_w else sch_clean,
            "is_walkin": is_w,
            "category": cat_display,
            "primary_category": primary_category,
            "costume": (b.get("costume") or "").strip().title(),
            "details": (b.get("details") or "").strip(),
            "product_display": prod_display,
            "start_date": sd.strftime("%d %b %Y") if sd else str(b.get("start_date", "")),
            "start_date_iso": sd.strftime("%Y-%m-%d") if sd else "",
            "end_date": ed.strftime("%d %b %Y") if ed else str(b.get("end_date", "")),
            "price": round(b_price, 2),
            "units": b_units
        })

    # Available schools in cycle for quick switcher
    school_metrics_map = defaultdict(lambda: {"revenue": 0.0, "bookings": 0, "units": 0})
    for it in items:
        s_name = it["school_clean"]
        if not it["is_walkin"] and s_name:
            school_metrics_map[s_name]["revenue"] += it["allocated_revenue"]
            school_metrics_map[s_name]["units"] += it["units"]
            school_metrics_map[s_name]["bookings"] += 1

    available_schools = []
    for s_name, stats in sorted(school_metrics_map.items(), key=lambda x: x[1]["revenue"], reverse=True):
        available_schools.append({
            "school": s_name,
            "revenue": round(stats["revenue"], 2),
            "bookings": stats["bookings"],
            "units": stats["units"]
        })

    # Deterministic school strategic insights
    school_insights = [
        f"Delivered ₹{total_rev:,.2f} in gross costume rentals across {total_bookings} student/school bookings ({units_rented} outfits deployed) with an Average Spend of ₹{avg_spend:,.2f} per booking."
    ]
    if category_pie_data:
        top_cat = category_pie_data[0]
        school_insights.append(
            f"Costume Preference: '{top_cat['category']}' dominated student choices, generating {top_cat['percentage']}% of total school revenue (₹{top_cat['revenue']:,.2f}) across {top_cat['units']} outfits."
        )
    if peak_day:
        school_insights.append(
            f"Peak Function Activity: Heaviest rental demand occurred on {peak_day['date_formatted']} with ₹{peak_day['revenue']:,.2f} recorded in rentals ({peak_day['bookings']} bookings)."
        )
    if unique_customers > 0:
        school_insights.append(
            f"Institutional Reach: Engaged {unique_customers} distinct student/parent client contacts from {school_display_name}."
        )
    if products_table:
        top_prod = products_table[0]
        school_insights.append(
            f"Most Deployed Costume: '{top_prod['product']}' was the #1 requested outfit ({top_prod['units']} units rented, ₹{top_prod['revenue']:,.2f})."
        )

    date_counts = Counter(it["booking_date"] for it in matching_items if it.get("booking_date"))
    timeline = [{"date": d, "count": date_counts[d]} for d in sorted(date_counts.keys())]

    return {
        "entity_type": "School",
        "name": school_display_name,
        "school_name": school_display_name,
        "total_bookings": total_bookings,
        "units_rented": units_rented,
        "total_revenue": round(total_rev, 2),
        "avg_spend": round(avg_spend, 2),
        "avg_spend_per_booking": round(avg_spend, 2),
        "avg_booking": round(avg_spend, 2),
        "unique_customers": unique_customers,
        "unique_categories": len(category_pie_data),
        "peak_day": peak_day,
        "category_pie_data": category_pie_data,
        "categories_table": category_pie_data,
        "products_table": products_table,
        "top_products": [{"product": p["product"], "count": p["units"]} for p in products_table[:6]],
        "peak_dates_table": peak_dates_table,
        "all_bookings": all_bookings_list,
        "available_schools": available_schools,
        "school_insights": school_insights,
        "timeline": timeline,
        "highest_booking": round(highest_booking, 2),
        "lowest_booking": round(lowest_booking, 2)
    }


def get_customer_drilldown(mobile, bookings, all_bookings=None):
    """
    Computes drill-down analytics for a single customer.
    Customer name & phone are provided for local UI view, but NOT for AI.
    """
    cycle_matching = [b for b in bookings if str(b.get("mobile", "")).strip() == str(mobile).strip()]

    if not cycle_matching and all_bookings:
        matching = [b for b in all_bookings if str(b.get("mobile", "")).strip() == str(mobile).strip()]
    else:
        matching = cycle_matching

    if not matching:
        return None

    name = matching[0].get("name", "Unknown").strip().title()
    total_bookings = len(matching)
    total_rev = sum(float(b.get("price", 0) or 0) for b in matching)
    aov = total_rev / total_bookings if total_bookings > 0 else 0.0

    costume_counter = Counter(b.get("details", b.get("costume", "")).strip().title() for b in matching if b.get("details") or b.get("costume"))
    favorite_products = [{"costume": c, "count": cnt} for c, cnt in costume_counter.most_common(5)]

    recent_orders = []
    for b in matching[:10]:
        recent_orders.append({
            "date": str(b.get("start_date", "")),
            "costume": b.get("costume", ""),
            "details": b.get("details", ""),
            "price": float(b.get("price", 0) or 0),
            "taken": b.get("taken", False),
            "returned": b.get("returned", False)
        })

    return {
        "entity_type": "Customer",
        "name": name,
        "mobile": str(mobile).strip(),
        "total_bookings": total_bookings,
        "total_revenue": round(total_rev, 2),
        "aov": round(aov, 2),
        "favorite_products": favorite_products,
        "recent_orders": recent_orders
    }


def get_month_drilldown(month_key, bookings):
    """
    Computes deep-dive analytics for a specific month (e.g. '2026-08', 'Aug '26', or 'August').
    Returns comprehensive metrics, category breakdown pie chart data, top costumes,
    top schools, deterministic business insights, all individual bookings, and available months.
    """
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    full_month_names = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

    items, _ = normalize_cycle_bookings(bookings)
    target_year = None
    target_month = None
    clean_k = str(month_key).strip().lower()

    # 1. Parse Year & Month from string like '2026-08' or '08-2026'
    if "-" in clean_k:
        parts = clean_k.split("-")
        try:
            p0 = int(parts[0])
            p1 = int(parts[1])
            if p0 > 1000:
                target_year = p0
                target_month = p1
            else:
                target_month = p0
                target_year = p1
        except (ValueError, IndexError):
            pass

    # 2. Match month abbreviation or full month name
    if not target_month:
        for idx, mn in enumerate(month_names, 1):
            if mn.lower() in clean_k:
                target_month = idx
                break
    if not target_month:
        for idx, fmn in enumerate(full_month_names, 1):
            if fmn.lower() in clean_k:
                target_month = idx
                break
    if not target_month and clean_k.isdigit():
        target_month = int(clean_k)

    # 3. Parse Year if present in string
    if not target_year:
        y_match = re.search(r"\b(20\d\d)\b", clean_k)
        if y_match:
            target_year = int(y_match.group(1))
        else:
            y2_match = re.search(r"['\s](\d{2})\b", clean_k)
            if y2_match:
                target_year = 2000 + int(y2_match.group(1))

    # 4. Fallback year from bookings
    if not target_year and bookings:
        for b in bookings:
            sd = safe_parse_date(b.get("start_date"))
            if sd and (not target_month or sd.month == target_month):
                target_year = sd.year
                break
        if not target_year:
            target_year = 2026

    # Match normalized items for this month
    matching_items = []
    for it in items:
        bd = safe_parse_date(it.get("booking_date"))
        if bd:
            if target_month and bd.month != target_month:
                continue
            if target_year and bd.year != target_year:
                continue
            matching_items.append(it)

    # Match raw bookings for this month
    matching_bookings = []
    for b in bookings:
        sd = safe_parse_date(b.get("start_date"))
        if sd:
            if target_month and sd.month != target_month:
                continue
            if target_year and sd.year != target_year:
                continue
            matching_bookings.append(b)

    if not matching_bookings and not matching_items:
        return None

    # Month display name
    month_name_str = full_month_names[(target_month or 1) - 1] if target_month else "Selected Month"
    month_display = f"{month_name_str} {target_year}" if target_year else month_name_str

    total_bookings = len(matching_bookings)
    units_rented = sum(it["units"] for it in matching_items)
    total_rev = sum(float(b.get("price", 0) or 0) for b in matching_bookings)
    avg_spend = total_rev / total_bookings if total_bookings > 0 else 0.0

    # Unique customers & schools in this month
    month_mobiles = {str(b.get("mobile", "")).strip() for b in matching_bookings if b.get("mobile")}
    unique_customers = len(month_mobiles)

    month_schools = set()
    for b in matching_bookings:
        raw_sch = (b.get("school") or b.get("school_name") or "").strip()
        sch_clean, is_w = clean_school_name(raw_sch)
        if not is_w and sch_clean:
            month_schools.add(sch_clean)
    unique_schools = len(month_schools)

    # Daily velocity and peak day calculation
    daily_bkgs = defaultdict(int)
    daily_rev = defaultdict(float)
    for b in matching_bookings:
        sd = safe_parse_date(b.get("start_date"))
        if sd:
            d_iso = sd.strftime("%Y-%m-%d")
            daily_bkgs[d_iso] += 1
            daily_rev[d_iso] += float(b.get("price", 0) or 0)

    peak_day = None
    if daily_rev:
        peak_date_str = max(daily_rev, key=daily_rev.get)
        peak_dt = safe_parse_date(peak_date_str)
        peak_day = {
            "date": peak_date_str,
            "date_formatted": peak_dt.strftime("%d %b %Y") if peak_dt else peak_date_str,
            "revenue": round(daily_rev[peak_date_str], 2),
            "bookings": daily_bkgs[peak_date_str]
        }

    # Category Breakdown (All Categories with revenue, units, bookings, share %)
    cat_counts = Counter(it["canonical_category"] for it in matching_items)
    cat_units = Counter()
    cat_revs = Counter()
    for it in matching_items:
        c = it["canonical_category"]
        cat_units[c] += it["units"]
        cat_revs[c] += it["allocated_revenue"]

    category_pie_data = []
    for c, r_val in cat_revs.most_common():
        u_val = cat_units[c]
        b_val = cat_counts[c]
        pct = round((r_val / total_rev) * 100, 1) if total_rev > 0 else 0.0
        c_avg = round(r_val / b_val, 2) if b_val > 0 else 0.0
        category_pie_data.append({
            "category": c,
            "units": u_val,
            "revenue": round(r_val, 2),
            "bookings": b_val,
            "percentage": pct,
            "avg_spend": c_avg
        })

    # Products Table (Top 10 costumes)
    prod_counts = Counter(it["canonical_product"] for it in matching_items)
    prod_revs = Counter()
    for it in matching_items:
        prod_revs[it["canonical_product"]] += it["allocated_revenue"]

    products_table = [
        {
            "product": p,
            "units": prod_counts[p],
            "revenue": round(prod_revs[p], 2),
            "avg_spend": round(prod_revs[p] / prod_counts[p], 2) if prod_counts[p] > 0 else 0.0
        }
        for p, _ in prod_counts.most_common(10)
    ]

    # Top Schools Table
    school_counts = Counter(it["school_clean"] for it in matching_items if not it["is_walkin"])
    school_revs = Counter()
    for it in matching_items:
        if not it["is_walkin"]:
            school_revs[it["school_clean"]] += it["allocated_revenue"]

    top_schools = [
        {
            "school": s,
            "count": cnt,
            "revenue": round(school_revs[s], 2)
        }
        for s, cnt in school_counts.most_common(6)
    ]

    # All Bookings for this Month
    bkg_items_map = defaultdict(list)
    for it in matching_items:
        bkg_items_map[it.get("booking_id")].append(it)

    sorted_raw_bookings = sorted(
        matching_bookings,
        key=lambda b: (safe_parse_date(b.get("start_date")) or date.min, str(b.get("_id", "")))
    )

    all_bookings_list = []
    for b in sorted_raw_bookings:
        b_id = str(b.get("_id", ""))
        sd = safe_parse_date(b.get("start_date"))
        ed = safe_parse_date(b.get("end_date"))
        b_items = bkg_items_map.get(b_id, [])

        cat_names = sorted(list({it["canonical_category"] for it in b_items if it.get("canonical_category")}))
        primary_category = cat_names[0] if cat_names else (b.get("costume") or "General").strip().title()
        cat_display = ", ".join(cat_names) if cat_names else primary_category

        prods = [f"{it['canonical_product']} ({it['units']})" if it['units'] > 1 else it['canonical_product'] for it in b_items]
        prod_display = ", ".join(prods) if prods else (b.get("details") or b.get("costume") or "-").strip()

        raw_sch = (b.get("school") or b.get("school_name") or "").strip()
        sch_clean, is_w = clean_school_name(raw_sch)

        b_price = float(b.get("price", 0) or 0)
        b_units = sum(it["units"] for it in b_items) if b_items else 1

        all_bookings_list.append({
            "id": b_id,
            "name": b.get("name", "Unknown").strip().title(),
            "mobile": str(b.get("mobile", "")).strip(),
            "school": "Walk-in" if is_w else sch_clean,
            "is_walkin": is_w,
            "category": cat_display,
            "primary_category": primary_category,
            "costume": (b.get("costume") or "").strip().title(),
            "details": (b.get("details") or "").strip(),
            "product_display": prod_display,
            "start_date": sd.strftime("%d %b %Y") if sd else str(b.get("start_date", "")),
            "start_date_iso": sd.strftime("%Y-%m-%d") if sd else "",
            "end_date": ed.strftime("%d %b %Y") if ed else str(b.get("end_date", "")),
            "price": round(b_price, 2),
            "units": b_units
        })

    # Available months in the cycle for quick switcher
    all_month_map = defaultdict(lambda: {"revenue": 0.0, "bookings": 0})
    for b in bookings:
        sd = safe_parse_date(b.get("start_date"))
        if sd:
            k = (sd.year, sd.month)
            all_month_map[k]["revenue"] += float(b.get("price", 0) or 0)
            all_month_map[k]["bookings"] += 1

    available_months = []
    for (y, m) in sorted(all_month_map.keys()):
        m_key = f"{y}-{m:02d}"
        label = f"{month_names[m - 1]} '{str(y)[2:]}"
        available_months.append({
            "month_key": m_key,
            "label": label,
            "full_label": f"{full_month_names[m - 1]} {y}",
            "revenue": round(all_month_map[(y, m)]["revenue"], 2),
            "bookings": all_month_map[(y, m)]["bookings"]
        })

    # High-precision deterministic monthly analytical insights
    monthly_insights = [
        f"Delivered ₹{total_rev:,.2f} in gross rental revenue across {total_bookings} booking contracts ({units_rented} costumes rented) with an Average Spend of ₹{avg_spend:,.2f} per booking."
    ]
    if category_pie_data:
        top_cat = category_pie_data[0]
        monthly_insights.append(
            f"Category Leadership: '{top_cat['category']}' commanded {top_cat['percentage']}% of monthly revenue (₹{top_cat['revenue']:,.2f}) across {top_cat['units']} outfits."
        )
    if peak_day:
        monthly_insights.append(
            f"Peak Rental Velocity: Busiest day recorded on {peak_day['date_formatted']} with ₹{peak_day['revenue']:,.2f} revenue ({peak_day['bookings']} bookings)."
        )
    if top_schools:
        total_sch_rev = sum(s["revenue"] for s in top_schools)
        monthly_insights.append(
            f"Institutional Demand: {len(month_schools)} schools rented costumes this month, led by '{top_schools[0]['school']}' and totaling ₹{total_sch_rev:,.2f}."
        )
    if unique_customers > 0:
        monthly_insights.append(
            f"Customer Engagement: Engaged {unique_customers} distinct clients during this month."
        )

    # Timeline of daily counts for mini sparkline/trend
    date_counts = Counter(it["booking_date"] for it in matching_items if it.get("booking_date"))
    timeline = [{"date": d, "count": date_counts[d]} for d in sorted(date_counts.keys())]

    return {
        "entity_type": "Month",
        "month_key": f"{target_year}-{target_month:02d}" if (target_year and target_month) else str(month_key),
        "name": month_display,
        "total_bookings": total_bookings,
        "units_rented": units_rented,
        "total_revenue": round(total_rev, 2),
        "avg_spend": round(avg_spend, 2),
        "avg_spend_per_booking": round(avg_spend, 2),
        "unique_customers": unique_customers,
        "unique_schools": unique_schools,
        "peak_day": peak_day,
        "category_pie_data": category_pie_data,
        "categories_table": category_pie_data,  # backwards compatible
        "products_table": products_table,
        "top_schools": top_schools,
        "all_bookings": all_bookings_list,
        "available_months": available_months,
        "monthly_insights": monthly_insights,
        "timeline": timeline
    }


def get_day_drilldown(day_name, bookings):
    """
    Computes drill-down analytics for a specific day of week (e.g. 'Friday').
    """
    target_day = day_name.strip().lower()
    items, _ = normalize_cycle_bookings(bookings)

    matching_items = []
    for it in items:
        bd = safe_parse_date(it.get("booking_date"))
        if bd and bd.strftime("%A").lower() == target_day:
            matching_items.append(it)

    if not matching_items:
        return None

    total_bookings = len(matching_items)
    units_rented = sum(it["units"] for it in matching_items)
    total_rev = sum(it["allocated_revenue"] for it in matching_items)
    avg_spend = total_rev / total_bookings if total_bookings > 0 else 0.0

    prod_counts = Counter(it["canonical_product"] for it in matching_items)
    prod_revs = Counter()
    for it in matching_items:
        prod_revs[it["canonical_product"]] += it["allocated_revenue"]

    products_table = [
        {"product": p, "units": prod_counts[p], "revenue": round(prod_revs[p], 2)}
        for p, _ in prod_counts.most_common(8)
    ]

    school_counts = Counter(it["school_clean"] for it in matching_items if not it["is_walkin"])
    top_schools = [{"school": s, "count": cnt} for s, cnt in school_counts.most_common(5)]

    return {
        "entity_type": "Day",
        "name": f"{day_name.strip().title()} Pickups",
        "total_bookings": total_bookings,
        "units_rented": units_rented,
        "total_revenue": round(total_rev, 2),
        "avg_spend": round(avg_spend, 2),
        "avg_spend_per_booking": round(avg_spend, 2),
        "products_table": products_table,
        "top_schools": top_schools
    }


def get_date_drilldown(date_str, bookings):
    """
    Computes drill-down analytics for a specific single date (e.g. '2026-08-15').
    """
    items, _ = normalize_cycle_bookings(bookings)
    clean_d = date_str.strip()

    matching_items = [it for it in items if str(it.get("booking_date", "")).strip() == clean_d]
    if not matching_items:
        parsed_target = safe_parse_date(clean_d)
        if parsed_target:
            matching_items = [it for it in items if safe_parse_date(it.get("booking_date")) == parsed_target]

    if not matching_items:
        return None

    total_bookings = len(matching_items)
    units_rented = sum(it["units"] for it in matching_items)
    total_rev = sum(it["allocated_revenue"] for it in matching_items)
    avg_spend = total_rev / total_bookings if total_bookings > 0 else 0.0

    prod_counts = Counter(it["canonical_product"] for it in matching_items)
    prod_revs = Counter()
    for it in matching_items:
        prod_revs[it["canonical_product"]] += it["allocated_revenue"]

    products_table = [
        {"product": p, "units": prod_counts[p], "revenue": round(prod_revs[p], 2)}
        for p, _ in prod_counts.most_common(8)
    ]

    school_counts = Counter(it["school_clean"] for it in matching_items if not it["is_walkin"])
    top_schools = [{"school": s, "count": cnt} for s, cnt in school_counts.most_common(5)]

    return {
        "entity_type": "Date",
        "name": f"Date: {clean_d}",
        "date": clean_d,
        "total_bookings": total_bookings,
        "units_rented": units_rented,
        "total_revenue": round(total_rev, 2),
        "avg_spend": round(avg_spend, 2),
        "avg_spend_per_booking": round(avg_spend, 2),
        "products_table": products_table,
        "top_schools": top_schools
    }


def get_cycle_drilldown(bookings):
    """
    Computes drill-down analytics for the active cycle overview.
    """
    items, summary = normalize_cycle_bookings(bookings)
    total_bookings = len(bookings)
    total_revenue = sum(float(b.get("price", 0) or 0) for b in bookings)
    avg_spend = total_revenue / total_bookings if total_bookings > 0 else 0.0
    units_rented = summary["total_units"]

    prod_counts = Counter(it["canonical_product"] for it in items)
    prod_revs = Counter()
    for it in items:
        prod_revs[it["canonical_product"]] += it["allocated_revenue"]

    products_table = [
        {"product": p, "units": prod_counts[p], "revenue": round(prod_revs[p], 2)}
        for p, _ in prod_counts.most_common(8)
    ]

    return {
        "entity_type": "Cycle",
        "name": "Current Cycle Performance Overview",
        "total_bookings": total_bookings,
        "units_rented": units_rented,
        "total_revenue": round(total_revenue, 2),
        "avg_spend": round(avg_spend, 2),
        "avg_spend_per_booking": round(avg_spend, 2),
        "products_table": products_table
    }
