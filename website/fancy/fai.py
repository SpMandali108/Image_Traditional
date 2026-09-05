"""
fai.py - AI & Gemini LLM Integration Engine for Fancy Dress Dashboard.
Uses google.genai with model 'gemini-3.6-flash'.
Strict Privacy Compliance:
- Zero customer phone numbers sent to LLM.
- Zero customer addresses sent to LLM.
- Zero real customer names sent to LLM: Customer names are replaced with anonymous IDs (e.g. cust_1),
  and after Gemini responds, the IDs are substituted back with real customer names.
- Response caching in MongoDB 'fancy_ai_cache'.
"""

import os
import re
import json
import hashlib
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

from website.general.db import db

# Cache collection in MongoDB
ai_cache = db["fancy_ai_cache"]


def sanitize_currency(obj):
    """
    Recursively ensures all monetary symbols are Indian Rupees (₹) and NEVER dollars ($).
    Converts '$1,300' -> '₹1,300', '$216.67' -> '₹216.67', etc.
    """
    if isinstance(obj, str):
        # Replace $ followed by numbers or standalone $ with ₹
        s = re.sub(r'\$\s*(\d)', r'₹\1', obj)
        s = s.replace('$', '₹')
        return s
    elif isinstance(obj, list):
        return [sanitize_currency(x) for x in obj]
    elif isinstance(obj, dict):
        return {k: sanitize_currency(v) for k, v in obj.items()}
    return obj

# Initialize Gemini Client lazily
_gemini_client = None


def get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return None
        try:
            from google import genai
            _gemini_client = genai.Client(api_key=api_key)
        except Exception as e:
            print(f"[fai.py] Error initializing google.genai client: {e}")
            return None
    return _gemini_client


def get_cached_response(cache_key):
    """Retrieves cached response from MongoDB if fresh (< 24 hours)."""
    doc = ai_cache.find_one({"key": cache_key})
    if doc:
        created_at = doc.get("created_at")
        if created_at and (datetime.utcnow() - created_at) < timedelta(hours=24):
            return doc.get("response")
    return None


def set_cached_response(cache_key, response_data):
    """Saves AI response in MongoDB cache."""
    ai_cache.update_one(
        {"key": cache_key},
        {
            "$set": {
                "key": cache_key,
                "response": response_data,
                "created_at": datetime.utcnow()
            }
        },
        upsert=True
    )


def compute_hash(data):
    """Computes SHA256 hash of JSON-serializable data."""
    raw = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def call_gemini(prompt, system_instruction=None, json_mode=False):
    """
    Executes a content generation call to gemini-3.6-flash.
    """
    client = get_gemini_client()
    if not client:
        return None

    try:
        config = {}
        if system_instruction:
            config["system_instruction"] = system_instruction
        if json_mode:
            config["response_mime_type"] = "application/json"

        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config=config if config else None
        )
        return response.text.strip() if response and response.text else None
    except Exception as e:
        print(f"[fai.py] Gemini call error: {e}")
        return None


