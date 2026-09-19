"""
Mistri Bills & PDF Invoice Routes
Enhanced with Dynamic UPI QR Generation, Online Payment Recording, and Embedded Invoice QR.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from db.database import get_db
from middleware.auth import get_current_user, require_role
from utils.qrcode_gen import generate_qr_base64
from utils.audit import log_audit_event
from datetime import datetime
import io
import re
import qrcode
import urllib.parse

router = APIRouter(prefix="/api/bills", tags=["bills"])

UTR_PATTERN = re.compile(r'^[A-Za-z0-9]{10,22}$')

class BillCreate(BaseModel):
    repair_job_id: int
    labour_charge: float = 0
    parts_cost: float = 0
    discount: float = 0
    tax_rate: float = 0.09  # 9% GST
    upi_id: Optional[str] = None  # Real shop UPI ID (e.g. 9876543210@paytm, name@okhdfcbank)

class OnlinePaymentRequest(BaseModel):
    payment_method: str = "UPI"  # UPI | Card | NetBanking | Razorpay
    transaction_id: str

class CashPaymentRequest(BaseModel):
    notes: Optional[str] = None

class PaymentVerifyRequest(BaseModel):
    action: str  # Approve | Reject | Refund
    notes: Optional[str] = None

class InvoiceActionRequest(BaseModel):
    reason: str

class CreateOfferRequest(BaseModel):
    code: str
    title: str
    description: Optional[str] = None
    discount_type: str = "percentage"  # percentage | flat
    discount_value: float
    min_bill_amount: float = 0
    max_discount: Optional[float] = None
    valid_from: Optional[str] = None   # YYYY-MM-DD
    valid_until: Optional[str] = None  # YYYY-MM-DD
    target_customer_id: Optional[int] = None

class ApplyOfferRequest(BaseModel):
    offer_code: Optional[str] = None
    coupon_code: Optional[str] = None

@router.post("/generate")
def generate_bill(req: BillCreate, current_user: dict = Depends(require_role("admin"))):
    conn = get_db()
    job = conn.execute("""
        SELECT rj.*, c.name as customer_name, c.phone as customer_phone, c.email as customer_email,
               d.device_type, d.brand, d.model
        FROM repair_jobs rj JOIN users c ON rj.customer_id=c.id
        JOIN devices d ON rj.device_id=d.id
        WHERE rj.id=?
    """, (req.repair_job_id,)).fetchone()
    if not job:
        conn.close()
        raise HTTPException(404, "Repair job not found")

    # Check if bill already exists
    existing = conn.execute("SELECT id FROM bills WHERE repair_job_id=?", (req.repair_job_id,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(400, "Bill already generated for this job.")

    subtotal = req.labour_charge + req.parts_cost
    taxable = max(0, subtotal - req.discount)
    tax = round(taxable * req.tax_rate, 2)
    total = round(taxable + tax, 2)

    year = datetime.now().year
    count = conn.execute("SELECT COUNT(*) FROM bills").fetchone()[0] + 1
    bill_number = f"BILL-{year}-{str(count).zfill(4)}"

    # Generate standard NPCI UPI Intent string with real UPI ID support
    job_shop_id = job["shop_id"] if "shop_id" in job.keys() and job["shop_id"] else 1
    if req.upi_id and req.upi_id.strip():
        upi_pa = req.upi_id.strip()
        # Save to shops table so it becomes default
        conn.execute("UPDATE shops SET upi_id=? WHERE id=?", (upi_pa, job_shop_id))
    else:
        shop_branch = conn.execute("SELECT upi_id FROM shops WHERE id=?", (job_shop_id,)).fetchone()
        upi_pa = shop_branch["upi_id"] if shop_branch and shop_branch["upi_id"] else "mistri@upi"

    upi_intent = (
        f"upi://pay?pa={upi_pa}"
        f"&pn={urllib.parse.quote('Mistri Electrical/Electronic')}"
        f"&am={total:.2f}"
        f"&cu=INR"
        f"&tn={urllib.parse.quote(f'Invoice {bill_number}')}"
    )

    cursor = conn.execute("""
        INSERT INTO bills (bill_number, repair_job_id, customer_id, shop_id, labour_charge,
                          parts_cost, discount, tax, total_amount, payment_status, upi_qr_url)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (bill_number, req.repair_job_id, job["customer_id"], job_shop_id,
          req.labour_charge, req.parts_cost, req.discount, tax, total, "Pending", upi_intent))

    conn.execute("UPDATE repair_jobs SET actual_cost=? WHERE id=?", (total, req.repair_job_id))
    conn.commit()
    bill_id = cursor.lastrowid
    conn.close()
    return {"bill_id": bill_id, "bill_number": bill_number, "total": total, "upi_intent": upi_intent}

@router.get("/")
def list_bills(current_user: dict = Depends(get_current_user)):
    conn = get_db()
    if current_user["role"] == "customer":
        bills = conn.execute("""
            SELECT b.*, rj.repair_id, d.device_type, d.brand, d.model
            FROM bills b JOIN repair_jobs rj ON b.repair_job_id=rj.id
            JOIN devices d ON rj.device_id=d.id
            WHERE b.customer_id=? ORDER BY b.created_at DESC
        """, (current_user["id"],)).fetchall()
    else:
        bills = conn.execute("""
            SELECT b.*, rj.repair_id, d.device_type, d.brand, d.model, u.name as customer_name
            FROM bills b JOIN repair_jobs rj ON b.repair_job_id=rj.id
            JOIN devices d ON rj.device_id=d.id
            JOIN users u ON b.customer_id=u.id
            ORDER BY b.created_at DESC
        """).fetchall()
    conn.close()
    return [dict(b) for b in bills]

@router.get("/{bill_id}")
def get_bill(bill_id: int, current_user: dict = Depends(get_current_user)):
    conn = get_db()
    bill = conn.execute("""
        SELECT b.*, rj.repair_id, rj.problem_description, rj.parts_used, rj.technician_notes,
               d.device_type, d.brand, d.model,
               u.name as customer_name, u.phone as customer_phone, u.email as customer_email
        FROM bills b JOIN repair_jobs rj ON b.repair_job_id=rj.id
        JOIN devices d ON rj.device_id=d.id
        JOIN users u ON b.customer_id=u.id
        WHERE b.id=?
    """, (bill_id,)).fetchone()
    conn.close()
    if not bill:
        raise HTTPException(404, "Bill not found")

    if current_user["role"] == "customer" and bill["customer_id"] != current_user["id"]:
        raise HTTPException(403, "Access denied. You can only access your own bills.")

    return dict(bill)

