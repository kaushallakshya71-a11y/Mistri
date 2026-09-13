"""
Mistri Warranty Management Routes
Issuance, live remaining day calculations, customer warranty claims, and revisit requests.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from db.database import get_db
from middleware.auth import get_current_user, require_role
from utils.audit import log_audit_event
from datetime import datetime, date, timedelta

router = APIRouter(prefix="/api/warranties", tags=["warranties"])

class WarrantyCreateRequest(BaseModel):
    repair_job_id: int
    duration_days: int = 90
    covered_terms: Optional[str] = "Covers parts replaced and workmanship. Physical water/electrical surge damage excluded."

class WarrantyClaimRequest(BaseModel):
    repair_job_id: int
    issue_description: str

class ClaimStatusUpdate(BaseModel):
    status: str  # Approved | Rejected | Resolved
    admin_notes: Optional[str] = None

@router.post("/create")
def create_warranty(req: WarrantyCreateRequest, current_user: dict = Depends(require_role("admin", "staff"))):
    """Issue a warranty for a completed repair job."""
    conn = get_db()
    job = conn.execute("SELECT * FROM repair_jobs WHERE id=?", (req.repair_job_id,)).fetchone()
    if not job:
        conn.close()
        raise HTTPException(404, "Repair job not found")

    if job["status"] not in ("Completed", "Delivered", "Ready"):
        conn.close()
        raise HTTPException(400, "Warranty can only be issued for completed or ready repairs.")

    existing = conn.execute("SELECT id FROM warranties WHERE repair_job_id=?", (req.repair_job_id,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(400, "Warranty has already been issued for this repair.")

    start_dt = date.today()
    end_dt = start_dt + timedelta(days=req.duration_days)

    cursor = conn.execute("""
        INSERT INTO warranties (repair_job_id, customer_id, duration_days, start_date, end_date, covered_terms, status)
        VALUES (?, ?, ?, ?, ?, ?, 'Active')
    """, (req.repair_job_id, job["customer_id"], req.duration_days, start_dt.isoformat(), end_dt.isoformat(), req.covered_terms))

    w_id = cursor.lastrowid

    # In-app notification to customer
    conn.execute("""
        INSERT INTO notifications (user_id, repair_job_id, title, message)
        VALUES (?, ?, 'Warranty Active', ?)
    """, (job["customer_id"], req.repair_job_id, f"Your repair now includes a {req.duration_days}-day warranty valid until {end_dt.strftime('%d %b %Y')}."))

    conn.commit()
    conn.close()

    log_audit_event(
        user=current_user,
        action="WARRANTY_CREATED",
        entity="warranties",
        entity_id=w_id,
        details={"repair_id": job["repair_id"], "duration_days": req.duration_days, "end_date": end_dt.isoformat()}
    )

    return {
        "message": f"{req.duration_days}-day warranty issued successfully!",
        "warranty_id": w_id,
        "warranty_code": f"WAR-{w_id:04d}",
        "duration_days": req.duration_days,
        "start_date": start_dt.isoformat(),
        "end_date": end_dt.isoformat()
    }


@router.get("/repair/{job_id}")
def get_repair_warranty(job_id: int, current_user: dict = Depends(get_current_user)):
    """Retrieve warranty status and live remaining days for a specific repair."""
    conn = get_db()
    job = conn.execute("SELECT customer_id FROM repair_jobs WHERE id=?", (job_id,)).fetchone()
    if not job:
        conn.close()
        raise HTTPException(404, "Repair not found")

    if current_user["role"] == "customer" and job["customer_id"] != current_user["id"]:
        conn.close()
        raise HTTPException(403, "Access denied")

    warranty = conn.execute("SELECT * FROM warranties WHERE repair_job_id=?", (job_id,)).fetchone()
    conn.close()

    if not warranty:
        return {"has_warranty": False, "message": "No warranty associated with this repair."}

    w_dict = dict(warranty)
    end_date = datetime.strptime(w_dict["end_date"], "%Y-%m-%d").date()
    today = date.today()
    days_remaining = (end_date - today).days

    is_active = (days_remaining >= 0 and w_dict["status"] == "Active")
    status_label = f"Warranty Active – {days_remaining} days remaining" if is_active else "Warranty Expired"

    return {
        "has_warranty": True,
        "is_active": is_active,
        "status_label": status_label,
        "days_remaining": max(0, days_remaining),
        "duration_days": w_dict["duration_days"],
        "start_date": w_dict["start_date"],
        "end_date": w_dict["end_date"],
        "covered_terms": w_dict["covered_terms"],
        "warranty_id": w_dict["id"]
    }

@router.post("/claim")
def submit_warranty_claim(req: WarrantyClaimRequest, current_user: dict = Depends(get_current_user)):
    """Customer files a revisit/warranty claim."""
    conn = get_db()
    warranty = conn.execute("""
        SELECT w.*, rj.repair_id
        FROM warranties w
        JOIN repair_jobs rj ON w.repair_job_id = rj.id
        WHERE w.repair_job_id = ?
    """, (req.repair_job_id,)).fetchone()

    if not warranty:
        conn.close()
        raise HTTPException(404, "No active warranty found for this repair.")

    if current_user["role"] == "customer" and warranty["customer_id"] != current_user["id"]:
        conn.close()
        raise HTTPException(403, "Access denied.")

    end_date = datetime.strptime(warranty["end_date"], "%Y-%m-%d").date()
    if date.today() > end_date:
        conn.close()
        raise HTTPException(400, "Warranty for this repair has already expired.")

    cursor = conn.execute("""
        INSERT INTO warranty_claims (warranty_id, repair_job_id, customer_id, issue_description, status)
        VALUES (?, ?, ?, ?, 'Pending')
    """, (warranty["id"], req.repair_job_id, current_user["id"], req.issue_description))

    claim_id = cursor.lastrowid

    # In-app notification to user
    conn.execute("""
        INSERT INTO notifications (user_id, repair_job_id, title, message)
        VALUES (?, ?, 'Warranty Claim Submitted', 'We have received your warranty revisit request. Our team will contact you shortly.')
    """, (current_user["id"], req.repair_job_id))

    conn.commit()
    conn.close()

    log_audit_event(
        user=current_user,
        action="WARRANTY_CLAIM_SUBMITTED",
        entity="warranty_claims",
        entity_id=claim_id,
        details={"repair_id": warranty["repair_id"], "issue": req.issue_description}
    )

    return {"message": "Warranty claim submitted successfully! We will prioritize your revisit.", "claim_id": claim_id, "status": "Pending"}

@router.get("/list")
def list_warranties(current_user: dict = Depends(require_role("admin", "staff"))):
    """List all warranties with days remaining."""
    conn = get_db()
    rows = conn.execute("""
        SELECT w.*, rj.repair_id, d.brand, d.model, d.device_type, u.name as customer_name, u.phone as customer_phone
        FROM warranties w
        JOIN repair_jobs rj ON w.repair_job_id = rj.id
        JOIN devices d ON rj.device_id = d.id
        JOIN users u ON w.customer_id = u.id
        ORDER BY w.created_at DESC
    """).fetchall()
    conn.close()

    result = []
    today = date.today()
    for r in rows:
        d = dict(r)
        d["warranty_code"] = f"WAR-{d['id']:04d}"
        try:
            end_dt = datetime.strptime(d["end_date"], "%Y-%m-%d").date()
            d["days_remaining"] = max(0, (end_dt - today).days)
        except Exception:
            d["days_remaining"] = 0
        result.append(d)
    return result


@router.get("/claims")
def list_warranty_claims(current_user: dict = Depends(require_role("admin", "staff"))):
    """List customer warranty claims."""
    conn = get_db()
    claims = conn.execute("""
        SELECT wc.*, rj.repair_id, d.brand, d.model, u.name as customer_name, u.phone as customer_phone,
               w.end_date, w.duration_days
        FROM warranty_claims wc
        JOIN repair_jobs rj ON wc.repair_job_id = rj.id
        JOIN devices d ON rj.device_id = d.id
        JOIN users u ON wc.customer_id = u.id
        JOIN warranties w ON wc.warranty_id = w.id
        ORDER BY wc.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(c) for c in claims]

