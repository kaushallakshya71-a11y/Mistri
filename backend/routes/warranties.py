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
    """Customer files a revisit/warranty claim. Prevents duplicate active claims."""
    if not req.issue_description or len(req.issue_description.strip()) < 5:
        raise HTTPException(400, "Please provide a detailed issue description (minimum 5 characters).")

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
        raise HTTPException(403, "Access denied. You can only file claims for your own warranties.")

    end_date = datetime.strptime(warranty["end_date"], "%Y-%m-%d").date()
    if date.today() > end_date:
        conn.close()
        raise HTTPException(400, "Warranty for this repair has already expired.")

    # Prevent duplicate pending/open claims
    existing_open = conn.execute("""
        SELECT id, status FROM warranty_claims
        WHERE warranty_id = ? AND status IN ('Pending', 'Under Review', 'In Progress')
    """, (warranty["id"],)).fetchone()
    if existing_open:
        conn.close()
        raise HTTPException(400, f"A claim (#{existing_open['id']}) for this warranty is already {existing_open['status']}. Please await resolution.")

    cursor = conn.execute("""
        INSERT INTO warranty_claims (warranty_id, repair_job_id, customer_id, issue_description, status)
        VALUES (?, ?, ?, ?, 'Pending')
    """, (warranty["id"], req.repair_job_id, current_user["id"], req.issue_description.strip()))

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
    """Admin updates status of a warranty claim (Approved, Rejected, Resolved). Rejection strictly requires reason."""
    status = req.status.strip().capitalize()
    if status not in ("Approved", "Rejected", "Resolved", "In progress"):
        raise HTTPException(400, "Status must be one of: Approved, Rejected, Resolved, In Progress.")

    if status == "Rejected":
        rejection_reason = req.admin_notes.strip() if req.admin_notes else ""
        if len(rejection_reason) < 5:
            raise HTTPException(400, "A clear rejection reason (minimum 5 characters) is required when rejecting a warranty claim.")
    else:
        rejection_reason = None

    conn = get_db()
    claim = conn.execute("SELECT * FROM warranty_claims WHERE id=?", (claim_id,)).fetchone()
    if not claim:
        conn.close()
        raise HTTPException(404, "Claim not found")

    conn.execute("""
        UPDATE warranty_claims
        SET status=?, admin_notes=?, rejection_reason=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (status, req.admin_notes, rejection_reason, claim_id))

    # Notify customer
    notification_msg = f"Your warranty claim status has been updated to: {status}."
    if status == "Rejected":
        notification_msg += f" Reason: {rejection_reason}"
    conn.execute("""
        INSERT INTO notifications (user_id, repair_job_id, title, message)
        VALUES (?, ?, 'Warranty Claim Update', ?)
    """, (claim["customer_id"], claim["repair_job_id"], notification_msg))

    conn.commit()
    conn.close()

    log_audit_event(
        user=current_user,
        action=f"WARRANTY_CLAIM_{status.upper()}",
        entity="warranty_claims",
        entity_id=claim_id,
        details={"status": status, "notes": req.admin_notes, "rejection_reason": rejection_reason}
    )

    return {
        "message": f"Claim status updated to {status}",
        "claim_id": claim_id,
        "status": status,
        "rejection_reason": rejection_reason
    }

# ─── PER-ITEM WARRANTY ENDPOINTS ─────────────────────────────────────────────

class ItemWarrantyCreateRequest(BaseModel):
    repair_job_id: int
    item_name: str
    device_type: Optional[str] = None
    warranty_type: str = "No Warranty"  # No Warranty | 7 Days | 15 Days | 30 Days | 3 Months | 6 Months | 1 Year | Custom
    duration_days: int = 0
    covered_terms: Optional[str] = "Covers parts replaced and workmanship."
    excluded_terms: Optional[str] = "Physical damage, water damage, misuse, unauthorized repair excluded."

class ItemWarrantyClaimRequest(BaseModel):
    item_warranty_id: int
    issue_description: str

@router.post("/item")
def create_item_warranty(req: ItemWarrantyCreateRequest, current_user: dict = Depends(require_role("admin", "staff"))):
    """Create/update individual item warranty for a repair."""
    conn = get_db()
    job = conn.execute("SELECT * FROM repair_jobs WHERE id=?", (req.repair_job_id,)).fetchone()
    if not job:
        conn.close()
        raise HTTPException(404, "Repair job not found")

    # Calculate dates
    if req.warranty_type == "No Warranty" or req.duration_days == 0:
        start_dt = None
        end_dt = None
        duration = 0
        wtype = "No Warranty"
    else:
        start_dt = date.today()
        end_dt = start_dt + timedelta(days=req.duration_days)
        duration = req.duration_days
        wtype = req.warranty_type

    # Check if item warranty already exists for this item name + job
    existing = conn.execute(
        "SELECT id FROM repair_item_warranties WHERE repair_job_id=? AND item_name=?",
        (req.repair_job_id, req.item_name)
    ).fetchone()

    if existing:
        conn.execute("""
            UPDATE repair_item_warranties 
            SET warranty_type=?, duration_days=?, start_date=?, end_date=?,
                covered_terms=?, excluded_terms=?, status='Active'
            WHERE id=?
        """, (wtype, duration, start_dt.isoformat() if start_dt else None,
               end_dt.isoformat() if end_dt else None,
               req.covered_terms, req.excluded_terms, existing["id"]))
        w_id = existing["id"]
    else:
        cursor = conn.execute("""
            INSERT INTO repair_item_warranties 
            (repair_job_id, item_name, device_type, warranty_type, duration_days,
             start_date, end_date, covered_terms, excluded_terms, status, created_by)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (req.repair_job_id, req.item_name, req.device_type, wtype, duration,
               start_dt.isoformat() if start_dt else None,
               end_dt.isoformat() if end_dt else None,
               req.covered_terms, req.excluded_terms, 'Active', current_user["id"]))
        w_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return {
        "message": f"Item warranty set: {req.item_name} → {wtype}",
        "warranty_id": w_id,
        "item_name": req.item_name,
        "warranty_type": wtype,
        "duration_days": duration,
        "start_date": start_dt.isoformat() if start_dt else None,
        "end_date": end_dt.isoformat() if end_dt else None
    }