@router.get("/{bill_id}/upi-qr")
def get_bill_upi_qr(bill_id: int, current_user: dict = Depends(get_current_user)):
    """Generate dynamic scannable UPI payment QR code for a bill."""
    conn = get_db()
    bill = conn.execute("SELECT * FROM bills WHERE id=?", (bill_id,)).fetchone()
    conn.close()
    if not bill:
        raise HTTPException(404, "Bill not found")

    if current_user["role"] == "customer" and bill["customer_id"] != current_user["id"]:
        raise HTTPException(403, "Access denied. You can only access your own bills.")

    upi_intent = bill["upi_qr_url"]
    if not upi_intent:
        upi_intent = f"upi://pay?pa=mistri@upi&pn=Mistri%20Electrical%2FElectronic&am={bill['total_amount']:.2f}&cu=INR&tn=Invoice-{bill['bill_number']}"

    qr_base64 = generate_qr_base64(upi_intent)
    return {
        "bill_id": bill_id,
        "bill_number": bill["bill_number"],
        "total_amount": bill["total_amount"],
        "payment_status": bill["payment_status"],
        "upi_intent": upi_intent,
        "qr_code": qr_base64
    }

@router.post("/{bill_id}/pay-online")
def record_online_payment(bill_id: int, req: OnlinePaymentRequest, current_user: dict = Depends(get_current_user)):
    """
    Customer submits online payment reference (UPI/Card).
    Sets status to 'Pending' awaiting Admin verification to prevent client-side fraud.
    If submitted directly by Admin, it is instantly approved.
    """
    conn = get_db()
    bill = conn.execute("SELECT * FROM bills WHERE id=?", (bill_id,)).fetchone()
    if not bill:
        conn.close()
        raise HTTPException(404, "Bill not found")

    if current_user["role"] == "customer" and bill["customer_id"] != current_user["id"]:
        conn.close()
        raise HTTPException(403, "Access denied. You can only submit payment for your own bills.")

    if bill["payment_status"] == "Paid":
        conn.close()
        raise HTTPException(400, "This bill has already been verified and marked as Paid.")

    txn_id = req.transaction_id.strip()
    if not UTR_PATTERN.match(txn_id) or len(set(txn_id.lower())) <= 2:
        conn.close()
        raise HTTPException(400, "Invalid UTR format. Please enter a valid 10-22 character alphanumeric reference.")

    # Prevent duplicate UTR submission
    dup = conn.execute("SELECT id FROM payments WHERE transaction_id = ? AND status != 'Failed'", (txn_id,)).fetchone()
    if dup:
        conn.close()
        raise HTTPException(400, f"UTR / Reference '{txn_id}' has already been submitted or verified.")

    is_admin = (current_user.get("role") == "admin")
    new_status = "Paid" if is_admin else "Pending"
    payment_status_record = "Confirmed" if is_admin else "Pending"

    conn.execute("""
        UPDATE bills SET payment_status=?, payment_method=?, transaction_id=? WHERE id=?
    """, (new_status, req.payment_method, txn_id, bill_id))

    cursor = conn.execute("""
        INSERT INTO payments (bill_id, amount, payment_method, transaction_id, status, verified_by, verified_at, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        bill_id,
        bill["total_amount"],
        req.payment_method,
        txn_id,
        payment_status_record,
        current_user["id"] if is_admin else None,
        datetime.now().isoformat() if is_admin else None,
        "Verified by Admin" if is_admin else "Submitted by customer, awaiting admin verification"
    ))
    payment_id = cursor.lastrowid

    if is_admin:
        # Update repair job status to Completed
        conn.execute("UPDATE repair_jobs SET status='Completed', updated_at=CURRENT_TIMESTAMP WHERE id=?", (bill["repair_job_id"],))

        # Auto-activate 180-day warranty
        existing_war = conn.execute("SELECT id FROM warranties WHERE repair_job_id=?", (bill["repair_job_id"],)).fetchone()
        if not existing_war:
            conn.execute("""
                INSERT INTO warranties (repair_job_id, customer_id, duration_days, start_date, end_date, covered_terms, status)
                VALUES (?, ?, 180, DATE('now'), DATE('now', '+180 days'), '180-day comprehensive repair warranty covering parts and labour', 'Active')
            """, (bill["repair_job_id"], bill["customer_id"]))

        conn.execute("""
            INSERT INTO notifications (user_id, repair_job_id, title, message)
            VALUES (?, ?, 'Payment Approved 🎉', ?)
        """, (bill["customer_id"], bill["repair_job_id"], f"Payment of ₹{bill['total_amount']:.2f} verified! Your 180-day warranty is now active."))
    else:
        # Notify admins that verification is needed
        admins = conn.execute("SELECT id FROM users WHERE role='admin'").fetchall()
        for a in admins:
            conn.execute("""
                INSERT INTO notifications (user_id, repair_job_id, title, message)
                VALUES (?, ?, 'Payment Verification Needed 💳', ?)
            """, (a["id"], bill["repair_job_id"], f"Customer submitted UPI payment of ₹{bill['total_amount']:.2f} for Bill {bill['bill_number']} (Ref: {txn_id})."))

    conn.commit()
    conn.close()

    log_audit_event(
        current_user,
        action="ONLINE_PAYMENT_SUBMITTED" if not is_admin else "ONLINE_PAYMENT_VERIFIED",
        entity="bills",
        entity_id=bill_id,
        details={"transaction_id": txn_id, "amount": bill["total_amount"], "status": new_status}
    )

    msg = "Payment recorded and verified successfully." if is_admin else "Payment reference submitted! Verification pending by Admin."
    return {
        "message": msg,
        "bill_id": bill_id,
        "payment_status": new_status,
        "transaction_id": txn_id
    }

@router.post("/{bill_id}/cash-payment")
def record_cash_payment(bill_id: int, req: CashPaymentRequest, current_user: dict = Depends(get_current_user)):
    """
    Staff or Admin records physical cash collected from customer.
    Records collected_by staff ID for accountability and reporting.
    """
    if current_user["role"] not in ("staff", "admin"):
        raise HTTPException(403, "Only staff or admin can record cash collections.")

    conn = get_db()
    bill = conn.execute("SELECT * FROM bills WHERE id=?", (bill_id,)).fetchone()
    if not bill:
        conn.close()
        raise HTTPException(404, "Bill not found")

    if bill["payment_status"] == "Paid":
        conn.close()
        raise HTTPException(400, "This bill has already been marked as Paid.")

    year_str = datetime.now().strftime("%Y%m%d%H%M%S")
    cash_txn_id = f"CASH-{bill['bill_number']}-{year_str}"
    notes = req.notes or f"Cash collected by {current_user['name']} ({current_user['role'].title()})"

    conn.execute("""
        UPDATE bills SET payment_status='Paid', payment_method='Cash', transaction_id=?, notes=? WHERE id=?
    """, (cash_txn_id, notes, bill_id))

    cursor = conn.execute("""
        INSERT INTO payments (bill_id, amount, payment_method, transaction_id, status, collected_by, verified_by, verified_at, notes)
        VALUES (?, ?, 'Cash', ?, 'Confirmed', ?, ?, CURRENT_TIMESTAMP, ?)
    """, (bill_id, bill["total_amount"], cash_txn_id, current_user["id"], current_user["id"], notes))
    payment_id = cursor.lastrowid

    # Update repair job to Completed
    conn.execute("UPDATE repair_jobs SET status='Completed', updated_at=CURRENT_TIMESTAMP WHERE id=?", (bill["repair_job_id"],))

    # Activate 180-day warranty
    existing_war = conn.execute("SELECT id FROM warranties WHERE repair_job_id=?", (bill["repair_job_id"],)).fetchone()
    if not existing_war:
        conn.execute("""
            INSERT INTO warranties (repair_job_id, customer_id, duration_days, start_date, end_date, covered_terms, status)
            VALUES (?, ?, 180, DATE('now'), DATE('now', '+180 days'), '180-day comprehensive repair warranty covering parts and labour', 'Active')
        """, (bill["repair_job_id"], bill["customer_id"]))

    # Notify customer
    conn.execute("""
        INSERT INTO notifications (user_id, repair_job_id, title, message)
        VALUES (?, ?, 'Cash Payment Received 🎉', ?)
    """, (bill["customer_id"], bill["repair_job_id"], f"Cash payment of ₹{bill['total_amount']:.2f} received by technician {current_user['name']}! Warranty is now active."))

    conn.commit()
    conn.close()

    log_audit_event(
        current_user,
        action="CASH_PAYMENT_COLLECTED",
        entity="payments",
        entity_id=payment_id,
        details={"bill_id": bill_id, "amount": bill["total_amount"], "collected_by": current_user["id"], "staff_name": current_user["name"]}
    )

    return {
        "message": "Cash payment recorded successfully",
        "bill_id": bill_id,
        "payment_status": "Paid",
        "collected_by": current_user["name"],
        "transaction_id": cash_txn_id
    }

@router.post("/{bill_id}/verify-payment")
def verify_payment(bill_id: int, req: PaymentVerifyRequest, current_user: dict = Depends(require_role("admin"))):
    """
    Admin verifies pending UPI/Online payments: Approve, Reject, or Refund.
    """
    action = req.action.strip().capitalize()
    if action not in ("Approve", "Reject", "Refund"):
        raise HTTPException(400, "Action must be one of: Approve, Reject, Refund")

    conn = get_db()
    bill = conn.execute("SELECT * FROM bills WHERE id=?", (bill_id,)).fetchone()
    if not bill:
        conn.close()
        raise HTTPException(404, "Bill not found")

    if action == "Approve":
        conn.execute("""
            UPDATE bills SET payment_status='Paid' WHERE id=?
        """, (bill_id,))

        conn.execute("""
            UPDATE payments SET status='Confirmed', verified_by=?, verified_at=CURRENT_TIMESTAMP, notes=?
            WHERE bill_id=? AND status='Pending'
        """, (current_user["id"], req.notes or "Payment verified by Admin", bill_id))

        # Complete repair job
        conn.execute("UPDATE repair_jobs SET status='Completed', updated_at=CURRENT_TIMESTAMP WHERE id=?", (bill["repair_job_id"],))

        # Activate warranty
        existing_war = conn.execute("SELECT id FROM warranties WHERE repair_job_id=?", (bill["repair_job_id"],)).fetchone()
        if not existing_war:
            conn.execute("""
                INSERT INTO warranties (repair_job_id, customer_id, duration_days, start_date, end_date, covered_terms, status)
                VALUES (?, ?, 180, DATE('now'), DATE('now', '+180 days'), '180-day comprehensive repair warranty covering parts and labour', 'Active')
            """, (bill["repair_job_id"], bill["customer_id"]))

        # Customer notification
        conn.execute("""
            INSERT INTO notifications (user_id, repair_job_id, title, message)
            VALUES (?, ?, 'Payment Approved 🎉', ?)
        """, (bill["customer_id"], bill["repair_job_id"], f"Your payment of ₹{bill['total_amount']:.2f} has been verified by Admin. 180-day warranty is now active!"))

    elif action == "Reject":
        if not req.notes or len(req.notes.strip()) < 3:
            conn.close()
            raise HTTPException(400, "A clear rejection reason (min 3 characters) is required when rejecting a payment.")

        conn.execute("""
            UPDATE bills SET payment_status='Failed', notes=? WHERE id=?
        """, (req.notes.strip(), bill_id))

        conn.execute("""
            UPDATE payments SET status='Failed', notes=? WHERE bill_id=? AND status='Pending'
        """, (req.notes.strip(), bill_id))

        conn.execute("""
            INSERT INTO notifications (user_id, repair_job_id, title, message)
            VALUES (?, ?, 'Payment Verification Failed ⚠️', ?)
        """, (bill["customer_id"], bill["repair_job_id"], f"Payment verification for Bill {bill['bill_number']} was unsuccessful. Reason: {req.notes.strip()}. Please retry payment."))

    elif action == "Refund":
        conn.execute("""
            UPDATE bills SET payment_status='Refunded', notes=? WHERE id=?
        """, (req.notes or "Refunded by Admin", bill_id))

        conn.execute("""
            UPDATE payments SET status='Refunded', notes=? WHERE bill_id=?
        """, (req.notes or "Refunded by Admin", bill_id))

        conn.execute("""
            INSERT INTO notifications (user_id, repair_job_id, title, message)
            VALUES (?, ?, 'Payment Refunded ℹ️', ?)
        """, (bill["customer_id"], bill["repair_job_id"], f"Refund processed for Bill {bill['bill_number']} (₹{bill['total_amount']:.2f}). Reason: {req.notes or 'Administrative refund'}."))

    conn.commit()
    conn.close()

    log_audit_event(
        current_user,
        action=f"PAYMENT_{action.upper()}",
        entity="bills",
        entity_id=bill_id,
        details={"action": action, "notes": req.notes, "amount": bill["total_amount"]}
    )

    return {"message": f"Payment {action.lower()}d successfully", "bill_id": bill_id, "action": action}

@router.get("/{bill_id}/pdf")
def download_invoice_pdf(bill_id: int, current_user: dict = Depends(get_current_user)):
    """Generate and stream professional PDF invoice with embedded UPI QR Code."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image as RLImage
    from reportlab.lib.units import cm
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT

    conn = get_db()
    bill = conn.execute("""
        SELECT b.*, rj.repair_id, rj.problem_description, rj.parts_used, rj.technician_notes,
               d.device_type, d.brand, d.model,
               u.name as customer_name, u.phone as customer_phone, u.email as customer_email
        FROM bills b JOIN repair_jobs rj ON b.repair_job_id=rj.id
        JOIN devices d ON rj.device_id=d.id
        JOIN users u ON b.customer_id=u.id
        WHERE b.id=?
    """, (bill_id,)).fetchone()
    conn.close()

    if not bill:
        raise HTTPException(404, "Bill not found")

    if current_user["role"] == "customer" and bill["customer_id"] != current_user["id"]:
        raise HTTPException(403, "Access denied. You can only download your own invoice.")

    bill = dict(bill)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.8*cm, leftMargin=1.8*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=24, textColor=colors.HexColor('#6C63FF'), alignment=TA_CENTER)
    subtitle_style = ParagraphStyle('Sub', parent=styles['Normal'], fontSize=10, textColor=colors.gray, alignment=TA_CENTER)
    label_style = ParagraphStyle('Label', parent=styles['Normal'], fontSize=9, textColor=colors.gray)
    value_style = ParagraphStyle('Value', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold')

    elements = []

    # Header
    elements.append(Paragraph("⚡ MISTRI ELECTRICAL/ELECTRONIC", title_style))
    elements.append(Paragraph("Smart Electrical/Electronic & Appliance Repair Management System", subtitle_style))
    elements.append(Spacer(1, 0.3*cm))
    elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#6C63FF')))
    elements.append(Spacer(1, 0.3*cm))

    # Meta table
    customer_data = [
        [Paragraph("<b>CUSTOMER DETAILS</b>", label_style), Paragraph("<b>DEVICE & JOB INFO</b>", label_style)],
        [Paragraph(f"Name: {bill['customer_name']}", value_style), Paragraph(f"Repair ID: {bill['repair_id']}", value_style)],
        [Paragraph(f"Phone: {bill.get('customer_phone') or 'N/A'}", label_style), Paragraph(f"Device: {bill['brand']} {bill['model']} ({bill['device_type']})", label_style)],
        [Paragraph(f"Bill Date: {bill['created_at'][:10]}", label_style), Paragraph(f"Bill Number: {bill['bill_number']}", value_style)],
    ]
    elements.append(Table(customer_data, colWidths=[8.5*cm, 8.5*cm]))
    elements.append(Spacer(1, 0.4*cm))

    # Line items
    item_rows = [
        [Paragraph("<b>Description</b>", label_style), Paragraph("<b>Amount (INR)</b>", ParagraphStyle('r', parent=label_style, alignment=TA_RIGHT))]
    ]
    item_rows.append([Paragraph("Labour & Service Charges", styles['Normal']), Paragraph(f"₹{bill['labour_charge']:,.2f}", ParagraphStyle('r', parent=styles['Normal'], alignment=TA_RIGHT))])
    item_rows.append([Paragraph("Spare Parts & Components", styles['Normal']), Paragraph(f"₹{bill['parts_cost']:,.2f}", ParagraphStyle('r', parent=styles['Normal'], alignment=TA_RIGHT))])
    if bill['discount'] > 0:
        item_rows.append([Paragraph("Special Discount", styles['Normal']), Paragraph(f"- ₹{bill['discount']:,.2f}", ParagraphStyle('r', parent=styles['Normal'], alignment=TA_RIGHT))])
    item_rows.append([Paragraph("GST / Taxes (9%)", styles['Normal']), Paragraph(f"₹{bill['tax']:,.2f}", ParagraphStyle('r', parent=styles['Normal'], alignment=TA_RIGHT))])
    item_rows.append([Paragraph("<b>TOTAL PAYABLE</b>", value_style), Paragraph(f"<b>₹{bill['total_amount']:,.2f}</b>", ParagraphStyle('r', parent=value_style, alignment=TA_RIGHT))])

    table = Table(item_rows, colWidths=[12*cm, 5*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F4F4F9')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('LINEBELOW', (0,0), (-1,0), 1, colors.HexColor('#6C63FF')),
        ('LINEBELOW', (0,-1), (-1,-1), 1.5, colors.HexColor('#6C63FF')),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.4*cm))

    # Payment status & Embedded UPI QR Code
    is_void = (bill.get('is_void') == 1 or bill['payment_status'] == 'Void')
    is_cancelled = (bill.get('is_cancelled') == 1 or bill['payment_status'] == 'Cancelled')
    is_paid = (bill['payment_status'] == 'Paid')
    
    if is_void:
        status_text = "<font color='#E74C3C'><b>PAYMENT STATUS: VOID (INVOICE VOIDED)</b></font>"
    elif is_cancelled:
        status_text = "<font color='#E74C3C'><b>PAYMENT STATUS: CANCELLED</b></font>"
    elif is_paid:
        status_text = "<font color='#27AE60'><b>PAYMENT STATUS: PAID</b></font>"
    else:
        status_text = f"<font color='#E67E22'><b>PAYMENT STATUS: {bill['payment_status'].upper()}</b></font>"
    elements.append(Paragraph(status_text, styles['Normal']))

    if not is_paid and not is_void and not is_cancelled:
        # Embed Dynamic Scannable UPI QR Code in PDF!
        upi_url = dict(bill).get("upi_qr_url") or f"upi://pay?pa=mistri@upi&pn=Mistri%20Electrical%2FElectronic&am={bill['total_amount']:.2f}&cu=INR&tn=Invoice-{bill['bill_number']}"
        qr = qrcode.make(upi_url)
        qr_buf = io.BytesIO()
        qr.save(qr_buf, format="PNG")
        qr_buf.seek(0)

        qr_block = [
            [
                RLImage(qr_buf, width=3.2*cm, height=3.2*cm),
                Paragraph("<b>⚡ Instant UPI Payment</b><br/><br/>Scan this QR using Google Pay, PhonePe, Paytm, or BHIM to pay instantly.<br/>Amount: <b>₹" + f"{bill['total_amount']:,.2f}" + "</b>", subtitle_style)
            ]
        ]
        qr_table = Table(qr_block, colWidths=[3.5*cm, 13.5*cm])
        qr_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#FAF9FE')),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#E2DEFF')),
            ('PADDING', (0,0), (-1,-1), 6)
        ]))
        elements.append(Spacer(1, 0.3*cm))
        elements.append(qr_table)

    elements.append(Spacer(1, 0.4*cm))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#CCCCCC')))
    elements.append(Spacer(1, 0.2*cm))
    elements.append(Paragraph("Thank you for choosing Mistri! 🔧 Trust & Quality Guaranteed.", subtitle_style))
    elements.append(Paragraph("Support: support@mistri.com | Phone: +91-9800000001", subtitle_style))

    doc.build(elements)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Invoice_{bill['bill_number']}.pdf"}
    )

