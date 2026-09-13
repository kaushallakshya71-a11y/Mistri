"""
Mistri Seed Data - Populates the database with demo users, inventory, and sample repairs
Domain: Electrical Appliance Repair (Fan, Cooler, Mixer, Motor, Geyser, Pump)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import get_db, init_db
import bcrypt as _bcrypt
from datetime import datetime, timedelta
import json
import string

def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def generate_repair_id(index):
    year = datetime.now().year
    return f"MIS-{year}-{str(index).zfill(4)}"

def generate_bill_number(index):
    year = datetime.now().year
    return f"BILL-{year}-{str(index).zfill(4)}"

def seed():
    init_db()
    conn = get_db()
    c = conn.cursor()

    # Clear existing data
    for table in ['payments','bills','notifications','repair_jobs','inventory','devices','users']:
        c.execute(f"DELETE FROM {table}")
    conn.commit()

    # --- USERS ---
    users = [
        ("Admin Owner", "admin@mistri.com", "9800000001", hash_password("Admin@123"), "admin"),
        ("Raju Technician", "raju@mistri.com", "9800000002", hash_password("Staff@123"), "staff"),
        ("Priya Singh", "priya@mistri.com", "9800000003", hash_password("Staff@123"), "staff"),
        ("Arun Kumar", "arun@example.com", "9900000001", hash_password("Customer@123"), "customer"),
        ("Meena Patel", "meena@example.com", "9900000002", hash_password("Customer@123"), "customer"),
        ("Vikram Sharma", "vikram@example.com", "9900000003", hash_password("Customer@123"), "customer"),
    ]
    for u in users:
        c.execute("INSERT INTO users (name, email, phone, password_hash, role) VALUES (?,?,?,?,?)", u)
    conn.commit()

    # Get IDs
    admin_id = c.execute("SELECT id FROM users WHERE role='admin'").fetchone()[0]
    staff_ids = [r[0] for r in c.execute("SELECT id FROM users WHERE role='staff'").fetchall()]
    customer_ids = [r[0] for r in c.execute("SELECT id FROM users WHERE role='customer'").fetchall()]

    # --- INVENTORY (Electrical Appliance Parts) ---
    parts = [
        # Fan Parts
        ("Fan Capacitor 2.5uF", "CAP-FAN25", "Capacitor", '["Fan"]', 25, 80, 10, "ElecParts Hub"),
        ("Fan Capacitor 4uF", "CAP-FAN40", "Capacitor", '["Fan"]', 20, 100, 10, "ElecParts Hub"),
        ("Ceiling Fan Motor Winding Kit", "WND-CFN1", "Winding", '["Fan"]', 10, 350, 5, "Motors India"),
        ("Fan Speed Regulator (5 Step)", "REG-FAN5", "Regulator", '["Fan"]', 15, 180, 8, "ElecParts Hub"),
        ("Fan Blade Set (3 Blades)", "BLD-FAN3", "Blade", '["Fan"]', 12, 250, 5, "ElecParts Hub"),
        # Cooler Parts
        ("Cooler Pump Motor 35W", "PMP-CLR1", "Pump", '["Cooler"]', 18, 320, 8, "CoolerParts Co"),
        ("Cooler Fan Motor 50W", "MTR-CLR1", "Motor", '["Cooler"]', 8, 550, 5, "CoolerParts Co"),
        ("Honeycomb Cooling Pad Set", "PAD-HNY1", "Pad", '["Cooler"]', 20, 280, 10, "CoolerParts Co"),
        # Mixer / Grinder Parts
        ("Mixer Carbon Brushes Pair", "BRS-MXR1", "Brush", '["Mixer/Grinder"]', 30, 60, 15, "ApplianceParts Pro"),
        ("Mixer Grinder Coupler", "CPL-MXR1", "Coupler", '["Mixer/Grinder"]', 35, 45, 15, "ApplianceParts Pro"),
        ("Mixer Motor 550W", "MTR-MXR1", "Motor", '["Mixer/Grinder"]', 6, 900, 5, "ApplianceParts Pro"),
        # Geyser Parts
        ("Geyser Heating Element 2000W", "HTR-GYZ1", "Element", '["Geyser"]', 10, 350, 5, "GeysrParts Store"),
        ("Geyser Thermostat", "THS-GYZ1", "Thermostat", '["Geyser"]', 12, 280, 5, "GeysrParts Store"),
        ("Geyser Pressure Relief Valve", "PRV-GYZ1", "Valve", '["Geyser"]', 15, 120, 8, "GeysrParts Store"),
        # Motor / Pump Parts
        ("Submersible Pump Capacitor 25uF", "CAP-PMP1", "Capacitor", '["Pump","Motor"]', 10, 200, 5, "PumpParts India"),
        ("Mechanical Seal Kit", "SEL-PMP1", "Seal", '["Pump"]', 8, 450, 5, "PumpParts India"),
    ]
    for p in parts:
        c.execute("""
            INSERT INTO inventory (part_name, part_code, category, compatible_devices, quantity, unit_price, reorder_level, supplier)
            VALUES (?,?,?,?,?,?,?,?)
        """, p)
    conn.commit()

    # --- DEVICES (Electrical Appliances) ---
    device_data = [
        (customer_ids[0], "Fan", "Crompton", "Aura 48 Inch"),
        (customer_ids[0], "Geyser", "Havells", "Instanio 25L"),
        (customer_ids[1], "Cooler", "Symphony", "Diet 35i"),
        (customer_ids[1], "Mixer/Grinder", "Bajaj", "GX-1 Mixer"),
        (customer_ids[2], "Motor", "Kirloskar", "Star 1HP Monoblock"),
        (customer_ids[2], "Pump", "Grundfos", "CM 3-5 Series"),
    ]
    for d in device_data:
        c.execute("INSERT INTO devices (customer_id, device_type, brand, model) VALUES (?,?,?,?)", d)
    conn.commit()
    device_ids = [r[0] for r in c.execute("SELECT id FROM devices").fetchall()]

    # --- REPAIR JOBS ---
    jobs = [
        (generate_repair_id(1), customer_ids[0], device_ids[0], staff_ids[0], "Fan not starting, makes humming sound – capacitor issue", "Received", 200, None),
        (generate_repair_id(2), customer_ids[0], device_ids[1], staff_ids[1], "Geyser not heating water, element may be fused", "Repairing", 500, 450),
        (generate_repair_id(3), customer_ids[1], device_ids[2], staff_ids[0], "Cooler motor stopped working, no air coming out", "Diagnosing", 700, None),
        (generate_repair_id(4), customer_ids[1], device_ids[3], staff_ids[1], "Mixer not starting, sparking from carbon brushes", "Completed", 150, 120),
        (generate_repair_id(5), customer_ids[2], device_ids[4], staff_ids[0], "Motor overheating and tripping after 10 minutes", "Delivered", 1200, 1100),
    ]
    for idx, j in enumerate(jobs):
        days_ago = len(jobs) - idx
        created = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
        c.execute("""
            INSERT INTO repair_jobs (repair_id, customer_id, device_id, technician_id, problem_description, status, estimated_cost, actual_cost, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (*j, created, created))
    conn.commit()

    # Get repair job IDs
    job_ids = [r[0] for r in c.execute("SELECT id FROM repair_jobs ORDER BY id").fetchall()]

    # --- BILLS for completed/delivered jobs ---
    bills_data = [
        (generate_bill_number(1), job_ids[3], customer_ids[1], 80, 60, 0, 8, 148, "Paid"),     # Mixer brushes
        (generate_bill_number(2), job_ids[4], customer_ids[2], 500, 550, 50, 60, 1060, "Paid"), # Motor winding
    ]
    for b in bills_data:
        c.execute("""
            INSERT INTO bills (bill_number, repair_job_id, customer_id, labour_charge, parts_cost, discount, tax, total_amount, payment_status)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, b)
    conn.commit()

    bill_ids = [r[0] for r in c.execute("SELECT id FROM bills ORDER BY id").fetchall()]
    # Payments
    c.execute("INSERT INTO payments (bill_id, amount, payment_method) VALUES (?,?,?)", (bill_ids[0], 148, "Cash"))
    c.execute("INSERT INTO payments (bill_id, amount, payment_method) VALUES (?,?,?)", (bill_ids[1], 1060, "UPI"))

    # --- NOTIFICATIONS ---
    notifications = [
        (customer_ids[0], job_ids[0], "Repair Received 🌀", f"Your fan repair {generate_repair_id(1)} has been received. We'll start diagnosis shortly."),
        (customer_ids[0], job_ids[1], "Repair in Progress 🔧", f"Your geyser repair {generate_repair_id(2)} is now in progress."),
        (customer_ids[1], job_ids[2], "Diagnosis Started 🔍", f"Our technician has started diagnosing your cooler motor issue."),
        (customer_ids[1], job_ids[3], "Repair Completed ✅", f"Your mixer repair {generate_repair_id(4)} is complete! Ready for pickup."),
        (customer_ids[2], job_ids[4], "Delivered 🎉", f"Your motor has been repaired and delivered. Thank you for choosing Mistri!"),
    ]
    for n in notifications:
        c.execute("INSERT INTO notifications (user_id, repair_job_id, title, message) VALUES (?,?,?,?)", n)

    conn.commit()
    conn.close()
    print("✅ Database seeded successfully with electrical appliance data!")
    print("\n📋 Demo Login Credentials:")
    print("  Admin:    admin@mistri.com    / Admin@123")
    print("  Staff 1:  raju@mistri.com     / Staff@123")
    print("  Staff 2:  priya@mistri.com    / Staff@123")
    print("  Customer: arun@example.com    / Customer@123")
    print("  Customer: meena@example.com   / Customer@123")

if __name__ == "__main__":
    seed()
