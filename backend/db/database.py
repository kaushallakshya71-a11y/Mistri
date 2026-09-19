"""
Mistri Database - SQLite initialization, connection management, and automated migrations.
Hardened with WAL mode, busy timeout, multi-shop support, comprehensive lifecycle history,
inventory transactions, warranties, audit logging, and database indexes.
"""
import sqlite3
import os
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent / "mistri.db"

def get_db():
    """Get a database connection with row factory, WAL mode and timeout for high concurrency."""
    conn = sqlite3.connect(str(DB_PATH), timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn

@contextmanager
def get_db_ctx():
    """Context manager for automatic connection closing and rollback on error."""
    conn = get_db()
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Initialize all database tables with multi-tenant shop support and professional features."""
    conn = get_db()
    cursor = conn.cursor()

    # 0. Shops Table (Multi-tenant support)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT,
            phone TEXT,
            email TEXT,
            upi_id TEXT DEFAULT 'mistri@upi',
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Default Branch
    cursor.execute("""
        INSERT OR IGNORE INTO shops (id, name, address, phone, email, upi_id)
        VALUES (1, 'Mistri Electrical/Electronic Main Branch', 'Shop 4, Market Road, Sector 12', '+91-9800000001', 'main@mistri.com', 'mistri@upi')
    """)
    cursor.execute("""
        UPDATE shops SET name='Mistri Electrical/Electronic Main Branch' WHERE id=1 AND name LIKE '%Electrical/Electronics%'
    """)

    # 1. Users Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'customer',  -- customer | admin | staff
            avatar TEXT,
            shop_id INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (shop_id) REFERENCES shops(id)
        )
    """)

    # 2. Devices Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            device_type TEXT NOT NULL,  -- Fan | Cooler | Mixer/Grinder | Motor | Geyser | Pump | Mobile | Laptop | TV | Other
            brand TEXT NOT NULL,
            model TEXT NOT NULL,
            serial_number TEXT,
            FOREIGN KEY (customer_id) REFERENCES users(id)
        )
    """)

    # 3. Repair Jobs Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS repair_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repair_id TEXT UNIQUE NOT NULL,  -- eg. MIS-2024-0001
            customer_id INTEGER NOT NULL,
            device_id INTEGER NOT NULL,
            technician_id INTEGER,
            assigned_at DATETIME,
            assigned_by INTEGER,
            shop_id INTEGER DEFAULT 1,
            service_type TEXT DEFAULT 'Store Drop-off',  -- Store Drop-off | Home Pickup
            pickup_address TEXT,
            problem_description TEXT NOT NULL,
            image_path TEXT,
            status TEXT NOT NULL DEFAULT 'Requested',  -- Requested | Assigned | Diagnosing | Approved | Repairing | Ready | Delivered | Completed | Cancelled | On Hold | Rejected
            priority TEXT DEFAULT 'Normal',  -- Low | Normal | High | Urgent
            estimated_cost REAL,
            actual_cost REAL,
            technician_notes TEXT,
            parts_used TEXT,  -- JSON string
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at DATETIME,
            FOREIGN KEY (customer_id) REFERENCES users(id),
            FOREIGN KEY (device_id) REFERENCES devices(id),
            FOREIGN KEY (technician_id) REFERENCES users(id),
            FOREIGN KEY (assigned_by) REFERENCES users(id),
            FOREIGN KEY (shop_id) REFERENCES shops(id)
        )
    """)

    # 4. Repair Status History (Lifecycle Timeline Audit)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS repair_status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repair_job_id INTEGER NOT NULL,
            from_status TEXT,
            to_status TEXT NOT NULL,
            changed_by INTEGER,
            note TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (repair_job_id) REFERENCES repair_jobs(id) ON DELETE CASCADE,
            FOREIGN KEY (changed_by) REFERENCES users(id)
        )
    """)

    # 5. Repair Photos (Before / During / After Evidence)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS repair_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repair_job_id INTEGER NOT NULL,
            photo_stage TEXT NOT NULL,  -- before | during | after
            photo_url TEXT NOT NULL,
            caption TEXT,
            uploaded_by INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (repair_job_id) REFERENCES repair_jobs(id) ON DELETE CASCADE,
            FOREIGN KEY (uploaded_by) REFERENCES users(id)
        )
    """)

    # 6. Inventory Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_name TEXT NOT NULL,
            part_code TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL,  -- Screen | Battery | Motherboard | IC | Bearing | Capacitor | Coil | Misc
            compatible_devices TEXT,  -- JSON list of device types
            quantity INTEGER NOT NULL DEFAULT 0,
            unit_price REAL NOT NULL,
            reorder_level INTEGER DEFAULT 5,
            reorder_quantity INTEGER DEFAULT 10,
            supplier TEXT,
            shop_id INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (shop_id) REFERENCES shops(id)
        )
    """)

    # 7. Inventory Transactions (Stock IN / OUT Audit)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            transaction_type TEXT NOT NULL,  -- IN | OUT
            repair_job_id INTEGER,
            staff_id INTEGER,
            reason TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (part_id) REFERENCES inventory(id),
            FOREIGN KEY (repair_job_id) REFERENCES repair_jobs(id),
            FOREIGN KEY (staff_id) REFERENCES users(id)
        )
    """)

    # 8. Bills Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_number TEXT UNIQUE NOT NULL,
            repair_job_id INTEGER NOT NULL,
            customer_id INTEGER NOT NULL,
            shop_id INTEGER DEFAULT 1,
            labour_charge REAL DEFAULT 0,
            parts_cost REAL DEFAULT 0,
            discount REAL DEFAULT 0,
            tax REAL DEFAULT 0,
            total_amount REAL NOT NULL,
            payment_status TEXT DEFAULT 'Pending',  -- Pending | Paid | Failed | Refunded | Partially Paid
            payment_method TEXT DEFAULT 'Cash',
            transaction_id TEXT,
            upi_qr_url TEXT,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (repair_job_id) REFERENCES repair_jobs(id),
            FOREIGN KEY (customer_id) REFERENCES users(id),
            FOREIGN KEY (shop_id) REFERENCES shops(id)
        )
    """)

    # 9. Payments Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            payment_method TEXT DEFAULT 'Cash',  -- Cash | Card | UPI | Online
            transaction_id TEXT,
            status TEXT DEFAULT 'Confirmed',
            paid_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (bill_id) REFERENCES bills(id)
        )
    """)

    # 10. Warranties Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS warranties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repair_job_id INTEGER NOT NULL UNIQUE,
            customer_id INTEGER NOT NULL,
            duration_days INTEGER NOT NULL DEFAULT 90,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            covered_terms TEXT,
            status TEXT DEFAULT 'Active',  -- Active | Expired | Claimed
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (repair_job_id) REFERENCES repair_jobs(id),
            FOREIGN KEY (customer_id) REFERENCES users(id)
        )
    """)

    # 11. Warranty Claims Table (Customer Revisit Requests)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS warranty_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            warranty_id INTEGER NOT NULL,
            repair_job_id INTEGER NOT NULL,
            customer_id INTEGER NOT NULL,
            issue_description TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',  -- Pending | Approved | Rejected | Resolved
            admin_notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (warranty_id) REFERENCES warranties(id),
            FOREIGN KEY (repair_job_id) REFERENCES repair_jobs(id),
            FOREIGN KEY (customer_id) REFERENCES users(id)
        )
    """)

    # 12. Feedback Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repair_job_id INTEGER NOT NULL,
            customer_id INTEGER NOT NULL,
            technician_id INTEGER,
            rating INTEGER NOT NULL,  -- 1-5 overall service rating
            technician_rating INTEGER,  -- 1-5 specific technician rating
            comment TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (repair_job_id) REFERENCES repair_jobs(id),
            FOREIGN KEY (customer_id) REFERENCES users(id),
            FOREIGN KEY (technician_id) REFERENCES users(id)
        )
    """)

    # 13. Audit Logs Table (Enterprise System Compliance)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_name TEXT,
            user_role TEXT,
            action TEXT NOT NULL,
            entity TEXT NOT NULL,
            entity_id TEXT,
            details TEXT,
            ip_address TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 14. Notifications Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            repair_job_id INTEGER,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            channel TEXT DEFAULT 'in_app',  -- in_app | whatsapp | sms
            is_read INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # 15. Shop Products Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shop_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_id INTEGER DEFAULT 1,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT NOT NULL,  -- Plug | Wire | Mixer Pot | Switch | Other
            brand TEXT,
            size_variant TEXT,
            unit TEXT,
            price REAL NOT NULL,
            stock_qty INTEGER NOT NULL DEFAULT 0,
            image_url TEXT,
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (shop_id) REFERENCES shops(id)
        )
    """)

    # 16. Shop Orders Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shop_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT UNIQUE NOT NULL,
            customer_id INTEGER NOT NULL,
            shop_id INTEGER DEFAULT 1,
            items TEXT NOT NULL,  -- JSON string of items and quantities
            total_amount REAL NOT NULL,
            status TEXT DEFAULT 'Pending',  -- Pending | Confirmed | Shipped | Delivered | Cancelled
            delivery_address TEXT,
            payment_method TEXT DEFAULT 'Cash on Delivery',
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES users(id),
            FOREIGN KEY (shop_id) REFERENCES shops(id)
        )
    """)

    # 17. Staff Leaves Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS staff_leaves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            leave_date DATE NOT NULL,
            days INTEGER NOT NULL DEFAULT 1,
            reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',  -- Pending | Approved | Rejected | Cancelled
            applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            reviewed_by INTEGER,
            reviewed_at DATETIME,
            admin_notes TEXT,
            FOREIGN KEY (staff_id) REFERENCES users(id),
            FOREIGN KEY (reviewed_by) REFERENCES users(id)
        )
    """)

    # 18. Salary Audit Logs Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS salary_audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            old_salary REAL,
            new_salary REAL,
            changed_by INTEGER NOT NULL,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (staff_id) REFERENCES users(id),
            FOREIGN KEY (changed_by) REFERENCES users(id)
        )
    """)

    # 19. Support Tickets Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS support_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT UNIQUE NOT NULL,  -- e.g. SUP-2026-1025
            customer_id INTEGER NOT NULL,
            repair_job_id INTEGER,
            category TEXT NOT NULL,  -- Repair Issue | Payment Issue | Repair Status | Staff Issue | Invoice Issue | Account Issue | General Query
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Open',  -- Open | In Progress | Resolved | Closed
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES users(id),
            FOREIGN KEY (repair_job_id) REFERENCES repair_jobs(id)
        )
    """)

    # 20. Support Ticket Messages Table (Conversation Thread)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS support_ticket_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            sender_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ticket_id) REFERENCES support_tickets(id) ON DELETE CASCADE,
            FOREIGN KEY (sender_id) REFERENCES users(id)
        )
    """)

    # 21. Customer Special & Festival Offers Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customer_offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,  -- e.g. DIWALI20, FESTIVE100
            title TEXT NOT NULL,
            description TEXT,
            discount_type TEXT NOT NULL DEFAULT 'percentage',  -- percentage | flat
            discount_value REAL NOT NULL,
            min_bill_amount REAL DEFAULT 0,
            max_discount REAL,
            valid_until DATE,
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 22. Staff Bonuses Table (Performance & Festival Bonuses)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS staff_bonuses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            bonus_type TEXT NOT NULL,  -- Performance Bonus | Festival Bonus | Special Incentive
            reason TEXT NOT NULL,
            awarded_by INTEGER NOT NULL,
            awarded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (staff_id) REFERENCES users(id),
            FOREIGN KEY (awarded_by) REFERENCES users(id)
        )
    """)

    
    # 23. Per-Item Warranties Table (independent per repair item)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS repair_item_warranties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repair_job_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            device_type TEXT,
            warranty_type TEXT NOT NULL DEFAULT 'No Warranty',
            duration_days INTEGER DEFAULT 0,
            start_date DATE,
            end_date DATE,
            covered_terms TEXT DEFAULT 'Covers parts replaced and workmanship.',
            excluded_terms TEXT DEFAULT 'Physical damage, water damage, misuse, unauthorized repair excluded.',
            status TEXT DEFAULT 'Active',
            created_by INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (repair_job_id) REFERENCES repair_jobs(id) ON DELETE CASCADE,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    """)

    # 24. Offer Redemptions Table (per-customer usage tracking)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS offer_redemptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            offer_id INTEGER NOT NULL,
            customer_id INTEGER NOT NULL,
            bill_id INTEGER,
            discount_applied REAL NOT NULL,
            redeemed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (offer_id) REFERENCES customer_offers(id),
            FOREIGN KEY (customer_id) REFERENCES users(id),
            FOREIGN KEY (bill_id) REFERENCES bills(id)
        )
    """)

    # # 25. Database Indexes for High Query Performance
    indexes = [
        
        "CREATE INDEX IF NOT EXISTS idx_item_warranties_job ON repair_item_warranties(repair_job_id)",
        "CREATE INDEX IF NOT EXISTS idx_offer_redemptions_offer ON offer_redemptions(offer_id)",
        "CREATE INDEX IF NOT EXISTS idx_offer_redemptions_customer ON offer_redemptions(customer_id)",
"CREATE INDEX IF NOT EXISTS idx_repairs_id ON repair_jobs(repair_id)",
        "CREATE INDEX IF NOT EXISTS idx_repairs_customer ON repair_jobs(customer_id)",
        "CREATE INDEX IF NOT EXISTS idx_repairs_tech ON repair_jobs(technician_id)",
        "CREATE INDEX IF NOT EXISTS idx_repairs_status ON repair_jobs(status)",
        "CREATE INDEX IF NOT EXISTS idx_repairs_created ON repair_jobs(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_bills_job ON bills(repair_job_id)",
        "CREATE INDEX IF NOT EXISTS idx_bills_payment_status ON bills(payment_status)",
        "CREATE INDEX IF NOT EXISTS idx_history_job ON repair_status_history(repair_job_id)",
        "CREATE INDEX IF NOT EXISTS idx_inv_tx_part ON inventory_transactions(part_id)",
        "CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_warranties_job ON warranties(repair_job_id)",
        "CREATE INDEX IF NOT EXISTS idx_repairs_batch ON repair_jobs(repair_batch_id)",
        "CREATE INDEX IF NOT EXISTS idx_users_google ON users(google_id)",
        "CREATE INDEX IF NOT EXISTS idx_leaves_staff ON staff_leaves(staff_id)",
        "CREATE INDEX IF NOT EXISTS idx_tickets_customer ON support_tickets(customer_id)",
        "CREATE INDEX IF NOT EXISTS idx_tickets_status ON support_tickets(status)",
        "CREATE INDEX IF NOT EXISTS idx_bonuses_staff ON staff_bonuses(staff_id)",
        "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
        "CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone)",
        "CREATE INDEX IF NOT EXISTS idx_bills_number ON bills(bill_number)",
        "CREATE INDEX IF NOT EXISTS idx_warranties_customer ON warranties(customer_id)",
        "CREATE INDEX IF NOT EXISTS idx_inventory_category ON inventory(category)",
        "CREATE INDEX IF NOT EXISTS idx_inventory_code ON inventory(part_code)",
        "CREATE INDEX IF NOT EXISTS idx_payments_txn ON payments(transaction_id)",
        "CREATE INDEX IF NOT EXISTS idx_warranty_claims_warranty ON warranty_claims(warranty_id)",
        "CREATE INDEX IF NOT EXISTS idx_warranty_claims_customer ON warranty_claims(customer_id)",
    ]
    for idx_sql in indexes:
        try:
            cursor.execute(idx_sql)
        except Exception:
            pass

    # 24. Auto-migration for existing databases: add any missing columns safely
    alter_queries = [
        "ALTER TABLE users ADD COLUMN shop_id INTEGER DEFAULT 1",
        "ALTER TABLE repair_jobs ADD COLUMN shop_id INTEGER DEFAULT 1",
        "ALTER TABLE inventory ADD COLUMN shop_id INTEGER DEFAULT 1",
        "ALTER TABLE bills ADD COLUMN shop_id INTEGER DEFAULT 1",
        "ALTER TABLE bills ADD COLUMN is_void INTEGER DEFAULT 0",
        "ALTER TABLE bills ADD COLUMN is_cancelled INTEGER DEFAULT 0",
        "ALTER TABLE bills ADD COLUMN is_archived INTEGER DEFAULT 0",
        "ALTER TABLE bills ADD COLUMN void_reason TEXT",
        "ALTER TABLE bills ADD COLUMN action_by INTEGER REFERENCES users(id)",
        "ALTER TABLE bills ADD COLUMN action_at DATETIME",
        "ALTER TABLE warranty_claims ADD COLUMN rejection_reason TEXT",
        "ALTER TABLE repair_jobs ADD COLUMN assigned_at DATETIME",
        "ALTER TABLE repair_jobs ADD COLUMN assigned_by INTEGER REFERENCES users(id)",
        "ALTER TABLE repair_jobs ADD COLUMN service_type TEXT DEFAULT 'Store Drop-off'",
        "ALTER TABLE repair_jobs ADD COLUMN pickup_address TEXT",
        "ALTER TABLE inventory ADD COLUMN reorder_quantity INTEGER DEFAULT 10",
        "ALTER TABLE feedback ADD COLUMN technician_id INTEGER REFERENCES users(id)",
        "ALTER TABLE feedback ADD COLUMN technician_rating INTEGER",
        "ALTER TABLE payments ADD COLUMN status TEXT DEFAULT 'Confirmed'",
        "ALTER TABLE users ADD COLUMN google_id TEXT",
        "ALTER TABLE users ADD COLUMN auth_provider TEXT DEFAULT 'email'",
        "ALTER TABLE repair_jobs ADD COLUMN repair_batch_id TEXT",
        "ALTER TABLE repair_jobs ADD COLUMN video_path TEXT",
        "ALTER TABLE repair_jobs ADD COLUMN landmark TEXT",
        "ALTER TABLE repair_jobs ADD COLUMN pincode TEXT",
        # Staff salary & employment commitment columns
        "ALTER TABLE users ADD COLUMN monthly_salary REAL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN joining_date DATE",
        "ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1",
        "ALTER TABLE users ADD COLUMN salary_policy_days INTEGER DEFAULT 30",
        "ALTER TABLE users ADD COLUMN minimum_commitment_months INTEGER DEFAULT 6",
        "ALTER TABLE users ADD COLUMN resignation_status TEXT DEFAULT 'None'",
        "ALTER TABLE users ADD COLUMN resignation_notice_date DATE",
        "ALTER TABLE users ADD COLUMN resignation_last_date DATE",
        "ALTER TABLE users ADD COLUMN resignation_reason TEXT",
        "ALTER TABLE users ADD COLUMN termination_notice_date DATE",
        "ALTER TABLE users ADD COLUMN termination_effective_date DATE",
        # Repair rejection & acceptance columns
        "ALTER TABLE repair_jobs ADD COLUMN rejection_reason TEXT",
        "ALTER TABLE repair_jobs ADD COLUMN rejection_notes TEXT",
        "ALTER TABLE repair_jobs ADD COLUMN accepted_at DATETIME",
        # Payment collection & verification columns
        "ALTER TABLE payments ADD COLUMN collected_by INTEGER REFERENCES users(id)",
        "ALTER TABLE payments ADD COLUMN verified_by INTEGER REFERENCES users(id)",
        "ALTER TABLE payments ADD COLUMN verified_at DATETIME",
        "ALTER TABLE payments ADD COLUMN notes TEXT",
        # Bills offer discount columns
        "ALTER TABLE bills ADD COLUMN offer_code TEXT",
        "ALTER TABLE bills ADD COLUMN offer_discount REAL DEFAULT 0",
        "ALTER TABLE customer_offers ADD COLUMN target_customer_id INTEGER REFERENCES users(id)",
        "ALTER TABLE customer_offers ADD COLUMN valid_from DATE",
        # User address and location columns for profile completion
        "ALTER TABLE users ADD COLUMN address TEXT",
        "ALTER TABLE users ADD COLUMN landmark TEXT",
        "ALTER TABLE users ADD COLUMN pincode TEXT",
    
        "ALTER TABLE customer_offers ADD COLUMN usage_limit INTEGER",
        "ALTER TABLE customer_offers ADD COLUMN per_customer_limit INTEGER DEFAULT 1",
        "ALTER TABLE customer_offers ADD COLUMN usage_count INTEGER DEFAULT 0",
        "ALTER TABLE inventory ADD COLUMN brand TEXT",
        "ALTER TABLE inventory ADD COLUMN sku TEXT",
        "ALTER TABLE inventory ADD COLUMN purchase_price REAL",
        "ALTER TABLE inventory ADD COLUMN sell_price REAL",
        "ALTER TABLE inventory ADD COLUMN unit TEXT DEFAULT 'piece'",
        "ALTER TABLE inventory ADD COLUMN is_active INTEGER DEFAULT 1",
    ]
    for q in alter_queries:
        try:
            cursor.execute(q)
        except sqlite3.OperationalError:
            pass  # Column already exists

    # Default joining_date for existing staff
    try:
        cursor.execute("UPDATE users SET joining_date=DATE(created_at) WHERE role='staff' AND joining_date IS NULL")
        cursor.execute("UPDATE users SET monthly_salary=20000 WHERE email='raju@mistri.com' AND (monthly_salary IS NULL OR monthly_salary=0)")
        cursor.execute("UPDATE users SET monthly_salary=22000 WHERE email='priya@mistri.com' AND (monthly_salary IS NULL OR monthly_salary=0)")
    except Exception:
        pass

    # Migrate any legacy 'Received' status to 'Requested'
    try:
        cursor.execute("UPDATE repair_jobs SET status='Requested' WHERE status='Received'")
    except Exception:
        pass

    # Ensure demo customer arun@gmail.com is available alongside arun@example.com
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO users (name, email, phone, password_hash, role, auth_provider)
            SELECT name, 'arun@gmail.com', phone, password_hash, role, auth_provider
            FROM users WHERE email = 'arun@example.com'
        """)
    except Exception:
        pass
    # Seed initial festival offers
    try:
        offer_count = cursor.execute("SELECT COUNT(*) FROM customer_offers").fetchone()[0]
        if offer_count == 0:
            cursor.execute("""
                INSERT INTO customer_offers (code, title, description, discount_type, discount_value, min_bill_amount, valid_until, is_active)
                VALUES 
                ('FESTIVE10', 'Festival Special 10% OFF', 'Flat 10% discount on all repair bills for festival celebration!', 'percentage', 10, 200, DATE('now', '+60 days'), 1),
                ('WELCOME50', 'New Customer Flat ₹50 OFF', 'Flat ₹50 instant discount on your first appliance repair.', 'flat', 50, 300, DATE('now', '+90 days'), 1)
            """)
    except Exception:
        pass

    # Reseed electrical inventory if empty or requested
    try:
        inv_count = cursor.execute("SELECT COUNT(*) FROM inventory").fetchone()[0]
        if inv_count == 0:
            cursor.execute("PRAGMA foreign_keys = OFF")
            cursor.execute("DELETE FROM inventory_transactions")
            cursor.execute("DELETE FROM inventory")
            cursor.execute("PRAGMA foreign_keys = ON")
        electrical_items = [
            # Fan Parts
            ('Fan Capacitor 2.5μF', 'FAN-CAP-25', 'Fan Parts', 'Fan', 15, 45.0, 80.0, 5, 'piece', 'Shiv Electric Wholesale'),
            ('Fan Capacitor 3.5μF', 'FAN-CAP-35', 'Fan Parts', 'Fan', 12, 55.0, 95.0, 5, 'piece', 'Shiv Electric Wholesale'),
            ('Fan Bearing Set (Ceiling)', 'FAN-BRG-CEI', 'Fan Parts', 'Fan', 10, 35.0, 65.0, 5, 'piece', 'Shiv Electric Wholesale'),
            ('Fan Regulator (5-speed)', 'FAN-REG-5SP', 'Fan Parts', 'Fan', 8, 120.0, 220.0, 3, 'piece', 'Shiv Electric Wholesale'),
            ('Fan Motor Winding (Ceiling)', 'FAN-MTR-WIN', 'Fan Parts', 'Fan', 5, 350.0, 650.0, 2, 'piece', 'Ravi Motor Works'),
            # Cooler Parts
            ('Cooler Pump (submersible)', 'CLR-PMP-SUB', 'Cooler Parts', 'Cooler', 10, 180.0, 320.0, 3, 'piece', 'Ravi Motor Works'),
            ('Cooler Motor 1/20 HP', 'CLR-MTR-020', 'Cooler Parts', 'Cooler', 6, 420.0, 750.0, 2, 'piece', 'Ravi Motor Works'),
            ('Cooler Pad (Honeycomb)', 'CLR-PAD-HNY', 'Cooler Parts', 'Cooler', 20, 180.0, 320.0, 5, 'piece', 'Local Market'),
            ('Cooler Float Valve', 'CLR-FLT-VLV', 'Cooler Parts', 'Cooler', 15, 45.0, 85.0, 5, 'piece', 'Local Market'),
            # Mixer/Grinder Parts
            ('Mixer Motor Brushes Set', 'MXR-BRS-SET', 'Mixer Parts', 'Mixer/Grinder', 20, 30.0, 60.0, 5, 'set', 'Shiv Electric Wholesale'),
            ('Mixer Coupler (Universal)', 'MXR-CPL-UNI', 'Mixer Parts', 'Mixer/Grinder', 25, 25.0, 50.0, 8, 'piece', 'Local Market'),
            ('Mixer Switch Assembly', 'MXR-SWT-ASM', 'Mixer Parts', 'Mixer/Grinder', 15, 65.0, 120.0, 5, 'piece', 'Shiv Electric Wholesale'),
            # Motor Parts
            ('Motor Bearing 6202', 'MTR-BRG-202', 'Motor Parts', 'Motor', 20, 45.0, 90.0, 5, 'piece', 'Ravi Motor Works'),
            ('Motor Bearing 6204', 'MTR-BRG-204', 'Motor Parts', 'Motor', 15, 55.0, 110.0, 5, 'piece', 'Ravi Motor Works'),
            ('Motor Capacitor 25μF', 'MTR-CAP-25U', 'Motor Parts', 'Motor', 10, 85.0, 160.0, 3, 'piece', 'Shiv Electric Wholesale'),
            ('Motor Winding Wire (1kg)', 'MTR-WND-1KG', 'Motor Parts', 'Motor', 8, 650.0, 1100.0, 2, 'kg', 'Ravi Motor Works'),
            # Geyser Parts
            ('Geyser Heating Element 2kW', 'GYS-ELM-2KW', 'Geyser Parts', 'Geyser', 8, 280.0, 520.0, 3, 'piece', 'Shiv Electric Wholesale'),
            ('Geyser Thermostat', 'GYS-THR-STD', 'Geyser Parts', 'Geyser', 10, 120.0, 220.0, 3, 'piece', 'Shiv Electric Wholesale'),
            ('Geyser Safety Valve', 'GYS-SFV-STD', 'Geyser Parts', 'Geyser', 12, 85.0, 155.0, 4, 'piece', 'Local Market'),
            # Pump Parts
            ('Pump Impeller (Standard)', 'PMP-IMP-STD', 'Pump Parts', 'Pump', 8, 220.0, 400.0, 2, 'piece', 'Ravi Motor Works'),
            ('Pump Mechanical Seal', 'PMP-SL-MCH', 'Pump Parts', 'Pump', 10, 95.0, 175.0, 3, 'piece', 'Ravi Motor Works'),
            # Wires & Cables
            ('Copper Wire 1.5mm (10m roll)', 'WIR-CU-15M', 'Wires & Cables', 'General', 30, 85.0, 150.0, 10, 'roll', 'Aggarwal Cables'),
            ('Copper Wire 2.5mm (10m roll)', 'WIR-CU-25M', 'Wires & Cables', 'General', 25, 140.0, 240.0, 8, 'roll', 'Aggarwal Cables'),
            ('Three-Core Cable 1.5mm (5m)', 'CBL-3C-15M', 'Wires & Cables', 'General', 20, 120.0, 210.0, 5, 'roll', 'Aggarwal Cables'),
            # Switches & Sockets
            ('Modular Switch (1-way)', 'SWT-MOD-1W', 'Switches & Sockets', 'General', 50, 28.0, 55.0, 15, 'piece', 'Havells Distributor'),
            ('Modular Socket (3-pin)', 'SCK-MOD-3P', 'Switches & Sockets', 'General', 40, 45.0, 85.0, 10, 'piece', 'Havells Distributor'),
            ('Plug Top (3-pin 6A)', 'PLG-3P-06A', 'Switches & Sockets', 'General', 60, 18.0, 35.0, 20, 'piece', 'Local Market'),
            # Capacitors
            ('Electrolytic Capacitor 470μF', 'CAP-ELC-470', 'Capacitors', 'General', 100, 8.0, 18.0, 20, 'piece', 'Shiv Electric Wholesale'),
            ('Capacitor 100μF 25V', 'CAP-100U-25', 'Capacitors', 'General', 80, 6.0, 14.0, 20, 'piece', 'Shiv Electric Wholesale'),
            # MCB & Fuse
            ('MCB 6A Single Pole', 'MCB-06A-1P', 'MCB & Fuse', 'General', 20, 95.0, 175.0, 5, 'piece', 'Havells Distributor'),
            ('MCB 16A Single Pole', 'MCB-16A-1P', 'MCB & Fuse', 'General', 15, 110.0, 200.0, 5, 'piece', 'Havells Distributor'),
            ('Ceramic Fuse 5A', 'FUS-CER-05A', 'MCB & Fuse', 'General', 100, 5.0, 12.0, 20, 'piece', 'Local Market'),
            ('Ceramic Fuse 15A', 'FUS-CER-15A', 'MCB & Fuse', 'General', 80, 6.0, 14.0, 20, 'piece', 'Local Market'),
            # Relays & Connectors
            ('12V Relay Module (5A)', 'RLY-12V-05A', 'Relays', 'General', 25, 35.0, 68.0, 5, 'piece', 'Shiv Electric Wholesale'),
            ('Terminal Block Connector', 'CON-TRM-BLK', 'Connectors', 'General', 50, 15.0, 32.0, 10, 'piece', 'Shiv Electric Wholesale'),
            # LED Bulbs
            ('LED Bulb 9W (Warm White)', 'LED-09W-WRM', 'LED Bulbs', 'General', 30, 45.0, 90.0, 8, 'piece', 'Local Market'),
            ('LED Bulb 15W (Cool White)', 'LED-15W-CLW', 'LED Bulbs', 'General', 25, 65.0, 125.0, 5, 'piece', 'Local Market'),
            # Tape & Insulation
            ('PVC Insulation Tape (Black)', 'TAPE-PVC-BLK', 'Tape & Insulation', 'General', 100, 15.0, 30.0, 20, 'roll', 'Local Market'),
            ('PVC Insulation Tape (Red)', 'TAPE-PVC-RED', 'Tape & Insulation', 'General', 60, 15.0, 30.0, 10, 'roll', 'Local Market'),
            # Fasteners
            ('Screws Assorted Pack (100pcs)', 'SCR-AST-100', 'Fasteners', 'General', 30, 35.0, 65.0, 5, 'pack', 'Local Market'),
            ('Cable Ties (100pcs)', 'CBT-100PCS', 'Fasteners', 'General', 20, 40.0, 75.0, 5, 'pack', 'Local Market'),
        ]
        for item in electrical_items:
            name, code, cat, device, qty, purchase, sell, reorder, unit, supplier = item
            cursor.execute("""
                INSERT OR IGNORE INTO inventory 
                (part_name, part_code, category, compatible_devices, quantity, unit_price, 
                 purchase_price, sell_price, reorder_level, reorder_quantity, supplier, unit, is_active, shop_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1,1)
            """, (name, code, cat, device, qty, sell, purchase, sell, reorder, reorder*2, supplier, unit))
            cursor.execute("""
                INSERT INTO inventory_transactions (part_id, quantity, transaction_type, reason)
                VALUES ((SELECT id FROM inventory WHERE part_code=?), ?, 'IN', 'Initial electrical stock setup')
            """, (code, qty))
    except Exception as e:
        print(f'Inventory seed: {e}')

    conn.commit()
    conn.close()
    print("✅ Database initialized successfully with comprehensive enterprise schema")

if __name__ == "__main__":
    init_db()
