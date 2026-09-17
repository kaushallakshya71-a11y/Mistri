"""
Mistri Customer Support & Ticket System
Allows customers to raise tickets (SUP-XXXX), exchange messages with Admin/Staff,
and track resolution status (Open, In Progress, Resolved, Closed).
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from db.database import get_db
from middleware.auth import get_current_user, require_role
from utils.audit import log_audit_event

router = APIRouter(prefix="/api/support", tags=["support"])

# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------

class CreateTicketRequest(BaseModel):
    subject: str
    category: str = "General"  # Repair Delay | Payment Issue | Warranty Claim | Quality Complaint | General
    priority: str = "Medium"   # Low | Medium | High | Urgent
    repair_job_id: Optional[int] = None
    initial_message: str

class ReplyTicketRequest(BaseModel):
    message: str
    attachment_url: Optional[str] = None

class UpdateTicketStatusRequest(BaseModel):
    status: str  # Open | In Progress | Resolved | Closed
    notes: Optional[str] = None

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/tickets")
def create_ticket(req: CreateTicketRequest, current_user: dict = Depends(get_current_user)):
    """Customer raises a new support ticket."""
    if len(req.subject.strip()) < 3:
        raise HTTPException(400, "Subject must be at least 3 characters.")
    if len(req.initial_message.strip()) < 5:
        raise HTTPException(400, "Initial message must be at least 5 characters.")

    conn = get_db()

    # Optional: verify repair_job_id belongs to customer if provided
    if req.repair_job_id:
        job = conn.execute("SELECT id, customer_id FROM repair_jobs WHERE id=?", (req.repair_job_id,)).fetchone()
        if not job:
            conn.close()
            raise HTTPException(404, "Referenced repair job not found.")
        if current_user["role"] == "customer" and job["customer_id"] != current_user["id"]:
            conn.close()
            raise HTTPException(403, "You can only reference your own repair jobs.")

    year = datetime.now().year
    count_row = conn.execute("SELECT COUNT(*) FROM support_tickets").fetchone()
    count = (count_row[0] if count_row else 0) + 1
    ticket_code = f"SUP-{year}-{str(count).zfill(4)}"

    cursor = conn.execute("""
        INSERT INTO support_tickets (ticket_code, customer_id, repair_job_id, subject, category, priority, status)
        VALUES (?, ?, ?, ?, ?, ?, 'Open')
    """, (ticket_code, current_user["id"], req.repair_job_id, req.subject.strip(), req.category, req.priority))

    ticket_id = cursor.lastrowid

    # Insert first message
    conn.execute("""
        INSERT INTO support_ticket_messages (ticket_id, sender_id, sender_role, message)
        VALUES (?, ?, ?, ?)
    """, (ticket_id, current_user["id"], current_user["role"], req.initial_message.strip()))

    # Notify admins
    admins = conn.execute("SELECT id FROM users WHERE role='admin'").fetchall()
    for admin in admins:
        conn.execute("""
            INSERT INTO notifications (user_id, repair_job_id, title, message)
            VALUES (?, ?, ?, ?)
        """, (
            admin["id"],
            req.repair_job_id,
            f"New Support Ticket {ticket_code}",
            f"Customer {current_user['name']} opened ticket: {req.subject.strip()} [{req.priority}]"
        ))

    conn.commit()
    conn.close()

    log_audit_event(
        current_user,
        action="CREATE_SUPPORT_TICKET",
        entity="support_tickets",
        entity_id=ticket_id,
        details={"ticket_code": ticket_code, "subject": req.subject}
    )

    return {
        "message": "Support ticket created successfully",
        "ticket_id": ticket_id,
        "ticket_code": ticket_code,
        "status": "Open"
    }

@router.get("/tickets")
def list_tickets(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    category: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """List tickets. Customers only see their own; Staff and Admin see all."""
    conn = get_db()
    query = """
        SELECT st.*, c.name as customer_name, c.email as customer_email, c.phone as customer_phone,
               rj.repair_id,
               (SELECT COUNT(*) FROM support_ticket_messages WHERE ticket_id = st.id) as message_count
        FROM support_tickets st
        JOIN users c ON st.customer_id = c.id
        LEFT JOIN repair_jobs rj ON st.repair_job_id = rj.id
        WHERE 1=1
    """
    params = []

    if current_user["role"] == "customer":
        query += " AND st.customer_id = ?"
        params.append(current_user["id"])

    if status and status != "All":
        query += " AND st.status = ?"
        params.append(status)

    if priority and priority != "All":
        query += " AND st.priority = ?"
        params.append(priority)

    if category and category != "All":
        query += " AND st.category = ?"
        params.append(category)

    query += " ORDER BY st.updated_at DESC, st.created_at DESC"
    tickets = conn.execute(query, tuple(params)).fetchall()
    conn.close()

    return [dict(t) for t in tickets]

@router.get("/tickets/{ticket_id}")
def get_ticket_details(ticket_id: int, current_user: dict = Depends(get_current_user)):
    """Fetch ticket details and full conversation history."""
    conn = get_db()
    ticket = conn.execute("""
        SELECT st.*, c.name as customer_name, c.email as customer_email, c.phone as customer_phone,
               rj.repair_id, d.device_type, d.brand, d.model
        FROM support_tickets st
        JOIN users c ON st.customer_id = c.id
        LEFT JOIN repair_jobs rj ON st.repair_job_id = rj.id
        LEFT JOIN devices d ON rj.device_id = d.id
        WHERE st.id = ?
    """, (ticket_id,)).fetchone()

    if not ticket:
        conn.close()
        raise HTTPException(404, "Ticket not found.")

    if current_user["role"] == "customer" and ticket["customer_id"] != current_user["id"]:
        conn.close()
        raise HTTPException(403, "Access denied. You can only view your own tickets.")

    messages = conn.execute("""
        SELECT stm.*, u.name as sender_name, u.role as sender_role_name
        FROM support_ticket_messages stm
        JOIN users u ON stm.sender_id = u.id
        WHERE stm.ticket_id = ?
        ORDER BY stm.created_at ASC
    """, (ticket_id,)).fetchall()

    conn.close()

    result = dict(ticket)
    result["messages"] = [dict(m) for m in messages]
    return result

@router.post("/tickets/{ticket_id}/reply")
def reply_ticket(ticket_id: int, req: ReplyTicketRequest, current_user: dict = Depends(get_current_user)):
    """Add a reply to a support ticket."""
    if len(req.message.strip()) < 1:
        raise HTTPException(400, "Message cannot be empty.")

    conn = get_db()
    ticket = conn.execute("SELECT * FROM support_tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not ticket:
        conn.close()
        raise HTTPException(404, "Ticket not found.")

    if current_user["role"] == "customer" and ticket["customer_id"] != current_user["id"]:
        conn.close()
        raise HTTPException(403, "Access denied.")

    if ticket["status"] == "Closed":
        conn.close()
        raise HTTPException(400, "Cannot reply to a closed ticket. Please open a new ticket.")

    cursor = conn.execute("""
        INSERT INTO support_ticket_messages (ticket_id, sender_id, sender_role, message, attachment_url)
        VALUES (?, ?, ?, ?, ?)
    """, (ticket_id, current_user["id"], current_user["role"], req.message.strip(), req.attachment_url))
    msg_id = cursor.lastrowid

    # Update ticket status if customer replied or staff/admin replied
    new_status = ticket["status"]
    if current_user["role"] in ("admin", "staff") and ticket["status"] == "Open":
        new_status = "In Progress"
    elif current_user["role"] == "customer" and ticket["status"] == "Resolved":
        new_status = "In Progress"  # Reopen if customer replies after resolve

    conn.execute("""
        UPDATE support_tickets SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
    """, (new_status, ticket_id))

    # Notifications
    if current_user["role"] == "customer":
        # Notify admins
        admins = conn.execute("SELECT id FROM users WHERE role='admin'").fetchall()
        for a in admins:
            conn.execute("""
                INSERT INTO notifications (user_id, repair_job_id, title, message)
                VALUES (?, ?, ?, ?)
            """, (a["id"], ticket["repair_job_id"], f"Update on {ticket['ticket_code']}", f"Customer replied: {req.message.strip()[:60]}..."))
    else:
        # Notify customer
        conn.execute("""
            INSERT INTO notifications (user_id, repair_job_id, title, message)
            VALUES (?, ?, ?, ?)
        """, (ticket["customer_id"], ticket["repair_job_id"], f"Reply on {ticket['ticket_code']}", f"Support team replied: {req.message.strip()[:60]}..."))

    conn.commit()
    conn.close()

    log_audit_event(
        current_user,
        action="REPLY_SUPPORT_TICKET",
        entity="support_tickets",
        entity_id=ticket_id,
        details={"message_id": msg_id, "snippet": req.message.strip()[:100]}
    )

    return {
        "message": "Reply sent successfully",
        "message_id": msg_id,
        "status": new_status
    }

@router.put("/tickets/{ticket_id}/status")
def update_ticket_status(
    ticket_id: int,
    req: UpdateTicketStatusRequest,
    current_user: dict = Depends(require_role("admin"))
):
    """Admin updates ticket status (Open, In Progress, Resolved, Closed)."""
    valid_statuses = ["Open", "In Progress", "Resolved", "Closed"]
    if req.status not in valid_statuses:
        raise HTTPException(400, f"Status must be one of: {', '.join(valid_statuses)}")

    conn = get_db()
    ticket = conn.execute("SELECT * FROM support_tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not ticket:
        conn.close()
        raise HTTPException(404, "Ticket not found.")

    conn.execute("""
        UPDATE support_tickets SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
    """, (req.status, ticket_id))

    # Add system notification message in thread
    status_msg = f"Status changed to '{req.status}' by Admin {current_user['name']}."
    if req.notes and req.notes.strip():
        status_msg += f" Note: {req.notes.strip()}"

    conn.execute("""
        INSERT INTO support_ticket_messages (ticket_id, sender_id, sender_role, message)
        VALUES (?, ?, 'admin', ?)
    """, (ticket_id, current_user["id"], status_msg))

    # Notify customer
    conn.execute("""
        INSERT INTO notifications (user_id, repair_job_id, title, message)
        VALUES (?, ?, ?, ?)
    """, (
        ticket["customer_id"],
        ticket["repair_job_id"],
        f"Ticket {ticket['ticket_code']} Status: {req.status}",
        f"Your ticket '{ticket['subject']}' status is now '{req.status}'."
    ))

    conn.commit()
    conn.close()

    log_audit_event(
        current_user,
        action="UPDATE_SUPPORT_TICKET_STATUS",
        entity="support_tickets",
        entity_id=ticket_id,
        details={"old_status": ticket["status"], "new_status": req.status, "notes": req.notes}
    )

    return {"message": f"Ticket status updated to {req.status}"}
