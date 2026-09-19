"""
Mistri Reports & Smart Analytics Routes
Comprehensive analytics covering revenue trends, branch breakdowns, repair turnaround speed,
parts vs. labour profitability, and enterprise audit logs.
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from db.database import get_db
from middleware.auth import require_role
from utils.audit import log_audit_event
from datetime import datetime, timedelta
import io, csv

router = APIRouter(prefix="/api/reports", tags=["reports"])

@router.get("/analytics")
def get_smart_analytics(current_user: dict = Depends(require_role("admin"))):
    """
    Comprehensive business intelligence & analytics dashboard data:
    Revenue, profitability, repair turnaround, inventory burnout, and staff metrics.
    """
    conn = get_db()

    # 1. Total Financials (Profitability)
    fin = conn.execute("""
        SELECT
            COALESCE(SUM(total_amount), 0) as total_revenue,
            COALESCE(SUM(labour_charge), 0) as total_labour,
            COALESCE(SUM(parts_cost), 0) as total_parts_cost,
            COALESCE(SUM(discount), 0) as total_discounts,
            COALESCE(SUM(tax), 0) as total_tax
        FROM bills
        WHERE payment_status = 'Paid'
    """).fetchone()

    total_revenue = float(fin["total_revenue"])
    total_labour = float(fin["total_labour"])
    total_parts_cost = float(fin["total_parts_cost"])
    # Estimated profit = Labour charges + 25% margin on parts
    estimated_profit = round(total_labour + (total_parts_cost * 0.25), 2)

    # 2. Repairs Health & Turnaround
    total_repairs = conn.execute("SELECT COUNT(*) FROM repair_jobs").fetchone()[0]
    pending_repairs = conn.execute(
        "SELECT COUNT(*) FROM repair_jobs WHERE status NOT IN ('Completed', 'Delivered', 'Cancelled', 'Rejected')"
    ).fetchone()[0]
    completed_repairs = conn.execute(
        "SELECT COUNT(*) FROM repair_jobs WHERE status IN ('Completed', 'Delivered')"
    ).fetchone()[0]
    cancelled_repairs = conn.execute(
        "SELECT COUNT(*) FROM repair_jobs WHERE status IN ('Cancelled', 'Rejected')"
    ).fetchone()[0]

    # Average repair turnaround hours
    completed_times = conn.execute("""
        SELECT created_at, completed_at
        FROM repair_jobs
        WHERE completed_at IS NOT NULL AND status IN ('Completed', 'Delivered')
    """).fetchall()

    total_hours = 0
    valid_count = 0
    for ct in completed_times:
        try:
            t1 = datetime.strptime(ct["created_at"][:19], "%Y-%m-%d %H:%M:%S")
            t2 = datetime.strptime(ct["completed_at"][:19], "%Y-%m-%d %H:%M:%S")
            hours = (t2 - t1).total_seconds() / 3600.0
            if hours > 0:
                total_hours += hours
                valid_count += 1
        except Exception:
            pass
    avg_turnaround_hours = round(total_hours / valid_count, 1) if valid_count > 0 else 4.5

    # 3. Revenue by Branch (Multi-tenant)
    branch_revenue = conn.execute("""
        SELECT s.name as branch_name, COALESCE(SUM(b.total_amount), 0) as revenue
        FROM shops s
        LEFT JOIN bills b ON s.id = b.shop_id AND b.payment_status = 'Paid'
        GROUP BY s.id
    """).fetchall()

    # 4. Daily Revenue (last 14 days)
    daily = conn.execute("""
        SELECT DATE(paid_at) as day, SUM(amount) as revenue, COUNT(*) as tx_count
        FROM payments
        WHERE paid_at >= DATE('now', '-14 days')
        GROUP BY DATE(paid_at) ORDER BY day ASC
    """).fetchall()

    # 5. Monthly Revenue (last 12 months)
    monthly = conn.execute("""
        SELECT strftime('%Y-%m', paid_at) as month, SUM(amount) as revenue, COUNT(*) as tx_count
        FROM payments
        WHERE paid_at >= DATE('now', '-365 days')
        GROUP BY strftime('%Y-%m', paid_at) ORDER BY month ASC
    """).fetchall()

    # 6. Most Repaired Devices
    devices = conn.execute("""
        SELECT d.device_type, COUNT(*) as count, COALESCE(SUM(b.total_amount), 0) as revenue
        FROM repair_jobs rj
        JOIN devices d ON rj.device_id = d.id
        LEFT JOIN bills b ON rj.id = b.repair_job_id AND b.payment_status = 'Paid'
        GROUP BY d.device_type
        ORDER BY count DESC
    """).fetchall()

    # 7. Most-Used Spare Parts
    most_used_parts = conn.execute("""
        SELECT i.part_name, i.part_code, SUM(it.quantity) as total_used, i.unit_price
        FROM inventory_transactions it
        JOIN inventory i ON it.part_id = i.id
        WHERE it.transaction_type = 'OUT'
        GROUP BY it.part_id
        ORDER BY total_used DESC LIMIT 5
    """).fetchall()

    # 8. Staff Performance Scorecard
    staff_scores = conn.execute("""
        SELECT u.id, u.name,
               COUNT(rj.id) as jobs_assigned,
               SUM(CASE WHEN rj.status IN ('Completed','Delivered') THEN 1 ELSE 0 END) as jobs_completed,
               AVG(COALESCE(f.technician_rating, f.rating)) as avg_rating
        FROM users u
        LEFT JOIN repair_jobs rj ON u.id = rj.technician_id
        LEFT JOIN feedback f ON u.id = f.technician_id
        WHERE u.role = 'staff'
        GROUP BY u.id
    """).fetchall()

    conn.close()

    return {
        "financials": {
            "total_revenue": total_revenue,
            "total_labour": total_labour,
            "total_parts_cost": total_parts_cost,
            "estimated_profit": estimated_profit,
            "total_discounts": float(fin["total_discounts"]),
            "total_tax": float(fin["total_tax"])
        },
        "repairs_summary": {
            "total": total_repairs,
            "pending": pending_repairs,
            "completed": completed_repairs,
            "cancelled": cancelled_repairs,
            "avg_turnaround_hours": avg_turnaround_hours
        },
        "branch_revenue": [dict(b) for b in branch_revenue],
        "daily_revenue": [dict(d) for d in daily],
        "monthly_revenue": [dict(m) for m in monthly],
        "device_breakdown": [dict(d) for d in devices],
        "most_used_parts": [dict(p) for p in most_used_parts],
        "staff_scorecard": [dict(s) for s in staff_scores]
    }

@router.get("/audit-logs")
def get_audit_logs(
    action: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(require_role("admin"))
):
    """Retrieve immutable audit trail records."""
    if current_user.get("role") != "admin":
        raise HTTPException(403, "Access denied. Admin role required.")
    conn = get_db()
    if action:
        rows = conn.execute(
            "SELECT * FROM audit_logs WHERE action=? ORDER BY created_at DESC LIMIT ?",
            (action, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@router.get("/revenue")
def legacy_revenue_report(period: str = "monthly", current_user: dict = Depends(require_role("admin"))):
    """Legacy endpoint preserved for backward compatibility."""
    conn = get_db()
    if period == "daily":
        rows = conn.execute("""
            SELECT DATE(paid_at) as period, SUM(amount) as revenue, COUNT(*) as transactions
            FROM payments
            WHERE paid_at >= DATE('now', '-30 days')
            GROUP BY DATE(paid_at) ORDER BY period
        """).fetchall()
    else:
        rows = conn.execute("""
            SELECT strftime('%Y-%m', paid_at) as period, SUM(amount) as revenue, COUNT(*) as transactions
            FROM payments
            WHERE paid_at >= DATE('now', '-365 days')
            GROUP BY strftime('%Y-%m', paid_at) ORDER BY period
        """).fetchall()

    device_breakdown = conn.execute("""
        SELECT d.device_type, COUNT(*) as count, COALESCE(SUM(b.total_amount),0) as revenue
        FROM repair_jobs rj JOIN devices d ON rj.device_id=d.id
        LEFT JOIN bills b ON rj.id=b.repair_job_id AND b.payment_status='Paid'
        GROUP BY d.device_type
    """).fetchall()

    top_tech = conn.execute("""
        SELECT u.name, COUNT(rj.id) as jobs_completed, COALESCE(SUM(b.total_amount),0) as revenue
        FROM repair_jobs rj JOIN users u ON rj.technician_id=u.id
        LEFT JOIN bills b ON rj.id=b.repair_job_id AND b.payment_status='Paid'
        WHERE rj.status IN ('Completed','Delivered')
        GROUP BY u.id ORDER BY jobs_completed DESC LIMIT 5
    """).fetchall()

    conn.close()
    return {
        "revenue_over_time": [dict(r) for r in rows],
        "device_breakdown": [dict(r) for r in device_breakdown],
        "top_technicians": [dict(r) for r in top_tech],
    }

@router.get("/export/csv")
def export_csv(type: str = "repairs", current_user: dict = Depends(require_role("admin"))):
    """Export repairs or payments data as CSV."""
    conn = get_db()
    output = io.StringIO()

    if type == "repairs":
        rows = conn.execute("""
            SELECT rj.repair_id, c.name as customer, c.phone, d.device_type, d.brand, d.model,
                   rj.problem_description, rj.status, rj.estimated_cost, rj.actual_cost,
                   t.name as technician, rj.created_at, rj.completed_at
            FROM repair_jobs rj JOIN users c ON rj.customer_id=c.id
            JOIN devices d ON rj.device_id=d.id
            LEFT JOIN users t ON rj.technician_id=t.id
            ORDER BY rj.created_at DESC
        """).fetchall()
        writer = csv.writer(output)
        writer.writerow(["Repair ID", "Customer", "Phone", "Device", "Brand", "Model",
                         "Problem", "Status", "Estimated Cost", "Actual Cost", "Technician",
                         "Created At", "Completed At"])
        for r in rows:
            writer.writerow(list(r))
        filename = f"mistri_repairs_{datetime.now().strftime('%Y%m%d')}.csv"
    else:
        rows = conn.execute("""
            SELECT p.id, b.bill_number, u.name as customer, p.amount, p.payment_method,
                   p.transaction_id, p.paid_at
            FROM payments p JOIN bills b ON p.bill_id=b.id
            JOIN users u ON b.customer_id=u.id
            ORDER BY p.paid_at DESC
        """).fetchall()
        writer = csv.writer(output)
        writer.writerow(["Payment ID", "Bill Number", "Customer", "Amount", "Method", "Txn ID", "Paid At"])
        for r in rows:
            writer.writerow(list(r))
        filename = f"mistri_payments_{datetime.now().strftime('%Y%m%d')}.csv"

    conn.close()
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# ----------------------------------------------------
# Database Backup & Disaster Recovery Endpoints
# ----------------------------------------------------

class RestoreBackupRequest(BaseModel):
    filename: str

@router.post("/backup")
def trigger_backup(current_user: dict = Depends(require_role("admin"))):
    """Admin triggers an immediate SQLite online database backup."""
    from utils.backup import create_database_backup
    try:
        res = create_database_backup()
        log_audit_event(
            user=current_user,
            action="DATABASE_BACKUP_CREATED",
            entity="system",
            entity_id=0,
            details={"filename": res["filename"], "size_kb": res["size_kb"]}
        )
        return {"message": "Database backup created successfully", "backup": res}
    except Exception as e:
        raise HTTPException(500, f"Database backup failed: {str(e)}")

@router.get("/backups")
def get_backups(current_user: dict = Depends(require_role("admin"))):
    """Admin lists all database backup snapshots."""
    from utils.backup import list_database_backups
    return {"backups": list_database_backups()}

@router.post("/restore")
def restore_backup(req: RestoreBackupRequest, current_user: dict = Depends(require_role("admin"))):
    """Admin restores the database from a specified backup snapshot."""
    from utils.backup import restore_database_backup
    try:
        res = restore_database_backup(req.filename)
        log_audit_event(
            user=current_user,
            action="DATABASE_RESTORED",
            entity="system",
            entity_id=0,
            details={"restored_from": req.filename, "safety_snapshot": res.get("safety_snapshot")}
        )
        return res
    except ValueError as ve:
        raise HTTPException(400, str(ve))
    except FileNotFoundError as fe:
        raise HTTPException(404, str(fe))
    except Exception as e:
        raise HTTPException(500, f"Database restore failed: {str(e)}")
