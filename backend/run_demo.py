"""
Mistri System Live Execution and Verification Demo
Demonstrates all functional modules, database queries, and AI capabilities.
"""
import os
import sys
import json
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.database import get_db, init_db
from routes.auth import login, LoginRequest
from routes.ai import estimate_cost, recommend_technician
from routes.inventory import get_reorder_alerts
from routes.reports import get_smart_analytics
from routes.bills import get_bill_upi_qr
from routes.warranties import list_warranties

def run_demo():
    print("=" * 70)
    print("🚀 MISTRI - SMART ELECTRONICS REPAIR MANAGEMENT SYSTEM")
    print("=" * 70)

    # 1. Database & Health Status
    print("\n[1] 🏥 SYSTEM HEALTH & DATABASE VERIFICATION")
    init_db()
    conn = get_db()
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    table_names = [t["name"] for t in tables]
    print(f"  • Total Database Tables: {len(table_names)}")
    print(f"  • Key Tables: {', '.join(table_names[:10])}...")
    user_count = conn.execute("SELECT count(*) as c FROM users").fetchone()["c"]
    repairs_count = conn.execute("SELECT count(*) as c FROM repair_jobs").fetchone()["c"]
    inventory_count = conn.execute("SELECT count(*) as c FROM inventory").fetchone()["c"]
    print(f"  • Active Records: {user_count} Users, {repairs_count} Repair Jobs, {inventory_count} Inventory Parts")

    # 2. Authentication Test
    print("\n[2] 🔐 AUTHENTICATION & ACCESS CONTROL (DEMO ACCOUNTS)")
    admin_login = login(LoginRequest(email="admin@mistri.com", password="Admin@123"))
    staff_login = login(LoginRequest(email="raju@mistri.com", password="Staff@123"))
    cust_login = login(LoginRequest(email="arun@example.com", password="Customer@123"))
    print(f"  ✅ Admin Login Success: {admin_login['name']} ({admin_login['role']}) -> Token Issued")
    print(f"  ✅ Staff Login Success: {staff_login['name']} ({staff_login['role']}) -> Token Issued")
    print(f"  ✅ Customer Login Success: {cust_login['name']} ({cust_login['role']}) -> Token Issued")

    admin_user = {"id": admin_login["user_id"], "name": admin_login["name"], "role": admin_login["role"]}

    # 3. AI Cost Estimator (English & Hinglish)
    print("\n[3] 🤖 EXPLAINABLE AI REPAIR COST ESTIMATOR")
    queries = [
        ("Cooler", "Heavy vibration and very slow fan speed, awaz aa rahi hai"),
        ("Fan", "Capacitor weak hai, haath se ghumana pad raha hai, dheema chal raha"),
        ("Motor", "Motor se dhuan nikla aur paani nahi utha raha hai, jal gaya shayad"),
        ("Mixer/Grinder", "Blade stuck ho gayi hai aur spark nikal raha hai")
    ]
    for device, desc in queries:
        res = estimate_cost(device_type=device, problem=desc, brand_tier="mid")
        print(f"  • Device: {device}")
        print(f"    Symptom Input: \"{desc}\"")
        print(f"    Suspected Fault: {res['repair_category']} (Diagnostic: {res['symptom_detected']})")
        print(f"    Estimated Cost: ₹{res['estimated_cost_min']} - ₹{res['estimated_cost_max']} (ML Point: ₹{res.get('ml_predicted_cost', 'N/A')})")
        print(f"    Turnaround Time: {res['estimated_time_min_hours']}-{res['estimated_time_max_hours']} hrs | Confidence: {res['confidence']}%")
        print(f"    Explanation: {res['explanation']}")
        print()

    # 4. AI Technician Recommendation
    print("[4] 🧠 SMART AI TECHNICIAN MATCHING & WORKLOAD BALANCING")
    job = conn.execute("""
        SELECT rj.id, d.device_type, rj.problem_description
        FROM repair_jobs rj JOIN devices d ON rj.device_id = d.id
        WHERE rj.status = 'Requested' LIMIT 1
    """).fetchone()
    if not job:
        job = conn.execute("""
            SELECT rj.id, d.device_type, rj.problem_description
            FROM repair_jobs rj JOIN devices d ON rj.device_id = d.id
            LIMIT 1
        """).fetchone()
    if job:
        rec = recommend_technician(job_id=job["id"], current_user=admin_user)
        top = rec["recommendations"][0]
        print(f"  • Job ID: #{job['id']} ({job['device_type']} - \"{job['problem_description']}\")")
        print(f"  • Recommended Technician: 🏆 {top['name']}")
        print(f"  • Match Score: {top['match_score']}/100")
        print(f"  • Rationale: {rec['reason']}")
        print("  • All Technician Rankings:")
        for t in rec['recommendations']:
            print(f"    - {t['name']}: Score {t['match_score']}/100 | Active Workload: {t['current_workload']} jobs | Avg Rating: {t['avg_rating']}★ | Device Exp: {t['completed_same_device']} jobs")

    # 5. Low-Stock Reorder Alerts
    print("\n[5] 📦 INVENTORY REORDER ALERTS & RE-STOCK TRACKING")
    alerts = get_reorder_alerts(current_user=admin_user)
    print(f"  • Total Low-Stock Alerts: {len(alerts)}")
    for a in alerts[:4]:
        print(f"    ⚠️ Part: {a['part_name']} ({a['category']}) | Current Stock: {a['quantity']} {a['unit']} | Reorder Level: {a['reorder_level']} | Suggested Order: {a['suggested_reorder_qty']}")

    # 6. Business Intelligence & Profitability Analytics
    print("\n[6] 📊 BUSINESS INTELLIGENCE & REPAIR SHOP ANALYTICS")
    analytics = get_smart_analytics(current_user=admin_user)
    fin = analytics["financials"]
    rep = analytics["repairs_summary"]
    print(f"  • Total Revenue: ₹{fin['total_revenue']:,.2f}")
    print(f"  • Parts Cost: ₹{fin['total_parts_cost']:,.2f} | Labour: ₹{fin['total_labour']:,.2f}")
    print(f"  • Gross Profit: ₹{fin['estimated_profit']:,.2f}")
    print(f"  • Average Turnaround Time: {rep['avg_turnaround_hours']} hours")
    print(f"  • Completed Repairs: {rep['completed']} | Active / Pending: {rep['pending']}")
    print("  • Top Replacement Parts Used:")
    for p in analytics["most_used_parts"][:3]:
        print(f"    - {p['part_name']} ({p['part_code']}): {p['total_used']} units used @ ₹{p['unit_price']}/unit")

    # 7. Dynamic UPI QR Generation
    print("\n[7] 💳 DYNAMIC UPI PAYMENT QR CODE")
    bill = conn.execute("SELECT id, total_amount, payment_status FROM bills LIMIT 1").fetchone()
    if bill:
        qr_info = get_bill_upi_qr(bill_id=bill["id"], current_user=admin_user)
        print(f"  • Bill #{bill['id']} ({qr_info['bill_number']}) Amount: ₹{qr_info['total_amount']}")
        print(f"  • Payment Status: {qr_info['payment_status']}")
        print(f"  • UPI Payment URI: {qr_info['upi_intent']}")
        print(f"  • Base64 QR Image String: {qr_info['qr_code'][:60]}... (Total {len(qr_info['qr_code'])} chars)")

    # 8. Warranties & Claims
    print("\n[8] 🛡️ WARRANTY & REVISIT CLAIMS")
    warranties = list_warranties(current_user=admin_user)
    print(f"  • Total Active Warranties: {len(warranties)}")
    for w in warranties[:2]:
        print(f"    - Code: {w['warranty_code']} | Device: {w['device_type']} ({w['customer_name']}) | Days Left: {w['days_remaining']} | Status: {w['status']}")

    conn.close()

    print("\n" + "=" * 70)
    print("🌐 MISTRI APP IS LIVE & READY TO USE")
    print("  • Web App URL:       http://localhost:8000")
    print("  • API Documentation: http://localhost:8000/api/docs")
    print("  • Admin Login:       admin@mistri.com / Admin@123")
    print("  • Staff Login:       raju@mistri.com / Staff@123")
    print("  • Customer Login:    arun@example.com / Customer@123")
    print("=" * 70)

if __name__ == "__main__":
    run_demo()
