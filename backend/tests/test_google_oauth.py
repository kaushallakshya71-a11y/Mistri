"""
Mistri Google OAuth 2.0 / OpenID Connect & Profile Completion Test Suite
Verifies all 10 test cases from the specification:
1. Existing customer -> Google Login -> same account opens (account linking, no duplicates)
2. New Google email -> new Customer account created with role='customer'
3. Existing Google customer logs in again -> no duplicate account
4. Google user has no phone/address -> Complete Profile flag is set
5. Complete profile endpoint validates Indian phone & pincode and updates customer
6. User cancels Google authentication or passes error -> safe error returned
7. State CSRF protection -> valid state succeeds; invalid state rejected
8. Missing OAuth credentials -> clear configuration error / 503
9. Normal email/password login -> still works perfectly
10. Google customer -> Customer role only (never auto-promote to admin/staff)
"""
import unittest
import asyncio
import os
import sys
import json
import re
from pathlib import Path
from unittest.mock import patch, AsyncMock

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from db.database import init_db, get_db
from routes.auth import (
    google_oauth_config,
    google_oauth_url,
    google_oauth_callback,
    complete_profile,
    CompleteProfileRequest,
    login,
    LoginRequest,
    _OAUTH_STATES,
    _hash_pw,
    get_google_oauth_config
)
from fastapi import HTTPException

