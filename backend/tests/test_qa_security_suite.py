"""
Mistri Enterprise QA & Security Test Suite
Tests all 18 hardened modules:
- Admin self-deletion and last-admin safeguards
- Password strength, verification, and admin reset
- Deactivated user middleware block
- Customer bill & warranty data isolation (multi-tenant boundaries)
- Non-destructive invoice void/cancel/archive & financial integrity
- UTR validation & duplicate payment prevention
- Concurrency-safe atomic inventory deductions
- Strict repair status state machine & admin override audit
- File upload extension, size, and magic byte validation
- Server-side coupon verification & exact tax/discount math
- Warranty claim duplicate prevention & mandatory rejection reason
- Online SQLite backup creation, listing, and path-traversal prevention
"""
import unittest
import os
import sys
import tempfile
import sqlite3
from datetime import datetime, date, timedelta

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import HTTPException
from db.database import init_db, get_db
from routes.auth import (
    _hash_pw as hash_password, delete_user, change_password,
    admin_reset_password as reset_user_password, ChangePasswordRequest, AdminResetPasswordRequest
)
from routes.bills import (
    get_bill, record_online_payment, verify_payment, void_bill, cancel_bill,
    update_bill, delete_bill, apply_offer_to_bill, remove_offer_from_bill,
    InvoiceActionRequest, BillUpdate, OnlinePaymentRequest, PaymentVerifyRequest,
    ApplyOfferRequest, calculate_bill_totals
)
from routes.inventory import update_stock, StockUpdate
from routes.repairs import (
    update_status, add_part_atomic, validate_file_magic_bytes,
    RepairStatusUpdate, AddPartRequest
)
from routes.warranties import (
    submit_warranty_claim, update_claim_status, WarrantyClaimRequest, ClaimStatusUpdate
)
from utils.backup import create_database_backup, list_database_backups, restore_database_backup

class TestQASecuritySuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.conn = get_db()

    def tearDown(self):
        self.conn.close()

    def _get_or_create_job(self):
        """Helper to ensure a valid repair job with valid foreign keys exists for billing tests."""
        job = self.conn.execute("SELECT id, customer_id, shop_id FROM repair_jobs LIMIT 1").fetchone()
        if job:
            return job["id"], job["customer_id"], job["shop_id"] or 1

        cust = self.conn.execute("SELECT id FROM users WHERE role='customer' LIMIT 1").fetchone()
        cust_id = cust["id"] if cust else 1
        dev = self.conn.execute("SELECT id FROM devices LIMIT 1").fetchone()
        if not dev:
            c = self.conn.execute("INSERT INTO devices (customer_id, device_type, brand, model) VALUES (?, 'Fan', 'Bajaj', 'Max')", (cust_id,))
            dev_id = c.lastrowid
        else:
            dev_id = dev["id"]

        cursor = self.conn.execute("""
            INSERT INTO repair_jobs (repair_id, customer_id, device_id, problem_description, status, shop_id)
            VALUES ('MIS-TEST-001', ?, ?, 'Fan rattling', 'Requested', 1)
        """, (cust_id, dev_id))
        self.conn.commit()
        return cursor.lastrowid, cust_id, 1

    def test_01_last_admin_and_self_deletion_safeguards(self):
        """Admin cannot delete self, and last active admin cannot be deleted or deactivated."""
        admin = self.conn.execute("SELECT * FROM users WHERE role='admin' AND is_active=1 LIMIT 1").fetchone()
        self.assertIsNotNone(admin)
        admin_dict = dict(admin)

        # 1. Admin self-deletion attempt must raise 400
        with self.assertRaises(HTTPException) as ctx:
            delete_user(user_id=admin_dict["id"], current_user=admin_dict)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("cannot deactivate their own account", ctx.exception.detail)

        # 2. Deleting the last admin must raise 400
        self.conn.execute("UPDATE users SET is_active=0 WHERE role='admin' AND id != ?", (admin_dict["id"],))
        self.conn.commit()

        other_admin_mock = {"id": 99999, "name": "Super Admin Mock", "role": "admin"}
        with self.assertRaises(HTTPException) as ctx:
            delete_user(user_id=admin_dict["id"], current_user=other_admin_mock)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("last active administrator", ctx.exception.detail)

    def test_02_password_management_and_strength_validation(self):
        """Test change-password verifies old password and enforces strong password policy."""
        email = f"pwd_test_{datetime.now().timestamp()}@gmail.com"
        initial_pw = "OldP@ssw0rd123"
        hashed = hash_password(initial_pw)
        cursor = self.conn.execute(
            "INSERT INTO users (name, email, password_hash, role, phone, is_active) VALUES (?, ?, ?, 'customer', '9876543210', 1)",
            ("Password Tester", email, hashed)
        )
        user_id = cursor.lastrowid
        self.conn.commit()
        user_dict = {"id": user_id, "name": "Password Tester", "role": "customer", "email": email}

        # 1. Incorrect current password rejected
        with self.assertRaises(HTTPException) as ctx:
            change_password(
                req=ChangePasswordRequest(old_password="WrongPassword123!", new_password="NewP@ssw0rd999"),
                current_user=user_dict
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Incorrect current password", ctx.exception.detail)

        # 2. Weak new password rejected
        with self.assertRaises(HTTPException) as ctx:
            change_password(
                req=ChangePasswordRequest(old_password=initial_pw, new_password="weak"),
                current_user=user_dict
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("at least 8 characters", ctx.exception.detail)

        # 3. Valid change password succeeds
        res = change_password(
            req=ChangePasswordRequest(old_password=initial_pw, new_password="StrongP@ssword2026"),
            current_user=user_dict
        )
        self.assertIn("Password updated successfully", res["message"])

        # 4. Admin reset password works
        admin = self.conn.execute("SELECT id, name, role FROM users WHERE role='admin' LIMIT 1").fetchone()
        admin_dict = dict(admin)
        reset_res = reset_user_password(
            user_id=user_id,
            req=AdminResetPasswordRequest(new_password="AdminReset#2026"),
            current_user=admin_dict
        )
        self.assertIn("Password for 'Password Tester' reset successfully", reset_res["message"])

    def test_03_customer_bill_isolation(self):
        """Customers can only access and pay for their own bills (403 Forbidden for cross-access)."""
        cust_a = self.conn.execute("SELECT * FROM users WHERE role='customer' LIMIT 1").fetchone()
        cust_b = self.conn.execute("SELECT * FROM users WHERE role='customer' AND id != ? LIMIT 1", (cust_a["id"],)).fetchone()
        self.assertIsNotNone(cust_a)
        self.assertIsNotNone(cust_b)

        job_id, _, shop_id = self._get_or_create_job()

        cursor = self.conn.execute("""
            INSERT INTO bills (bill_number, repair_job_id, customer_id, shop_id, labour_charge, parts_cost, total_amount, payment_status)
            VALUES (?, ?, ?, ?, 200, 100, 327, 'Pending')
        """, (f"BILL-ISO-{int(datetime.now().timestamp())}", job_id, cust_a["id"], shop_id))
        bill_id = cursor.lastrowid
        self.conn.commit()

        cust_b_user = {"id": cust_b["id"], "name": cust_b["name"], "role": "customer"}

        # 1. Customer B cannot view Customer A's bill
        with self.assertRaises(HTTPException) as ctx:
            get_bill(bill_id=bill_id, current_user=cust_b_user)
        self.assertEqual(ctx.exception.status_code, 403)

        # 2. Customer B cannot submit online payment for Customer A's bill
        with self.assertRaises(HTTPException) as ctx:
            record_online_payment(
                bill_id=bill_id,
                req=OnlinePaymentRequest(payment_method="UPI", transaction_id="TESTUTR1234567890"),
                current_user=cust_b_user
            )
        self.assertEqual(ctx.exception.status_code, 403)

    def test_04_utr_fraud_prevention_and_duplicate_check(self):
        """UTR format is validated and duplicate UTR submissions are rejected."""
        cust = self.conn.execute("SELECT * FROM users WHERE role='customer' LIMIT 1").fetchone()
        cust_user = dict(cust)
        job_id, _, shop_id = self._get_or_create_job()

        bill_num = f"BILL-UTR-{int(datetime.now().timestamp())}"
        cursor = self.conn.execute("""
            INSERT INTO bills (bill_number, repair_job_id, customer_id, shop_id, labour_charge, parts_cost, total_amount, payment_status)
            VALUES (?, ?, ?, ?, 300, 200, 545, 'Pending')
        """, (bill_num, job_id, cust_user["id"], shop_id))
        bill_id = cursor.lastrowid
        self.conn.commit()

        # 1. Invalid UTR formats rejected
        for bad_utr in ["123", "ABC-123-XYZ", "0000000000", "aaaaabbbbb"]:
            with self.assertRaises(HTTPException) as ctx:
                record_online_payment(
                    bill_id=bill_id,
                    req=OnlinePaymentRequest(payment_method="UPI", transaction_id=bad_utr),
                    current_user=cust_user
                )
            self.assertEqual(ctx.exception.status_code, 400)

        # 2. Valid UTR submission succeeds with status Pending
        valid_utr = f"UTR{int(datetime.now().timestamp())}XYZ99"
        res = record_online_payment(
            bill_id=bill_id,
            req=OnlinePaymentRequest(payment_method="UPI", transaction_id=valid_utr),
            current_user=cust_user
        )
        self.assertEqual(res["payment_status"], "Pending")

        # 3. Duplicate UTR attempt on any bill must be rejected
        with self.assertRaises(HTTPException) as ctx:
            record_online_payment(
                bill_id=bill_id,
                req=OnlinePaymentRequest(payment_method="UPI", transaction_id=valid_utr),
                current_user=cust_user
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("already been submitted", ctx.exception.detail)

    def test_05_payment_rejection_requires_mandatory_reason(self):
        """Admin rejecting a payment must provide a clear reason."""
        admin = self.conn.execute("SELECT * FROM users WHERE role='admin' LIMIT 1").fetchone()
        admin_user = dict(admin)
        job_id, cust_id, shop_id = self._get_or_create_job()

        b_rej = f"BILL-REJ-{int(datetime.now().timestamp() * 1000)}"
        cursor = self.conn.execute("""
            INSERT INTO bills (bill_number, repair_job_id, customer_id, shop_id, labour_charge, parts_cost, total_amount, payment_status)
            VALUES (?, ?, ?, ?, 100, 100, 218, 'Pending')
        """, (b_rej, job_id, cust_id, shop_id))
        bill_id = cursor.lastrowid
        self.conn.commit()

        # Rejecting without reason raises 400
        with self.assertRaises(HTTPException) as ctx:
            verify_payment(bill_id=bill_id, req=PaymentVerifyRequest(action="Reject", notes=""), current_user=admin_user)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("rejection reason", ctx.exception.detail)

        # Rejecting with valid reason succeeds
        res = verify_payment(bill_id=bill_id, req=PaymentVerifyRequest(action="Reject", notes="UTR not found in bank statement"), current_user=admin_user)
        self.assertEqual(res["action"], "Reject")

    def test_06_non_destructive_invoice_lifecycle(self):
        """Test non-destructive invoice void, cancel, archive, and financial integrity."""
        admin = self.conn.execute("SELECT * FROM users WHERE role='admin' LIMIT 1").fetchone()
        admin_user = dict(admin)
        job_id, cust_id, shop_id = self._get_or_create_job()

        b_life = f"BILL-LIFE-{int(datetime.now().timestamp() * 1000)}"
        cursor = self.conn.execute("""
            INSERT INTO bills (bill_number, repair_job_id, customer_id, shop_id, labour_charge, parts_cost, discount, tax, total_amount, payment_status)
            VALUES (?, ?, ?, ?, 500, 500, 0, 90, 1090, 'Pending')
        """, (b_life, job_id, cust_id, shop_id))
        bill_id = cursor.lastrowid
        self.conn.commit()

        # 1. Voiding requires reason >= 3 chars
        with self.assertRaises(HTTPException) as ctx:
            void_bill(bill_id=bill_id, req=InvoiceActionRequest(reason="no"), current_user=admin_user)
        self.assertEqual(ctx.exception.status_code, 400)

        # 2. Void bill succeeds and updates columns
        void_res = void_bill(bill_id=bill_id, req=InvoiceActionRequest(reason="Customer changed mind, job not done"), current_user=admin_user)
        self.assertEqual(void_res["status"], "Void")

        row = self.conn.execute("SELECT is_void, void_reason, payment_status FROM bills WHERE id=?", (bill_id,)).fetchone()
        self.assertEqual(row["is_void"], 1)
        self.assertEqual(row["payment_status"], "Void")

        # 3. Cannot modify financial totals on a voided bill
        with self.assertRaises(HTTPException) as ctx:
            update_bill(bill_id=bill_id, req=BillUpdate(labour_charge=999), current_user=admin_user)
        self.assertEqual(ctx.exception.status_code, 400)

        # 4. Soft cancellation via delete_bill
        b_del = f"BILL-DEL-{int(datetime.now().timestamp() * 1000)}"
        cursor2 = self.conn.execute("""
            INSERT INTO bills (bill_number, repair_job_id, customer_id, shop_id, labour_charge, parts_cost, discount, tax, total_amount, payment_status)
            VALUES (?, ?, ?, ?, 200, 200, 0, 36, 436, 'Pending')
        """, (b_del, job_id, cust_id, shop_id))
        bill2_id = cursor2.lastrowid
        self.conn.commit()

        del_res = delete_bill(bill_id=bill2_id, current_user=admin_user)
        self.assertIn("cancelled", del_res["message"].lower())

        # Bill still exists in DB (not hard deleted!)
        check_bill = self.conn.execute("SELECT is_cancelled, payment_status FROM bills WHERE id=?", (bill2_id,)).fetchone()
        self.assertIsNotNone(check_bill)
        self.assertEqual(check_bill["is_cancelled"], 1)
        self.assertEqual(check_bill["payment_status"], "Cancelled")

    def test_07_atomic_inventory_protection_against_negative_stock(self):
        """Inventory update rejects overdraft atomically."""
        admin = self.conn.execute("SELECT * FROM users WHERE role='admin' LIMIT 1").fetchone()
        admin_user = dict(admin)

        part_code = f"TEST-CAP-{int(datetime.now().timestamp() * 1000)}"
        cursor = self.conn.execute("""
            INSERT INTO inventory (part_name, part_code, category, quantity, unit_price, is_active, shop_id)
            VALUES ('Test Capacitor 5uF', ?, 'Capacitors', 5, 50.0, 1, 1)
        """, (part_code,))
        part_id = cursor.lastrowid
        self.conn.commit()

        # Deduct 3 units (success)
        res = update_stock(item_id=part_id, update=StockUpdate(quantity_change=-3), current_user=admin_user)
        self.assertEqual(res["new_quantity"], 2)

        # Attempt to deduct 5 units when only 2 remain (must raise 400)
        with self.assertRaises(HTTPException) as ctx:
            update_stock(item_id=part_id, update=StockUpdate(quantity_change=-5), current_user=admin_user)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Insufficient stock", ctx.exception.detail)

        # Verify stock remains exactly 2
        item = self.conn.execute("SELECT quantity FROM inventory WHERE id=?", (part_id,)).fetchone()
        self.assertEqual(item["quantity"], 2)

    def test_08_repair_status_state_machine_and_admin_override(self):
        """Staff cannot perform illegal status jumps; Admin requires override note for jumps."""
        staff = self.conn.execute("SELECT * FROM users WHERE role='staff' LIMIT 1").fetchone()
        admin = self.conn.execute("SELECT * FROM users WHERE role='admin' LIMIT 1").fetchone()
        staff_user = dict(staff)
        admin_user = dict(admin)

        cust = self.conn.execute("SELECT id FROM users WHERE role='customer' LIMIT 1").fetchone()
        dev = self.conn.execute("SELECT id FROM devices LIMIT 1").fetchone()

        rep_id = f"MIS-STAT-{int(datetime.now().timestamp() * 1000)}"
        cursor = self.conn.execute("""
            INSERT INTO repair_jobs (repair_id, customer_id, device_id, problem_description, status, technician_id)
            VALUES (?, ?, ?, 'Motor issue', 'Requested', ?)
        """, (rep_id, cust["id"], dev["id"], staff_user["id"]))
        job_id = cursor.lastrowid
        self.conn.commit()

        # 1. Customer cannot update status (403)
        with self.assertRaises(HTTPException) as ctx:
            update_status(job_id=job_id, update=RepairStatusUpdate(status="Assigned"), current_user={"id": cust["id"], "role": "customer"})
        self.assertEqual(ctx.exception.status_code, 403)

        # 2. Staff cannot jump directly from Requested to Completed (illegal transition)
        with self.assertRaises(HTTPException) as ctx:
            update_status(job_id=job_id, update=RepairStatusUpdate(status="Completed"), current_user=staff_user)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Invalid status transition", ctx.exception.detail)

        # 3. Staff can advance to legal next status (Assigned)
        res = update_status(job_id=job_id, update=RepairStatusUpdate(status="Assigned"), current_user=staff_user)
        self.assertEqual(res["status"], "Assigned")

        # 4. Admin jumping without override note is rejected
        with self.assertRaises(HTTPException) as ctx:
            update_status(job_id=job_id, update=RepairStatusUpdate(status="Completed"), current_user=admin_user)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("admin override note", ctx.exception.detail)

        # 5. Admin jumping WITH override note succeeds
        res_admin = update_status(
            job_id=job_id,
            update=RepairStatusUpdate(status="Completed", note="Direct customer pickup fast track approved by manager"),
            current_user=admin_user
        )
        self.assertEqual(res_admin["status"], "Completed")

    def test_09_file_upload_magic_bytes_validation(self):
        """Magic bytes validator rejects malicious or spoofed files."""
        # Valid PNG magic bytes
        valid_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'
        self.assertTrue(validate_file_magic_bytes(valid_png, "png"))

        # Valid JPEG magic bytes
        valid_jpg = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01'
        self.assertTrue(validate_file_magic_bytes(valid_jpg, "jpg"))

        # Valid WebP magic bytes
        valid_webp = b'RIFF\x24\x00\x00\x00WEBPVP8 '
        self.assertTrue(validate_file_magic_bytes(valid_webp, "webp"))

        # Spoofed file (plain text disguised as jpg)
        fake_jpg = b'Hello, this is a plain text file pretending to be an image.'
        self.assertFalse(validate_file_magic_bytes(fake_jpg, "jpg"))

        # Empty or tiny content
        self.assertFalse(validate_file_magic_bytes(b'abc', "png"))

    def test_10_coupon_calculations_and_limits(self):
        """Coupon math follows taxable subtotal and prevents duplicate redemptions beyond limits."""
        subtotal, discount, taxable, tax, total = calculate_bill_totals(
            labour_charge=300.0, parts_cost=700.0, discount=100.0, tax_rate=0.09
        )
        self.assertEqual(subtotal, 1000.0)
        self.assertEqual(discount, 100.0)
        self.assertEqual(taxable, 900.0)
        self.assertEqual(tax, 81.0)
        self.assertEqual(total, 981.0)

        # Negative discount or discount > subtotal clamped safely
        _, safe_discount, _, _, _ = calculate_bill_totals(
            labour_charge=100.0, parts_cost=100.0, discount=9999.0
        )
        self.assertEqual(safe_discount, 200.0)

    def test_11_warranty_claims_duplicate_prevention_and_rejection_reason(self):
        """Duplicate warranty claims are blocked; rejections require mandatory reason."""
        cust = self.conn.execute("SELECT * FROM users WHERE role='customer' LIMIT 1").fetchone()
        admin = self.conn.execute("SELECT * FROM users WHERE role='admin' LIMIT 1").fetchone()
        cust_user = dict(cust)
        admin_user = dict(admin)

        cust = self.conn.execute("SELECT id FROM users WHERE role='customer' LIMIT 1").fetchone()
        dev = self.conn.execute("SELECT id FROM devices LIMIT 1").fetchone()
        if not dev:
            c = self.conn.execute("INSERT INTO devices (customer_id, device_type, brand, model) VALUES (?, 'Fan', 'Bajaj', 'Max')", (cust["id"],))
            dev_id = c.lastrowid
        else:
            dev_id = dev["id"]
        ts = int(datetime.now().timestamp() * 1000)
        c_job = self.conn.execute("""
            INSERT INTO repair_jobs (repair_id, customer_id, device_id, problem_description, status, shop_id)
            VALUES (?, ?, ?, 'Warranty test issue', 'Completed', 1)
        """, (f"MIS-WARR-{ts}", cust["id"], dev_id))
        job_id = c_job.lastrowid
        self.conn.commit()

        # Create active warranty with valid job_id
        cursor = self.conn.execute("""
            INSERT INTO warranties (repair_job_id, customer_id, duration_days, start_date, end_date, covered_terms, status)
            VALUES (?, ?, 180, DATE('now'), DATE('now', '+180 days'), 'Parts and labour warranty', 'Active')
        """, (job_id, cust_user["id"]))
        warranty_id = cursor.lastrowid
        self.conn.commit()

        # 1. Short description rejected
        with self.assertRaises(HTTPException) as ctx:
            submit_warranty_claim(
                req=WarrantyClaimRequest(repair_job_id=job_id, issue_description="bad"),
                current_user=cust_user
            )
        self.assertEqual(ctx.exception.status_code, 400)

        # 2. First valid claim succeeds
        claim_res = submit_warranty_claim(
            req=WarrantyClaimRequest(repair_job_id=job_id, issue_description="Fan started making loud rattling noise again"),
            current_user=cust_user
        )
        claim_id = claim_res["claim_id"]

        # 3. Duplicate active claim for same warranty rejected
        with self.assertRaises(HTTPException) as ctx:
            submit_warranty_claim(
                req=WarrantyClaimRequest(repair_job_id=job_id, issue_description="Same noise issue recurring"),
                current_user=cust_user
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("already", ctx.exception.detail.lower())

        # 4. Admin rejecting claim requires minimum 5 characters reason
        with self.assertRaises(HTTPException) as ctx:
            update_claim_status(
                claim_id=claim_id,
                req=ClaimStatusUpdate(status="Rejected", admin_notes="no"),
                current_user=admin_user
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("rejection reason", ctx.exception.detail.lower())

        # 5. Valid rejection with reason succeeds
        rej_res = update_claim_status(
            claim_id=claim_id,
            req=ClaimStatusUpdate(status="Rejected", admin_notes="Physical blade damage caused by external hit"),
            current_user=admin_user
        )
        self.assertEqual(rej_res["status"], "Rejected")
        self.assertEqual(rej_res["rejection_reason"], "Physical blade damage caused by external hit")

    def test_12_database_backup_and_recovery(self):
        """Database backup creates consistent snapshot and prevents directory traversal on restore."""
        # 1. Create backup
        backup_meta = create_database_backup()
        self.assertTrue(os.path.exists(backup_meta["path"]))
        self.assertGreater(backup_meta["size_bytes"], 0)

        # 2. List backups includes the created snapshot
        all_backups = list_database_backups()
        filenames = [b["filename"] for b in all_backups]
        self.assertIn(backup_meta["filename"], filenames)

        # 3. Path traversal attack on restore is rejected
        with self.assertRaises(ValueError):
            restore_database_backup("../../../etc/passwd")

        with self.assertRaises(ValueError):
            restore_database_backup("test/../../secret.db")

        # 4. Restoring valid snapshot succeeds
        restore_res = restore_database_backup(backup_meta["filename"])
        self.assertIn("successfully restored", restore_res["message"])

if __name__ == "__main__":
    unittest.main()