def generate_dashboard_ai_insights(primary_kpis, best_performers, top_products, category_share, top_schools, top_customer):
    """
    Generates high-level executive insights for the dashboard.
    Customer names are converted to IDs before prompting, and reversed on return.
    """
    # Create customer surrogate mapping
    id_to_name = {}
    name_to_id = {}
    if top_customer and top_customer.get("name"):
        cid = "cust_top_1"
        real_name = top_customer["name"]
        id_to_name[cid] = real_name
        name_to_id[real_name] = cid
        top_cust_sanitized = {
            "customer_id": cid,
            "revenue": top_customer.get("revenue", 0),
            "bookings": top_customer.get("bookings", 0),
            "aov": top_customer.get("aov", 0)
        }
    else:
        top_cust_sanitized = None

    payload = {
        "kpis": primary_kpis,
        "best_performers": {
            "best_category_by_units": best_performers.get("best_category_by_units"),
            "best_category_by_revenue": best_performers.get("best_category_by_revenue"),
            "best_product_by_units": best_performers.get("best_product_by_units"),
            "best_product_by_revenue": best_performers.get("best_product_by_revenue"),
            "top_school": best_performers.get("top_school"),
            "top_customer": top_cust_sanitized
        },
        "top_products_sample": top_products[:6],
        "category_share_sample": category_share[:6],
        "top_schools_sample": top_schools[:5]
    }

    cache_key = f"dashboard_insights_{compute_hash(payload)}"
    cached = get_cached_response(cache_key)
    if cached:
        return cached

    prompt = f"""
You are an expert retail business intelligence analyst for 'Image Traditional', a fancy dress and costume rental store in Ahmedabad, India.
IMPORTANT: All currency is Indian Rupees (₹). You must NEVER use the dollar symbol ($) or USD. ALWAYS use the Rupee symbol (₹) or 'Rs.' for all currency amounts (e.g. ₹15,000, ₹312.89).

Analyze the following cycle performance metrics and provide actionable, data-backed insights.

Data:
{json.dumps(payload, indent=2)}

Requirements:
1. Ground your observations strictly in the data provided. Do not fabricate patterns.
2. Structure your response as valid JSON with the following keys:
   - "executive_summary": string (2-3 concise sentences on overall business health, revenue, and order volume)
   - "key_trends": array of 3 strings (specific observed trends, e.g. costume category concentration, high-value schools)
   - "top_opportunities": array of 2 strings (data-backed actions to grow revenue or optimize stock)
   - "risk_alerts": array of 2 strings (e.g. over-dependence on a single category, underperforming categories)
3. If referring to the top customer, refer to them using their ID (e.g. {name_to_id.get(top_customer.get('name', ''), 'cust_top_1')}).
4. Ensure all currency values are prefixed with '₹' and NEVER '$'.
Return ONLY the JSON object.
"""

    res = call_gemini(prompt, json_mode=True)
    if not res:
        # Fallback heuristic summary if API is unreachable
        return {
            "executive_summary": f"Total cycle revenue reached ₹{primary_kpis.get('total_revenue', 0):,.2f} across {primary_kpis.get('total_bookings', 0)} bookings with an average order value of ₹{primary_kpis.get('avg_revenue_per_booking', 0):.2f}.",
            "key_trends": [
                f"Top category '{best_performers.get('best_category_by_revenue', {}).get('name')}' generated highest revenue of ₹{best_performers.get('best_category_by_revenue', {}).get('revenue', 0):,.2f}.",
                f"Most rented dress design is '{best_performers.get('best_product_by_units', {}).get('name')}' with {best_performers.get('best_product_by_units', {}).get('units', 0)} total physical units rented.",
                f"Top contributing educational institution is '{best_performers.get('top_school', {}).get('name')}' contributing ₹{best_performers.get('top_school', {}).get('revenue', 0):,.2f}."
            ],
            "top_opportunities": [
                "Expand catalog inventory in high-velocity categories prior to seasonal surges.",
                "Develop institutional tie-ups with leading schools for annual function bulk bookings."
            ],
            "risk_alerts": [
                "High revenue concentration in the top 2 categories makes the cycle sensitive to holiday scheduling.",
                "Ensure sufficient return inspection protocols on peak pickup days."
            ]
        }

    try:
        parsed = json.loads(res)
        # Convert IDs back to real customer names
        parsed_str = json.dumps(parsed)
        for cid, real_name in id_to_name.items():
            parsed_str = parsed_str.replace(cid, real_name)
        result = json.loads(parsed_str)
        result = sanitize_currency(result)
        set_cached_response(cache_key, result)
        return result
    except Exception as e:
        print(f"[fai.py] JSON parsing error in dashboard insights: {e}")
        return None