@router.get("/items/{job_id}")
def get_item_warranties(job_id: int, current_user: dict = Depends(get_current_user)):
    """Get all per-item warranties for a specific repair job."""
    conn = get_db()
    job = conn.execute("SELECT customer_id FROM repair_jobs WHERE id=?", (job_id,)).fetchone()
    if not job:
        conn.close()
        raise HTTPException(404, "Repair not found")
    if current_user["role"] == "customer" and job["customer_id"] != current_user["id"]:
        conn.close()
        raise HTTPException(403, "Access denied")

    items = conn.execute(
        "SELECT * FROM repair_item_warranties WHERE repair_job_id=? ORDER BY created_at",
        (job_id,)
    ).fetchall()
    conn.close()

    result = []
    today = date.today()
    for item in items:
        d = dict(item)
        if d.get('end_date') and d['warranty_type'] != 'No Warranty':
            end_dt = datetime.strptime(d['end_date'], "%Y-%m-%d").date()
            d['days_remaining'] = max(0, (end_dt - today).days)
            d['is_active'] = (end_dt >= today and d.get('status') == 'Active')
        else:
            d['days_remaining'] = 0
            d['is_active'] = False
        result.append(d)
    return result

@router.put("/item/{warranty_id}")
def update_item_warranty(warranty_id: int, req: ItemWarrantyCreateRequest, 
                         current_user: dict = Depends(require_role("admin"))):
    """Admin updates an existing per-item warranty."""
    conn = get_db()
    if req.warranty_type == "No Warranty" or req.duration_days == 0:
        start_dt, end_dt, duration, wtype = None, None, 0, "No Warranty"
    else:
        start_dt = date.today()
        end_dt = start_dt + timedelta(days=req.duration_days)
        duration, wtype = req.duration_days, req.warranty_type

    conn.execute("""
        UPDATE repair_item_warranties 
        SET warranty_type=?, duration_days=?, start_date=?, end_date=?,
            covered_terms=?, excluded_terms=?, status='Active'
        WHERE id=?
    """, (wtype, duration,
           start_dt.isoformat() if start_dt else None,
           end_dt.isoformat() if end_dt else None,
           req.covered_terms, req.excluded_terms, warranty_id))
    conn.commit()
    conn.close()
    return {"message": "Item warranty updated"}

@router.post("/item-claim")
def submit_item_warranty_claim(req: ItemWarrantyClaimRequest, current_user: dict = Depends(get_current_user)):
    """Submit warranty claim for a specific repair item."""
    if not req.issue_description or len(req.issue_description.strip()) < 5:
        raise HTTPException(400, "Please provide a detailed issue description (minimum 5 characters).")

    conn = get_db()
    iw = conn.execute("SELECT * FROM repair_item_warranties WHERE id=?", (req.item_warranty_id,)).fetchone()
    if not iw:
        conn.close()
        raise HTTPException(404, "Item warranty not found")
    if iw['warranty_type'] == 'No Warranty':
        conn.close()
        raise HTTPException(400, f"No warranty applies to '{iw['item_name']}'. Cannot file a claim.")
    if iw.get('end_date'):
        end_dt = datetime.strptime(iw['end_date'], "%Y-%m-%d").date()
        if date.today() > end_dt:
            conn.close()
            raise HTTPException(400, f"Warranty for '{iw['item_name']}' expired on {iw['end_date']}. Claim not allowed.")

    job = conn.execute("SELECT customer_id, repair_id FROM repair_jobs WHERE id=?", (iw['repair_job_id'],)).fetchone()
    if current_user['role'] == 'customer' and job['customer_id'] != current_user['id']:
        conn.close()
        raise HTTPException(403, "Access denied. You can only file claims for your own repairs.")

    existing_open = conn.execute("""
        SELECT id, status FROM warranty_claims
        WHERE warranty_id = ? AND repair_job_id = ? AND status IN ('Pending', 'Under Review', 'In Progress')
    """, (req.item_warranty_id, iw['repair_job_id'])).fetchone()
    if existing_open:
        conn.close()
        raise HTTPException(400, f"A claim for this item is already {existing_open['status']}.")

    cursor = conn.execute("""
        INSERT INTO warranty_claims (warranty_id, repair_job_id, customer_id, issue_description, status)
        VALUES (?,?,?,?, 'Pending')
    """, (req.item_warranty_id, iw['repair_job_id'], current_user['id'], req.issue_description.strip()))
    claim_id = cursor.lastrowid
    conn.execute("""
        INSERT INTO notifications (user_id, repair_job_id, title, message)
        VALUES (?,?,'Warranty Claim Submitted',?)
    """, (current_user['id'], iw['repair_job_id'],
           f"Warranty claim submitted for '{iw['item_name']}'. Our team will contact you shortly."))
    conn.commit()
    conn.close()
    return {"message": "Warranty claim submitted!", "claim_id": claim_id, "item_name": iw['item_name']}
