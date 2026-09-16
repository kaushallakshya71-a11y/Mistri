"""
Mistri Bills & PDF Invoice Routes
Enhanced with Dynamic UPI QR Generation, Online Payment Recording, and Embedded Invoice QR.
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from db.database import get_db
from middleware.auth import get_current_user, require_role
from utils.qrcode_gen import generate_qr_base64
from datetime import datetime
import io
import qrcode
import urllib.parse

router = APIRouter(prefix="/api/bills", tags=["bills"])

class BillCreate(BaseModel):
    repair_job_id: int
    labour_charge: float = 0
    parts_cost: float = 0
    discount: float = 0
    tax_rate: float = 0.09  # 9% GST

class OnlinePaymentRequest(BaseModel):
    payment_method: str = "UPI"  # UPI | Card | NetBanking | Razorpay
    transaction_id: str

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

    # Generate standard NPCI UPI Intent string
    upi_pa = "mistri@upi"
    job_shop_id = job["shop_id"] if "shop_id" in job.keys() and job["shop_id"] else 1
    shop_branch = conn.execute("SELECT upi_id FROM shops WHERE id=?", (job_shop_id,)).fetchone()
    if shop_branch and shop_branch["upi_id"]:
        upi_pa = shop_branch["upi_id"]

    upi_intent = (
        f"upi://pay?pa={upi_pa}"
        f"&pn={urllib.parse.quote('Mistri Electronics')}"
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
    return dict(bill)

@router.get("/{bill_id}/upi-qr")
def get_bill_upi_qr(bill_id: int, current_user: dict = Depends(get_current_user)):
    """Generate dynamic scannable UPI payment QR code for a bill."""
    conn = get_db()
    bill = conn.execute("SELECT * FROM bills WHERE id=?", (bill_id,)).fetchone()
    conn.close()
    if not bill:
        raise HTTPException(404, "Bill not found")

    upi_intent = bill["upi_qr_url"]
    if not upi_intent:
        upi_intent = f"upi://pay?pa=mistri@upi&pn=Mistri%20Electronics&am={bill['total_amount']:.2f}&cu=INR&tn=Invoice-{bill['bill_number']}"

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
    """Record online payment via UPI, Razorpay, or Card and auto-update status to Paid."""
    conn = get_db()
    bill = conn.execute("SELECT * FROM bills WHERE id=?", (bill_id,)).fetchone()
    if not bill:
        conn.close()
        raise HTTPException(404, "Bill not found")

    conn.execute("""
        UPDATE bills SET payment_status='Paid', payment_method=?, transaction_id=? WHERE id=?
    """, (req.payment_method, req.transaction_id, bill_id))

    conn.execute("""
        INSERT INTO payments (bill_id, amount, payment_method, transaction_id)
        VALUES (?, ?, ?, ?)
    """, (bill_id, bill["total_amount"], req.payment_method, req.transaction_id))

    conn.commit()
    conn.close()
    return {
        "message": "Payment recorded successfully",
        "bill_id": bill_id,
        "payment_status": "Paid",
        "transaction_id": req.transaction_id
    }

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
    elements.append(Paragraph("⚡ MISTRI ELECTRONICS", title_style))
    elements.append(Paragraph("Smart Electronics & Appliance Repair Management System", subtitle_style))
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
    is_paid = (bill['payment_status'] == 'Paid')
    status_text = f"<font color='{'#27AE60' if is_paid else '#E74C3C'}'><b>PAYMENT STATUS: {bill['payment_status'].upper()}</b></font>"
    elements.append(Paragraph(status_text, styles['Normal']))

    if not is_paid:
        # Embed Dynamic Scannable UPI QR Code in PDF!
        upi_url = bill.get("upi_qr_url") or f"upi://pay?pa=mistri@upi&pn=Mistri%20Electronics&am={bill['total_amount']:.2f}&cu=INR&tn=Invoice-{bill['bill_number']}"
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

class BillUpdate(BaseModel):
    labour_charge: Optional[float] = None
    parts_cost: Optional[float] = None
    discount: Optional[float] = None
    tax_rate: Optional[float] = None
    payment_status: Optional[str] = None
    notes: Optional[str] = None

@router.put("/{bill_id}")
def update_bill(bill_id: int, req: BillUpdate, current_user: dict = Depends(require_role("admin"))):
    """Admin can edit bill charges and payment status."""
    conn = get_db()
    bill = conn.execute("SELECT * FROM bills WHERE id=?", (bill_id,)).fetchone()
    if not bill:
        conn.close()
        raise HTTPException(404, "Bill not found")

    labour = req.labour_charge if req.labour_charge is not None else bill["labour_charge"]
    parts = req.parts_cost if req.parts_cost is not None else bill["parts_cost"]
    discount = req.discount if req.discount is not None else bill["discount"]
    tax_rate = req.tax_rate if req.tax_rate is not None else 0.09
    taxable = max(0, labour + parts - discount)
    tax = round(taxable * tax_rate, 2)
    total = round(taxable + tax, 2)
    status = req.payment_status or bill["payment_status"]
    notes = req.notes if req.notes is not None else bill["notes"]

    conn.execute("""
        UPDATE bills SET labour_charge=?, parts_cost=?, discount=?, tax=?,
        total_amount=?, payment_status=?, notes=? WHERE id=?
    """, (labour, parts, discount, tax, total, status, notes, bill_id))
    conn.commit()
    conn.close()
    return {"message": "Bill updated", "total": total}
