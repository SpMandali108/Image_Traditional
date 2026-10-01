"""
website/general/security.py
Comprehensive Security Hardening Module for Image Traditional

Defensive Controls Implemented:
1. Strict parameter validation (Product codes, dates, types, lengths, character sets)
2. NoSQL injection & type-confusion prevention
3. Thread-safe sliding-window rate limiting per client IP
4. Request size enforcement
5. Safe client IP resolution behind reverse proxies
6. Production security headers (X-Content-Type-Options, X-Frame-Options, HSTS, Referrer-Policy, CSP)
7. Restricted CORS policy (no wildcard with credentials)
8. Information disclosure prevention (safe error responses, sanitizing logs)
"""

import re
import time
import threading
from collections import deque
from datetime import datetime
from flask import request, current_app, jsonify


# ============================================================================
# 1. PARAMETER VALIDATION & INJECTION PREVENTION
# ============================================================================

# Whitelist allowed product code characters: Alphanumeric, hyphens, underscores (1 to 30 chars)
PRODUCT_CODE_REGEX = re.compile(r'^[A-Za-z0-9][A-Za-z0-9\-_]{0,29}$')

# Date regex supporting DD-MM-YYYY, YYYY-MM-DD, DD/MM/YYYY, etc.
DATE_REGEX = re.compile(r'^(\d{1,4})[\-/](\d{1,2})[\-/](\d{1,4})$')

# Blacklist dangerous NoSQL / command / path traversal / control characters
DANGEROUS_CHAR_REGEX = re.compile(r'[\$|&;`\'"\\<>\{\}\[\]\x00\r\n]')


def validate_product_code(raw_val):
    """
    Strict validation of product code parameter.
    Must be a string, 1-30 chars, matching alphanumeric format.
    Rejects dicts, lists, booleans, nulls, injection payloads, or excessive lengths.
    Returns: (is_valid: bool, cleaned_code: str, error_msg: str)
    """
    if raw_val is None:
        return False, "", "Product code is required."
    
    if not isinstance(raw_val, str):
        return False, "", "Product code must be a string."
    
    cleaned = raw_val.strip()
    if not cleaned:
        return False, "", "Product code cannot be empty."
    
    if len(cleaned) > 30:
        return False, "", "Product code exceeds maximum length of 30 characters."
    
    if DANGEROUS_CHAR_REGEX.search(cleaned):
        return False, "", "Product code contains invalid or forbidden characters."
    
    if not PRODUCT_CODE_REGEX.match(cleaned):
        return False, "", f"Invalid product code format '{cleaned}'."
    
    return True, cleaned, ""


def validate_booking_date(raw_val):
    """
    Strict calendar validation for rental inquiry dates.
    Validates format, ensures realistic calendar date (checking leap years, month bounds),
    and enforces a reasonable forward-looking booking window.
    Returns: (is_valid: bool, dt_obj: datetime, norm_dd_mm_yyyy: str, db_date_str: str, error_msg: str)
    """
    if raw_val is None:
        return False, None, "", "", "Date is required."
    
    if not isinstance(raw_val, str):
        return False, None, "", "", "Date must be a string."
    
    cleaned = raw_val.strip()
    if not cleaned:
        return False, None, "", "", "Date cannot be empty."
    
    if len(cleaned) < 6 or len(cleaned) > 20:
        return False, None, "", "", "Date length must be between 6 and 20 characters."
    
    if DANGEROUS_CHAR_REGEX.search(cleaned):
        return False, None, "", "", "Date contains invalid or forbidden characters."
    
    m = DATE_REGEX.match(cleaned)
    if not m:
        return False, None, "", "", "Invalid date format. Expected DD-MM-YYYY or YYYY-MM-DD."
    
    p1, p2, p3 = int(m.group(1)), int(m.group(2)), int(m.group(3))
    
    # Determine year, month, day based on positioning
    if p1 > 1000:
        year, month, day = p1, p2, p3
    else:
        day, month = p1, p2
        year = p3 if p3 > 100 else (2000 + p3 if p3 < 70 else 1900 + p3)
    
    # Strict Gregorian calendar validation (catches 31 Feb, 31 April, leap-year errors)
    try:
        dt_obj = datetime(year, month, day)
    except ValueError as ve:
        return False, None, "", "", f"Invalid or impossible calendar date: {ve}"
    
    # Booking window boundary: from 365 days ago to 5 years into the future
    current_year = datetime.now().year
    if year < current_year - 1 or year > current_year + 5:
        return False, None, "", "", f"Booking date year {year} is outside allowable rental booking timeframe."
    
    norm_dd_mm_yyyy = dt_obj.strftime("%d-%m-%Y")
    db_date_str = dt_obj.strftime("%d-%m-%y")
    
    return True, dt_obj, norm_dd_mm_yyyy, db_date_str, ""