@router.post("/{bill_id}/pay")
def mark_paid(bill_id: int, current_user: dict = Depends(require_role("admin"))):
    conn = get_db()
    conn.execute("UPDATE bills SET payment_status='Paid' WHERE id=?", (bill_id,))
    conn.execute("INSERT INTO payments (bill_id, amount, payment_method) SELECT id, total_amount, 'Cash' FROM bills WHERE id=?", (bill_id,))
    conn.commit()
    conn.close()
    return {"message": "Payment recorded"}

def calculate_bill_totals(labour_charge: float, parts_cost: float, discount: float, tax_rate: float = 0.09):
    subtotal = round(float(labour_charge) + float(parts_cost), 2)
    effective_discount = round(min(subtotal, max(0.0, float(discount))), 2)
    taxable = round(subtotal - effective_discount, 2)
    tax = round(taxable * tax_rate, 2)
    total = round(taxable + tax, 2)
    return subtotal, effective_discount, taxable, tax, total

class BillUpdate(BaseModel):
    labour_charge: Optional[float] = None
    parts_cost: Optional[float] = None
    discount: Optional[float] = None
    tax_rate: Optional[float] = None
    payment_status: Optional[str] = None
    notes: Optional[str] = None

@router.put("/{bill_id}")
def update_bill(bill_id: int, req: BillUpdate, current_user: dict = Depends(require_role("admin"))):
    """Admin can edit bill charges and payment status. Modifying financial values of settled or void invoices is blocked."""
    conn = get_db()
    bill = conn.execute("SELECT * FROM bills WHERE id=?", (bill_id,)).fetchone()
    if not bill:
        conn.close()
        raise HTTPException(404, "Bill not found")

    bill_dict = dict(bill)
    is_settled_or_inactive = (
        bill["payment_status"] in ("Paid", "Void", "Cancelled") or
        bill_dict.get("is_void") == 1 or
        bill_dict.get("is_cancelled") == 1
    )

    if is_settled_or_inactive:
        if (req.labour_charge is not None and req.labour_charge != bill["labour_charge"]) or \
           (req.parts_cost is not None and req.parts_cost != bill["parts_cost"]) or \
           (req.discount is not None and req.discount != bill["discount"]) or \
           (req.tax_rate is not None and req.tax_rate != 0.09):
            conn.close()
            raise HTTPException(400, "Cannot modify financial figures of a Paid, Void, or Cancelled invoice.")

    labour = req.labour_charge if req.labour_charge is not None else bill["labour_charge"]
    parts = req.parts_cost if req.parts_cost is not None else bill["parts_cost"]
    discount = req.discount if req.discount is not None else bill["discount"]
    tax_rate = req.tax_rate if req.tax_rate is not None else 0.09
    subtotal, effective_discount, taxable, tax, total = calculate_bill_totals(labour, parts, discount, tax_rate)
    status = req.payment_status or bill["payment_status"]
    notes = req.notes if req.notes is not None else bill["notes"]

    conn.execute("""
        UPDATE bills SET labour_charge=?, parts_cost=?, discount=?, tax=?,
        total_amount=?, payment_status=?, notes=? WHERE id=?
    """, (labour, parts, effective_discount, tax, total, status, notes, bill_id))
    conn.commit()
    conn.close()
    return {"message": "Bill updated", "total": total}

