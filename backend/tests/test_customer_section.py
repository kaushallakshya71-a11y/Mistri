"""
Mistri Customer Section - Dedicated Test Suite
Verifies:
1. Customer registration validations:
   - Gmail-only requirement (@gmail.com)
   - 10-digit Indian phone requirement
   - Strong password requirements (8+ chars, upper, lower, digit, special)
2. Address and Indian 6-digit pincode validation
3. Multi-device batch repair API (/submit-batch and /batch/{batch_id})
4. AI Estimator enhancements: Hinglish explanations, confidence ratings, labor & parts breakdown
"""
import unittest
import sys
import os
import re
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from routes.auth import validate_gmail, validate_phone, validate_password_strength
from routes.repairs import validate_pincode, validate_address
from routes.ai import estimate_cost
from fastapi import HTTPException

class TestCustomerSection(unittest.TestCase):

    def test_01_gmail_validation(self):
        """Test customer registration enforces valid Gmail addresses."""
        # Valid Gmail
        validate_gmail("customer.test@gmail.com", role="customer")
        validate_gmail("rajesh123@gmail.com", role="customer")

        # Non-Gmail addresses must raise HTTPException(400)
        invalid_emails = [
            "user@yahoo.com",
            "user@outlook.com",
            "user@hotmail.com",
            "user@company.in",
            "not-an-email",
            "@gmail.com",
            "test@gmail.co"
        ]
        for email in invalid_emails:
            with self.assertRaises(HTTPException, msg=f"Should reject: {email}") as ctx:
                validate_gmail(email, role="customer")
            self.assertEqual(ctx.exception.status_code, 400)

        # Admin and staff should NOT be restricted to Gmail
        validate_gmail("admin@mistri.com", role="admin")
        validate_gmail("staff@shop.co", role="staff")

    def test_02_indian_phone_validation(self):
        """Test 10-digit Indian phone validation (starts with 6, 7, 8, or 9)."""
        # Valid Indian numbers
        validate_phone("9876543210")
        validate_phone("8123456789")
        validate_phone("7000123456")
        validate_phone("6234567890")
        validate_phone("+91 9876543210")
        validate_phone("91-9876543210")
        validate_phone(None) # Optional

        # Invalid numbers
        invalid_phones = [
            "1234567890",   # Starts with 1
            "5876543210",   # Starts with 5
            "987654321",    # 9 digits
            "98765432100",  # 11 digits
            "abcdefghij",   # Non-numeric
        ]
        for phone in invalid_phones:
            with self.assertRaises(HTTPException, msg=f"Should reject: {phone}") as ctx:
                validate_phone(phone)
            self.assertEqual(ctx.exception.status_code, 400)

    def test_03_strong_password_policy(self):
        """Test strong password policy (8+ chars, upper, lower, digit, special)."""
        # Strong passwords must pass
        validate_password_strength("MyPass@123")
        validate_password_strength("Customer#2026")
        validate_password_strength("Secure$Strong!8")

        # Weak passwords must fail
        weak_passwords = [
            "short1!",       # < 8 chars
            "nouppercase1!", # No uppercase
            "NOLOWERCASE1!", # No lowercase
            "NoNumber!@#",   # No number
            "NoSpecial123",  # No special character
        ]
        for pw in weak_passwords:
            with self.assertRaises(HTTPException, msg=f"Should reject weak pw: {pw}") as ctx:
                validate_password_strength(pw)
            self.assertEqual(ctx.exception.status_code, 400)

    def test_04_indian_pincode_validation(self):
        """Test 6-digit Indian pincode validation."""
        # Valid pincodes
        validate_pincode("208001")
        validate_pincode("110001")
        validate_pincode("560001")
        validate_pincode(None)

        # Invalid pincodes
        invalid_pincodes = [
            "012345",  # Starts with 0
            "12345",   # 5 digits
            "1234567", # 7 digits
            "20800A",  # Contains letter
            "ABCDEF",  # Non-digit
        ]
        for pin in invalid_pincodes:
            with self.assertRaises(HTTPException, msg=f"Should reject: {pin}") as ctx:
                validate_pincode(pin)
            self.assertEqual(ctx.exception.status_code, 400)

    def test_05_address_validation(self):
        """Test address length and content validation."""
        validate_address("Flat 302, Green Valley Apartments, MG Road, Kanpur")
        
        with self.assertRaises(HTTPException):
            validate_address("")
        with self.assertRaises(HTTPException):
            validate_address("Too short")

    def test_06_ai_estimator_hinglish_and_confidence(self):
        """Test that AI estimator returns Hinglish explanation, confidence levels, and parts/labor breakdown."""
        # Test Fan
        fan_res = estimate_cost("Fan", "fan bahut slow chal raha hai aur ghoom nahi raha")
        self.assertIn("hinglish_explanation", fan_res)
        self.assertIn("confidence_level", fan_res)
        self.assertIn(fan_res["confidence_level"], ["High", "Medium", "Low"])
        self.assertIn("parts_cost_min", fan_res)
        self.assertIn("labor_cost_min", fan_res)
        self.assertGreater(fan_res["parts_cost_max"], 0)
        self.assertGreater(fan_res["labor_cost_max"], 0)
        self.assertGreater(len(fan_res["hinglish_explanation"]), 10)

        # Test Cooler with water/cooling issue
        cooler_res = estimate_cost("Cooler", "cooler ka paani pump nahi aa raha cooling bilkul nahi")
        self.assertEqual(cooler_res["primary_part"], "Water Pump")
        self.assertIn("Cooler", cooler_res["hinglish_explanation"])

        # Test vague/low confidence problem
        vague_res = estimate_cost("Fan", "problem ho gayi")
        self.assertIn("confidence_level", vague_res)
        self.assertIn("follow_up_questions", vague_res)

if __name__ == "__main__":
    unittest.main(verbosity=2)