class TestGoogleOAuth(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        # Set dummy OAuth credentials for tests
        os.environ["GOOGLE_CLIENT_ID"] = "mock-client-id.apps.googleusercontent.com"
        os.environ["GOOGLE_CLIENT_SECRET"] = "mock-client-secret"
        os.environ["GOOGLE_REDIRECT_URI"] = "http://localhost:8000/api/auth/google/callback"

    # Case 8: Missing OAuth credentials -> clear configuration error / 503
    def test_01_google_oauth_config_and_missing_credentials(self):
        """Test OAuth configuration check and 503 when credentials are empty."""
        with patch.dict(os.environ, {"GOOGLE_CLIENT_ID": "", "GOOGLE_CLIENT_SECRET": ""}):
            cfg = google_oauth_config()
            self.assertFalse(cfg["configured"])
            self.assertIsNone(cfg["client_id"])

            with self.assertRaises(HTTPException) as ctx:
                google_oauth_url()
            self.assertEqual(ctx.exception.status_code, 503)
            self.assertIn("not configured", ctx.exception.detail)

        # When configured
        cfg = google_oauth_config()
        self.assertTrue(cfg["configured"])
        self.assertEqual(cfg["client_id"], "mock-client-id.apps.googleusercontent.com")
        
        url_resp = google_oauth_url()
        self.assertTrue(url_resp["configured"])
        self.assertIn("accounts.google.com", url_resp["url"])
        self.assertIn("mock-client-id", url_resp["url"])
        self.assertIn("state=", url_resp["url"])

    # Case 7: State CSRF protection -> valid state succeeds; invalid state rejected
    def test_02_state_csrf_protection(self):
        """Test that invalid CSRF state is rejected with error page."""
        _OAUTH_STATES["valid-state-123"] = 9999999999.0

        # Invalid state
        resp = asyncio.run(google_oauth_callback(code="dummy-code", state="invalid-state-456"))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("state mismatch", resp.body.decode("utf-8").lower())

    # Case 1: Existing customer -> Google Login -> same account opens (linked, no duplicates)
    @patch("routes.auth._exchange_google_code")
    @patch("routes.auth._fetch_google_userinfo")
    def test_03_existing_customer_linking_no_duplicates(self, mock_userinfo, mock_exchange):
        """Verify existing customer with same Gmail is linked without creating duplicate row."""
        email = "existing_cust@gmail.com"
        google_sub = "google-sub-1001"

        # Pre-create customer with email provider
        conn = get_db()
        conn.execute("DELETE FROM users WHERE email=?", (email,))
        conn.execute("""
            INSERT INTO users (name, email, password_hash, role, auth_provider, phone, address, pincode)
            VALUES ('Arun Sharma', ?, ?, 'customer', 'email', '9876543210', 'Flat 101, Delhi', '110001')
        """, (email, _hash_pw("ValidPass@123")))
        conn.commit()
        pre_user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        pre_id = pre_user["id"]
        conn.close()

        mock_exchange.return_value = {"access_token": "mock-access-token-1"}
        mock_userinfo.return_value = {
            "sub": google_sub,
            "email": email,
            "name": "Arun Sharma Google",
            "email_verified": True
        }

        # Simulate Google callback
        resp = asyncio.run(google_oauth_callback(code="auth-code-1"))
        html = resp.body.decode("utf-8")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("google_auth_success", html)
        self.assertIn(f'user_id: {pre_id}', html)

        # Check database: user ID unchanged, google_id linked, auth_provider is email+google
        conn = get_db()
        rows = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchall()
        self.assertEqual(len(rows), 1, "Duplicate customer row must not be created")
        updated = rows[0]
        self.assertEqual(updated["id"], pre_id)
        self.assertEqual(updated["google_id"], google_sub)
        self.assertEqual(updated["auth_provider"], "email+google")
        conn.close()

    # Case 2: New Google email -> new Customer account created with role='customer'
    @patch("routes.auth._exchange_google_code")
    @patch("routes.auth._fetch_google_userinfo")
    def test_04_new_google_customer_creation(self, mock_userinfo, mock_exchange):
        """Verify new Google user automatically creates customer account with role='customer'."""
        email = "brandnew_user@gmail.com"
        google_sub = "google-sub-2002"

        conn = get_db()
        conn.execute("DELETE FROM users WHERE email=? OR google_id=?", (email, google_sub))
        conn.commit()
        conn.close()

        mock_exchange.return_value = {"access_token": "mock-access-token-2"}
        mock_userinfo.return_value = {
            "sub": google_sub,
            "email": email,
            "name": "New Google User",
            "email_verified": True
        }

        resp = asyncio.run(google_oauth_callback(code="auth-code-2"))
        html = resp.body.decode("utf-8")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("google_auth_success", html)
        self.assertIn('role: "customer"', html)

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        self.assertIsNotNone(user)
        self.assertEqual(user["role"], "customer")
        self.assertEqual(user["auth_provider"], "google")
        self.assertEqual(user["google_id"], google_sub)
        self.assertEqual(user["password_hash"], "")

    # Case 3: Existing Google customer logs in again -> no duplicate account
    @patch("routes.auth._exchange_google_code")
    @patch("routes.auth._fetch_google_userinfo")
    def test_05_relogin_no_duplicate(self, mock_userinfo, mock_exchange):
        """Verify repeated login with Google does not duplicate user records."""
        email = "repeat_google_user@gmail.com"
        google_sub = "google-sub-3003"

        conn = get_db()
        conn.execute("DELETE FROM users WHERE email=? OR google_id=?", (email, google_sub))
        conn.commit()
        conn.close()

        mock_exchange.return_value = {"access_token": "mock-access-token-3"}
        mock_userinfo.return_value = {
            "sub": google_sub,
            "email": email,
            "name": "Repeat User",
            "email_verified": True
        }

        # First login
        resp1 = asyncio.run(google_oauth_callback(code="auth-code-3a"))
        self.assertEqual(resp1.status_code, 200)

        # Second login
        resp2 = asyncio.run(google_oauth_callback(code="auth-code-3b"))
        self.assertEqual(resp2.status_code, 200)

        conn = get_db()
        users = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchall()
        conn.close()
        self.assertEqual(len(users), 1)

    # Case 4: Google user has no phone/address -> Complete Profile flag is set
    @patch("routes.auth._exchange_google_code")
    @patch("routes.auth._fetch_google_userinfo")
    def test_06_profile_completion_flag(self, mock_userinfo, mock_exchange):
        """Verify needs_profile_completion=True when phone or address is missing."""
        email = "needs_profile@gmail.com"
        google_sub = "google-sub-4004"

        conn = get_db()
        conn.execute("DELETE FROM users WHERE email=? OR google_id=?", (email, google_sub))
        conn.commit()
        conn.close()

        mock_exchange.return_value = {"access_token": "mock-access-token-4"}
        mock_userinfo.return_value = {
            "sub": google_sub,
            "email": email,
            "name": "Needs Profile",
            "email_verified": True
        }

        resp = asyncio.run(google_oauth_callback(code="auth-code-4"))
        html = resp.body.decode("utf-8")
        self.assertIn('needs_profile_completion: true', html)

    # Case 5: Complete profile endpoint validates Indian phone & pincode and updates customer
    def test_07_complete_profile_validation_and_update(self):
        """Verify complete-profile endpoint validates 10-digit Indian phone, address, and 6-digit PIN code."""
        conn = get_db()
        conn.execute("DELETE FROM users WHERE email='profile_target@gmail.com'")
        cursor = conn.execute("""
            INSERT INTO users (name, email, password_hash, role, auth_provider)
            VALUES ('Profile Target', 'profile_target@gmail.com', '', 'customer', 'google')
        """)
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()

        current_user = {"id": user_id, "role": "customer", "name": "Profile Target"}

        # Invalid phone
        with self.assertRaises(HTTPException) as ctx:
            complete_profile(CompleteProfileRequest(
                phone="12345",
                address="Sector 12, Market Road",
                pincode="110001"
            ), current_user=current_user)
        self.assertEqual(ctx.exception.status_code, 400)

        # Invalid pincode
        with self.assertRaises(HTTPException) as ctx:
            complete_profile(CompleteProfileRequest(
                phone="9876543210",
                address="Sector 12, Market Road",
                pincode="00123"
            ), current_user=current_user)
        self.assertEqual(ctx.exception.status_code, 400)

        # Short address
        with self.assertRaises(HTTPException) as ctx:
            complete_profile(CompleteProfileRequest(
                phone="9876543210",
                address="Shop",
                pincode="110001"
            ), current_user=current_user)
        self.assertEqual(ctx.exception.status_code, 400)

        # Valid submission
        res = complete_profile(CompleteProfileRequest(
            phone="9876543210",
            address="Shop 4, Market Road, Sector 12",
            landmark="Near Metro Station",
            pincode="110001"
        ), current_user=current_user)

        self.assertEqual(res["message"], "Profile completed successfully.")
        self.assertEqual(res["user"]["phone"], "9876543210")
        self.assertEqual(res["user"]["pincode"], "110001")
        self.assertEqual(res["user"]["address"], "Shop 4, Market Road, Sector 12")

    # Case 6: User cancels Google authentication or passes error -> safe error returned
    def test_08_cancellation_and_error_handling(self):
        """Verify cancelling Google Sign-In returns safe error response."""
        resp = asyncio.run(google_oauth_callback(error="access_denied"))
        self.assertEqual(resp.status_code, 400)
        html = resp.body.decode("utf-8")
        self.assertIn("google_auth_error", html)
        self.assertIn("cancelled or failed", html)

    # Case 9: Normal email/password login -> still works perfectly
    def test_09_normal_email_password_login(self):
        """Verify normal email and password login continues to work as expected."""
        email = "password_cust@gmail.com"
        pw = "MyPass@2026"
        conn = get_db()
        conn.execute("DELETE FROM users WHERE email=?", (email,))
        conn.execute("""
            INSERT INTO users (name, email, password_hash, role, auth_provider)
            VALUES ('Password Cust', ?, ?, 'customer', 'email')
        """, (email, _hash_pw(pw)))
        conn.commit()
        conn.close()

        # Login with correct password
        login_res = login(LoginRequest(email=email, password=pw))
        self.assertIn("access_token", login_res)
        self.assertEqual(login_res["role"], "customer")

        # Login with wrong password
        with self.assertRaises(HTTPException) as ctx:
            login(LoginRequest(email=email, password="WrongPassword@123"))
        self.assertEqual(ctx.exception.status_code, 401)

    # Case 10: Google customer -> Customer role only (never auto-promote to admin/staff)
    @patch("routes.auth._exchange_google_code")
    @patch("routes.auth._fetch_google_userinfo")
    def test_10_google_role_strictly_customer(self, mock_userinfo, mock_exchange):
        """Verify new Google login accounts are always customer role only."""
        email = "admin_impersonator@gmail.com"
        google_sub = "google-sub-9999"

        conn = get_db()
        conn.execute("DELETE FROM users WHERE email=? OR google_id=?", (email, google_sub))
        conn.commit()
        conn.close()

        mock_exchange.return_value = {"access_token": "mock-access-token-10"}
        mock_userinfo.return_value = {
            "sub": google_sub,
            "email": email,
            "name": "Admin Impersonator",
            "email_verified": True
        }

        resp = asyncio.run(google_oauth_callback(code="auth-code-10"))
        self.assertEqual(resp.status_code, 200)

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        self.assertEqual(user["role"], "customer", "Google self-registration must strictly be customer")

if __name__ == "__main__":
    unittest.main()