@router.post("/{bill_id}/void")
def void_bill(bill_id: int, req: InvoiceActionRequest, current_user: dict = Depends(require_role("admin"))):
    """Admin voids an invoice with a mandatory audit reason."""
    reason = req.reason.strip()
    if len(reason) < 3:
        raise HTTPException(400, "A valid reason (minimum 3 characters) is required to void an invoice.")

    conn = get_db()
    bill = conn.execute("SELECT * FROM bills WHERE id=?", (bill_id,)).fetchone()
    if not bill:
        conn.close()
        raise HTTPException(404, "Bill not found")

    bill_dict = dict(bill)
    if bill_dict.get("is_void") == 1:
        conn.close()
        raise HTTPException(400, "This invoice is already void.")

    conn.execute("""
        UPDATE bills SET is_void=1, void_reason=?, payment_status='Void', action_by=?, action_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (reason, current_user["id"], bill_id))
    conn.commit()
    conn.close()

    log_audit_event(
        current_user,
        action="INVOICE_VOIDED",
        entity="bills",
        entity_id=bill_id,
        details={"bill_number": bill["bill_number"], "reason": reason}
    )
    return {"message": f"Invoice #{bill['bill_number']} has been voided.", "bill_id": bill_id, "status": "Void"}

@router.post("/{bill_id}/cancel")
def cancel_bill(bill_id: int, req: InvoiceActionRequest, current_user: dict = Depends(require_role("admin"))):
    """Admin cancels an unpaid invoice with a mandatory audit reason."""
    reason = req.reason.strip()
    if len(reason) < 3:
        raise HTTPException(400, "A valid reason (minimum 3 characters) is required to cancel an invoice.")

    conn = get_db()
    bill = conn.execute("SELECT * FROM bills WHERE id=?", (bill_id,)).fetchone()
    if not bill:
        conn.close()
        raise HTTPException(404, "Bill not found")

    if bill["payment_status"] == "Paid":
        conn.close()
        raise HTTPException(400, "Cannot cancel an already Paid bill. Use refund or void instead.")

    bill_dict = dict(bill)
    if bill_dict.get("is_cancelled") == 1:
        conn.close()
        raise HTTPException(400, "This invoice is already cancelled.")

    conn.execute("""
        UPDATE bills SET is_cancelled=1, void_reason=?, payment_status='Cancelled', action_by=?, action_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (reason, current_user["id"], bill_id))
    conn.commit()
    conn.close()

    log_audit_event(
        current_user,
        action="INVOICE_CANCELLED",
        entity="bills",
        entity_id=bill_id,
        details={"bill_number": bill["bill_number"], "reason": reason}
    )
    return {"message": f"Invoice #{bill['bill_number']} has been cancelled.", "bill_id": bill_id, "status": "Cancelled"}

