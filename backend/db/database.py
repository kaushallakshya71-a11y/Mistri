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
        VALUES (1, 'Mistri Electronics Main Branch', 'Shop 4, Market Road, Sector 12', '+91-9800000001', 'main@mistri.com', 'mistri@upi')
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

    # 23. Database Indexes for High Query Performance
    indexes = [
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

    conn.commit()
    conn.close()
    print("✅ Database initialized successfully with comprehensive enterprise schema")

if __name__ == "__main__":
    init_db()
