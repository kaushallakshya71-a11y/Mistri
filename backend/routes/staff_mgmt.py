"""
Mistri Staff Management Routes
Features:
- Staff Salary Management & Audit Trail
- Monthly Leave Policy (4 leaves/month, 2-day advance notice rule)
- Transparent Salary Deduction Math (Unpaid leaves * Daily rate)
- Performance & Festival Bonuses
- 6-Month Employment Commitment & 30-Day Resignation Notice
- 15-Day Admin Termination Notice
- Comprehensive Audit Logging
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date, timedelta
from db.database import get_db
from middleware.auth import get_current_user, require_role
from utils.audit import log_audit_event

router = APIRouter(prefix="/api/staff-mgmt", tags=["staff-management"])

# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------

class SalaryUpdateRequest(BaseModel):
    monthly_salary: float
    salary_policy_days: Optional[int] = 30
    notes: Optional[str] = None

class LeaveApplyRequest(BaseModel):
    leave_date: str  # YYYY-MM-DD
    days: int = 1
    reason: str

class LeaveReviewRequest(BaseModel):
    status: str  # Approved | Rejected | Cancelled
    admin_notes: Optional[str] = None

class ResignationSubmitRequest(BaseModel):
    proposed_last_date: str  # YYYY-MM-DD
    reason: str
    emergency_justification: Optional[str] = None

class ResignationReviewRequest(BaseModel):
    status: str  # Approved | Rejected
    admin_notes: Optional[str] = None

class TerminationNoticeRequest(BaseModel):
    reason: str

class AwardBonusRequest(BaseModel):
    staff_id: int
    amount: float
    bonus_type: str = "Performance Bonus"  # Performance Bonus | Festival Bonus | Special Incentive
    reason: str

# ---------------------------------------------------------------------------
# 1. Staff Summary & Leave/Salary Status
# ---------------------------------------------------------------------------

@router.get("/summary")
def get_staff_summary(current_user: dict = Depends(get_current_user)):
    """
    Get staff operational, salary, and leave status.
    Staff can only see their own summary; Admin sees all staff.
    """
    conn = get_db()
    today = date.today()
    current_month = today.strftime("%Y-%m")

    if current_user["role"] == "staff":
        staff_rows = conn.execute("SELECT * FROM users WHERE id=? AND role='staff'", (current_user["id"],)).fetchall()
    else:
        staff_rows = conn.execute("SELECT * FROM users WHERE role='staff' ORDER BY id DESC").fetchall()

    results = []
    for s in staff_rows:
        sid = s["id"]
        salary = s["monthly_salary"] or 0.0
        policy_days = s["salary_policy_days"] or 30
        daily_rate = round(salary / policy_days, 2) if policy_days > 0 else 0.0

        # Commitment progress
        joining_str = s["joining_date"] or str(s["created_at"])[:10]
        try:
            join_dt = datetime.strptime(joining_str[:10], "%Y-%m-%d").date()
            days_served = (today - join_dt).days
            months_served = round(days_served / 30.44, 1)
        except Exception:
            months_served = 0.0
            join_dt = today

        min_commitment = s["minimum_commitment_months"] or 6
        commitment_completed = months_served >= min_commitment

        # Approved leaves in current month
        leaves_data = conn.execute("""
            SELECT SUM(days) as total_days
            FROM staff_leaves
            WHERE staff_id=? AND status='Approved' AND strftime('%Y-%m', leave_date) = ?
        """, (sid, current_month)).fetchone()
        approved_leave_days = int(leaves_data["total_days"] or 0)

        allowed_leaves = 4
        leaves_remaining = max(0, allowed_leaves - approved_leave_days)
        unpaid_leaves = max(0, approved_leave_days - allowed_leaves)
        deduction = round(unpaid_leaves * daily_rate, 2)

        # Bonuses in current month
        bonus_data = conn.execute("""
            SELECT SUM(amount) as total_bonus
            FROM staff_bonuses
            WHERE staff_id=? AND strftime('%Y-%m', awarded_at) = ?
        """, (sid, current_month)).fetchone()
        bonuses = float(bonus_data["total_bonus"] or 0.0)

        net_salary = max(0.0, round(salary - deduction + bonuses, 2))

        # Active repairs count
        active_count = conn.execute("""
            SELECT COUNT(*) FROM repair_jobs
            WHERE technician_id=? AND status NOT IN ('Completed', 'Delivered', 'Cancelled', 'Rejected')
        """, (sid,)).fetchone()[0]

        # Completed repairs count
        completed_count = conn.execute("""
            SELECT COUNT(*) FROM repair_jobs
            WHERE technician_id=? AND status IN ('Completed', 'Delivered')
        """, (sid,)).fetchone()[0]

        results.append({
            "id": sid,
            "name": s["name"],
            "email": s["email"],
            "phone": s["phone"],
            "role": s["role"],
            "is_active": s["is_active"] if s["is_active"] is not None else 1,
            "joining_date": str(join_dt),
            "months_served": months_served,
            "minimum_commitment_months": min_commitment,
            "commitment_completed": commitment_completed,
            "monthly_salary": salary,
            "salary_policy_days": policy_days,
            "daily_rate": daily_rate,
            "allowed_leaves": allowed_leaves,
            "leaves_used": approved_leave_days,
            "leaves_remaining": leaves_remaining,
            "unpaid_leaves": unpaid_leaves,
            "salary_deduction": deduction,
            "current_month_bonuses": bonuses,
            "estimated_final_salary": net_salary,
            "active_repairs": active_count,
            "completed_repairs": completed_count,
            "resignation_status": s["resignation_status"] or "None",
            "resignation_notice_date": s["resignation_notice_date"],
            "resignation_last_date": s["resignation_last_date"],
            "resignation_reason": s["resignation_reason"],
            "termination_notice_date": s["termination_notice_date"],
            "termination_effective_date": s["termination_effective_date"],
        })

    conn.close()
    return results

# ---------------------------------------------------------------------------
# 2. Salary Management
# ---------------------------------------------------------------------------

@router.put("/salary/{staff_id}")
def update_staff_salary(staff_id: int, req: SalaryUpdateRequest, current_user: dict = Depends(require_role("admin"))):
    """Admin updates a staff member's monthly salary with audit logging."""
    if req.monthly_salary < 0:
        raise HTTPException(400, "Salary cannot be negative.")

    conn = get_db()
    staff = conn.execute("SELECT * FROM users WHERE id=? AND role='staff'", (staff_id,)).fetchone()
    if not staff:
        conn.close()
        raise HTTPException(404, "Staff member not found.")

    old_salary = staff["monthly_salary"] or 0.0

    conn.execute("""
        UPDATE users
        SET monthly_salary=?, salary_policy_days=?
        WHERE id=?
    """, (req.monthly_salary, req.salary_policy_days or 30, staff_id))

    conn.execute("""
        INSERT INTO salary_audit_logs (staff_id, old_salary, new_salary, changed_by, notes)
        VALUES (?, ?, ?, ?, ?)
    """, (staff_id, old_salary, req.monthly_salary, current_user["id"], req.notes or "Salary revision"))

    conn.commit()
    conn.close()

    log_audit_event(
        current_user,
        action="SALARY_UPDATED",
        entity="users",
        entity_id=staff_id,
        details={
            "staff_name": staff["name"],
            "old_salary": old_salary,
            "new_salary": req.monthly_salary,
            "policy_days": req.salary_policy_days or 30,
            "notes": req.notes
        }
    )

    return {
        "message": f"Salary updated for {staff['name']}: ₹{old_salary:,.2f} ➔ ₹{req.monthly_salary:,.2f}",
        "staff_id": staff_id,
        "new_salary": req.monthly_salary
    }

