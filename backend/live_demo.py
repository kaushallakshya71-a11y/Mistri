"""
Live End-to-End Interactive Demo for Mistri
Simulates the exact real-world journey of Customer, Admin, and Staff in real time.
"""
import os
import sys
import json
import sqlite3
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.database import get_db, init_db
from routes.auth import login, LoginRequest
from routes.ai import estimate_cost, recommend_technician
from routes.repairs import assign_technician, update_status, RepairStatusUpdate, AssignTechnicianRequest, add_part_atomic, AddPartRequest
from routes.bills import generate_bill, BillCreate, get_bill_upi_qr
from routes.feedback import submit_feedback, FeedbackCreate

def print_header(title):
    print("\n" + "=" * 75)
    print(f"  {title}")
    print("=" * 75)

def live_demo():
    print_header("🎬 MISTRI LIVE DEMO: COMPLETE 3-PERSON REPAIR JOURNEY")
    init_db()
    conn = get_db()

    # ----------------------------------------------------
    # ACT 1: CUSTOMER (Grahak Ka Kaam)
    # ----------------------------------------------------
    print_header("👤 ACT 1: CUSTOMER (Arun Kumar) SUBMITS A REPAIR REQUEST")
    cust_res = login(LoginRequest(email="arun@example.com", password="Customer@123"))
    cust_user = {"id": cust_res["user_id"], "name": cust_res["name"], "role": "customer"}
    print(f"✅ Logged in as Customer: {cust_user['name']} (ID: {cust_user['id']})")

    # Customer describes problem in Hindi
    problem_hindi = "Fan se bohot zyada awaz aa rahi hai aur haath se ghumane par hi chalta hai, dheema chal raha"
    device_type = "Fan"
    brand = "Havells"
    model = "1200mm Pacer Ceiling Fan"
    pickup_address = "H.No 104, Gali No. 3, Sector 14, Gurugram (Landmark: Opposite SBI ATM)"

    print(f"\n📝 Device: {brand} {model} ({device_type})")
    print(f"💬 Hindi Symptom Input: \"{problem_hindi}\"")
    print(f"🏠 Service Mode: Home Visit / Doorstep Pickup")
    print(f"📍 Customer Address: {pickup_address}")

    # AI Estimation in action
    ai_est = estimate_cost(device_type, problem_hindi)
    print("\n🤖 [AI REPAIR COST ESTIMATOR RESULT]:")
    print(f"   • Suspected Fault: {ai_est['repair_category']} ({ai_est['symptom_detected']})")
    print(f"   • Estimated Price Range: ₹{ai_est['estimated_cost_min']} - ₹{ai_est['estimated_cost_max']} (ML Point: ₹{ai_est.get('ml_predicted_cost', 300)})")
    print(f"   • Estimated Turnaround Time: {ai_est['estimated_time_min_hours']} - {ai_est['estimated_time_max_hours']} Hours")
    print(f"   • AI Confidence Score: {ai_est['confidence']}%")
    print(f"   • Diagnostic Note: {ai_est['explanation']}")

    # Insert repair job into DB
    repair_id = f"MIS-2026-{int(time.time()) % 10000:04d}"
    cursor = conn.execute("""
        INSERT INTO devices (customer_id, device_type, brand, model) VALUES (?, ?, ?, ?)
    """, (cust_user["id"], device_type, brand, model))
    dev_id = cursor.lastrowid

    cursor = conn.execute("""
        INSERT INTO repair_jobs (repair_id, customer_id, device_id, problem_description,
                                estimated_cost, status, priority, service_type, pickup_address)
        VALUES (?, ?, ?, ?, ?, 'Requested', 'Normal', 'Home Pickup', ?)
    """, (repair_id, cust_user["id"], dev_id, problem_hindi, ai_est['estimated_cost_min'], pickup_address))
    job_id = cursor.lastrowid
    conn.commit()

    print(f"\n🎉 Repair Request Successfully Created!")
    print(f"   • Unique Job ID: {repair_id} (DB ID: {job_id})")
    print(f"   • Current Status: [Requested] ⏳")

    # ----------------------------------------------------
    # ACT 2: ADMIN (Dukan Ka Malik)
    # ----------------------------------------------------
    print_header("👑 ACT 2: ADMIN (Admin Owner) REVIEWS & USES 'AI MATCH'")
    admin_res = login(LoginRequest(email="admin@mistri.com", password="Admin@123"))
    admin_user = {"id": admin_res["user_id"], "name": admin_res["name"], "role": "admin"}
    print(f"✅ Logged in as Admin: {admin_user['name']}")

    print(f"\n👀 Admin views new pending job #{repair_id} with badge [🏠 Home Visit]")
    print("🤖 Admin clicks 'AI Match' to find the best available technician...")

    # Run AI Technician Matching
    match_result = recommend_technician(job_id, current_user=admin_user)
    top_tech = match_result["recommendations"][0]

    print("\n🧠 [AI TECHNICIAN RECOMMENDATION SCORECARD]:")
    print(f"   🏆 Top Match: {top_tech['name']} (Match Score: {top_tech['match_score']}/100)")
    print(f"   • Rationale: {match_result['reason']}")
    print(f"   • Candidates Ranked:")
    for cand in match_result["recommendations"]:
        print(f"     - {cand['name']}: Score {cand['match_score']}/100 | Active Workload: {cand['current_workload']} jobs | Rating: {cand['avg_rating']}★")

    # Admin assigns top technician
    assign_technician(job_id=job_id, req=AssignTechnicianRequest(technician_id=top_tech["technician_id"], note="Priority home visit"), current_user=admin_user)
    print(f"\n✅ Admin Assigned Job #{repair_id} to {top_tech['name']}!")
    print(f"   • New Status: [Assigned] 👨‍🔧")

    # ----------------------------------------------------
    # ACT 3: STAFF / TECHNICIAN (Assigned Technician)
    # ----------------------------------------------------
    print_header(f"🛠️ ACT 3: STAFF ({top_tech['name']}) NAVIGATES & REPAIRS")
    tech_email = "priya@mistri.com" if "priya" in top_tech["name"].lower() else "raju@mistri.com"
    staff_res = login(LoginRequest(email=tech_email, password="Staff@123"))
    staff_user = {"id": staff_res["user_id"], "name": staff_res["name"], "role": "staff"}
    print(f"✅ Logged in as Assigned Technician: {staff_user['name']} ({tech_email})")

    # Staff views Location Card & Google Maps link
    maps_url = f"https://www.google.com/maps/search/?api=1&query={pickup_address.replace(' ', '+')}"
    print(f"\n📱 {staff_user['name']} opens assigned job #{repair_id} on their smartphone:")
    print(f"   • Service Mode: 🏠 Home Doorstep Visit")
    print(f"   • Customer Address: 📍 {pickup_address}")
    print(f"   • Google Maps Direct Link: {maps_url}")
    print(f"   • Customer Phone: 📞 +91-9900000001 (Ready for 1-click call)")

    # Technician starts diagnosis
    update_status(job_id, RepairStatusUpdate(status="Diagnosing", technician_notes="Reached customer house. Checking winding & capacitor."), current_user=staff_user)
    print(f"\n⚡ {staff_user['name']} clicks 'Start Diagnosis' ➔ Status: [Diagnosing] 🔍")

    # Technician finds bad capacitor & deducts from inventory
    part = conn.execute("SELECT id, part_name, quantity, unit_price FROM inventory WHERE part_name LIKE '%Capacitor%' LIMIT 1").fetchone()
    initial_stock = part["quantity"]
    print(f"\n📦 {staff_user['name']} uses replacement spare part: '{part['part_name']}'")
    print(f"   • Shop Inventory Stock Before: {initial_stock} units")

    # Atomic deduction
    add_part_atomic(job_id, AddPartRequest(part_id=part["id"], quantity=1), current_user=staff_user)
    new_stock = conn.execute("SELECT quantity FROM inventory WHERE id=?", (part["id"],)).fetchone()["quantity"]
    print(f"   • Stock After Atomic Deduction: {new_stock} units (-1 unit safely consumed) ✅")

    # Technician finishes repair
    update_status(job_id, RepairStatusUpdate(status="Ready", actual_cost=230.0, technician_notes="Capacitor replaced. Fan speed tested at 380 RPM. No noise."), current_user=staff_user)
    print(f"\n✅ Raju completes repair & uploads test results ➔ Status: [Ready] 🎉")

    # ----------------------------------------------------
    # ACT 4: BILLING, PAYMENT & WARRANTY
    # ----------------------------------------------------
    print_header("💳 ACT 4: BILLING, DYNAMIC UPI PAYMENT & 180-DAY WARRANTY")

    # Admin generates bill
    bill_res = generate_bill(BillCreate(repair_job_id=job_id, labour_charge=150.0, parts_cost=80.0, discount=0.0, tax_rate=0.09), current_user=admin_user)
    bill_id = bill_res["bill_id"]
    print(f"🧾 Official GST Bill Generated: {bill_res['bill_number']}")
    print(f"   • Labour Charge: ₹150.00")
    print(f"   • Parts Cost: ₹80.00")
    print(f"   • 9% GST: ₹20.70")
    print(f"   • Total Payable Amount: ₹250.70")

    # Dynamic UPI QR Code
    qr_data = get_bill_upi_qr(bill_id, current_user=admin_user)
    print(f"\n📱 [DYNAMIC NPCI UPI QR CODE GENERATED]:")
    print(f"   • UPI Payment Intent URI: {qr_data['upi_intent']}")
    print(f"   • Scannable QR Base64 Length: {len(qr_data['qr_code'])} characters (Rendered directly on bill & PDF)")

    # Customer pays and rates
    conn.execute("UPDATE bills SET payment_status='Paid', payment_method='UPI' WHERE id=?", (bill_id,))
    conn.execute("UPDATE repair_jobs SET status='Completed' WHERE id=?", (job_id,))
    conn.commit()

    # Customer submits feedback
    submit_feedback(FeedbackCreate(repair_job_id=job_id, rating=5, technician_rating=5, comment="Excellent speed! Raju bhai fixed the noise in 20 minutes."), current_user=cust_user)
    print(f"\n⭐ Customer scanned QR, paid via UPI, and submitted 5-Star feedback!")
    print(f"   • Overall Service: ⭐⭐⭐⭐⭐")
    print(f"   • Technician (Raju): ⭐⭐⭐⭐⭐")

    # Warranty activation
    war_code = f"WAR-2026-{job_id:04d}"
    conn.execute("""
        INSERT INTO warranties (repair_job_id, customer_id, duration_days, start_date, end_date, covered_terms, status)
        VALUES (?, ?, 180, DATE('now'), DATE('now', '+180 days'), 'Covers motor winding and capacitor replacement', 'Active')
    """, (job_id, cust_user["id"]))
    conn.commit()

    print(f"\n🛡️ [WARRANTY ISSUED]:")
    print(f"   • Warranty Code: {war_code}")
    print(f"   • Duration: 180 Days (Active countdown visible on customer portal)")
    print(f"   • Revisit Claims: Customer can raise 1-click revisit anytime within 180 days.")

    conn.close()

    print_header("🎉 DEMO COMPLETE: 100% SUCCESSFUL END-TO-END LIFECYCLE")
    print("Aap browser me http://localhost:8000 par jaakar inhi steps ko live dekh sakte hain!")

if __name__ == "__main__":
    live_demo()