@router.put("/claims/{claim_id}")
def update_claim_status(claim_id: int, req: ClaimStatusUpdate, current_user: dict = Depends(require_role("admin"))):
    """Admin updates status of a warranty claim (Approved, Rejected, Resolved)."""
    conn = get_db()
    claim = conn.execute("SELECT * FROM warranty_claims WHERE id=?", (claim_id,)).fetchone()
    if not claim:
        conn.close()
        raise HTTPException(404, "Claim not found")

    conn.execute("""
        UPDATE warranty_claims
        SET status=?, admin_notes=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (req.status, req.admin_notes, claim_id))

    # Notify customer
    conn.execute("""
        INSERT INTO notifications (user_id, repair_job_id, title, message)
        VALUES (?, ?, 'Warranty Claim Update', ?)
    """, (claim["customer_id"], claim["repair_job_id"], f"Your warranty claim status is now: {req.status}."))

    conn.commit()
    conn.close()

    log_audit_event(
        user=current_user,
        action="WARRANTY_CLAIM_UPDATED",
        entity="warranty_claims",
        entity_id=claim_id,
        details={"status": req.status, "notes": req.admin_notes}
    )

    return {
        "message": f"Claim status updated to {req.status}",
        "claim_id": claim_id,
        "status": req.status
    }
