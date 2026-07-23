import io
import os
import csv
from datetime import datetime
from collections import Counter
from flask import send_file, Response, current_app
from fpdf import FPDF
import qrcode


# =========================
# 📊 ANALYTICS FUNCTIONS
# =========================

def find_best_products_by_letter(traditional_data):
    product_c_counts = {}
    product_k_counts = {}

    for booking in traditional_data:
        bookings_dict = booking.get('bookings', {})
        if not isinstance(bookings_dict, dict):
            continue

        for _, products in bookings_dict.items():
            if isinstance(products, list):
                for product in products:
                    if isinstance(product, str) and product.strip():
                        product_upper = product.upper().strip()
                        if product_upper.startswith('C'):
                            product_c_counts[product_upper] = product_c_counts.get(product_upper, 0) + 1
                        elif product_upper.startswith('K'):
                            product_k_counts[product_upper] = product_k_counts.get(product_upper, 0) + 1

    best_c = max(product_c_counts, key=product_c_counts.get) if product_c_counts else "N/A"
    best_k = max(product_k_counts, key=product_k_counts.get) if product_k_counts else "N/A"

    return best_c, product_c_counts.get(best_c, 0), best_k, product_k_counts.get(best_k, 0)


def find_highest_booking_customer(traditional_data):
    customer_totals = {}

    for booking in traditional_data:
        name = booking.get('Name') or booking.get('name', 'Unknown')
        try:
            total_price = int(booking.get('total_price') or 0)
        except:
            total_price = 0

        customer_totals[name] = customer_totals.get(name, 0) + total_price

    if not customer_totals:
        return "N/A", 0

    best = max(customer_totals, key=customer_totals.get)
    return best, customer_totals[best]


def get_all_product_counts(collection):
    product_counts = {}

    for customer in collection.find({}):
        bookings = customer.get("bookings", {})
        if not isinstance(bookings, dict):
            continue

        for date, products in bookings.items():
            if isinstance(products, list):
                for p in products:
                    code = p.strip().upper()
                    product_counts[code] = product_counts.get(code, 0) + 1

    return product_counts


# =========================
# 📄 CSV EXPORT
# =========================

def export_bookings_csv(collection):
    docs = list(collection.find())

    date_keys = set()
    other_keys = set()

    for doc in docs:
        bookings = doc.get("bookings", {})
        date_keys.update(bookings.keys())

        for key in doc.keys():
            if key not in ("_id", "bookings"):
                other_keys.add(key)

    date_keys = sorted(date_keys)
    other_keys = sorted(other_keys)

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=other_keys + date_keys)
    writer.writeheader()

    for doc in docs:
        row = {}

        for key in other_keys:
            val = doc.get(key, "")
            row[key] = str(val) if isinstance(val, (dict, list)) else val

        bookings = doc.get("bookings", {})
        for date in date_keys:
            products = bookings.get(date, [])
            row[date] = ", ".join(products) if isinstance(products, list) else ""

        writer.writerow(row)

    output.seek(0)

    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=bookings.csv"}
    )


# =========================
# 📄 PDF GENERATION
# =========================

def sanitize_latin1(text):
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    return text.encode('latin-1', 'ignore').decode('latin-1')

def generate_customer_pdf(customer):
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 16)
            self.cell(0, 10, 'Customer Bill', ln=True)

    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)

    name = sanitize_latin1(customer.get('Name'))
    mobile = sanitize_latin1(customer.get('mobile'))
    pdf.cell(0, 10, f"Name: {name}", ln=True)
    pdf.cell(0, 10, f"Mobile: {mobile}", ln=True)

    pdf_output = pdf.output(dest="S")

    pdf_bytes = pdf_output.encode("latin1") if isinstance(pdf_output, str) else bytes(pdf_output)

    buffer = io.BytesIO(pdf_bytes)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="customer.pdf",
        mimetype="application/pdf"
    )



# =========================
# 📱 QR GENERATION
# =========================

def generate_qr_code(url):
    qr_img = qrcode.make(url)

    buf = io.BytesIO()
    qr_img.save(buf, format="PNG")
    buf.seek(0)

    return send_file(buf, mimetype="image/png")


# =========================
# 💬 META WHATSAPP CLOUD API INTEGRATION
# =========================

import requests

def send_whatsapp_pdf_cloud_api(mobile_number, pdf_url, customer_name, filename=None):
    """
    Sends a PDF document directly to a customer's WhatsApp inbox via Meta Cloud API.
    Requires WHATSAPP_TOKEN and WHATSAPP_PHONE_ID environment variables.
    """
    token = os.environ.get("WHATSAPP_TOKEN")
    phone_id = os.environ.get("WHATSAPP_PHONE_ID")

    if not token or not phone_id:
        print("[WhatsApp API] Missing WHATSAPP_TOKEN or WHATSAPP_PHONE_ID in .env")
        return False, "WhatsApp API credentials not configured."

    # Ensure clean 10-digit mobile number with country code 91
    clean_mobile = str(mobile_number).strip().replace("+", "").replace(" ", "").replace("-", "")
    if len(clean_mobile) == 10:
        clean_mobile = "91" + clean_mobile

    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    doc_filename = filename or f"{customer_name.strip().replace(' ', '_')}_Rental_Invoice.pdf"

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_mobile,
        "type": "document",
        "document": {
            "link": pdf_url,
            "filename": doc_filename,
            "caption": f"Hello {customer_name}, here is your rental invoice PDF from Image Traditional!"
        }
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        res_data = res.json()

        if res.status_code in (200, 201):
            return True, res_data
        else:
            err_msg = res_data.get("error", {}).get("message", res.text)
            print(f"[WhatsApp API Error]: {err_msg}")
            return False, err_msg
    except Exception as e:
        print(f"[WhatsApp API Exception]: {str(e)}")
        return False, str(e)


def send_whatsapp_text_cloud_api(mobile_number, message_text):
    """
    Sends a text message directly to a customer's WhatsApp inbox via Meta Cloud API.
    """
    token = os.environ.get("WHATSAPP_TOKEN")
    phone_id = os.environ.get("WHATSAPP_PHONE_ID")

    if not token or not phone_id:
        return False, "WhatsApp API credentials not configured."

    clean_mobile = str(mobile_number).strip().replace("+", "").replace(" ", "").replace("-", "")
    if len(clean_mobile) == 10:
        clean_mobile = "91" + clean_mobile

    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_mobile,
        "type": "text",
        "text": {
            "preview_url": True,
            "body": message_text
        }
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        return res.status_code in (200, 201), res.json()
    except Exception as e:
        return False, str(e)