# Project Todo & Refactoring List — Image Traditional

**Image Traditional** is a rental management Flask application that handles costume rentals (Kediya, Chaniya Choli, Fancy Dress) and printing services for a shop located in Ahmedabad, Gujarat. 

This document lists architectural observations, bugs, security vulnerabilities, and code quality improvement tasks that can be performed **without modifying the functional logic of the application**.

---

## 📄 Table of Contents
1. [Code Duplications & Refactoring](#1-code-duplications--refactoring)
2. [Database Connection Optimization](#2-database-connection-optimization)
3. [Environment & Deployment Configuration](#3-environment--deployment-configuration)
4. [WhatsApp Messaging Integration](#4-whatsapp-messaging-integration)
5. [Security & Robustness Enhancements](#5-security--robustness-enhancements)

---

## 1. Code Duplications & Refactoring

### 🔍 Duplicate Functions
- **`get_fancy_profile_data`**
  - **Location**: Defined twice in [website/fancy/fservices.py](file:///F:/Shashwat_Mandali/Coding%20Script/Image-Traditional/Rental_Mandagement_Flask_App_Image_Traditional/Rental_Mandagement_Flask_App_Image_Traditional/website/fancy/fservices.py#L51-L103) (lines 51–76 and lines 78–103).
  - **Action**: Delete the duplicate second definition.
- **`is_selected_cycle_locked`**
  - **Location**: Defined twice in [website/fancy/fcycle.py](file:///F:/Shashwat_Mandali/Coding%20Script/Image-Traditional/Rental_Mandagement_Flask_App_Image_Traditional/Rental_Mandagement_Flask_App_Image_Traditional/website/fancy/fcycle.py#L204-L226) (lines 204–211 and lines 213–226).
  - **Action**: Keep the second definition as it contains override checks (`edit_override`), and remove the simpler first definition.

### 🔄 Duplicated Services/Utilities
Several analytic functions are copied verbatim across files:
- **`find_best_products_by_letter`**: Defined in [website/navaratri/nservices.py](file:///F:/Shashwat_Mandali/Coding%20Script/Image-Traditional/Rental_Mandagement_Flask_App_Image_Traditional/Rental_Mandagement_Flask_App_Image_Traditional/website/navaratri/nservices.py#L30) and [website/general/utils.py](file:///F:/Shashwat_Mandali/Coding%20Script/Image-Traditional/Rental_Mandagement_Flask_App_Image_Traditional/Rental_Mandagement_Flask_App_Image_Traditional/website/general/utils.py#L15).
- **`find_highest_booking_customer`**: Defined in [website/navaratri/nservices.py](file:///F:/Shashwat_Mandali/Coding%20Script/Image-Traditional/Rental_Mandagement_Flask_App_Image_Traditional/Rental_Mandagement_Flask_App_Image_Traditional/website/navaratri/nservices.py#L54) and [website/general/utils.py](file:///F:/Shashwat_Mandali/Coding%20Script/Image-Traditional/Rental_Mandagement_Flask_App_Image_Traditional/Rental_Mandagement_Flask_App_Image_Traditional/website/general/utils.py#L40).
- **`get_all_product_counts`**: Defined in [website/navaratri/nservices.py](file:///F:/Shashwat_Mandali/Coding%20Script/Image-Traditional/Rental_Mandagement_Flask_App_Image_Traditional/Rental_Mandagement_Flask_App_Image_Traditional/website/navaratri/nservices.py#L74) and [website/general/utils.py](file:///F:/Shashwat_Mandali/Coding%20Script/Image-Traditional/Rental_Mandagement_Flask_App_Image_Traditional/Rental_Mandagement_Flask_App_Image_Traditional/website/general/utils.py#L59).
- **Action**: Delete these from `nservices.py` and import them directly from `utils.py` to keep the codebase DRY (Don't Repeat Yourself).

### ⚙️ Duplicate Imports
- **`is_selected_cycle_locked`** is imported twice in [website/fancy/froutes.py](file:///F:/Shashwat_Mandali/Coding%20Script/Image-Traditional/Rental_Mandagement_Flask_App_Image_Traditional/Rental_Mandagement_Flask_App_Image_Traditional/website/fancy/froutes.py#L20-L26) (lines 20 and 26).
- **Action**: Remove the duplicate import on line 26.

---

## 2. Database Connection Optimization

- **Issue**: A brand new connection pool (`MongoClient`) is initialized separately in both [website/general/db.py](file:///F:/Shashwat_Mandali/Coding%20Script/Image-Traditional/Rental_Mandagement_Flask_App_Image_Traditional/Rental_Mandagement_Flask_App_Image_Traditional/website/general/db.py#L9) and [website/auth.py](file:///F:/Shashwat_Mandali/Coding%20Script/Image-Traditional/Rental_Mandagement_Flask_App_Image_Traditional/Rental_Mandagement_Flask_App_Image_Traditional/website/auth.py#L35).
- **Impact**: Under high concurrency, this duplicates connections to MongoDB, potentially exceeding cluster limits.
- **Action**: Initialize `client` and `db` once inside `db.py`, and import `db` in `auth.py`.

---

## 3. Environment & Deployment Configuration

- **Procfile Misplacement**
  - **Issue**: The [Procfile](file:///F:/Shashwat_Mandali/Coding%20Script/Image-Traditional/Rental_Mandagement_Flask_App_Image_Traditional/Rental_Mandagement_Flask_App_Image_Traditional/website/Procfile) is currently located in the `website/` subfolder.
  - **Impact**: Deployment services (e.g., Render, Heroku) require the `Procfile` to be present at the root of the repository to detect Gunicorn configurations correctly.
  - **Action**: Move `Procfile` from the `website/` directory to the project's root folder.
- **Environment Variables Template**
  - **Issue**: No `.env.example` file exists.
  - **Action**: Create a `.env.example` in the project root to document the required environment variables:
    ```ini
    client=mongodb+srv://...  # MongoDB connection URL
    key=your_flask_secret_key
    ADMIN_ID=admin_username
    ADMIN_PASS=admin_password
    PORT=5500
    ```
- **Requirements Encoding**
  - **Issue**: The [requirements.txt](file:///F:/Shashwat_Mandali/Coding%20Script/Image-Traditional/Rental_Mandagement_Flask_App_Image_Traditional/Rental_Mandagement_Flask_App_Image_Traditional/requirements.txt) file is encoded in UTF-16LE.
  - **Action**: Convert `requirements.txt` to UTF-8 to prevent command-line execution or package-manager failures in standard build systems.

---

## 4. WhatsApp Messaging Integration

- **Issue**: The script [import pywhatkit.py](file:///F:/Shashwat_Mandali/Coding%20Script/Image-Traditional/Rental_Mandagement_Flask_App_Image_Traditional/Rental_Mandagement_Flask_App_Image_Traditional/import%20pywhatkit.py) exists in the root, but WhatsApp notifications are not integrated into the Flask app.
- **Action**: 
  - Integrate a messaging service into the booking/rental routines (e.g., in `froutes.py` and `nroutes.py`).
  - Auto-send receipt URLs, QR codes, and pending payment reminders when a booking is created or updated.

---

## 5. Security & Robustness Enhancements

- **Hardcoded Production URL**
  - **Location**: [website/navaratri/nroutes.py](file:///F:/Shashwat_Mandali/Coding%20Script/Image-Traditional/Rental_Mandagement_Flask_App_Image_Traditional/Rental_Mandagement_Flask_App_Image_Traditional/website/navaratri/nroutes.py#L110)
  - **Issue**: `store_base_url` is hardcoded as `"https://image-traditional.onrender.com/download-bill"`.
  - **Action**: Replace it with Flask's dynamic URL routing, such as `url_for('navaratri.download_bill', mobile=mobile, _external=True)`, so it works seamlessly during local development and testing.
- **Replace Print Statements with Logging**
  - **Location**: Throughout `froutes.py` and `nroutes.py`.
  - **Issue**: The code uses raw `print()` statements (e.g., `print("DATA =", data)` and `print("ERROR:", e)`).
  - **Action**: Use standard logging via Python's `logging` module or Flask's `current_app.logger` to facilitate production log capturing.
- **Admin Password Weak Fallback**
  - **Location**: [website/auth.py](file:///F:/Shashwat_Mandali/Coding%20Script/Image-Traditional/Rental_Mandagement_Flask_App_Image_Traditional/Rental_Mandagement_Flask_App_Image_Traditional/website/auth.py#L49-L50).
  - **Issue**: If environment variables are missing, `ADMIN_ID` and `ADMIN_PASS` will evaluate to `None`. This can allow authentication bypassing under certain POST configurations if they are sent as empty strings.
  - **Action**: Implement safety checks that throw an error at boot time or fall back to randomly generated safe passwords if these environment variables are missing.
- **PDF Unicode Support**
  - **Location**: [website/general/utils.py](file:///F:/Shashwat_Mandali/Coding%20Script/Image-Traditional/Rental_Mandagement_Flask_App_Image_Traditional/Rental_Mandagement_Flask_App_Image_Traditional/website/general/utils.py#L128).
  - **Issue**: The PDF generator utilizes standard Arial/Helvetica, which fails when rendering local/Indian names containing Unicode/UTF-8 characters.
  - **Action**: Upgrade fpdf2 to include a TrueType/OpenType Unicode-compatible font (e.g., Noto Sans) or add a sanitization function to strip non-latin1 characters.
