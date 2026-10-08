import os
import sys
import unittest
from unittest.mock import patch

# Ensure APP_ENV is explicitly set before importing app modules
os.environ["APP_ENV"] = "production"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import app
from website.general.db import client, MONGO_DB_PRODUCTION, MONGO_DB_TESTING, ADMIN_PASS, ADMIN_ID
from website.general.data_review import (
    scan_suspicious_entities,
    safe_delete_candidate_entity,
    get_retained_records_set,
    create_full_backup,
    mark_entity_retained,
    unmark_entity_retained
)

class DataReviewSecurityTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'test-secret-key-security-audit'
        self.client = self.app.test_client()
        self.prod_db = client[MONGO_DB_PRODUCTION]
        self.test_db = client[MONGO_DB_TESTING]

    def test_01_unauthenticated_access_blocked(self):
        """Verify unauthenticated requests cannot access any data review endpoint."""
        # 1. UI review page (Browser GET) -> Expect 302 redirect to login
        res = self.client.get('/admin/data-review')
        self.assertEqual(res.status_code, 302, "Unauthenticated GET /admin/data-review must redirect")
        self.assertIn('/login', res.headers.get('Location', ''))

        # 2. Export (Browser GET without session) -> Expect 302 redirect to login
        res = self.client.get('/admin/data-review/export')
        self.assertEqual(res.status_code, 302, "Unauthenticated GET /export must redirect")

        # 3. Export (API JSON request without session) -> Expect 401 Unauthorized
        res = self.client.get('/admin/data-review/export?format=json', headers={'Accept': 'application/json'})
        self.assertEqual(res.status_code, 401, "Unauthenticated JSON /export must return 401")

        # 4. Retain endpoint (API POST without session) -> Expect 401 Unauthorized
        res = self.client.post('/admin/data-review/retain', json={'mobile': '9999999999'})
        self.assertEqual(res.status_code, 401, "Unauthenticated POST /retain must return 401")

        # 5. Unretain endpoint (API POST without session) -> Expect 401 Unauthorized
        res = self.client.post('/admin/data-review/unretain', json={'mobile': '9999999999'})
        self.assertEqual(res.status_code, 401, "Unauthenticated POST /unretain must return 401")

        # 6. Delete endpoint (API POST without session) -> Expect 401 Unauthorized
        res = self.client.post('/admin/data-review/delete', json={'mobile': '9999999999', 'admin_password': ADMIN_PASS})
        self.assertEqual(res.status_code, 401, "Unauthenticated POST /delete must return 401")

    def test_02_unauthorized_non_admin_session_blocked(self):
        """Verify session without logged_in=True cannot access or perform review actions."""
        with self.client.session_transaction() as sess:
            sess['logged_in'] = False
            sess['user_role'] = 'customer'

        res = self.client.get('/admin/data-review')
        self.assertEqual(res.status_code, 302, "Non-admin session must be redirected")

        res = self.client.post('/admin/data-review/delete', json={'mobile': '9999999999', 'admin_password': ADMIN_PASS})
        self.assertEqual(res.status_code, 401, "Non-admin session must return 401 for delete")

    def test_03_http_methods_restriction(self):
        """Verify destructive actions strictly reject GET requests with 405 Method Not Allowed."""
        with self.client.session_transaction() as sess:
            sess['logged_in'] = True

        # Accidental browser GET or link navigation on destructive routes
        res_del = self.client.get('/admin/data-review/delete?mobile=9999999999')
        self.assertEqual(res_del.status_code, 405, "GET /admin/data-review/delete must return 405 Method Not Allowed")

        res_ret = self.client.get('/admin/data-review/retain?mobile=9999999999')
        self.assertEqual(res_ret.status_code, 405, "GET /admin/data-review/retain must return 405 Method Not Allowed")

        res_unret = self.client.get('/admin/data-review/unretain?mobile=9999999999')
        self.assertEqual(res_unret.status_code, 405, "GET /admin/data-review/unretain must return 405")

    def test_04_admin_password_not_exposed(self):
        """Verify ADMIN_PASS is never exposed in HTML, JS, API responses, or error messages."""
        with self.client.session_transaction() as sess:
            sess['logged_in'] = True

        # Render HTML page
        res = self.client.get('/admin/data-review')
        self.assertEqual(res.status_code, 200)
        html_content = res.get_data(as_text=True)
        self.assertNotIn(str(ADMIN_PASS), html_content, "ADMIN_PASS must NEVER appear in rendered HTML")

        # Wrong password deletion attempt
        res_del = self.client.post('/admin/data-review/delete', json={
            'mobile': '9999999999',
            'admin_password': 'wrong_password_attempt'
        })
        self.assertEqual(res_del.status_code, 400)
        err_data = res_del.get_json()
        self.assertNotIn(str(ADMIN_PASS), str(err_data), "ADMIN_PASS must NEVER appear in error messages")
        self.assertIn("Invalid administrator password", err_data.get("error", ""))

        # Export API
        res_exp = self.client.get('/admin/data-review/export?format=json', headers={'Accept': 'application/json'})
        self.assertEqual(res_exp.status_code, 200)
        exp_data = res_exp.get_json()
        self.assertNotIn(str(ADMIN_PASS), str(exp_data), "ADMIN_PASS must NEVER appear in export metadata")

    def test_05_retained_records_cannot_be_deleted(self):
        """Verify retained records (like 9876543210) CANNOT be deleted even with valid password."""
        with self.client.session_transaction() as sess:
            sess['logged_in'] = True

        # Verify 9876543210 is in retained set
        retained_set = get_retained_records_set(self.prod_db)
        self.assertIn("9876543210", retained_set, "9876543210 must be in retained records set")

        # Attempt deletion via HTTP endpoint with correct ADMIN_PASS
        res = self.client.post('/admin/data-review/delete', json={
            'mobile': '9876543210',
            'admin_password': ADMIN_PASS
        })
        self.assertEqual(res.status_code, 400, "Deletion of retained record must be rejected with 400")
        resp_json = res.get_json()
        self.assertFalse(resp_json.get("success"))
        self.assertIn("RETAINED", resp_json.get("error", ""))

        # Also test direct function call
        res_func = safe_delete_candidate_entity("9876543210", ADMIN_PASS, target_db=self.prod_db)
        self.assertFalse(res_func.get("success"))
        self.assertIn("RETAINED", res_func.get("error", ""))

        # Verify retained registry document is untouched
        ret_doc = self.prod_db["Audit_Retained_Records"].find_one({"mobile": "9876543210"})
        self.assertIsNotNone(ret_doc, "Retained registry entry for 9876543210 must NOT be deleted")

    def test_06_parameter_tampering_unrelated_customer_protected(self):
        """Verify non-candidate / genuine customer records CANNOT be deleted by parameter tampering."""
        with self.client.session_transaction() as sess:
            sess['logged_in'] = True

        # Find a genuine customer who does NOT match suspicious regexes
        genuine_cust = self.prod_db["Navaratri_Customers"].find_one({
            "mobile": {"$nin": ["9876543210", "9799988889"], "$regex": r"^[6-9]\d{9}$"},
            "name": {"$not": {"$regex": r"test|dummy|fake|sample", "$options": "i"}}
        })
        self.assertIsNotNone(genuine_cust, "Must find a genuine customer for test")
        genuine_mobile = str(genuine_cust["mobile"])

        # Attempt deletion of genuine customer with valid ADMIN_PASS
        res = self.client.post('/admin/data-review/delete', json={
            'mobile': genuine_mobile,
            'admin_password': ADMIN_PASS
        })
        self.assertEqual(res.status_code, 400, "Deletion of unrelated genuine customer must be rejected")
        resp_json = res.get_json()
        self.assertFalse(resp_json.get("success"))
        self.assertIn("No candidate records found", resp_json.get("error", ""))

        # Verify genuine customer still exists
        still_exists = self.prod_db["Navaratri_Customers"].find_one({"mobile": genuine_mobile})
        self.assertIsNotNone(still_exists, f"Genuine customer {genuine_mobile} must NOT be deleted")

    def test_07_backup_required_before_deletion(self):
        """Verify backup is required before deletion and failure halts deletion completely."""
        # Insert a candidate into test_db
        self.test_db["Navaratri_Customers"].insert_one({"name": "Test Backup Fail Cust", "mobile": "9999909999"})
        try:
            with patch("website.general.data_review.create_full_backup", side_effect=IOError("Disk write simulated failure")):
                res = safe_delete_candidate_entity("9999909999", ADMIN_PASS, target_db=self.test_db)
                self.assertFalse(res.get("success"))
                self.assertIn("Backup creation failed", res.get("error", ""))
        finally:
            self.test_db["Navaratri_Customers"].delete_many({"mobile": "9999909999"})

    def test_08_environment_centralization_and_safety(self):
        """Verify data review operations honor target database and cannot touch production in testing."""
        # Test scan on test_db
        test_candidates = scan_suspicious_entities(target_db=self.test_db)
        self.assertIsInstance(test_candidates, list)

        # Retain an entity in test_db only
        mark_entity_retained("8888888888", notes="Test retention in testing DB", target_db=self.test_db)
        test_retained = get_retained_records_set(self.test_db)
        prod_retained = get_retained_records_set(self.prod_db)

        self.assertIn("8888888888", test_retained, "Must exist in test_db retained set")
        self.assertNotIn("8888888888", prod_retained, "Must NOT exist in prod_db retained set")

        # Cleanup test retention
        unmark_entity_retained("8888888888", target_db=self.test_db)


if __name__ == "__main__":
    unittest.main()
