"""
Mistri Repair Jobs Routes - Full CRUD, Lifecycle Status Management, Technician Assignment,
Atomic Inventory Deduction, Staged Photo Evidence, Multi-criteria Search & Pagination.
"""
from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Form, Query
from pydantic import BaseModel
from typing import Optional, List
from db.database import get_db
from middleware.auth import get_current_user, require_role
from utils.messaging import dispatch_repair_status_alert
from utils.audit import log_audit_event
from datetime import datetime
import json, uuid, os, math

router = APIRouter(prefix="/api/repairs", tags=["repairs"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_VIDEO_EXTENSIONS = {"mp4", "mov", "avi", "mkv", "webm", "3gp"}
MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50MB for videos
import re
INDIAN_PINCODE_PATTERN = re.compile(r'^[1-9][0-9]{5}$')  # 6-digit Indian pincode

def validate_pincode(pincode: str) -> None:
    """Validate 6-digit Indian pincode."""
    if not pincode:
        return
    pincode = pincode.strip()
    if not INDIAN_PINCODE_PATTERN.match(pincode):
        raise HTTPException(
            400,
            f"Invalid pincode '{pincode}'. Pincode must be exactly 6 digits and cannot start with 0 (e.g. 208001). "
            "Please enter a valid Indian pincode."
        )

def validate_address(address: str, field_name: str = "Address") -> None:
    """Validate that address is meaningful."""
    if not address or not address.strip():
        raise HTTPException(400, f"{field_name} cannot be empty. Please enter a valid address.")
    if len(address.strip()) < 10:
        raise HTTPException(400, f"{field_name} is too short. Please enter a complete address (min 10 characters).")
    if len(address.strip()) > 500:
        raise HTTPException(400, f"{field_name} is too long. Please keep it under 500 characters.")

# Extended Professional Repair Lifecycle
STATUS_FLOW = [
    "Requested", "Assigned", "Diagnosing", "Approved", "Repairing", "Ready", "Completed", "Delivered"
]
EXCEPTION_STATUSES = ["Cancelled", "On Hold", "Rejected"]
ALL_VALID_STATUSES = set(STATUS_FLOW + EXCEPTION_STATUSES + ["Received"])  # Support legacy "Received"

VALID_STATUS_TRANSITIONS = {
    "Requested": {"Assigned", "Diagnosing", "Cancelled", "Rejected"},
    "Received": {"Assigned", "Diagnosing", "Cancelled", "Rejected"},
    "Assigned": {"Diagnosing", "On Hold", "Cancelled", "Rejected"},
    "Diagnosing": {"Approved", "On Hold", "Cancelled", "Rejected"},
    "Approved": {"Repairing", "On Hold", "Cancelled"},
    "Repairing": {"Ready", "On Hold", "Cancelled"},
    "Ready": {"Completed", "Delivered", "On Hold"},
    "Completed": {"Delivered", "Ready"},
    "Delivered": {"Completed"},
    "On Hold": {"Assigned", "Diagnosing", "Approved", "Repairing", "Ready", "Cancelled"},
    "Cancelled": set(),
    "Rejected": set()
}

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB limit

def validate_file_magic_bytes(content: bytes, ext: str) -> bool:
    """Validate file magic bytes to prevent spoofed/executable uploads disguised as images/videos."""
    if not content or len(content) < 4:
        return False
    ext = ext.lower()
    if ext in ("jpg", "jpeg"):
        return content.startswith(b'\xff\xd8\xff')
    if ext == "png":
        return content.startswith(b'\x89PNG\r\n\x1a\n')
    if ext == "webp":
        return len(content) >= 12 and content.startswith(b'RIFF') and content[8:12] == b'WEBP'
    if ext in ("mp4", "mov"):
        return len(content) >= 12 and (b'ftyp' in content[:16] or b'moov' in content[:16] or b'wide' in content[:16] or b'mdat' in content[:16])
    if ext in ("webm", "mkv"):
        return content.startswith(b'\x1a\x45\xdf\xa3')
    if ext == "avi":
        return len(content) >= 12 and content.startswith(b'RIFF') and content[8:12] == b'AVI '
    if ext == "3gp":
        return len(content) >= 12 and b'ftyp' in content[:16]
    return True

def generate_repair_id(conn):
    year = datetime.now().year
    count = conn.execute("SELECT COUNT(*) FROM repair_jobs").fetchone()[0] + 1
    return f"MIS-{year}-{str(count).zfill(4)}"

# ---- Request Models ----
class RepairStatusUpdate(BaseModel):
    status: str
    technician_id: Optional[int] = None
    priority: Optional[str] = None
    actual_cost: Optional[float] = None
    technician_notes: Optional[str] = None
    note: Optional[str] = None

class AssignTechnicianRequest(BaseModel):
    technician_id: int
    note: Optional[str] = None

class RejectRepairRequest(BaseModel):
    reason: str  # Required part unavailable | Location/area issue | Staff unavailable | Workload issue | Incorrect device/problem | Other
    notes: Optional[str] = None

class ReassignTechnicianRequest(BaseModel):
    new_technician_id: int
    reason: Optional[str] = None

class AddPartRequest(BaseModel):
    part_id: int
    quantity: int = 1

class PartsUpdate(BaseModel):
    parts_used: list  # [{part_id, part_name, quantity, unit_price}]

# ----------------------------------------------------
# 1. Submit New Repair
# ----------------------------------------------------
@router.post("/submit")
async def submit_repair(
    device_type: str = Form(...),
    brand: str = Form(...),
    model: str = Form(...),
    problem_description: str = Form(...),
    estimated_cost: float = Form(0),
    service_type: str = Form("Store Drop-off"),
    pickup_address: Optional[str] = Form(None),
    landmark: Optional[str] = Form(None),
    pincode: Optional[str] = Form(None),
    repair_batch_id: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    video: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user)
):
    """Customer or admin submits a new repair request with validated image uploads."""
    # Normalize service_type
    s_type = "Home Pickup" if "home" in service_type.lower() or "pickup" in service_type.lower() else "Store Drop-off"
    
    # Validation
    if s_type == "Home Pickup":
        validate_address(pickup_address, "pickup_address")
        if pincode:
            validate_pincode(pincode)

    conn = get_db()

    # Create/get device
    device = conn.execute(
        "SELECT id FROM devices WHERE customer_id=? AND device_type=? AND brand=? AND model=?",
        (current_user["id"], device_type, brand, model)
    ).fetchone()

    if device:
        device_id = device["id"]
    else:
        cursor = conn.execute(
            "INSERT INTO devices (customer_id, device_type, brand, model) VALUES (?,?,?,?)",
            (current_user["id"], device_type, brand, model)
        )
        device_id = cursor.lastrowid

    # Handle initial image upload safely
    image_path = None
    if image and image.filename:
        filename_parts = image.filename.rsplit(".", 1)
        ext = filename_parts[-1].lower() if len(filename_parts) > 1 else ""
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            conn.close()
            raise HTTPException(400, f"Unsupported file extension '{ext}'. Allowed: JPG, PNG, WEBP.")
        
        file_bytes = await image.read()
        if len(file_bytes) > MAX_FILE_SIZE:
            conn.close()
            raise HTTPException(400, "Image size exceeds maximum limit of 5MB.")
        if not validate_file_magic_bytes(file_bytes, ext):
            conn.close()
            raise HTTPException(400, f"File content does not match image extension '{ext}' (spoofed or invalid file format).")
            
        safe_filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(UPLOAD_DIR, safe_filename)
        with open(filepath, "wb") as f:
            f.write(file_bytes)
        image_path = f"/uploads/{safe_filename}"

    # Handle video upload
    video_path = None
    if video and video.filename:
        filename_parts = video.filename.rsplit(".", 1)
        ext = filename_parts[-1].lower() if len(filename_parts) > 1 else ""
        if ext not in ALLOWED_VIDEO_EXTENSIONS:
            conn.close()
            raise HTTPException(400, f"Unsupported video extension '{ext}'. Allowed: MP4, MOV, AVI, MKV, WEBM, 3GP.")
        
        file_bytes = await video.read()
        if len(file_bytes) > MAX_VIDEO_SIZE:
            conn.close()
            raise HTTPException(400, "Video size exceeds maximum limit of 50MB.")
        if not validate_file_magic_bytes(file_bytes, ext):
            conn.close()
            raise HTTPException(400, f"File content does not match video extension '{ext}' (spoofed or invalid file format).")
            
        safe_filename = f"vid_{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(UPLOAD_DIR, safe_filename)
        with open(filepath, "wb") as f:
            f.write(file_bytes)
        video_path = f"/uploads/{safe_filename}"

    repair_id = generate_repair_id(conn)

    cursor = conn.execute("""
        INSERT INTO repair_jobs (repair_id, customer_id, device_id, problem_description,
                                image_path, video_path, estimated_cost, status, priority, shop_id,
                                service_type, pickup_address, landmark, pincode, repair_batch_id)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (repair_id, current_user["id"], device_id, problem_description,
          image_path, video_path, estimated_cost, "Requested", "Normal", current_user.get("shop_id", 1),
          s_type, pickup_address, landmark, pincode, repair_batch_id))

    job_db_id = cursor.lastrowid

    # Record initial lifecycle history
    conn.execute("""
        INSERT INTO repair_status_history (repair_job_id, from_status, to_status, changed_by, note)
        VALUES (?, ?, ?, ?, ?)
    """, (job_db_id, None, "Requested", current_user["id"], "Initial repair request submitted"))

    # If an initial photo was uploaded, record in repair_photos as 'before'
    if image_path:
        conn.execute("""
            INSERT INTO repair_photos (repair_job_id, photo_stage, photo_url, caption, uploaded_by)
            VALUES (?, 'before', ?, 'Device condition at request submission', ?)
        """, (job_db_id, image_path, current_user["id"]))

    # In-app notification
    conn.execute(
        "INSERT INTO notifications (user_id, repair_job_id, title, message) VALUES (?,?,?,?)",
        (current_user["id"], job_db_id, "Repair Request Received",
         f"Your {brand} {model} has been submitted. Tracking ID: {repair_id}")
    )

    conn.commit()
    conn.close()

    # Log audit event safely
    try:
        log_audit_event(
            user=current_user,
            action="REPAIR_CREATED",
            entity="repair_jobs",
            entity_id=job_db_id,
            details={"repair_id": repair_id, "device": f"{brand} {model}", "estimated_cost": estimated_cost}
        )
    except Exception as e:
        pass

    # Trigger Automated WhatsApp / SMS dispatch alert safely
    try:
        dispatch_repair_status_alert(
            customer_id=current_user["id"],
            customer_name=current_user.get("name", "Valued Customer"),
            customer_phone=current_user.get("phone"),
            repair_id=repair_id,
            device_name=f"{brand} {model}",
            status="Requested",
            total_amount=estimated_cost
        )
    except Exception as e:
        pass

    return {
        "id": job_db_id,
        "repair_id": repair_id,
        "status": "Requested",
        "message": "Repair submitted successfully"
    }

# ----------------------------------------------------
# 2. List Repairs (Role-based)
# ----------------------------------------------------
@router.get("/")
def list_repairs(current_user: dict = Depends(get_current_user)):
    """Role-based repair job listing."""
    conn = get_db()
    role = current_user["role"]

    if role == "customer":
        jobs = conn.execute("""
            SELECT rj.*, d.device_type, d.brand, d.model,
                   u.name as technician_name
            FROM repair_jobs rj
            JOIN devices d ON rj.device_id = d.id
            LEFT JOIN users u ON rj.technician_id = u.id
            WHERE rj.customer_id = ?
            ORDER BY rj.created_at DESC
        """, (current_user["id"],)).fetchall()
    elif role == "staff":
        jobs = conn.execute("""
            SELECT rj.*, d.device_type, d.brand, d.model,
                   c.name as customer_name, c.phone as customer_phone
            FROM repair_jobs rj
            JOIN devices d ON rj.device_id = d.id
            JOIN users c ON rj.customer_id = c.id
            WHERE rj.technician_id = ?
            ORDER BY rj.created_at DESC
        """, (current_user["id"],)).fetchall()
    else:  # admin
        jobs = conn.execute("""
            SELECT rj.*, d.device_type, d.brand, d.model,
                   c.name as customer_name, c.phone as customer_phone,
                   t.name as technician_name
            FROM repair_jobs rj
            JOIN devices d ON rj.device_id = d.id
            JOIN users c ON rj.customer_id = c.id
            LEFT JOIN users t ON rj.technician_id = t.id
            ORDER BY rj.created_at DESC
        """).fetchall()

    conn.close()
    return [dict(j) for j in jobs]

# ----------------------------------------------------
# 3. Multi-criteria Search & Pagination
# ----------------------------------------------------
@router.get("/search")
def search_repairs(
    q: Optional[str] = None,
    status: Optional[str] = None,
    device_type: Optional[str] = None,
    technician_id: Optional[int] = None,
    payment_status: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Advanced search & filter with pagination."""
    conn = get_db()
    offset = (page - 1) * limit
    params = []
    where_clauses = []

    # Role protection
    if current_user["role"] == "customer":
        where_clauses.append("rj.customer_id = ?")
        params.append(current_user["id"])
    elif current_user["role"] == "staff":
        where_clauses.append("rj.technician_id = ?")
        params.append(current_user["id"])

    if q:
        query_pattern = f"%{q.strip()}%"
        where_clauses.append("""(
            rj.repair_id LIKE ? OR
            c.name LIKE ? OR
            c.phone LIKE ? OR
            d.brand LIKE ? OR
            d.model LIKE ? OR
            rj.problem_description LIKE ?
        )""")
        params.extend([query_pattern] * 6)

    if status:
        where_clauses.append("rj.status = ?")
        params.append(status)

    if device_type:
        where_clauses.append("d.device_type = ?")
        params.append(device_type)

    if technician_id:
        where_clauses.append("rj.technician_id = ?")
        params.append(technician_id)

    if payment_status:
        where_clauses.append("b.payment_status = ?")
        params.append(payment_status)

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    # Count total
    count_sql = f"""
        SELECT COUNT(DISTINCT rj.id)
        FROM repair_jobs rj
        JOIN devices d ON rj.device_id = d.id
        JOIN users c ON rj.customer_id = c.id
        LEFT JOIN bills b ON rj.id = b.repair_job_id
        {where_sql}
    """
    total = conn.execute(count_sql, params).fetchone()[0]

    # Fetch page
    data_sql = f"""
        SELECT rj.*, d.device_type, d.brand, d.model,
               c.name as customer_name, c.phone as customer_phone,
               t.name as technician_name,
               b.payment_status, b.total_amount as billed_amount
        FROM repair_jobs rj
        JOIN devices d ON rj.device_id = d.id
        JOIN users c ON rj.customer_id = c.id
        LEFT JOIN users t ON rj.technician_id = t.id
        LEFT JOIN bills b ON rj.id = b.repair_job_id
        {where_sql}
        ORDER BY rj.created_at DESC
        LIMIT ? OFFSET ?
    """
    rows = conn.execute(data_sql, params + [limit, offset]).fetchall()
    conn.close()

    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": math.ceil(total / limit) if limit else 1
    }

# ----------------------------------------------------
# 4. Public Tracker
# ----------------------------------------------------
@router.get("/track/{repair_id}")
def track_repair(repair_id: str):
    """Public endpoint - track repair by repair ID (for QR code link)."""
    conn = get_db()
    job = conn.execute("""
        SELECT rj.id, rj.repair_id, rj.status, rj.problem_description, rj.created_at, rj.updated_at,
               rj.estimated_cost, rj.actual_cost, rj.technician_notes, rj.service_type, rj.pickup_address,
               d.device_type, d.brand, d.model,
               c.name as customer_name
        FROM repair_jobs rj
        JOIN devices d ON rj.device_id = d.id
        JOIN users c ON rj.customer_id = c.id
        WHERE rj.repair_id = ?
    """, (repair_id,)).fetchone()
    
    if not job:
        conn.close()
        raise HTTPException(404, "Repair not found")

    job_dict = dict(job)
    
    # Also fetch public timeline history
    history = conn.execute("""
        SELECT to_status, note, created_at
        FROM repair_status_history
        WHERE repair_job_id = ?
        ORDER BY created_at ASC
    """, (job["id"],)).fetchall()
    conn.close()

    job_dict["history"] = [dict(h) for h in history]
    return job_dict

# ----------------------------------------------------
# 5. Single Repair Details
# ----------------------------------------------------
@router.get("/{job_id}")
def get_repair(job_id: int, current_user: dict = Depends(get_current_user)):
    conn = get_db()
    job = conn.execute("""
        SELECT rj.*, d.device_type, d.brand, d.model,
               c.name as customer_name, c.phone as customer_phone, c.email as customer_email,
               t.name as technician_name
        FROM repair_jobs rj
        JOIN devices d ON rj.device_id = d.id
        JOIN users c ON rj.customer_id = c.id
        LEFT JOIN users t ON rj.technician_id = t.id
        WHERE rj.id = ?
    """, (job_id,)).fetchone()
    conn.close()
    if not job:
        raise HTTPException(404, "Repair job not found")
    job = dict(job)
    if current_user["role"] == "customer" and job["customer_id"] != current_user["id"]:
        raise HTTPException(403, "Access denied")
    return job

# ----------------------------------------------------
# 6. Status History Endpoint
# ----------------------------------------------------
@router.get("/{job_id}/history")
def get_repair_history(job_id: int, current_user: dict = Depends(get_current_user)):
    """Retrieve full audit timeline history of repair status changes."""
    conn = get_db()
    job = conn.execute("SELECT customer_id FROM repair_jobs WHERE id=?", (job_id,)).fetchone()
    if not job:
        conn.close()
        raise HTTPException(404, "Repair not found")
    if current_user["role"] == "customer" and job["customer_id"] != current_user["id"]:
        conn.close()
        raise HTTPException(403, "Access denied")

    history = conn.execute("""
        SELECT rsh.*, u.name as changed_by_name, u.role as changed_by_role
        FROM repair_status_history rsh
        LEFT JOIN users u ON rsh.changed_by = u.id
        WHERE rsh.repair_job_id = ?
        ORDER BY rsh.created_at ASC
    """, (job_id,)).fetchall()
    conn.close()
    return [dict(h) for h in history]

# ----------------------------------------------------
# 7. Technician Assignment
# ----------------------------------------------------
@router.post("/{job_id}/assign")
def assign_technician(job_id: int, req: AssignTechnicianRequest, current_user: dict = Depends(require_role("admin"))):
    """Admin assigns repair to a specific technician with duplicate check."""
    conn = get_db()
    job = conn.execute("SELECT * FROM repair_jobs WHERE id=?", (job_id,)).fetchone()
    if not job:
        conn.close()
        raise HTTPException(404, "Repair job not found")

    tech = conn.execute("SELECT id, name, role FROM users WHERE id=?", (req.technician_id,)).fetchone()
    if not tech or tech["role"] not in ("staff", "admin"):
        conn.close()
        raise HTTPException(400, "Selected user is not an eligible technician.")

    # Avoid duplicate assignment
    if job["technician_id"] == req.technician_id:
        conn.close()
        return {"message": f"Technician {tech['name']} is already assigned to this repair."}

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    from_status = job["status"]
    new_status = "Assigned" if job["status"] in ("Requested", "Received") else job["status"]

    conn.execute("""
        UPDATE repair_jobs
        SET technician_id=?, assigned_at=?, assigned_by=?, status=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (req.technician_id, now, current_user["id"], new_status, job_id))

    # Record in history
    note_text = f"Assigned to {tech['name']}." + (f" Note: {req.note}" if req.note else "")
    conn.execute("""
        INSERT INTO repair_status_history (repair_job_id, from_status, to_status, changed_by, note)
        VALUES (?, ?, ?, ?, ?)
    """, (job_id, from_status, new_status, current_user["id"], note_text))

    # Notify technician in-app
    conn.execute("""
        INSERT INTO notifications (user_id, repair_job_id, title, message)
        VALUES (?, ?, 'New Repair Assigned', ?)
    """, (req.technician_id, job_id, f"You have been assigned repair {job['repair_id']}."))

    conn.commit()
    conn.close()

    log_audit_event(
        user=current_user,
        action="TECHNICIAN_ASSIGNED",
        entity="repair_jobs",
        entity_id=job_id,
        details={"technician_id": req.technician_id, "technician_name": tech["name"], "repair_id": job["repair_id"]}
    )

    return {"message": f"Technician {tech['name']} assigned successfully!", "status": new_status}

VALID_REJECTION_REASONS = {
    "Required part unavailable",
    "Location/area issue",
    "Staff unavailable",
    "Workload issue",
    "Incorrect device/problem",
    "Other"
}

@router.post("/{job_id}/reject")
def reject_assigned_repair(job_id: int, req: RejectRepairRequest, current_user: dict = Depends(get_current_user)):
    """
    Staff member rejects their assigned repair request with mandatory valid reason.
    Only assigned staff can reject their own repair.
    """
    if current_user["role"] != "staff":
        raise HTTPException(403, "Only assigned staff members can reject repairs.")

    conn = get_db()
    job = conn.execute("SELECT * FROM repair_jobs WHERE id=?", (job_id,)).fetchone()
    if not job:
        conn.close()
        raise HTTPException(404, "Repair job not found.")

    if job["technician_id"] != current_user["id"]:
        conn.close()
        raise HTTPException(403, "You can only reject repairs assigned directly to you.")

    if job["status"] in ("Completed", "Delivered", "Cancelled", "Rejected"):
        conn.close()
        raise HTTPException(400, f"Cannot reject repair with status '{job['status']}'.")

    # Validate mandatory reason
    cleaned_reason = req.reason.strip() if req.reason else ""
    if not cleaned_reason or cleaned_reason not in VALID_REJECTION_REASONS:
        conn.close()
        raise HTTPException(400, f"Please select a valid rejection reason. Allowed: {sorted(list(VALID_REJECTION_REASONS))}")

    if cleaned_reason == "Other":
        if not req.notes or len(req.notes.strip()) < 5:
            conn.close()
            raise HTTPException(400, "When selecting 'Other', a detailed explanation (at least 5 characters) is mandatory.")

    notes_text = req.notes.strip() if req.notes else ""
    from_status = job["status"]

    conn.execute("""
        UPDATE repair_jobs
        SET status='Rejected', rejection_reason=?, rejection_notes=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (cleaned_reason, notes_text, job_id))

    # Log in repair_status_history
    history_note = f"Rejected by technician {current_user['name']}. Reason: {cleaned_reason}" + (f" ({notes_text})" if notes_text else "")
    conn.execute("""
        INSERT INTO repair_status_history (repair_job_id, from_status, to_status, changed_by, note)
        VALUES (?, ?, 'Rejected', ?, ?)
    """, (job_id, from_status, current_user["id"], history_note))

    # Notify all admins in-app
    admins = conn.execute("SELECT id FROM users WHERE role='admin'").fetchall()
    for a in admins:
        conn.execute("""
            INSERT INTO notifications (user_id, repair_job_id, title, message)
            VALUES (?, ?, '⚠️ Repair Rejected by Staff', ?)
        """, (a["id"], job_id, f"Technician {current_user['name']} rejected repair {job['repair_id']}. Reason: {cleaned_reason}."))

    conn.commit()
    conn.close()

    log_audit_event(
        user=current_user,
        action="TECHNICIAN_REJECTED_JOB",
        entity="repair_jobs",
        entity_id=job_id,
        details={"repair_id": job["repair_id"], "reason": cleaned_reason, "notes": notes_text}
    )

    return {"message": "Repair rejected successfully. Admin has been notified for reassignment.", "status": "Rejected"}

@router.post("/{job_id}/reassign")
def reassign_repair(job_id: int, req: ReassignTechnicianRequest, current_user: dict = Depends(require_role("admin"))):
    """
    Admin reassigns a repair job (rejected or active) to another available staff member.
    Maintains full assignment history.
    """
    conn = get_db()
    job = conn.execute("""
        SELECT rj.*, u.name as old_tech_name
        FROM repair_jobs rj
        LEFT JOIN users u ON rj.technician_id=u.id
        WHERE rj.id=?
    """, (job_id,)).fetchone()

    if not job:
        conn.close()
        raise HTTPException(404, "Repair job not found.")

    new_tech = conn.execute("SELECT id, name, role, is_active FROM users WHERE id=?", (req.new_technician_id,)).fetchone()
    if not new_tech or new_tech["role"] not in ("staff", "admin") or new_tech["is_active"] == 0:
        conn.close()
        raise HTTPException(400, "Selected user is not an active staff technician.")

    if job["technician_id"] == req.new_technician_id:
        conn.close()
        raise HTTPException(400, f"Technician {new_tech['name']} is already assigned to this repair.")

    old_tech_name = job["old_tech_name"] or "None"
    from_status = job["status"]
    new_status = "Assigned"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn.execute("""
        UPDATE repair_jobs
        SET technician_id=?, assigned_at=?, assigned_by=?, status=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (req.new_technician_id, now_str, current_user["id"], new_status, job_id))

    history_note = f"Reassigned from {old_tech_name} to {new_tech['name']} by Admin." + (f" Reason: {req.reason}" if req.reason else "")
    conn.execute("""
        INSERT INTO repair_status_history (repair_job_id, from_status, to_status, changed_by, note)
        VALUES (?, ?, ?, ?, ?)
    """, (job_id, from_status, new_status, current_user["id"], history_note))

    # Notify new technician
    conn.execute("""
        INSERT INTO notifications (user_id, repair_job_id, title, message)
        VALUES (?, ?, 'New Repair Reassigned to You', ?)
    """, (req.new_technician_id, job_id, f"Repair {job['repair_id']} has been reassigned to you by admin."))

    # Notify customer
    conn.execute("""
        INSERT INTO notifications (user_id, repair_job_id, title, message)
        VALUES (?, ?, 'Technician Assigned', ?)
    """, (job["customer_id"], job_id, f"Your repair {job['repair_id']} has been assigned to technician {new_tech['name']}."))

    conn.commit()
    conn.close()

    log_audit_event(
        user=current_user,
        action="REPAIR_REASSIGNED",
        entity="repair_jobs",
        entity_id=job_id,
        details={
            "repair_id": job["repair_id"],
            "old_technician": old_tech_name,
            "new_technician": new_tech["name"],
            "new_technician_id": req.new_technician_id,
            "reason": req.reason
        }
    )

    return {
        "message": f"Repair reassigned to {new_tech['name']} successfully!",
        "repair_id": job["repair_id"],
        "status": new_status,
        "technician_name": new_tech["name"]
    }

@router.post("/{job_id}/accept")
def accept_assigned_repair(job_id: int, current_user: dict = Depends(get_current_user)):
    """
    Staff accepts an assigned repair request, transitioning it to Diagnosing.
    """
    if current_user["role"] != "staff":
        raise HTTPException(403, "Only staff can accept assigned repairs.")

    conn = get_db()
    job = conn.execute("SELECT * FROM repair_jobs WHERE id=?", (job_id,)).fetchone()
    if not job:
        conn.close()
        raise HTTPException(404, "Repair job not found.")

    if job["technician_id"] != current_user["id"]:
        conn.close()
        raise HTTPException(403, "You can only accept repairs assigned directly to you.")

    if job["status"] not in ("Assigned", "Requested", "Received"):
        conn.close()
        return {"message": f"Repair is already in '{job['status']}' state.", "status": job["status"]}

    from_status = job["status"]
    new_status = "Diagnosing"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn.execute("""
        UPDATE repair_jobs
        SET status=?, accepted_at=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (new_status, now_str, job_id))

    conn.execute("""
        INSERT INTO repair_status_history (repair_job_id, from_status, to_status, changed_by, note)
        VALUES (?, ?, ?, ?, ?)
    """, (job_id, from_status, new_status, current_user["id"], f"Accepted by technician {current_user['name']}. Diagnosis started."))

    # Notify customer
    conn.execute("""
        INSERT INTO notifications (user_id, repair_job_id, title, message)
        VALUES (?, ?, 'Diagnosis Started', ?)
    """, (job["customer_id"], job_id, f"Technician {current_user['name']} has accepted your repair {job['repair_id']} and started diagnosis."))

    conn.commit()
    conn.close()

    log_audit_event(
        user=current_user,
        action="REPAIR_ACCEPTED",
        entity="repair_jobs",
        entity_id=job_id,
        details={"repair_id": job["repair_id"], "status": new_status}
    )

    return {"message": "Repair accepted! Diagnosis started.", "status": new_status}

# ----------------------------------------------------
# 8. Technician Workload Stats
# ----------------------------------------------------
@router.get("/technicians/workload")
def get_technician_workload(current_user: dict = Depends(require_role("admin"))):
    """Retrieve workload, active jobs, and completion metrics for all technicians."""
    conn = get_db()
    techs = conn.execute("SELECT id, name, email, phone FROM users WHERE role='staff'").fetchall()
    workload_data = []

    for t in techs:
        tid = t["id"]
        active_count = conn.execute(
            "SELECT COUNT(*) FROM repair_jobs WHERE technician_id=? AND status NOT IN ('Completed', 'Delivered', 'Cancelled', 'Rejected')",
            (tid,)
        ).fetchone()[0]

        completed_count = conn.execute(
            "SELECT COUNT(*) FROM repair_jobs WHERE technician_id=? AND status IN ('Completed', 'Delivered')",
            (tid,)
        ).fetchone()[0]

        # Calculate average turnaround hours
        completed_jobs = conn.execute(
            "SELECT created_at, completed_at FROM repair_jobs WHERE technician_id=? AND completed_at IS NOT NULL",
            (tid,)
        ).fetchall()

        total_hours = 0
        valid_jobs = 0
        for cj in completed_jobs:
            try:
                t_start = datetime.strptime(cj["created_at"][:19], "%Y-%m-%d %H:%M:%S")
                t_end = datetime.strptime(cj["completed_at"][:19], "%Y-%m-%d %H:%M:%S")
                diff = (t_end - t_start).total_seconds() / 3600.0
                if diff > 0:
                    total_hours += diff
                    valid_jobs += 1
            except Exception:
                pass

        avg_hours = round(total_hours / valid_jobs, 1) if valid_jobs > 0 else 0

        # Customer rating for technician
        avg_rating = conn.execute(
            "SELECT AVG(COALESCE(technician_rating, rating)) FROM feedback WHERE technician_id=?",
            (tid,)
        ).fetchone()[0]

        workload_data.append({
            "technician_id": tid,
            "name": t["name"],
            "email": t["email"],
            "phone": t["phone"],
            "active_repairs": active_count,
            "completed_repairs": completed_count,
            "avg_repair_hours": avg_hours,
            "customer_rating": round(float(avg_rating), 1) if avg_rating else 5.0
        })

    conn.close()
    return workload_data

# ----------------------------------------------------
# 9. Update Status
# ----------------------------------------------------
@router.put("/{job_id}/status")
def update_status(job_id: int, update: RepairStatusUpdate, current_user: dict = Depends(get_current_user)):
    """Admin or staff updates repair status with audit logging and WhatsApp alert."""
    if current_user["role"] == "customer":
        raise HTTPException(403, "Only staff or admin can update repair status.")

    if update.status not in ALL_VALID_STATUSES:
        raise HTTPException(400, f"Invalid status. Must be one of: {sorted(list(ALL_VALID_STATUSES))}")

    conn = get_db()
    job = conn.execute("""
        SELECT rj.*, u.name as customer_name, u.phone as customer_phone,
               d.brand, d.model
        FROM repair_jobs rj
        JOIN users u ON rj.customer_id=u.id
        JOIN devices d ON rj.device_id=d.id
        WHERE rj.id=?
    """, (job_id,)).fetchone()
    
    if not job:
        conn.close()
        raise HTTPException(404, "Job not found")

    # Staff can only update their assigned jobs
    if current_user["role"] == "staff" and job["technician_id"] != current_user["id"]:
        conn.close()
        raise HTTPException(403, "You can only update your assigned jobs.")

    from_status = job["status"]
    if from_status == update.status:
        conn.close()
        return {"message": f"Job is already in {update.status} status", "status": update.status}

    # State transition enforcement
    allowed_next = VALID_STATUS_TRANSITIONS.get(from_status, set())
    is_valid_flow = (update.status in allowed_next)

    if not is_valid_flow:
        if current_user["role"] == "staff":
            conn.close()
            raise HTTPException(400, f"Invalid status transition from '{from_status}' to '{update.status}'. Allowed next statuses: {sorted(list(allowed_next)) if allowed_next else 'None (Terminal state)'}.")
        elif current_user["role"] == "admin":
            override_reason = update.note or update.technician_notes
            if not override_reason or len(override_reason.strip()) < 5:
                conn.close()
                raise HTTPException(400, f"Non-standard status transition from '{from_status}' to '{update.status}' requires an admin override note (minimum 5 characters).")
            log_audit_event(
                user=current_user,
                action="ADMIN_STATUS_OVERRIDE",
                entity="repair_jobs",
                entity_id=job_id,
                details={"from": from_status, "to": update.status, "reason": override_reason.strip()}
            )

    completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if update.status in ("Completed", "Delivered") else job["completed_at"]

    conn.execute("""
        UPDATE repair_jobs SET status=?, updated_at=CURRENT_TIMESTAMP,
        technician_id=COALESCE(?, technician_id),
        priority=COALESCE(?, priority),
        actual_cost=COALESCE(?, actual_cost),
        technician_notes=COALESCE(?, technician_notes),
        completed_at=?
        WHERE id=?
    """, (update.status, update.technician_id, update.priority,
          update.actual_cost, update.technician_notes, completed_at, job_id))

    # Log in repair_status_history
    history_note = update.note or update.technician_notes or f"Status updated from {from_status} to {update.status}"
    conn.execute("""
        INSERT INTO repair_status_history (repair_job_id, from_status, to_status, changed_by, note)
        VALUES (?, ?, ?, ?, ?)
    """, (job_id, from_status, update.status, current_user["id"], history_note))

    # In-app notification
    status_messages = {
        "Assigned": "👨‍🔧 A technician has been assigned to your repair.",
        "Diagnosing": "🔍 We've started diagnosing your device.",
        "Approved": "👍 Repair estimate approved. Work commencing.",
        "Repairing": "🔧 Repair is in progress!",
        "Ready": "📦 Your device is ready for pickup or delivery!",
        "Completed": "✅ Your repair is complete! Thank you for your trust.",
        "Delivered": "🎉 Your device has been delivered.",
        "Cancelled": "❌ This repair request has been cancelled.",
        "On Hold": "⏳ Repair placed on hold pending customer confirmation or parts.",
        "Rejected": "⚠️ Repair request could not be accepted."
    }
    if update.status in status_messages:
        conn.execute(
            "INSERT INTO notifications (user_id, repair_job_id, title, message) VALUES (?,?,?,?)",
            (job["customer_id"], job_id, f"Status Update: {update.status}", status_messages[update.status])
        )

    conn.commit()
    conn.close()

    # Log system audit
    log_audit_event(
        user=current_user,
        action="STATUS_UPDATED",
        entity="repair_jobs",
        entity_id=job_id,
        details={"from": from_status, "to": update.status, "note": history_note}
    )

    # Trigger Real-Time WhatsApp Alert Dispatch
    total_cost = update.actual_cost or job["actual_cost"] or job["estimated_cost"]
    dispatch_repair_status_alert(
        customer_id=job["customer_id"],
        customer_name=job["customer_name"],
        customer_phone=job["customer_phone"],
        repair_id=job["repair_id"],
        device_name=f"{job['brand']} {job['model']}",
        status=update.status,
        total_amount=total_cost
    )

    return {"message": f"Status updated to {update.status}", "status": update.status}

# ----------------------------------------------------
# 10. Atomic Inventory Deduction on Adding Part
# ----------------------------------------------------
@router.post("/{job_id}/add-part")
def add_part_atomic(job_id: int, req: AddPartRequest, current_user: dict = Depends(get_current_user)):
    """
    Atomically adds a part to a repair and decrements inventory stock.
    Guarantees stock cannot become negative.
    """
    if current_user["role"] == "customer":
        raise HTTPException(403, "Customers cannot modify parts.")

    if req.quantity <= 0:
        raise HTTPException(400, "Quantity must be greater than 0.")

    conn = get_db()
    try:
        job = conn.execute("SELECT * FROM repair_jobs WHERE id=?", (job_id,)).fetchone()
        if not job:
            raise HTTPException(404, "Repair job not found")

        # Staff can only add parts to their assigned repair
        if current_user["role"] == "staff" and job["technician_id"] != current_user["id"]:
            raise HTTPException(403, "You can only add parts to repairs assigned directly to you.")

        part = conn.execute("SELECT * FROM inventory WHERE id=?", (req.part_id,)).fetchone()
        if not part:
            raise HTTPException(404, "Part not found in inventory.")

        # 1. Decrement inventory atomically
        cursor = conn.execute(
            "UPDATE inventory SET quantity = quantity - ?, updated_at=CURRENT_TIMESTAMP WHERE id = ? AND quantity >= ?",
            (req.quantity, req.part_id, req.quantity)
        )
        if cursor.rowcount == 0:
            current = conn.execute("SELECT quantity FROM inventory WHERE id=?", (req.part_id,)).fetchone()
            avail = current["quantity"] if current else 0
            raise HTTPException(400, f"Insufficient stock: only {avail} units of '{part['part_name']}' available.")

        # Fetch new remaining stock
        new_stock = conn.execute("SELECT quantity FROM inventory WHERE id=?", (req.part_id,)).fetchone()["quantity"]

        # 2. Record inventory transaction
        conn.execute("""
            INSERT INTO inventory_transactions (part_id, quantity, transaction_type, repair_job_id, staff_id, reason)
            VALUES (?, ?, 'OUT', ?, ?, ?)
        """, (req.part_id, req.quantity, job_id, current_user["id"], f"Consumed for repair {job['repair_id']}"))

        # 3. Update parts_used in repair_jobs
        existing_parts = json.loads(job["parts_used"]) if job["parts_used"] else []
        existing_parts.append({
            "part_id": part["id"],
            "part_name": part["part_name"],
            "part_code": part["part_code"],
            "quantity": req.quantity,
            "unit_price": part["unit_price"]
        })

        conn.execute("UPDATE repair_jobs SET parts_used=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                     (json.dumps(existing_parts), job_id))

        conn.commit()
    finally:
        conn.close()


    log_audit_event(
        user=current_user,
        action="INVENTORY_DEDUCTED",
        entity="inventory",
        entity_id=req.part_id,
        details={"part": part["part_name"], "qty": req.quantity, "repair_id": job["repair_id"], "remaining_stock": new_stock}
    )

    return {
        "message": f"Added {req.quantity}x {part['part_name']} to repair.",
        "remaining_stock": new_stock,
        "new_stock": new_stock,
        "parts_used": existing_parts
    }


@router.put("/{job_id}/parts")
def update_parts_legacy(job_id: int, update: PartsUpdate, current_user: dict = Depends(get_current_user)):
    """Staff/Admin direct parts list update (backward compatibility)."""
    if current_user["role"] == "customer":
        raise HTTPException(403, "Access denied")
    conn = get_db()
    conn.execute("UPDATE repair_jobs SET parts_used=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                 (json.dumps(update.parts_used), job_id))
    conn.commit()
    conn.close()
    return {"message": "Parts updated"}

# ----------------------------------------------------
# 11. Staged Photo Uploads (Before / During / After)
# ----------------------------------------------------
@router.post("/{job_id}/photos")
async def upload_repair_photo(
    job_id: int,
    stage: str = Form(...),  # before | during | after
    caption: Optional[str] = Form(None),
    photo: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload staged repair evidence photos (Before, During, After)."""
    if stage not in ("before", "during", "after"):
        raise HTTPException(400, "Stage must be one of: 'before', 'during', 'after'.")

    conn = get_db()
    job = conn.execute("SELECT * FROM repair_jobs WHERE id=?", (job_id,)).fetchone()
    if not job:
        conn.close()
        raise HTTPException(404, "Repair job not found")

    # Access check: customer can only upload 'before', staff/admin can upload all
    if current_user["role"] == "customer" and (job["customer_id"] != current_user["id"] or stage != "before"):
        conn.close()
        raise HTTPException(403, "Customers can only upload 'before' photos for their own repairs.")

    ext = photo.filename.rsplit(".", 1)[-1].lower() if "." in photo.filename else ""
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        conn.close()
        raise HTTPException(400, f"Unsupported file extension '{ext}'. Allowed: JPG, PNG, WEBP.")

    content = await photo.read()
    if len(content) > MAX_FILE_SIZE:
        conn.close()
        raise HTTPException(400, "Photo size exceeds 5MB limit.")
    if not validate_file_magic_bytes(content, ext):
        conn.close()
        raise HTTPException(400, f"File content does not match image extension '{ext}' (spoofed or invalid file format).")

    filename = f"repair_{job_id}_{stage}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(content)

    photo_url = f"/uploads/{filename}"

    conn.execute("""
        INSERT INTO repair_photos (repair_job_id, photo_stage, photo_url, caption, uploaded_by)
        VALUES (?, ?, ?, ?, ?)
    """, (job_id, stage, photo_url, caption or f"{stage.capitalize()} repair photo", current_user["id"]))

    conn.commit()
    conn.close()

    log_audit_event(
        user=current_user,
        action="PHOTO_UPLOADED",
        entity="repair_photos",
        entity_id=job_id,
        details={"stage": stage, "url": photo_url}
    )

    return {"message": f"{stage.capitalize()} photo uploaded successfully!", "url": photo_url, "stage": stage}

@router.get("/{job_id}/photos")
def list_repair_photos(job_id: int, current_user: dict = Depends(get_current_user)):
    """Retrieve all staged photos for a repair."""
    conn = get_db()
    job = conn.execute("SELECT customer_id FROM repair_jobs WHERE id=?", (job_id,)).fetchone()
    if not job:
        conn.close()
        raise HTTPException(404, "Repair job not found")
    if current_user["role"] == "customer" and job["customer_id"] != current_user["id"]:
        conn.close()
        raise HTTPException(403, "Access denied")

    photos = conn.execute("""
        SELECT rp.*, u.name as uploaded_by_name
        FROM repair_photos rp
        LEFT JOIN users u ON rp.uploaded_by = u.id
        WHERE rp.repair_job_id = ?
        ORDER BY rp.created_at ASC
    """, (job_id,)).fetchall()
    conn.close()
    return [dict(p) for p in photos]

# ----------------------------------------------------
# 12. Dashboard KPIs
# ----------------------------------------------------
@router.get("/stats/dashboard")
def get_dashboard_stats(current_user: dict = Depends(require_role("admin"))):
    """Admin dashboard KPIs and metrics."""
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM repair_jobs").fetchone()[0]
    pending = conn.execute(
        "SELECT COUNT(*) FROM repair_jobs WHERE status NOT IN ('Completed','Delivered','Cancelled','Rejected')"
    ).fetchone()[0]
    completed = conn.execute("SELECT COUNT(*) FROM repair_jobs WHERE status IN ('Completed','Delivered')").fetchone()[0]
    cancelled = conn.execute("SELECT COUNT(*) FROM repair_jobs WHERE status IN ('Cancelled','Rejected')").fetchone()[0]
    revenue = conn.execute("SELECT COALESCE(SUM(total_amount),0) FROM bills WHERE payment_status='Paid'").fetchone()[0]
    low_stock = conn.execute("SELECT COUNT(*) FROM inventory WHERE quantity <= reorder_level").fetchone()[0]

    # Recent jobs
    recent = conn.execute("""
        SELECT rj.id, rj.repair_id, rj.status, rj.created_at, d.device_type, d.brand,
               c.name as customer_name, t.name as technician_name
        FROM repair_jobs rj
        JOIN devices d ON rj.device_id=d.id
        JOIN users c ON rj.customer_id=c.id
        LEFT JOIN users t ON rj.technician_id=t.id
        ORDER BY rj.created_at DESC LIMIT 6
    """).fetchall()

    # Revenue by day (last 7 days)
    daily_revenue = conn.execute("""
        SELECT DATE(paid_at) as day, SUM(amount) as revenue
        FROM payments
        WHERE paid_at >= DATE('now', '-7 days')
        GROUP BY DATE(paid_at) ORDER BY day
    """).fetchall()

    # Status distribution
    status_dist = conn.execute("""
        SELECT status, COUNT(*) as count FROM repair_jobs GROUP BY status
    """).fetchall()

    conn.close()
    return {
        "total": total,
        "pending": pending,
        "completed": completed,
        "cancelled": cancelled,
        "revenue": revenue,
        "low_stock_alerts": low_stock,
        "recent_jobs": [dict(r) for r in recent],
        "daily_revenue": [dict(r) for r in daily_revenue],
        "status_distribution": [dict(r) for r in status_dist]
    }

import uuid as _uuid

# ----------------------------------------------------
# BATCH: Submit multiple devices in one request
# ----------------------------------------------------
class RepairItemRequest(BaseModel):
    device_type: str
    brand: str
    model: str
    problem_description: str
    estimated_cost: float = 0

class BatchSubmitRequest(BaseModel):
    items: List[RepairItemRequest]
    service_type: str = "Store Drop-off"
    pickup_address: Optional[str] = None
    landmark: Optional[str] = None
    pincode: Optional[str] = None

@router.post("/submit-batch")
def submit_batch_repair(
    req: BatchSubmitRequest,
    current_user: dict = Depends(get_current_user)
):
    """Submit multiple devices/appliances in one repair batch request."""
    if not req.items:
        raise HTTPException(400, "Please add at least one device to the repair request.")
    if len(req.items) > 10:
        raise HTTPException(400, "Maximum 10 devices allowed in one batch request.")

    # Validate Home Pickup address
    s_type = "Home Pickup" if "home" in req.service_type.lower() or "pickup" in req.service_type.lower() else "Store Drop-off"
    if s_type == "Home Pickup":
        if not req.pickup_address or len(req.pickup_address.strip()) < 10:
            raise HTTPException(400, "Please provide a complete home address (min 10 characters) for Home Pickup service.")
        if req.pincode:
            validate_pincode(req.pincode)

    # Generate batch ID
    batch_id = f"BATCH-{_uuid.uuid4().hex[:10].upper()}"

    conn = get_db()
    created_jobs = []

    for item in req.items:
        # Create/get device
        device = conn.execute(
            "SELECT id FROM devices WHERE customer_id=? AND device_type=? AND brand=? AND model=?",
            (current_user["id"], item.device_type, item.brand, item.model)
        ).fetchone()
        if device:
            device_id = device["id"]
        else:
            cur = conn.execute(
                "INSERT INTO devices (customer_id, device_type, brand, model) VALUES (?,?,?,?)",
                (current_user["id"], item.device_type, item.brand, item.model)
            )
            device_id = cur.lastrowid

        repair_id = generate_repair_id(conn)
        full_address = req.pickup_address

        cur = conn.execute("""
            INSERT INTO repair_jobs
                (repair_id, customer_id, device_id, problem_description,
                 estimated_cost, status, priority, shop_id,
                 service_type, pickup_address, landmark, pincode, repair_batch_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            repair_id, current_user["id"], device_id, item.problem_description,
            item.estimated_cost, "Requested", "Normal", current_user.get("shop_id", 1),
            s_type, full_address, req.landmark, req.pincode, batch_id
        ))
        job_db_id = cur.lastrowid

        conn.execute("""
            INSERT INTO repair_status_history (repair_job_id, from_status, to_status, changed_by, note)
            VALUES (?,?,?,?,?)
        """, (job_db_id, None, "Requested", current_user["id"],
              f"Part of batch {batch_id}: {item.device_type} repair request submitted"))

        created_jobs.append({
            "id": job_db_id,
            "repair_id": repair_id,
            "device_type": item.device_type,
            "brand": item.brand,
            "model": item.model,
            "estimated_cost": item.estimated_cost,
            "status": "Requested"
        })

    # Batch-level in-app notification
    total_est = sum(j["estimated_cost"] for j in created_jobs)
    conn.execute(
        "INSERT INTO notifications (user_id, title, message) VALUES (?,?,?)",
        (current_user["id"],
         f"Batch Request Received ({len(created_jobs)} devices)",
         f"Your repair request for {len(created_jobs)} device(s) has been submitted. Batch ID: {batch_id}. Total Estimated: ₹{total_est:,.0f}")
    )

    conn.commit()
    conn.close()

    log_audit_event(
        user=current_user,
        action="BATCH_REPAIR_CREATED",
        entity="repair_jobs",
        entity_id=batch_id,
        details={"batch_id": batch_id, "item_count": len(created_jobs), "total_estimated": total_est}
    )

    return {
        "batch_id": batch_id,
        "total_items": len(created_jobs),
        "total_estimated_cost": total_est,
        "jobs": created_jobs,
        "message": f"{len(created_jobs)} repair request(s) submitted successfully in batch {batch_id}!"
    }


@router.get("/batch/{batch_id}")
def get_batch_repairs(batch_id: str, current_user: dict = Depends(get_current_user)):
    """Get all repair jobs in a batch, with totals. Customer can only see their own batch."""
    conn = get_db()
    jobs = conn.execute("""
        SELECT rj.*, d.device_type, d.brand, d.model,
               u.name as customer_name
        FROM repair_jobs rj
        JOIN devices d ON rj.device_id = d.id
        JOIN users u ON rj.customer_id = u.id
        WHERE rj.repair_batch_id = ?
        ORDER BY rj.created_at ASC
    """, (batch_id,)).fetchall()
    conn.close()

    if not jobs:
        raise HTTPException(404, "Batch not found.")

    # Access control: customer can only see their own batch
    if current_user["role"] == "customer":
        if any(j["customer_id"] != current_user["id"] for j in jobs):
            raise HTTPException(403, "Access denied.")

    job_list = [dict(j) for j in jobs]
    total_est = sum((j["estimated_cost"] or 0) for j in job_list)
    total_actual = sum((j["actual_cost"] or 0) for j in job_list)

    return {
        "batch_id": batch_id,
        "total_items": len(job_list),
        "total_estimated_cost": total_est,
        "total_actual_cost": total_actual,
        "jobs": job_list
    }


class AdminRepairUpdateRequest(BaseModel):
    device_type: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    problem_description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    estimated_cost: Optional[float] = None
    actual_cost: Optional[float] = None
    technician_id: Optional[int] = None
    service_type: Optional[str] = None
    pickup_address: Optional[str] = None
    technician_notes: Optional[str] = None


@router.put("/{job_id}")
def admin_update_repair(job_id: int, req: AdminRepairUpdateRequest, current_user: dict = Depends(require_role("admin"))):
    """Admin full edit of any repair job details."""
    conn = get_db()
    job = conn.execute("SELECT * FROM repair_jobs WHERE id=?", (job_id,)).fetchone()
    if not job:
        conn.close()
        raise HTTPException(404, "Repair job not found.")

    device_id = job["device_id"]
    if req.device_type or req.brand or req.model:
        dev = conn.execute("SELECT * FROM devices WHERE id=?", (device_id,)).fetchone()
        if dev:
            conn.execute("""
                UPDATE devices
                SET device_type=COALESCE(?, device_type),
                    brand=COALESCE(?, brand),
                    model=COALESCE(?, model)
                WHERE id=?
            """, (req.device_type, req.brand, req.model, device_id))

    from_status = job["status"]
    to_status = req.status or from_status

    conn.execute("""
        UPDATE repair_jobs
        SET problem_description=COALESCE(?, problem_description),
            status=COALESCE(?, status),
            priority=COALESCE(?, priority),
            estimated_cost=COALESCE(?, estimated_cost),
            actual_cost=COALESCE(?, actual_cost),
            technician_id=COALESCE(?, technician_id),
            service_type=COALESCE(?, service_type),
            pickup_address=COALESCE(?, pickup_address),
            technician_notes=COALESCE(?, technician_notes),
            updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (
        req.problem_description,
        req.status,
        req.priority,
        req.estimated_cost,
        req.actual_cost,
        req.technician_id,
        req.service_type,
        req.pickup_address,
        req.technician_notes,
        job_id
    ))

    if req.status and req.status != from_status:
        conn.execute("""
            INSERT INTO repair_status_history (repair_job_id, from_status, to_status, changed_by, note)
            VALUES (?, ?, ?, ?, 'Status updated by Admin in full edit')
        """, (job_id, from_status, to_status, current_user["id"]))

    conn.commit()
    conn.close()

    try:
        log_audit_event(
            user=current_user,
            action="REPAIR_UPDATED_BY_ADMIN",
            entity="repair_jobs",
            entity_id=job_id,
            details={"repair_id": job["repair_id"], "from_status": from_status, "to_status": to_status}
        )
    except Exception:
        pass

    return {"message": f"Repair {job['repair_id']} updated successfully by Admin.", "id": job_id}


@router.delete("/{job_id}")
def admin_delete_repair(job_id: int, current_user: dict = Depends(require_role("admin"))):
    """Admin deletes/removes a repair job."""
    conn = get_db()
    job = conn.execute("SELECT * FROM repair_jobs WHERE id=?", (job_id,)).fetchone()
    if not job:
        conn.close()
        raise HTTPException(404, "Repair job not found.")

    conn.execute("DELETE FROM repair_status_history WHERE repair_job_id=?", (job_id,))
    conn.execute("DELETE FROM repair_photos WHERE repair_job_id=?", (job_id,))
    conn.execute("DELETE FROM notifications WHERE repair_job_id=?", (job_id,))
    conn.execute("DELETE FROM feedback WHERE repair_job_id=?", (job_id,))
    conn.execute("DELETE FROM repair_item_warranties WHERE repair_job_id=?", (job_id,))
    conn.execute("DELETE FROM warranty_claims WHERE repair_job_id=?", (job_id,))
    conn.execute("DELETE FROM warranties WHERE repair_job_id=?", (job_id,))
    conn.execute("DELETE FROM bills WHERE repair_job_id=?", (job_id,))
    conn.execute("DELETE FROM repair_jobs WHERE id=?", (job_id,))
    conn.commit()
    conn.close()

    try:
        log_audit_event(
            user=current_user,
            action="REPAIR_DELETED_BY_ADMIN",
            entity="repair_jobs",
            entity_id=job_id,
            details={"repair_id": job["repair_id"]}
        )
    except Exception:
        pass

    return {"message": f"Repair {job['repair_id']} deleted successfully."}