@router.get("/salary-history/{staff_id}")
def get_salary_history(staff_id: int, current_user: dict = Depends(get_current_user)):
    """View salary changes audit trail."""
    if current_user["role"] == "staff" and current_user["id"] != staff_id:
        raise HTTPException(403, "You can only view your own salary history.")

    conn = get_db()
    history = conn.execute("""
        SELECT sal.*, u.name as changed_by_name
        FROM salary_audit_logs sal
        LEFT JOIN users u ON sal.changed_by = u.id
        WHERE sal.staff_id = ?
        ORDER BY sal.created_at DESC
    """, (staff_id,)).fetchall()
    conn.close()
    return [dict(h) for h in history]

# ---------------------------------------------------------------------------
# 3. Leave Management (4 leaves/month, 2-day advance notice rule)
# ---------------------------------------------------------------------------

@router.post("/leave/apply")
def apply_leave(req: LeaveApplyRequest, current_user: dict = Depends(get_current_user)):
    """
    Staff applies for leave.
    Enforces minimum 2-day advance notice rule and mandatory reason.
    """
    if current_user["role"] != "staff":
        raise HTTPException(403, "Only staff can apply for leave.")

    if not req.reason or len(req.reason.strip()) < 5:
        raise HTTPException(400, "Please provide a valid leave reason (minimum 5 characters).")

    if req.days <= 0 or req.days > 15:
        raise HTTPException(400, "Number of days must be between 1 and 15.")

    try:
        target_date = datetime.strptime(req.leave_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD.")

    today = date.today()
    diff_days = (target_date - today).days

    # Strict rule: at least 2 days advance notice
    if diff_days < 2:
        raise HTTPException(
            400,
            f"Leave request minimum 2 days before submit karni hai. "
            f"(Selected date: {req.leave_date}. Today: {today.isoformat()}. Notice given: {diff_days} day(s)). "
            "Emergency situation ke liye kripya Admin se directly contact karein."
        )

    conn = get_db()
    # Prevent duplicate pending leave on same date
    existing = conn.execute("""
        SELECT id FROM staff_leaves
        WHERE staff_id=? AND leave_date=? AND status IN ('Pending', 'Approved')
    """, (current_user["id"], req.leave_date)).fetchone()

    if existing:
        conn.close()
        raise HTTPException(400, f"You already have a Pending or Approved leave on {req.leave_date}.")

    cursor = conn.execute("""
        INSERT INTO staff_leaves (staff_id, leave_date, days, reason, status)
        VALUES (?, ?, ?, ?, 'Pending')
    """, (current_user["id"], req.leave_date, req.days, req.reason.strip()))
    leave_id = cursor.lastrowid

    # Notify admins
    admins = conn.execute("SELECT id FROM users WHERE role='admin'").fetchall()
    for a in admins:
        conn.execute("""
            INSERT INTO notifications (user_id, title, message)
            VALUES (?, 'New Leave Request', ?)
        """, (a["id"], f"Staff {current_user['name']} applied for {req.days} day(s) leave on {req.leave_date}."))

    conn.commit()
    conn.close()

    log_audit_event(
        current_user,
        action="LEAVE_REQUESTED",
        entity="staff_leaves",
        entity_id=leave_id,
        details={"leave_date": req.leave_date, "days": req.days, "reason": req.reason.strip()}
    )

    return {
        "message": f"Leave request for {req.leave_date} ({req.days} days) submitted successfully for Admin review.",
        "leave_id": leave_id,
        "status": "Pending"
    }

@router.get("/leaves")
def list_leaves(
    staff_id: Optional[int] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """List staff leave requests with status filters."""
    conn = get_db()
    params = []
    where_clauses = []

    if current_user["role"] == "staff":
        where_clauses.append("sl.staff_id = ?")
        params.append(current_user["id"])
    elif staff_id:
        where_clauses.append("sl.staff_id = ?")
        params.append(staff_id)

    if status:
        where_clauses.append("sl.status = ?")
        params.append(status)

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    leaves = conn.execute(f"""
        SELECT sl.*, u.name as staff_name, u.email as staff_email,
               r.name as reviewer_name
        FROM staff_leaves sl
        JOIN users u ON sl.staff_id = u.id
        LEFT JOIN users r ON sl.reviewed_by = r.id
        {where_sql}
        ORDER BY sl.leave_date DESC
    """, params).fetchall()

    conn.close()
    return [dict(l) for l in leaves]

@router.put("/leave/{leave_id}/review")
def review_leave(leave_id: int, req: LeaveReviewRequest, current_user: dict = Depends(require_role("admin"))):
    """Admin approves or rejects a staff leave request."""
    if req.status not in ("Approved", "Rejected", "Cancelled"):
        raise HTTPException(400, "Status must be 'Approved', 'Rejected', or 'Cancelled'.")

    conn = get_db()
    leave = conn.execute("""
        SELECT sl.*, u.name as staff_name
        FROM staff_leaves sl
        JOIN users u ON sl.staff_id = u.id
        WHERE sl.id = ?
    """, (leave_id,)).fetchone()

    if not leave:
        conn.close()
        raise HTTPException(404, "Leave request not found.")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn.execute("""
        UPDATE staff_leaves
        SET status=?, reviewed_by=?, reviewed_at=?, admin_notes=?
        WHERE id=?
    """, (req.status, current_user["id"], now_str, req.admin_notes, leave_id))

    # Notify the staff member
    notif_title = f"Leave Request {req.status}"
    notif_msg = f"Your leave for {leave['leave_date']} has been {req.status.lower()} by Admin." + (f" Note: {req.admin_notes}" if req.admin_notes else "")
    conn.execute("""
        INSERT INTO notifications (user_id, title, message)
        VALUES (?, ?, ?)
    """, (leave["staff_id"], notif_title, notif_msg))

    conn.commit()
    conn.close()

    log_audit_event(
        current_user,
        action="LEAVE_REVIEWED",
        entity="staff_leaves",
        entity_id=leave_id,
        details={
            "staff_id": leave["staff_id"],
            "staff_name": leave["staff_name"],
            "status": req.status,
            "leave_date": leave["leave_date"],
            "admin_notes": req.admin_notes
        }
    )

    return {
        "message": f"Leave request for {leave['staff_name']} marked as {req.status}.",
        "leave_id": leave_id,
        "status": req.status
    }

# ---------------------------------------------------------------------------
# 4. Employment Commitment (6 Months) & Resignation Notice (1 Month)
# ---------------------------------------------------------------------------

@router.post("/resignation")
def submit_resignation(req: ResignationSubmitRequest, current_user: dict = Depends(get_current_user)):
    """
    Staff submits formal exit / resignation notice.
    Enforces 6-month minimum commitment and 30-day notice period.
    """
    if current_user["role"] != "staff":
        raise HTTPException(403, "Only staff can submit resignation notices.")

    if not req.reason or len(req.reason.strip()) < 10:
        raise HTTPException(400, "Please provide a detailed reason for resignation (minimum 10 characters).")

    try:
        last_dt = datetime.strptime(req.proposed_last_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD.")

    today = date.today()
    notice_diff = (last_dt - today).days

    # 1. Enforce 30-day notice
    if notice_diff < 30:
        raise HTTPException(
            400,
            f"Job chhodne se kam se kam 1 mahina (30 din) pehle notice dena zaroori hai. "
            f"Selected last date gives only {notice_diff} day(s) notice. "
            f"Please select a date on or after {(today + timedelta(days=30)).isoformat()}."
        )

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (current_user["id"],)).fetchone()

    # 2. Check 6-month minimum tenure
    joining_str = user["joining_date"] or str(user["created_at"])[:10]
    try:
        join_dt = datetime.strptime(joining_str[:10], "%Y-%m-%d").date()
        months_served = (today - join_dt).days / 30.44
    except Exception:
        months_served = 0.0

    min_months = user["minimum_commitment_months"] or 6
    if months_served < min_months:
        if not req.emergency_justification or len(req.emergency_justification.strip()) < 15:
            conn.close()
            raise HTTPException(
                400,
                f"Aapne abhi tak minimum 6 mahine ka commitment poora nahi kiya hai ({months_served:.1f} of {min_months} months served). "
                "Kisi bade/critical reason ke bina 6 mahine se pehle resignation allow nahi hai. "
                "Kripya emergency justification (minimum 15 characters) provide karein."
            )

    full_reason = req.reason.strip()
    if req.emergency_justification:
        full_reason += f" [Early Exit Justification: {req.emergency_justification.strip()}]"

    conn.execute("""
        UPDATE users
        SET resignation_status='Notice_Served',
            resignation_notice_date=?,
            resignation_last_date=?,
            resignation_reason=?
        WHERE id=?
    """, (today.isoformat(), req.proposed_last_date, full_reason, current_user["id"]))

    # Notify admins
    admins = conn.execute("SELECT id FROM users WHERE role='admin'").fetchall()
    for a in admins:
        conn.execute("""
            INSERT INTO notifications (user_id, title, message)
            VALUES (?, '⚠️ Staff Resignation Notice', ?)
        """, (a["id"], f"Staff {current_user['name']} submitted resignation notice. Proposed last day: {req.proposed_last_date}."))

    conn.commit()
    conn.close()

    log_audit_event(
        current_user,
        action="STAFF_RESIGNATION_SUBMITTED",
        entity="users",
        entity_id=current_user["id"],
        details={
            "proposed_last_date": req.proposed_last_date,
            "months_served": round(months_served, 1),
            "reason": full_reason
        }
    )

    return {
        "message": f"Resignation notice submitted. Proposed last working day: {req.proposed_last_date}. Admin will review your notice.",
        "resignation_status": "Notice_Served"
    }

@router.put("/resignation/{staff_id}/review")
def review_resignation(staff_id: int, req: ResignationReviewRequest, current_user: dict = Depends(require_role("admin"))):
    """Admin reviews staff resignation request."""
    if req.status not in ("Approved", "Rejected"):
        raise HTTPException(400, "Status must be 'Approved' or 'Rejected'.")

    conn = get_db()
    staff = conn.execute("SELECT * FROM users WHERE id=? AND role='staff'", (staff_id,)).fetchone()
    if not staff:
        conn.close()
        raise HTTPException(404, "Staff not found.")

    conn.execute("UPDATE users SET resignation_status=? WHERE id=?", (req.status, staff_id))

    conn.execute("""
        INSERT INTO notifications (user_id, title, message)
        VALUES (?, 'Resignation Notice Update', ?)
    """, (staff_id, f"Your resignation notice has been {req.status.lower()} by Admin." + (f" Note: {req.admin_notes}" if req.admin_notes else "")))

    conn.commit()
    conn.close()

    log_audit_event(
        current_user,
        action="STAFF_RESIGNATION_REVIEWED",
        entity="users",
        entity_id=staff_id,
        details={"status": req.status, "admin_notes": req.admin_notes}
    )

    return {"message": f"Resignation for {staff['name']} marked as {req.status}."}

# ---------------------------------------------------------------------------
# 5. Admin Termination Notice (15-Day Rule)
# ---------------------------------------------------------------------------

@router.post("/termination-notice/{staff_id}")
def issue_termination_notice(staff_id: int, req: TerminationNoticeRequest, current_user: dict = Depends(require_role("admin"))):
    """
    Admin issues 15-day termination notice to a staff member.
    """
    if not req.reason or len(req.reason.strip()) < 5:
        raise HTTPException(400, "Reason is mandatory (minimum 5 characters).")

    conn = get_db()
    staff = conn.execute("SELECT * FROM users WHERE id=? AND role='staff'", (staff_id,)).fetchone()
    if not staff:
        conn.close()
        raise HTTPException(404, "Staff not found.")

    today = date.today()
    effective_date = today + timedelta(days=15)

    conn.execute("""
        UPDATE users
        SET termination_notice_date=?, termination_effective_date=?
        WHERE id=?
    """, (today.isoformat(), effective_date.isoformat(), staff_id))

    # Notify the staff member
    conn.execute("""
        INSERT INTO notifications (user_id, title, message)
        VALUES (?, 'Official Notice: Employment Termination Notice', ?)
    """, (staff_id, f"A 15-day termination notice has been issued. Effective last working date: {effective_date.isoformat()}. Reason: {req.reason.strip()}."))

    conn.commit()
    conn.close()

    log_audit_event(
        current_user,
        action="TERMINATION_NOTICE_ISSUED",
        entity="users",
        entity_id=staff_id,
        details={
            "staff_name": staff["name"],
            "notice_date": today.isoformat(),
            "effective_date": effective_date.isoformat(),
            "reason": req.reason.strip()
        }
    )

    return {
        "message": f"15-day termination notice issued to {staff['name']}. Effective termination date: {effective_date.isoformat()}.",
        "termination_notice_date": today.isoformat(),
        "termination_effective_date": effective_date.isoformat()
    }

# ---------------------------------------------------------------------------
# 6. Staff Bonuses (Performance & Festival Bonuses)
# ---------------------------------------------------------------------------

@router.post("/bonus")
def award_bonus(req: AwardBonusRequest, current_user: dict = Depends(require_role("admin"))):
    """
    Admin awards a performance or festival bonus to staff.
    """
    if req.amount <= 0:
        raise HTTPException(400, "Bonus amount must be greater than zero.")

    if not req.reason or len(req.reason.strip()) < 3:
        raise HTTPException(400, "Please provide a reason or festival name for the bonus.")

    conn = get_db()
    staff = conn.execute("SELECT * FROM users WHERE id=? AND role='staff'", (req.staff_id,)).fetchone()
    if not staff:
        conn.close()
        raise HTTPException(404, "Staff member not found.")

    cursor = conn.execute("""
        INSERT INTO staff_bonuses (staff_id, amount, bonus_type, reason, awarded_by)
        VALUES (?, ?, ?, ?, ?)
    """, (req.staff_id, req.amount, req.bonus_type, req.reason.strip(), current_user["id"]))
    bonus_id = cursor.lastrowid

    # Notify the staff member
    conn.execute("""
        INSERT INTO notifications (user_id, title, message)
        VALUES (?, '🎉 Bonus Awarded!', ?)
    """, (req.staff_id, f"Congratulations! You have been awarded a {req.bonus_type} of ₹{req.amount:,.2f} for '{req.reason.strip()}'."))

    conn.commit()
    conn.close()

    log_audit_event(
        current_user,
        action="BONUS_AWARDED",
        entity="staff_bonuses",
        entity_id=bonus_id,
        details={
            "staff_id": req.staff_id,
            "staff_name": staff["name"],
            "amount": req.amount,
            "bonus_type": req.bonus_type,
            "reason": req.reason.strip()
        }
    )

    return {
        "message": f"Bonus of ₹{req.amount:,.2f} awarded to {staff['name']} successfully!",
        "bonus_id": bonus_id
    }

@router.get("/bonuses/{staff_id}")
def get_staff_bonuses(staff_id: int, current_user: dict = Depends(get_current_user)):
    """View bonuses awarded to a staff member."""
    if current_user["role"] == "staff" and current_user["id"] != staff_id:
        raise HTTPException(403, "You can only view your own bonuses.")

    conn = get_db()
    bonuses = conn.execute("""
        SELECT sb.*, u.name as awarded_by_name
        FROM staff_bonuses sb
        LEFT JOIN users u ON sb.awarded_by = u.id
        WHERE sb.staff_id = ?
        ORDER BY sb.awarded_at DESC
    """, (staff_id,)).fetchall()
    conn.close()
    return [dict(b) for b in bonuses]

# ---------------------------------------------------------------------------
# 7. Monthly Payroll Calculation
# ---------------------------------------------------------------------------

@router.get("/payroll-calculation")
def calculate_monthly_payroll(
    month: Optional[str] = Query(None, description="Month format YYYY-MM, defaults to current month"),
    current_user: dict = Depends(require_role("admin"))
):
    """
    Transparent monthly payroll calculation for all staff members.
    Formula: Final Payout = Base Salary - Leave Deductions + Bonuses
    """
    target_month = month or date.today().strftime("%Y-%m")
    conn = get_db()

    staff_rows = conn.execute("SELECT * FROM users WHERE role='staff' ORDER BY id ASC").fetchall()
    payroll = []

    for s in staff_rows:
        sid = s["id"]
        base_salary = float(s["monthly_salary"] or 0.0)
        policy_days = int(s["salary_policy_days"] or 30)
        daily_rate = round(base_salary / policy_days, 2) if policy_days > 0 else 0.0

        # Approved leaves in month
        leave_data = conn.execute("""
            SELECT SUM(days) as total_days
            FROM staff_leaves
            WHERE staff_id=? AND status='Approved' AND strftime('%Y-%m', leave_date) = ?
        """, (sid, target_month)).fetchone()
        used_leaves = int(leave_data["total_days"] or 0)

        allowed_leaves = 4
        unpaid_leaves = max(0, used_leaves - allowed_leaves)
        leaves_remaining = max(0, allowed_leaves - used_leaves)
        deduction = round(unpaid_leaves * daily_rate, 2)

        # Bonuses in month
        bonus_data = conn.execute("""
            SELECT SUM(amount) as total_bonus
            FROM staff_bonuses
            WHERE staff_id=? AND strftime('%Y-%m', awarded_at) = ?
        """, (sid, target_month)).fetchone()
        bonuses = float(bonus_data["total_bonus"] or 0.0)

        final_payout = max(0.0, round(base_salary - deduction + bonuses, 2))

        payroll.append({
            "staff_id": sid,
            "staff_name": s["name"],
            "email": s["email"],
            "month": target_month,
            "base_salary": base_salary,
            "salary_policy_days": policy_days,
            "daily_rate": daily_rate,
            "allowed_leaves": allowed_leaves,
            "used_leaves": used_leaves,
            "leaves_remaining": leaves_remaining,
            "unpaid_leaves": unpaid_leaves,
            "leave_deduction": deduction,
            "bonuses": bonuses,
            "final_payout": final_payout,
            "is_active": s["is_active"] if s["is_active"] is not None else 1
        })

    conn.close()
    return {"month": target_month, "payroll": payroll}