@router.post("/{bill_id}/archive")
def archive_bill(bill_id: int, req: InvoiceActionRequest, current_user: dict = Depends(require_role("admin"))):
    """Admin archives an invoice without deleting it."""
    reason = req.reason.strip()
    conn = get_db()
    bill = conn.execute("SELECT * FROM bills WHERE id=?", (bill_id,)).fetchone()
    if not bill:
        conn.close()
        raise HTTPException(404, "Bill not found")

    conn.execute("""
        UPDATE bills SET is_archived=1, action_by=?, action_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (current_user["id"], bill_id))
    conn.commit()
    conn.close()

    log_audit_event(
        current_user,
        action="INVOICE_ARCHIVED",
        entity="bills",
        entity_id=bill_id,
        details={"bill_number": bill["bill_number"], "reason": reason}
    )
    return {"message": f"Invoice #{bill['bill_number']} has been archived.", "bill_id": bill_id}

@router.delete("/{bill_id}")
def delete_bill(bill_id: int, current_user: dict = Depends(require_role("admin"))):
    """
    Non-destructive invoice cancellation.
    Soft-cancels the invoice instead of deleting historical financial records.
    """
    conn = get_db()
    bill = conn.execute("SELECT * FROM bills WHERE id=?", (bill_id,)).fetchone()
    if not bill:
        conn.close()
        raise HTTPException(404, "Bill not found")

    if bill["payment_status"] == "Paid":
        conn.close()
        raise HTTPException(400, "Cannot delete or cancel a Paid invoice. Use refund or void instead.")

    conn.execute("""
        UPDATE bills SET is_cancelled=1, void_reason='Cancelled via invoice delete request',
        payment_status='Cancelled', action_by=?, action_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (current_user["id"], bill_id))
    conn.commit()
    conn.close()

    log_audit_event(
        current_user,
        action="INVOICE_SOFT_DELETED",
        entity="bills",
        entity_id=bill_id,
        details={"bill_number": bill["bill_number"]}
    )
    return {"message": f"Bill #{bill['bill_number']} successfully cancelled."}


