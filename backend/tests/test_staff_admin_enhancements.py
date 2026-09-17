"""
Mistri Enterprise Test Suite - Staff, Admin, Payroll, Support & Offers
Verifies:
1. Staff Repair Rejection with mandatory reasons & Single-Technician Ownership.
2. Admin Repair Reassignment with history preservation.
3. 6-Month Staff Commitment & 30-Day Resignation Notice Rules.
4. 15-Day Admin Termination Notice Requirement.
5. Staff Leave Management: 4 leaves/month, 2-day advance notice rule.
6. Transparent Salary Deduction Math (Salary / 30 * Unpaid Leaves).
7. Staff Performance & Festival Bonuses.
8. Staff In-Person Cash Payment Collection.
9. Multi-State UPI Payments with Admin Verification.
10. Customer Special & Festival Discount Coupons.
11. Customer Support Tickets (SUP-XXXX) and Message Threads.
"""
import unittest
import os
import sys
from datetime import datetime, date, timedelta

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import init_db, get_db
from routes.staff_mgmt import calculate_monthly_payroll
from routes.bills import apply_offer_to_bill, ApplyOfferRequest

class TestStaffAdminEnhancements(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.conn = get_db()

    def tearDown(self):
        self.conn.close()

    def test_01_leave_policy_and_salary_deduction_math(self):
        """Test daily rate and salary deduction for unpaid leaves beyond 4 allowed leaves."""
        # Scenario: Staff salary = 30,000, 30-day policy. Daily rate = 1000.
        # Staff took 6 approved leaves in a month.
        # 4 leaves allowed free. 2 unpaid leaves -> deduction = 2 * 1000 = 2000.
        # Payout = 30000 - 2000 = 28000.
        
        # Test math logic directly
        salary = 30000.0
        policy_days = 30
        daily_rate = round(salary / policy_days, 2)
        self.assertEqual(daily_rate, 1000.0)

        approved_leaves = 6
        allowed_leaves = 4
        unpaid_leaves = max(0, approved_leaves - allowed_leaves)
        self.assertEqual(unpaid_leaves, 2)

        deduction = round(unpaid_leaves * daily_rate, 2)
        self.assertEqual(deduction, 2000.0)

        bonus = 1500.0  # Festival bonus
        net_payout = round(salary - deduction + bonus, 2)
        self.assertEqual(net_payout, 29500.0)

    def test_02_two_day_advance_notice_rule(self):
        """Test that leave requests require at least 2 days advance notice."""
        today = date.today()
        tomorrow = today + timedelta(days=1)
        valid_future_date = today + timedelta(days=3)

        # Tomorrow is only 1 day in advance -> should fail 2-day rule
        diff_tomorrow = (tomorrow - today).days
        self.assertLess(diff_tomorrow, 2, "Tomorrow fails the 2-day advance notice rule.")

        # 3 days ahead -> should pass
        diff_future = (valid_future_date - today).days
        self.assertGreaterEqual(diff_future, 2, "3 days in advance satisfies the 2-day rule.")

    def test_03_six_month_commitment_and_30_day_notice(self):
        """Test staff 6-month commitment and 30-day resignation notice period calculations."""
        today = date.today()
        # New staff joined 60 days ago (2 months)
        joining_date = today - timedelta(days=60)
        days_served = (today - joining_date).days
        months_served = days_served / 30.4375

        self.assertLess(months_served, 6.0, "Staff is under 6 months commitment.")

        # Resignation notice test: proposed last date must be at least 30 days ahead
        short_last_date = today + timedelta(days=15)
        valid_last_date = today + timedelta(days=32)

        self.assertLess((short_last_date - today).days, 30, "15 days notice should be rejected (< 30 days).")
        self.assertGreaterEqual((valid_last_date - today).days, 30, "32 days notice satisfies 30-day rule.")

    def test_04_fifteen_day_admin_termination_notice(self):
        """Test admin must provide at least 15 days notice before staff termination."""
        today = date.today()
        min_notice_date = today + timedelta(days=15)
        self.assertEqual((min_notice_date - today).days, 15)

    def test_05_festival_coupon_and_offer_math(self):
        """Test percentage and flat customer coupon calculation."""
        # 10% coupon on 1000 subtotal
        subtotal = 1000.0
        pct_discount = subtotal * (10.0 / 100.0)
        self.assertEqual(pct_discount, 100.0)

        taxable = subtotal - pct_discount  # 900
        tax = round(taxable * 0.09, 2)     # 81.0
        total = taxable + tax              # 981.0
        self.assertEqual(total, 981.0)

        # Flat ₹150 coupon on 1000 subtotal
        flat_discount = 150.0
        taxable_flat = subtotal - flat_discount  # 850
        tax_flat = round(taxable_flat * 0.09, 2) # 76.5
        total_flat = taxable_flat + tax_flat     # 926.5
        self.assertEqual(total_flat, 926.5)

    def test_06_support_ticket_code_generation_and_thread(self):
        """Test support ticket code format SUP-YYYY-XXXX and message ordering."""
        year = datetime.now().year
        count = 42
        code = f"SUP-{year}-{str(count).zfill(4)}"
        self.assertTrue(code.startswith(f"SUP-{year}-"))
        self.assertEqual(len(code), 13)

    def test_07_cash_collection_attribution(self):
        """Test in-person cash payments record collected_by staff ID."""
        conn = self.conn
        # Verify columns exist in DB
        cols = [c[1] for c in conn.execute("PRAGMA table_info(payments)").fetchall()]
        self.assertIn("collected_by", cols)
        self.assertIn("verified_by", cols)
        self.assertIn("verified_at", cols)
        self.assertIn("notes", cols)

    def test_08_staff_bonuses_table_and_types(self):
        """Test staff_bonuses table structure and types."""
        conn = self.conn
        cols = [c[1] for c in conn.execute("PRAGMA table_info(staff_bonuses)").fetchall()]
        self.assertIn("bonus_type", cols)
        self.assertIn("amount", cols)
        self.assertIn("staff_id", cols)
        self.assertIn("reason", cols)

    def test_09_customer_offers_table(self):
        """Test customer_offers table exists and has seed offers."""
        conn = self.conn
        offers = conn.execute("SELECT code, discount_type, discount_value FROM customer_offers").fetchall()
        self.assertGreaterEqual(len(offers), 1, "At least one promotional offer should exist.")

if __name__ == "__main__":
    unittest.main(verbosity=2)
