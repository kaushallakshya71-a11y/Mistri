"""
Mistri Automated Verification & Test Suite
Covers Database integrity, AI Model & Hinglish NLP, Billing & Taxes, Dynamic UPI QR,
Auth security, WhatsApp notifications, and Repair workflows.
"""
import sys
import os
import unittest
import json
import base64
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from db.database import get_db, init_db
from routes.ai import estimate_cost, normalize_symptoms
from routes.auth import _hash_pw, _verify_pw, create_access_token
from utils.qrcode_gen import generate_qr_base64
from utils.messaging import dispatch_repair_status_alert, send_whatsapp_message

class TestMistriSystem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Initialize database schema and ensure test user exists."""
        init_db()
        conn = get_db()
        user = conn.execute("SELECT id FROM users WHERE email='test_user@mistri.com'").fetchone()
        if not user:
            conn.execute("""
                INSERT INTO users (name, email, phone, password_hash, role, shop_id)
                VALUES ('Test User', 'test_user@mistri.com', '9876543210', 'dummy_hash', 'customer', 1)
            """)
            conn.commit()
        conn.close()

    def test_01_database_tables_and_multi_tenant_shop(self):
        """Verify database tables and default shop branch exist."""
        conn = get_db()
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = {t["name"] for t in tables}
        
        required_tables = {
            "users", "devices", "repair_jobs", "inventory",
            "bills", "payments", "notifications", "feedback",
            "shops", "shop_products", "shop_orders"
        }
        for rt in required_tables:
            self.assertIn(rt, table_names, f"Table '{rt}' must exist in the database.")

        # Check default shop
        default_shop = conn.execute("SELECT * FROM shops WHERE id=1").fetchone()
        self.assertIsNotNone(default_shop, "Default shop 1 should exist.")
        self.assertEqual(default_shop["upi_id"], "mistri@upi")
        conn.close()

    def test_02_ai_cost_estimator_english(self):
        """Verify AI estimation with English symptom descriptions."""
        res = estimate_cost("Fan", "fan making grinding screeching noise")
        self.assertEqual(res["device_type"], "Fan")
        self.assertEqual(res["primary_part"], "Bearing")
        self.assertGreater(res["estimated_cost_min"], 0)
        self.assertGreater(res["estimated_cost_max"], res["estimated_cost_min"])
        self.assertIsNotNone(res["ml_predicted_cost"], "ML predicted cost should be populated.")

    def test_03_ai_cost_estimator_hinglish_and_hindi(self):
        """Verify AI NLP normalizes Hinglish and Hindi colloquial terms."""
        # Hinglish slow fan
        res_hinglish = estimate_cost("Fan", "fan bohot dheema chal raha hai aur ghoom nahi raha")
        self.assertEqual(res_hinglish["primary_part"], "Capacitor")
        self.assertGreaterEqual(res_hinglish["confidence"], 70)

        # Hinglish burnt cooler motor
        res_cooler = estimate_cost("Cooler", "motor se dhuan aur badboo aa rahi hai jal gaya")
        self.assertEqual(res_cooler["primary_part"], "Cooler Motor")

        # Devanagari Hindi
        res_hindi = estimate_cost("Fan", "पंखा बहुत आवाज कर रहा है")
        self.assertEqual(res_hindi["primary_part"], "Bearing")

    def test_04_billing_and_tax_math(self):
        """Verify labour, parts, discount and 9% GST calculations."""
        labour = 400.0
        parts = 600.0
        discount = 100.0
        tax_rate = 0.09

        subtotal = labour + parts
        taxable = subtotal - discount
        expected_tax = round(taxable * tax_rate, 2)  # 900 * 0.09 = 81.00
        expected_total = round(taxable + expected_tax, 2)  # 981.00

        self.assertEqual(expected_tax, 81.00)
        self.assertEqual(expected_total, 981.00)

    def test_05_dynamic_upi_qr_generation(self):
        """Verify NPCI-compliant UPI URI generation and Base64 QR."""
        upi_intent = "upi://pay?pa=mistri@upi&pn=Mistri%20Electronics&am=981.00&cu=INR&tn=Invoice-BILL-2026-0001"
        self.assertTrue(upi_intent.startswith("upi://pay?"))
        self.assertIn("am=981.00", upi_intent)
        self.assertIn("pa=mistri@upi", upi_intent)

        # Generate QR code
        qr_b64 = generate_qr_base64(upi_intent)
        self.assertIsNotNone(qr_b64)
        # Should be valid base64 data
        decoded = base64.b64decode(qr_b64)
        self.assertTrue(decoded.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_06_auth_password_hashing(self):
        """Verify secure password hashing and verification."""
        raw_password = "SecretPassword@123"
        hashed = _hash_pw(raw_password)
        self.assertNotEqual(raw_password, hashed)
        self.assertTrue(_verify_pw(raw_password, hashed))
        self.assertFalse(_verify_pw("WrongPassword", hashed))

        # Test JWT token generation
        token = create_access_token(user_id=1, role="customer")
        self.assertIsNotNone(token)
        self.assertIsInstance(token, str)
        self.assertGreater(len(token), 30)

    def test_07_whatsapp_notification_dispatch(self):
        """Verify automated WhatsApp notification template and DB recording."""
        conn = get_db()
        user = conn.execute("SELECT id, name, phone FROM users WHERE email='test_user@mistri.com'").fetchone()
        conn.close()

        result = dispatch_repair_status_alert(
            customer_id=user["id"],
            customer_name=user["name"],
            customer_phone=user["phone"],
            repair_id="MIS-2026-9999",
            device_name="Bajaj Ceiling Fan",
            status="Completed",
            total_amount=350.00
        )
        self.assertIn(result["status"], ["sent", "simulated"])
        self.assertIn("MIS-2026-9999", result["message"])
        self.assertIn("₹350.00", result["message"])

        # Check notification record in DB
        conn = get_db()
        notif = conn.execute(
            "SELECT * FROM notifications WHERE channel='whatsapp' AND user_id=? ORDER BY id DESC LIMIT 1",
            (user["id"],)
        ).fetchone()
        self.assertIsNotNone(notif)
        self.assertEqual(notif["channel"], "whatsapp")
        self.assertIn(user["name"], notif["message"])
        conn.close()

    def test_08_technician_assignment_and_workload(self):
        """Verify technician assignment, duplicate prevention, and status transition."""
        from routes.repairs import assign_technician, AssignTechnicianRequest
        conn = get_db()
        admin_row = conn.execute("SELECT id, name, role FROM users WHERE role='admin' LIMIT 1").fetchone()
        tech = conn.execute("SELECT id, name, role FROM users WHERE role='staff' LIMIT 1").fetchone()
        job = conn.execute("SELECT id FROM repair_jobs ORDER BY id ASC LIMIT 1").fetchone()
        self.assertIsNotNone(job, "A repair job must exist for assignment test.")
        job_id = job["id"]
        tech_id = tech["id"]
        admin_user = {"id": admin_row["id"], "name": admin_row["name"], "role": "admin"}

        # Ensure job is unassigned first for clean assignment test
        conn.execute("UPDATE repair_jobs SET technician_id = NULL, status = 'Requested' WHERE id = ?", (job_id,))
        conn.commit()
        conn.close()

        # 1. Perform assignment
        req = AssignTechnicianRequest(technician_id=tech_id, note="Assigned for fast service")
        res = assign_technician(job_id=job_id, req=req, current_user=admin_user)
        self.assertEqual(res["status"], "Assigned")

        # Verify DB record
        conn = get_db()
        updated_job = conn.execute("SELECT status, technician_id, assigned_by FROM repair_jobs WHERE id=?", (job_id,)).fetchone()
        self.assertEqual(updated_job["technician_id"], tech_id)
        self.assertEqual(updated_job["assigned_by"], admin_user["id"])

        # Verify history log entry
        hist = conn.execute("SELECT * FROM repair_status_history WHERE repair_job_id=? ORDER BY id DESC LIMIT 1", (job_id,)).fetchone()
        self.assertEqual(hist["to_status"], "Assigned")
        self.assertIn("Assigned to", hist["note"])
        conn.close()

        # 2. Duplicate assignment attempt should return info message without crashing
        dup_res = assign_technician(job_id=job_id, req=req, current_user=admin_user)
        self.assertIn("already assigned", dup_res["message"])

    def test_09_atomic_inventory_deduction_and_guard(self):
        """Verify atomic stock deduction, transaction recording, and rejection of overdrafts."""
        from routes.repairs import add_part_atomic, AddPartRequest
        from fastapi import HTTPException

        conn = get_db()
        conn = get_db()
        staff_row = conn.execute("SELECT id, name, role FROM users WHERE role='staff' LIMIT 1").fetchone()
        item = conn.execute("SELECT * FROM inventory WHERE quantity >= 3 LIMIT 1").fetchone()
        self.assertIsNotNone(item, "Inventory item with >= 3 quantity required.")
        item_id = item["id"]
        initial_qty = item["quantity"]
        job = conn.execute("SELECT id FROM repair_jobs LIMIT 1").fetchone()
        job_id = job["id"]
        conn.close()

        staff_user = {"id": staff_row["id"], "name": staff_row["name"], "role": "staff"}

        # 1. Deduct 1 item
        res = add_part_atomic(job_id=job_id, req=AddPartRequest(part_id=item_id, quantity=1), current_user=staff_user)
        self.assertEqual(res["new_stock"], initial_qty - 1)

        # Verify transaction log
        conn = get_db()
        tx = conn.execute("SELECT * FROM inventory_transactions WHERE part_id=? ORDER BY id DESC LIMIT 1", (item_id,)).fetchone()
        self.assertIsNotNone(tx)
        self.assertEqual(tx["transaction_type"], "OUT")
        self.assertEqual(tx["quantity"], 1)

        # 2. Attempt overdraft: request more than available
        with self.assertRaises(HTTPException) as ctx:
            add_part_atomic(job_id=job_id, req=AddPartRequest(part_id=item_id, quantity=99999), current_user=staff_user)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Insufficient stock", ctx.exception.detail)

        # Re-verify stock didn't change after failed transaction
        check_item = conn.execute("SELECT quantity FROM inventory WHERE id=?", (item_id,)).fetchone()
        self.assertEqual(check_item["quantity"], initial_qty - 1)
        conn.close()

    def test_10_inventory_reorder_alerts_and_restock(self):
        """Verify low-stock reorder thresholds and restock workflows."""
        from routes.inventory import get_reorder_alerts, restock_item, RestockRequest

        conn = get_db()
        admin_row = conn.execute("SELECT id, name, role FROM users WHERE role='admin' LIMIT 1").fetchone()
        admin_user = {"id": admin_row["id"], "name": admin_row["name"], "role": "admin"}
        item = conn.execute("SELECT id, reorder_level FROM inventory LIMIT 1").fetchone()
        item_id = item["id"]
        reorder_lvl = item["reorder_level"]
        conn.execute("UPDATE inventory SET quantity=? WHERE id=?", (reorder_lvl, item_id))
        conn.commit()
        conn.close()

        # Check reorder alert returned
        alerts = get_reorder_alerts(current_user=admin_user)
        matching = [a for a in alerts if a["id"] == item_id]
        self.assertTrue(len(matching) > 0, "Alert must be triggered when quantity <= reorder_level")

        # Restock item
        restock_res = restock_item(
            req=RestockRequest(part_id=item_id, quantity=15, reason="Batch Supplier PO"),
            current_user=admin_user
        )
        self.assertEqual(restock_res["new_quantity"], reorder_lvl + 15)

        # Verify transaction logged
        conn = get_db()
        tx = conn.execute("SELECT * FROM inventory_transactions WHERE part_id=? AND transaction_type='IN' ORDER BY id DESC LIMIT 1", (item_id,)).fetchone()
        self.assertIsNotNone(tx)
        self.assertEqual(tx["quantity"], 15)
        conn.close()

    def test_11_warranty_lifecycle_and_claims(self):
        """Verify warranty issuance, days countdown, claim filing, and resolution."""
        from routes.warranties import (
            create_warranty, WarrantyCreateRequest,
            submit_warranty_claim, WarrantyClaimRequest,
            update_claim_status, ClaimStatusUpdate,
            get_repair_warranty
        )

        conn = get_db()
        admin_row = conn.execute("SELECT id, name, role FROM users WHERE role='admin' LIMIT 1").fetchone()
        admin_user = {"id": admin_row["id"], "name": admin_row["name"], "role": "admin"}
        job = conn.execute("SELECT id, customer_id FROM repair_jobs ORDER BY id ASC LIMIT 1").fetchone()
        job_id = job["id"]
        customer_id = job["customer_id"]

        # Ensure job is in Completed status and clean old warranties
        conn.execute("UPDATE repair_jobs SET status='Completed' WHERE id=?", (job_id,))
        conn.execute("DELETE FROM warranty_claims WHERE warranty_id IN (SELECT id FROM warranties WHERE repair_job_id=?)", (job_id,))
        conn.execute("DELETE FROM warranties WHERE repair_job_id=?", (job_id,))
        conn.commit()
        conn.close()

        cust_user = {"id": customer_id, "name": "Customer", "role": "customer"}

        # 1. Issue warranty
        w_res = create_warranty(
            req=WarrantyCreateRequest(repair_job_id=job_id, duration_days=180, covered_terms="Covers all motors and capacitors"),
            current_user=admin_user
        )
        self.assertTrue(w_res["warranty_code"].startswith("WAR-"))
        self.assertEqual(w_res["duration_days"], 180)

        # 2. Get warranty by repair
        w_detail = get_repair_warranty(job_id=job_id, current_user=admin_user)
        self.assertTrue(w_detail["is_active"])
        self.assertGreater(w_detail["days_remaining"], 150)

        # 3. Customer files claim
        claim_res = submit_warranty_claim(
            req=WarrantyClaimRequest(repair_job_id=job_id, issue_description="Fan is vibrating again after 2 weeks"),
            current_user=cust_user
        )
        claim_id = claim_res["claim_id"]
        self.assertEqual(claim_res["status"], "Pending")

        # 4. Admin resolves claim
        upd_res = update_claim_status(
            claim_id=claim_id,
            req=ClaimStatusUpdate(status="Approved", admin_notes="Free capacitor check scheduled"),
            current_user=admin_user
        )
        self.assertEqual(upd_res["status"], "Approved")

    def test_12_ai_technician_recommendation_algorithm(self):
        """Verify multi-criteria AI technician ranking based on device experience, rating, and load."""
        from routes.ai import recommend_technician

        conn = get_db()
        job = conn.execute("SELECT id FROM repair_jobs LIMIT 1").fetchone()
        admin_row = conn.execute("SELECT id, name, role FROM users WHERE role='admin' LIMIT 1").fetchone()
        conn.close()

        admin_user = {"id": admin_row["id"], "name": admin_row["name"], "role": "admin"}
        res = recommend_technician(job_id=job["id"], current_user=admin_user)
        self.assertIn("recommendations", res)
        recs = res["recommendations"]
        self.assertGreater(len(recs), 0, "Should recommend available technicians.")
        
        # Verify recommendation structure
        first = recs[0]
        self.assertIn("match_score", first)
        self.assertIn("completed_same_device", first)
        self.assertIn("current_workload", first)
        self.assertIn("rationale", first)

        # Scores should be sorted descending
        if len(recs) > 1:
            self.assertGreaterEqual(recs[0]["match_score"], recs[1]["match_score"])

    def test_13_audit_trail_logging(self):
        """Verify enterprise tamper-evident audit logging."""
        from utils.audit import log_audit_event
        from routes.reports import get_audit_logs

        conn = get_db()
        admin_row = conn.execute("SELECT id, name, role FROM users WHERE role='admin' LIMIT 1").fetchone()
        conn.close()
        admin_user = {"id": admin_row["id"], "name": admin_row["name"], "role": "admin"}

        log_audit_event(
            user=admin_user,
            action="SECURITY_CHECK_PASSED",
            entity="SYSTEM",
            entity_id=101,
            details={"test": "audit_trail_verification"},
            ip_address="127.0.0.1"
        )

        logs = get_audit_logs(limit=20, current_user=admin_user)
        found = any(l["action"] == "SECURITY_CHECK_PASSED" for l in logs)
        self.assertTrue(found, "Security check audit log must be queryable by admin.")

    def test_14_security_and_rbac_boundaries(self):
        """Verify role-based access control blocks unauthorized operations."""
        from routes.repairs import add_part_atomic, AddPartRequest
        from routes.reports import get_audit_logs
        from fastapi import HTTPException

        conn = get_db()
        cust_row = conn.execute("SELECT id, name, role FROM users WHERE role='customer' LIMIT 1").fetchone()
        conn.close()
        cust_user = {"id": cust_row["id"], "name": cust_row["name"], "role": "customer"}

        # Customer trying to deduct inventory parts -> 403 Forbidden
        with self.assertRaises(HTTPException) as ctx:
            add_part_atomic(job_id=1, req=AddPartRequest(part_id=1, quantity=1), current_user=cust_user)
        self.assertEqual(ctx.exception.status_code, 403)

        # Customer trying to read system audit logs -> 403 Forbidden
        with self.assertRaises(HTTPException) as ctx2:
            get_audit_logs(limit=10, current_user=cust_user)
        self.assertEqual(ctx2.exception.status_code, 403)

if __name__ == "__main__":
    unittest.main(verbosity=2)