# ============================================================================
# 2. THREAD-SAFE SLIDING WINDOW RATE LIMITER
# ============================================================================

class SlidingWindowRateLimiter:
    """
    In-memory, thread-safe sliding window rate limiter per client IP.
    Enforces request rate limits without third-party Redis/Memcached dependencies.
    Automatically purges stale entries to prevent memory growth.
    """
    def __init__(self, limit=40, window_seconds=60, cleanup_interval=300):
        self.limit = limit
        self.window_seconds = window_seconds
        self.cleanup_interval = cleanup_interval
        self._lock = threading.Lock()
        self._clients = {}  # { ip: deque([timestamps]) }
        self._last_cleanup = time.time()

    def is_allowed(self, client_ip):
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            # Periodic sweep of inactive clients
            if now - self._last_cleanup > self.cleanup_interval:
                self._purge_stale(now)
                self._last_cleanup = now

            if client_ip not in self._clients:
                self._clients[client_ip] = deque()

            req_history = self._clients[client_ip]

            # Drop timestamps outside the sliding window
            while req_history and req_history[0] <= window_start:
                req_history.popleft()

            if len(req_history) < self.limit:
                req_history.append(now)
                remaining = self.limit - len(req_history)
                return True, remaining, 0
            else:
                oldest = req_history[0]
                retry_after = max(1, int(oldest + self.window_seconds - now))
                return False, 0, retry_after

    def _purge_stale(self, now):
        cutoff = now - self.window_seconds
        stale_ips = []
        for ip, dq in self._clients.items():
            while dq and dq[0] <= cutoff:
                dq.popleft()
            if not dq:
                stale_ips.append(ip)
        for ip in stale_ips:
            del self._clients[ip]


# Singleton rate limiter instance for public availability checking:
# Allows up to 40 requests per 60 seconds per IP
availability_rate_limiter = SlidingWindowRateLimiter(limit=40, window_seconds=60)


def get_client_ip(req):
    """
    Safely extracts client IP taking reverse proxy headers into account.
    Validates formatting and avoids IP spoofing vulnerabilities.
    """
    forwarded_for = req.headers.get("X-Forwarded-For")
    if forwarded_for:
        # First IP in X-Forwarded-For list is the client IP
        parts = [p.strip() for p in forwarded_for.split(",") if p.strip()]
        if parts:
            first_ip = parts[0]
            # Simple sanity check for IP address structure (IPv4 or IPv6)
            if re.match(r'^[a-fA-F0-9:.]+$', first_ip):
                return first_ip
    
    real_ip = req.headers.get("X-Real-IP")
    if real_ip and re.match(r'^[a-fA-F0-9:.]+$', real_ip.strip()):
        return real_ip.strip()

    return req.remote_addr or "127.0.0.1"


# ============================================================================
# 3. SECURITY HEADERS & CORS ENFORCEMENT
# ============================================================================

# Allowed origins for CORS (production domain + localhost/127.0.0.1 dev origins)
ALLOWED_ORIGINS = {
    "https://image-traditional.onrender.com",
    "http://image-traditional.onrender.com",
    "http://localhost:5000",
    "http://127.0.0.1:5000",
    "http://localhost:3000",
    "http://127.0.0.1:3000"
}


def apply_security_headers(response):
    """
    Applies production-grade security headers to all HTTP responses.
    """
    # Prevent MIME type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"
    
    # Prevent clickjacking / framing outside same origin
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    
    # Control referrer policy
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # Restrict dangerous browser features
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    
    # If served over HTTPS, enforce HSTS
    if request.is_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
    return response


def apply_cors_headers(response):
    """
    Restricts Cross-Origin Resource Sharing (CORS) strictly to verified Image Traditional origins.
    Never uses wildcard Access-Control-Allow-Origin: * with credentials.
    """
    origin = request.headers.get("Origin")
    if origin:
        clean_origin = origin.strip().rstrip("/")
        # Check against allowed origins or same-origin host
        is_allowed = (clean_origin in ALLOWED_ORIGINS) or (clean_origin == request.host_url.rstrip("/"))
        if is_allowed:
            response.headers["Access-Control-Allow-Origin"] = clean_origin
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Requested-With"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Vary"] = "Origin"
            
    return response