def explain_anomaly_spikes(spikes):
    """
    Generates intelligent, factual explanations for detected rental velocity spikes.
    Zero customer PII included.
    """
    if not spikes:
        return []

    cache_key = f"spikes_{compute_hash(spikes)}"
    cached = get_cached_response(cache_key)
    if cached:
        return cached

    prompt = f"""
You are an expert BI analyst for a costume rental store in Gujarat, India.
IMPORTANT: All currency is Indian Rupees (₹). You must NEVER use dollar ($). ALWAYS use ₹ for any prices or amounts.
Explain each of the following rental velocity spikes using the factual context provided (festival proximity, school concentration, top costume category, top product).

Spikes data:
{json.dumps(spikes, indent=2)}

Format: Return a JSON array where each object has:
- "date": string (same as input)
- "explanation": string (2 sentences clearly explaining WHY the spike occurred based on the event, festival proximity, and costume/school concentration)
- "operational_tip": string (1 concise recommendation for inventory or staffing during this date window)

Return ONLY valid JSON.
"""

    res = call_gemini(prompt, json_mode=True)
    if not res:
        # Factual fallback
        fallback = []
        for sp in spikes:
            reason = f"Surge of {sp['count']} rentals"
            if sp.get("festival"):
                reason += f" directly driven by upcoming {sp['festival']} celebrations"
            if sp.get("top_category"):
                reason += f", with heavy concentration in {sp['top_category']} outfits (especially '{sp.get('top_product')}')"
            if sp.get("top_school") and sp.get("top_school") != "None":
                reason += f" and bulk orders from {sp['top_school']}."
            else:
                reason += "."
            fallback.append({
                "date": sp["date"],
                "explanation": reason,
                "operational_tip": "Prepare pre-ironed stock and streamline counter pickup slots."
            })
        return fallback

    try:
        result = json.loads(res)
        result = sanitize_currency(result)
        set_cached_response(cache_key, result)
        return result
    except Exception as e:
        print(f"[fai.py] Error parsing spike explanations: {e}")
        return []


def generate_festival_forecast_insights(events_data):
    """
    Generates intelligent procurement advisory for upcoming Indian cultural festivals based on
    historical rental volume, stock counts, and projected deficits.
    """
    cache_key = f"festival_forecast_{compute_hash(events_data)}"
    cached = get_cached_response(cache_key)
    if cached:
        return cached

    sanitized_events = []
    for ev in events_data:
        sanitized_events.append({
            "id": ev.get("id"),
            "name": ev.get("name"),
            "date": ev.get("date"),
            "countdown": ev.get("countdown"),
            "category": ev.get("category"),
            "spike_count": ev.get("spike_count", 0),
            "total_stock": ev.get("total_stock", 0),
            "deficit": ev.get("deficit", 0)
        })

    prompt = f"""
You are a retail inventory and demand forecasting specialist for Indian fancy dress and festive costumes in India.
IMPORTANT: All currency is Indian Rupees (₹). NEVER use dollar ($).
Analyze the following upcoming cultural events with historical booking spikes (±3 days) and current physical inventory levels.

Data:
{json.dumps(sanitized_events, indent=2)}

Instructions:
Provide a strategic procurement and stocking advisory in valid JSON.
Return an object where keys are the event 'id' (e.g. "republic_day", "independence_day", "janmashtami", "navaratri") and values are:
- "demand_outlook": "High" | "Moderate" | "Steady"
- "actionable_advice": string (2 actionable sentences specifying whether to procure more outfits, stitch new sizes, or reallocate existing inventory based on deficit)
- "key_characters": array of 3 top costume characters to stock for this event.

Return ONLY the JSON object.
"""

    res = call_gemini(prompt, json_mode=True)
    if not res:
        return {}

    try:
        result = json.loads(res)
        result = sanitize_currency(result)
        set_cached_response(cache_key, result)
        return result
    except Exception as e:
        print(f"[fai.py] Error parsing festival forecast: {e}")
        return {}