# ---------------------------------------------------------------------------
# Customer Special Offers & Festival Coupons
# ---------------------------------------------------------------------------

@router.post("/offers")
def create_offer(req: CreateOfferRequest, current_user: dict = Depends(require_role("admin"))):
    """Admin creates a festival or customer special discount offer."""
    code = req.code.strip().upper()
    if not code:
        raise HTTPException(400, "Offer code is required.")
    if req.discount_value <= 0:
        raise HTTPException(400, "Discount value must be greater than 0.")
    if req.discount_type not in ("percentage", "flat"):
        raise HTTPException(400, "Discount type must be 'percentage' or 'flat'.")

    conn = get_db()
    existing = conn.execute("SELECT id FROM customer_offers WHERE code=?", (code,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(400, f"Offer code '{code}' already exists.")

    cursor = conn.execute("""
        INSERT INTO customer_offers (code, title, description, discount_type, discount_value,
                                    min_bill_amount, max_discount, valid_from, valid_until,
                                    target_customer_id, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, (
        code, req.title.strip(), req.description, req.discount_type, req.discount_value,
        req.min_bill_amount, req.max_discount, req.valid_from, req.valid_until, req.target_customer_id
    ))
    offer_id = cursor.lastrowid
    conn.commit()
    conn.close()

    log_audit_event(
        current_user,
        action="CREATE_OFFER",
        entity="customer_offers",
        entity_id=offer_id,
        details={"code": code, "discount_type": req.discount_type, "discount_value": req.discount_value}
    )

    return {"message": f"Offer '{code}' created successfully", "offer_id": offer_id, "code": code}

@router.get("/offers")
def list_offers(current_user: dict = Depends(require_role("admin"))):
    """Admin lists all promotional and festival offers."""
    conn = get_db()
    offers = conn.execute("""
        SELECT co.*, u.name as target_customer_name, u.email as target_customer_email,
               (SELECT COUNT(*) FROM bills WHERE offer_code = co.code) as usage_count
        FROM customer_offers co
        LEFT JOIN users u ON co.target_customer_id = u.id
        ORDER BY co.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(o) for o in offers]

@router.get("/offers/active")
def list_active_offers(current_user: dict = Depends(get_current_user)):
    """List active offers valid for current user."""
    conn = get_db()
    query = """
        SELECT id, code, title, description, discount_type, discount_value, min_bill_amount, max_discount, valid_until
        FROM customer_offers
        WHERE is_active = 1
          AND (valid_until IS NULL OR valid_until >= DATE('now'))
          AND (valid_from IS NULL OR valid_from <= DATE('now'))
    """
    params = []
    if current_user["role"] == "customer":
        query += " AND (target_customer_id IS NULL OR target_customer_id = ?)"
        params.append(current_user["id"])

    query += " ORDER BY discount_value DESC"
    offers = conn.execute(query, tuple(params)).fetchall()
    conn.close()
    return [dict(o) for o in offers]

@router.delete("/offers/{offer_id}")
def toggle_offer(offer_id: int, current_user: dict = Depends(require_role("admin"))):
    """Admin can deactivate/activate an offer."""
    conn = get_db()
    offer = conn.execute("SELECT * FROM customer_offers WHERE id=?", (offer_id,)).fetchone()
    if not offer:
        conn.close()
        raise HTTPException(404, "Offer not found")
    new_state = 0 if offer["is_active"] == 1 else 1
    conn.execute("UPDATE customer_offers SET is_active=? WHERE id=?", (new_state, offer_id))
    conn.commit()
    conn.close()
    return {"message": f"Offer {'deactivated' if new_state == 0 else 'activated'} successfully"}

@router.put("/offers/{offer_id}")
def update_offer(offer_id: int, req: CreateOfferRequest, current_user: dict = Depends(require_role("admin"))):
    """Admin updates an existing offer."""
    conn = get_db()
    offer = conn.execute("SELECT id FROM customer_offers WHERE id=?", (offer_id,)).fetchone()
    if not offer:
        conn.close()
        raise HTTPException(404, "Offer not found")
    conn.execute("""
        UPDATE customer_offers 
        SET code=?, title=?, description=?, discount_type=?, discount_value=?,
            min_bill_amount=?, max_discount=?, valid_from=?, valid_until=?,
            target_customer_id=?, usage_limit=?, per_customer_limit=?
        WHERE id=?
    """, (req.code.strip().upper(), req.title, req.description, req.discount_type,
          req.discount_value, req.min_bill_amount, req.max_discount,
          req.valid_from, req.valid_until, req.target_customer_id,
          getattr(req, 'usage_limit', None), getattr(req, 'per_customer_limit', 1),
          offer_id))
    conn.commit()
    conn.close()
    return {"message": "Offer updated successfully"}


# ---------------------------------------------------------------------------
# Core Unified Coupon / Offer Application Logic
# ---------------------------------------------------------------------------

def _apply_offer_core(bill_id: int, raw_code: str, current_user: dict):
    if not raw_code or not raw_code.strip():
        raise HTTPException(400, "Coupon code cannot be empty.")

    code = raw_code.strip().upper()
    conn = get_db()

    bill = conn.execute("SELECT * FROM bills WHERE id=?", (bill_id,)).fetchone()
    if not bill:
        conn.close()
        raise HTTPException(404, "Bill not found")

    if current_user["role"] == "customer" and bill["customer_id"] != current_user["id"]:
        conn.close()
        raise HTTPException(403, "Access denied. You can only apply offers to your own bills.")

    bill_dict = dict(bill)
    if bill["payment_status"] in ("Paid", "Refunded", "Void", "Cancelled") or bill_dict.get("is_void") == 1 or bill_dict.get("is_cancelled") == 1:
        conn.close()
        raise HTTPException(400, "Cannot apply offer to an already settled, void, or cancelled bill.")

    offer = conn.execute("SELECT * FROM customer_offers WHERE code=? COLLATE NOCASE", (code,)).fetchone()
    if not offer:
        conn.close()
        raise HTTPException(404, f"Offer code '{code}' is invalid.")

    offer_dict = dict(offer)
    if offer["is_active"] != 1:
        conn.close()
        raise HTTPException(400, "This offer is no longer active.")

    from datetime import date
    today_str = date.today().isoformat()
    if offer["valid_until"] and offer["valid_until"] < today_str:
        conn.close()
        raise HTTPException(400, "This offer has expired.")
    if offer["valid_from"] and offer["valid_from"] > today_str:
        conn.close()
        raise HTTPException(400, "This offer is not valid yet.")

    if offer["target_customer_id"] and offer["target_customer_id"] != bill["customer_id"]:
        conn.close()
        raise HTTPException(403, "This offer is personalized for another customer.")

    # Check overall usage limit
    if offer_dict.get("usage_limit") and (offer_dict.get("usage_count") or 0) >= offer["usage_limit"]:
        conn.close()
        raise HTTPException(400, "This offer has reached its maximum total usage limit.")

    # Check per-customer limit
    per_cust_limit = offer_dict.get("per_customer_limit") or 1
    cust_usage = conn.execute(
        "SELECT COUNT(*) FROM offer_redemptions WHERE offer_id=? AND customer_id=?",
        (offer["id"], bill["customer_id"])
    ).fetchone()[0]
    if cust_usage >= per_cust_limit:
        conn.close()
        raise HTTPException(400, f"You have already redeemed this offer the maximum allowed number of times ({per_cust_limit}).")

    subtotal = bill["labour_charge"] + bill["parts_cost"]
    min_amount = offer["min_bill_amount"] or 0
    if subtotal < min_amount:
        conn.close()
        raise HTTPException(400, f"Minimum bill amount of ₹{min_amount:.2f} required for this coupon. Your subtotal is ₹{subtotal:.2f}.")

    if offer["discount_type"] == "percentage":
        discount = subtotal * (offer["discount_value"] / 100.0)
        if offer["max_discount"] and offer["max_discount"] > 0:
            discount = min(discount, offer["max_discount"])
    else:  # flat
        discount = min(subtotal, offer["discount_value"])

    discount = round(discount, 2)
    subtotal, effective_discount, taxable, tax, total = calculate_bill_totals(bill["labour_charge"], bill["parts_cost"], discount, 0.09)

    # Re-generate UPI intent with proper shop UPI ID
    job_shop_id = bill["shop_id"] if bill_dict.get("shop_id") else 1
    shop_branch = conn.execute("SELECT upi_id FROM shops WHERE id=?", (job_shop_id,)).fetchone()
    upi_pa = shop_branch["upi_id"] if shop_branch and shop_branch["upi_id"] else "mistri@upi"
    b_num = bill["bill_number"]
    new_upi_intent = (
        f"upi://pay?pa={upi_pa}"
        f"&pn={urllib.parse.quote('Mistri Electrical/Electronic')}"
        f"&am={total:.2f}"
        f"&cu=INR"
        f"&tn={urllib.parse.quote(f'Invoice {b_num}')}"
    )

    conn.execute("""
        UPDATE bills SET discount=?, offer_code=?, offer_discount=?, tax=?, total_amount=?, upi_qr_url=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (effective_discount, code, effective_discount, tax, total, new_upi_intent, bill_id))

    conn.execute("UPDATE repair_jobs SET actual_cost=? WHERE id=?", (total, bill["repair_job_id"]))

    # Record redemption
    conn.execute("""
        INSERT INTO offer_redemptions (offer_id, customer_id, bill_id, discount_applied)
        VALUES (?, ?, ?, ?)
    """, (offer["id"], bill["customer_id"], bill_id, effective_discount))

    # Increment usage count
    conn.execute("UPDATE customer_offers SET usage_count=COALESCE(usage_count,0)+1 WHERE id=?", (offer["id"],))

    conn.commit()
    conn.close()

    log_audit_event(
        current_user,
        action="OFFER_APPLIED",
        entity="bills",
        entity_id=bill_id,
        details={"offer_code": code, "discount": effective_discount, "new_total": total}
    )

    return {
        "message": f"Coupon '{code}' applied! You saved ₹{effective_discount:,.2f}.",
        "discount": effective_discount,
        "tax": tax,
        "total_amount": total,
        "final_amount": total,
        "original_amount": subtotal,
        "offer_code": code,
        "offer_title": offer["title"]
    }


class ApplyCouponRequest(BaseModel):
    bill_id: int
    offer_code: str

@router.post("/{bill_id}/apply-offer")
def apply_offer_to_bill(bill_id: int, req: ApplyOfferRequest, current_user: dict = Depends(get_current_user)):
    """Apply discount coupon / festival offer to bill by route parameter."""
    code = req.offer_code or req.coupon_code
    return _apply_offer_core(bill_id, code, current_user)

@router.post("/apply-offer")
def apply_offer_by_body(req: ApplyCouponRequest, current_user: dict = Depends(get_current_user)):
    """Apply discount coupon / festival offer to bill by request body."""
    return _apply_offer_core(req.bill_id, req.offer_code, current_user)

@router.delete("/apply-offer/{bill_id}")
def remove_offer_from_bill(bill_id: int, current_user: dict = Depends(get_current_user)):
    """Remove applied offer from bill and restore original subtotal and GST."""
    conn = get_db()
    bill = conn.execute("SELECT * FROM bills WHERE id=?", (bill_id,)).fetchone()
    if not bill:
        conn.close()
        raise HTTPException(404, "Bill not found")

    if current_user["role"] == "customer" and bill["customer_id"] != current_user["id"]:
        conn.close()
        raise HTTPException(403, "Access denied. You can only remove offers from your own bills.")

    bill_dict = dict(bill)
    if not bill_dict.get("offer_code"):
        conn.close()
        raise HTTPException(400, "No offer applied to this bill.")

    if bill["payment_status"] in ("Paid", "Refunded", "Void", "Cancelled"):
        conn.close()
        raise HTTPException(400, "Cannot modify an already settled or cancelled bill.")

    subtotal, effective_discount, taxable, tax, original_total = calculate_bill_totals(bill["labour_charge"], bill["parts_cost"], 0, 0.09)

    # Re-generate standard UPI intent
    job_shop_id = bill["shop_id"] if bill_dict.get("shop_id") else 1
    shop_branch = conn.execute("SELECT upi_id FROM shops WHERE id=?", (job_shop_id,)).fetchone()
    upi_pa = shop_branch["upi_id"] if shop_branch and shop_branch["upi_id"] else "mistri@upi"
    b_num = bill["bill_number"]
    restored_upi_intent = (
        f"upi://pay?pa={upi_pa}"
        f"&pn={urllib.parse.quote('Mistri Electrical/Electronic')}"
        f"&am={original_total:.2f}"
        f"&cu=INR"
        f"&tn={urllib.parse.quote(f'Invoice {b_num}')}"
    )

    conn.execute("""
        UPDATE bills SET discount=0, offer_code=NULL, offer_discount=0, tax=?, total_amount=?, upi_qr_url=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (tax, original_total, restored_upi_intent, bill_id))

    conn.execute("UPDATE repair_jobs SET actual_cost=? WHERE id=?", (original_total, bill["repair_job_id"]))

    # Remove redemption record
    offer_code = bill["offer_code"]
    offer = conn.execute("SELECT id FROM customer_offers WHERE code=?", (offer_code,)).fetchone()
    if offer:
        conn.execute("""
            DELETE FROM offer_redemptions WHERE offer_id=? AND customer_id=? AND bill_id=?
        """, (offer["id"], bill["customer_id"], bill_id))
        conn.execute("UPDATE customer_offers SET usage_count=MAX(0, COALESCE(usage_count,1)-1) WHERE id=?", (offer["id"],))

    conn.commit()
    conn.close()
    return {"message": "Offer removed", "restored_amount": original_total}

@router.delete("/{bill_id}/remove-offer")
def remove_offer_from_bill_alt(bill_id: int, current_user: dict = Depends(get_current_user)):
    """Alternate route for removing offer from bill."""
    return remove_offer_from_bill(bill_id, current_user)


# ---------------------------------------------------------------------------
# Payment Audit & Cash Report
# ---------------------------------------------------------------------------

@router.get("/payments-report")
def get_payments_report(
    payment_method: Optional[str] = None,
    status: Optional[str] = None,
    staff_id: Optional[int] = None,
    current_user: dict = Depends(require_role("admin"))
):
    """
    Admin Payments & Cash Collections Report.
    Audits physical cash collected by staff vs UPI online payments.
    """
    conn = get_db()
    query = """
        SELECT p.*, b.bill_number, b.total_amount as bill_total, b.payment_status as bill_status,
               c.name as customer_name, c.phone as customer_phone,
               s.name as collected_by_name,
               v.name as verified_by_name,
               rj.repair_id, d.device_type, d.brand, d.model
        FROM payments p
        JOIN bills b ON p.bill_id = b.id
        JOIN users c ON b.customer_id = c.id
        JOIN repair_jobs rj ON b.repair_job_id = rj.id
        JOIN devices d ON rj.device_id = d.id
        LEFT JOIN users s ON p.collected_by = s.id
        LEFT JOIN users v ON p.verified_by = v.id
        WHERE 1=1
    """
    params = []
    if payment_method and payment_method != "All":
        query += " AND p.payment_method = ?"
        params.append(payment_method)

    if status and status != "All":
        query += " AND p.status = ?"
        params.append(status)

    if staff_id:
        query += " AND p.collected_by = ?"
        params.append(staff_id)

    query += " ORDER BY p.paid_at DESC"
    rows = conn.execute(query, tuple(params)).fetchall()

    # Aggregate summaries
    total_cash = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE payment_method='Cash' AND status='Confirmed'").fetchone()[0]
    total_upi = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE payment_method!='Cash' AND status='Confirmed'").fetchone()[0]
    total_pending = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status='Pending'").fetchone()[0]

    # Cash breakdown by staff
    cash_by_staff_rows = conn.execute("""
        SELECT s.id as staff_id, s.name as staff_name, COALESCE(SUM(p.amount), 0) as total_collected, COUNT(p.id) as payment_count
        FROM users s
        JOIN payments p ON p.collected_by = s.id
        WHERE p.payment_method = 'Cash' AND p.status = 'Confirmed'
        GROUP BY s.id
        ORDER BY total_collected DESC
    """).fetchall()

    conn.close()

    return {
        "payments": [dict(r) for r in rows],
        "summary": {
            "total_cash_collected": round(float(total_cash), 2),
            "total_upi_collected": round(float(total_upi), 2),
            "total_pending_verification": round(float(total_pending), 2),
            "total_revenue": round(float(total_cash + total_upi), 2),
            "cash_by_staff": [dict(s) for s in cash_by_staff_rows]
        }
    }

