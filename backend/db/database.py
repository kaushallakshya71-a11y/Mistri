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

    # 17. Database Indexes for High Query Performance
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
    ]
    for idx_sql in indexes:
        try:
            cursor.execute(idx_sql)
        except Exception:
            pass

    # 18. Auto-migration for existing databases: add any missing columns safely
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
    ]
    for q in alter_queries:
        try:
            cursor.execute(q)
        except sqlite3.OperationalError:
            pass  # Column already exists

    # Migrate any legacy 'Received' status to 'Requested'
    try:
        cursor.execute("UPDATE repair_jobs SET status='Requested' WHERE status='Received'")
    except Exception:
        pass

    conn.commit()
    conn.close()
    print("✅ Database initialized successfully with comprehensive enterprise schema")

if __name__ == "__main__":
    init_db()