def generate_drilldown_ai_insights(entity_type, entity_data):
    """
    Generates deep-dive entity insights (Category, Product, or School).
    AI intelligence is completely disabled for Customer.
    """
    if entity_type.lower() == "customer":
        return []

    data_copy = {k: v for k, v in entity_data.items() if k not in ("all_bookings", "available_months", "available_schools")}

    cache_key = f"drilldown_{entity_type}_{compute_hash(data_copy)}"
    cached = get_cached_response(cache_key)
    if cached:
        return sanitize_currency(cached)

    extra_requirements = ""
    if entity_type.lower() in ("category", "product", "month", "day", "date", "cycle", "school"):
        avg_spend = data_copy.get('avg_spend', data_copy.get('avg_spend_per_booking', data_copy.get('avg_revenue_per_booking', data_copy.get('avg_booking', 0))))
        extra_requirements = f"""
- Highlight the Average Spend per Booking (Avg Spend: ₹{avg_spend:,.2f}) as a primary KPI in your analysis.
- Comment on whether this {entity_type}'s average spend indicates strong revenue contribution per rental.
"""
    if entity_type.lower() == "month":
        extra_requirements += """
- Specifically analyze the category-wise distribution (which categories generated the highest revenue share and units).
- Note any peak rental spike dates or institutional school booking dynamics present in the monthly data.
"""
    elif entity_type.lower() == "school":
        extra_requirements += """
- Analyze this school's costume preferences, category breakdown, and student participation volume.
- Suggest proactive reservation packaging, student group discounts, or costume inventory preparation for upcoming school annual days and competitions.
"""

    prompt = f"""
You are a business intelligence assistant for 'Image Traditional', a traditional fancy dress rental store in Ahmedabad, India.
IMPORTANT: All currency is Indian Rupees (₹). You must NEVER use the dollar sign ($) or USD. ALWAYS use the Rupee symbol (₹) or 'Rs.' for all currency amounts (e.g. ₹1,300, ₹216.67).

Analyze the performance data for this {entity_type}:

{json.dumps(data_copy, indent=2)}

Requirements:
{extra_requirements}
Provide 3 concise, highly relevant, data-backed business takeaways:
1. Performance evaluation (explicitly state total revenue, total bookings, and {"Average Spend per Booking of ₹" + f"{data_copy.get('avg_spend', data_copy.get('avg_spend_per_booking', data_copy.get('avg_revenue_per_booking', data_copy.get('avg_booking', 0)))):,.2f}" if entity_type.lower() in ("category", "product", "month", "day", "date", "cycle", "school") else "volume"}).
2. Demand seasonality, costume concentration, or institutional order pattern.
3. Specific actionable recommendation for the shop manager to grow revenue or optimize stock.

Return JSON with a single key: "insights": ["bullet 1", "bullet 2", "bullet 3"].
Ensure all monetary figures start with '₹' and NEVER '$'.
"""

    res = call_gemini(prompt, json_mode=True)
    if not res:
        if entity_type.lower() == "category":
            avg_spend = data_copy.get('avg_spend', data_copy.get('avg_spend_per_booking', data_copy.get('avg_revenue_per_booking', data_copy.get('avg_booking', 0))))
            fallback = [
                f"Average Spend per Booking is ₹{avg_spend:,.2f} across {data_copy.get('total_bookings', 0)} bookings, generating ₹{data_copy.get('total_revenue', 0):,.2f} in gross category revenue.",
                f"Top costume '{data_copy.get('most_rented_product', 'General')}' drives category volume with {data_copy.get('units_rented', 0)} total units rented.",
                "Maintain sufficient size variations in peak costumes to prevent booking spillover."
            ]
        elif entity_type.lower() == "product":
            avg_spend = data_copy.get('avg_spend', data_copy.get('avg_spend_per_booking', 0))
            fallback = [
                f"Average Spend per Booking for this product is ₹{avg_spend:,.2f} across {data_copy.get('total_bookings', 0)} bookings.",
                f"Generated ₹{data_copy.get('total_revenue', 0):,.2f} with {data_copy.get('units_rented', 0)} units rented.",
                "Maintain adequate inventory and size options for peak seasonal demand."
            ]
        elif entity_type.lower() == "month":
            avg_spend = data_copy.get('avg_spend', 0)
            pie = data_copy.get('category_pie_data', [])
            top_cat_str = f"Category '{pie[0]['category']}' led monthly volume, generating ₹{pie[0]['revenue']:,.2f} ({pie[0]['percentage']}% of monthly revenue) across {pie[0]['units']} units." if pie else "Strong diversified rental volume observed."
            peak_str = f"Peak single-day rental velocity achieved on {data_copy['peak_day']['date_formatted']} with ₹{data_copy['peak_day']['revenue']:,.2f} revenue across {data_copy['peak_day']['bookings']} bookings." if data_copy.get('peak_day') else "Consistent rental progression maintained across the cycle month."
            fallback = [
                f"Delivered ₹{data_copy.get('total_revenue', 0):,.2f} across {data_copy.get('total_bookings', 0)} bookings ({data_copy.get('units_rented', 0)} units) with an Average Spend of ₹{avg_spend:,.2f} per booking.",
                top_cat_str,
                peak_str,
                "Restock high-demand sizes and align staff shifts with historical weekend and festival pickup spikes."
            ]
        elif entity_type.lower() == "school":
            avg_spend = data_copy.get('avg_spend', 0)
            pie = data_copy.get('category_pie_data', [])
            top_cat_str = f"Costumes in category '{pie[0]['category']}' generated the highest volume (₹{pie[0]['revenue']:,.2f}, {pie[0]['percentage']}% of school total)." if pie else "Consistent costume distribution across categories."
            peak_str = f"Peak rental volume concentrated on {data_copy['peak_day']['date_formatted']} with ₹{data_copy['peak_day']['revenue']:,.2f} recorded in rentals." if data_copy.get('peak_day') else "Consistent order flow across the academic term."
            fallback = [
                f"Delivered ₹{data_copy.get('total_revenue', 0):,.2f} across {data_copy.get('total_bookings', 0)} bookings ({data_copy.get('units_rented', 0)} outfits deployed) with an Average Spend of ₹{avg_spend:,.2f} per booking.",
                top_cat_str,
                peak_str,
                "Establish early group rental contracts with school coordinators ahead of annual day functions."
            ]
        elif entity_type.lower() in ("day", "date", "cycle"):
            avg_spend = data_copy.get('avg_spend', 0)
            fallback = [
                f"Average Spend per Booking during this period is ₹{avg_spend:,.2f} across {data_copy.get('total_bookings', 0)} bookings.",
                f"Generated ₹{data_copy.get('total_revenue', 0):,.2f} in total gross revenue with {data_copy.get('units_rented', 0)} units rented.",
                "Optimize staffing and stock allocation according to peak volume periods."
            ]
        else:
            fallback = [
                f"Contributes significant rental activity in the active cycle with {data_copy.get('total_bookings', 0)} bookings.",
                f"Generated ₹{data_copy.get('total_revenue', 0):,.2f} in total revenue.",
                "Maintain adequate inventory and streamline turnaround times."
            ]
        fallback_clean = sanitize_currency(fallback)
        set_cached_response(cache_key, fallback_clean)
        return fallback_clean

    try:
        parsed = json.loads(res)
        insights = parsed.get("insights", [])
        insights = sanitize_currency(insights)
        if entity_type.lower() in ("category", "product", "month", "day", "date", "cycle", "school"):
            avg_spend = data_copy.get('avg_spend', data_copy.get('avg_spend_per_booking', data_copy.get('avg_revenue_per_booking', data_copy.get('avg_booking', 0))))
            has_spend = any("spend" in str(ins).lower() or "revenue per booking" in str(ins).lower() for ins in insights)
            if not has_spend:
                insights.insert(0, f"Average Spend per Booking: ₹{avg_spend:,.2f} (Total Revenue: ₹{data_copy.get('total_revenue', 0):,.2f} across {data_copy.get('total_bookings', 0)} bookings).")
        set_cached_response(cache_key, insights)
        return insights
    except Exception as e:
        print(f"[fai.py] Error parsing drilldown insights: {e}")
        return []
