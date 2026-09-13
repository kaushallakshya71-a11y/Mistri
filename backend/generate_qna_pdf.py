"""
Generate a professional PDF document containing the 10 Project Q&A points for Mistri.
Saves to Desktop and project root.
"""
import os
import sys
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.HexColor("#64748b"))
        # Header rule
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.5)
        self.line(54, letter[1] - 40, letter[0] - 54, letter[1] - 40)
        self.drawString(54, letter[1] - 35, "Mistri – Smart Electronics Repair Management System | Project Q&A")
        
        # Footer
        self.line(54, 45, letter[0] - 54, 45)
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 54, 32, page_text)
        self.drawString(54, 32, "Confidential & Proprietary – Project Viva / Interview Reference Guide")
        self.restoreState()

def create_pdf(output_path):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    # Custom styles
    primary_color = colors.HexColor("#1e3a8a")  # Deep blue
    accent_color = colors.HexColor("#0284c7")   # Bright cyan/blue
    dark_text = colors.HexColor("#0f172a")      # Slate 900
    body_text = colors.HexColor("#334155")      # Slate 700
    card_bg = colors.HexColor("#f8fafc")        # Slate 50
    border_color = colors.HexColor("#cbd5e1")

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=primary_color,
        spaceAfter=4
    )

    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leading=15,
        textColor=accent_color,
        spaceAfter=15
    )

    q_style = ParagraphStyle(
        "QuestionHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=primary_color,
        spaceBefore=10,
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=body_text,
        spaceAfter=6
    )

    bullet_style = ParagraphStyle(
        "BulletDark",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13.5,
        textColor=body_text,
        leftIndent=14,
        firstLineIndent=-10,
        spaceAfter=4
    )

    story = []

    # Title Banner
    story.append(Paragraph("MISTRI – SMART REPAIR MANAGEMENT SYSTEM", title_style))
    story.append(Paragraph("Comprehensive 10-Point Technical Interview & Viva Guide (Hinglish)", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=accent_color, spaceAfter=14))

    # Introduction Box
    intro_p = Paragraph(
        "<b>Overview:</b> Yeh document Mistri project ke top 10 standard architectural, technical aur problem-solving questions ka structured format me detailed answer provide karta hai. Isme system architecture, ML models, concurrency handling, database schema aur future scalability sabhi covers hain.",
        body_style
    )
    intro_table = Table([[intro_p]], colWidths=[letter[0] - 108])
    intro_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f0f9ff")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#bae6fd")),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(intro_table)
    story.append(Spacer(1, 12))

    # The 10 Q&A Items
    qna_data = [
        {
            "num": "1",
            "q": "Project Title & One-Line Summary",
            "points": [
                "<b>Project Title:</b> Mistri – Smart Electronics & Appliance Repair Management System (Enterprise Edition).",
                "<b>One-Line Summary:</b> Yeh ek intelligent, multi-role web platform hai jo local electronics repair shops ke unorganized pen-and-paper workflow ko digital banata hai—jisme bilingual (Hindi/English) AI cost estimation, smart technician assignment, real-time repair tracking, atomic inventory management aur automated UPI/WhatsApp billing integrated hai."
            ]
        },
        {
            "num": "2",
            "q": "Why did you build it? (Real-World Motivation / Pain Point)",
            "points": [
                "<b>Trust Issue:</b> Bharat me electronics repair industry 90% unorganized hai. Customers ko repair ka exact kharcha pehle nahi pata hota, baad me dukan wale manmana bill charge karte hain.",
                "<b>Tracking ki kami:</b> Customer ko repair progress janne ke liye dukan ke baar-baar chakkar lagane padte hain ya call karni padti hai.",
                "<b>Shop Owner ki pareshani:</b> Spare parts ki chori/stock mismatch, technician par kaunsa job chal raha hai uska record na hona, aur kacchi parchi (paper receipt) kho jane par disputes hona.",
                "<b>Motivation:</b> Ek aisa transparent system banana jo local shopkeeper (Mistri) aur regular customer dono ki bhasha (Hindi/Hinglish) samajh sake aur ek single portal se repair, stock aur billing sab manage kar sake."
            ]
        },
        {
            "num": "3",
            "q": "Problem Statement (Existing Solutions mein kya khamiyan thi)",
            "points": [
                "<b>Urban Company Model:</b> Door-step services ke liye hai; local physical electronics shop ke walk-in repair jobs aur spare parts inventory ke liye unsuitable hai.",
                "<b>Generic ERPs (SAP / Tally):</b> Bahut complex, heavyweight aur expensive hote hain; local technician smartphone se use nahi kar sakta.",
                "<b>AI ka Lack:</b> Kisi bhi existing software me colloquial Hindi bhasha (<i>'dhuan nikal raha hai'</i>, <i>'awaz kar raha hai'</i>) samajhkar estimated cost batane ka mechanism nahi tha.",
                "<b>Paper Receipts:</b> Physical slip kho jane par warranty claim ya delivery verify karne ka koi tamper-evident mechanism nahi tha."
            ]
        },
        {
            "num": "4",
            "q": "Your Solution (End-to-End kya build kiya)",
            "points": [
                "<b>Customer Module:</b> Walk-in ya online repair request submission with problem photos, bilingual explainable AI cost estimation, 11-stage visual timeline tracking via QR code, aur 1-click warranty revisit claims.",
                "<b>Staff / Technician Module:</b> Mobile-first interface jahan technician assigned jobs dekhta hai, stage-wise photos (Before/During/After) upload karta hai, aur repair me lage spare parts select karta hai.",
                "<b>Admin / Owner Module:</b> Multi-criteria AI Technician Match (Device Experience 40% + Rating 35% + Workload 25%), low-stock reorder alerts with atomic stock deduction, dynamic NPCI UPI QR code generation, GST printable PDF invoices, aur automated WhatsApp notification dispatch."
            ]
        },
        {
            "num": "5",
            "q": "Tech Stack Justification (Kyun choose kiya?)",
            "points": [
                "<b>Backend – FastAPI (Python 3.11+):</b> Scikit-Learn ML models ke native Python integration ke liye best hai. Asynchronous, high performance/low latency, automatic OpenAPI documentation, aur Pydantic data validation provide karta hai.",
                "<b>Database – SQLite with WAL (Write-Ahead Logging) Mode:</b> Shop-level edge-readiness aur low deployment footprint ke liye SQLite choose kiya. High concurrency solve karne ke liye <code>PRAGMA journal_mode=WAL</code> aur 15s connection timeout lagaya, jisse concurrent readers writer ko lock nahi karte. Schema 100% ANSI SQL hai jo PostgreSQL me seamlessly migrate ho sakta hai.",
                "<b>Machine Learning – Scikit-Learn (RandomForestRegressor) + Custom Bilingual NLP:</b> Heavy external LLMs par depend hone ke bajaye offline Random Forest choose kiya taaki bina API cost ya internet latency ke sub-millisecond me accurate cost prediction mile. Sath me custom Regex-based NLP banaya jo Hindi/Hinglish colloquial slangs ko standardize karta hai.",
                "<b>Frontend – Pure Vanilla JavaScript SPA:</b> Heavy framework (React/Angular) build overhead ke bina lightweight class-based SPA banaya jo low-end smartphones par bhi zero lag ke sath ultra-fast load hota hai."
            ]
        },
        {
            "num": "6",
            "q": "Your Exact Role & Contributions",
            "points": [
                "<b>AI & NLP Module:</b> 9 appliance categories ke 35+ fault scenarios ka dataset develop kiya aur Scikit-Learn model train karke backend me serialize kiya. Hindi-to-Diagnostic normalizer rule engine likha.",
                "<b>Smart Dispatch Algorithm:</b> Multi-criteria weighted algorithm develop kiya jo Device Experience (40%), Rating (35%), aur Workload (25%) calculate karke technicians ko rank karta hai.",
                "<b>Concurrency & Inventory Guard:</b> SQLite WAL configuration aur atomic SQL transactions likhe taaki stock negative me na jaye (race-condition protection).",
                "<b>Dynamic NPCI UPI QR & PDF Generator:</b> Python <code>reportlab</code> aur <code>qrcode</code> libraries se dynamically generated Base64 UPI QR code aur printable invoice layout tayyar kiya.",
                "<b>End-to-End Integration & Test Suite:</b> 14 automated unit tests likhe jo core logic, billing math, auth token verification aur state-machine lifecycle ko validate karte hain."
            ]
        },
        {
            "num": "7",
            "q": "Architecture & Data Flow (Request kaise travel karti hai)",
            "points": [
                "<b>Client Request:</b> Browser/Mobile client Fetch API ke through JWT Bearer token ke sath FastAPI server (Port 8000) ko request bhejta hai.",
                "<b>Auth Middleware:</b> JWT token verify karta hai aur RBAC guards (Admin, Staff, Customer) enforce karta hai.",
                "<b>API Route Layer:</b> Request appropriate handler (<code>/repairs</code>, <code>/ai</code>, <code>/inventory</code>, <code>/bills</code>) par route hoti hai.",
                "<b>Business Logic & Diagnostics:</b> Example: Customer problem likhta hai <i>'Motor se dhuan nikla aur awaz kar rahi hai'</i> -> NLP engine text normalize karke Winding Burn diagnostic isolate karta hai -> ML model feature vector par price range predict karta hai.",
                "<b>Database Layer:</b> SQLite WAL database me atomic operations execute hote hain (18 tables, 11 performance indexes).",
                "<b>Background Dispatch:</b> Status change par <code>messaging.py</code> background me automated WhatsApp/SMS payload trigger karta hai."
            ]
        },
        {
            "num": "8",
            "q": "Database Schema & APIs (Primary Entities & Endpoints)",
            "points": [
                "<b>Primary Entities (18 Tables):</b> <code>users</code> (roles, auth), <code>shops</code> (multi-tenant branch info), <code>devices</code>, <code>repair_jobs</code> (status machine), <code>repair_status_history</code> (audit logs), <code>repair_photos</code> (staged evidence), <code>inventory</code> & <code>inventory_transactions</code> (stock tracking), <code>bills</code> & <code>payments</code> (tax, upi qr), <code>warranties</code> & <code>warranty_claims</code>, aur <code>audit_logs</code>.",
                "<b>Key Endpoints:</b><br/>"
                "• <code>POST /api/auth/login</code> – JWT token issuance.<br/>"
                "• <code>POST /api/ai/estimate</code> – Explainable cost estimation.<br/>"
                "• <code>GET /api/ai/recommend-technician/{id}</code> – Smart technician matching.<br/>"
                "• <code>POST /api/repairs/{id}/add-part</code> – Atomic stock deduction.<br/>"
                "• <code>GET /api/bills/{id}/upi-qr</code> – Dynamic NPCI UPI QR code.<br/>"
                "• <code>GET /api/bills/{id}/pdf</code> – Downloadable PDF invoice with embedded QR.<br/>"
                "• <code>POST /api/warranties/claim</code> – Customer revisit claim.<br/>"
                "• <code>GET /api/reports/analytics</code> – Business intelligence & profit dashboard."
            ]
        },
        {
            "num": "9",
            "q": "Major Technical Challenges & Resolution",
            "points": [
                "<b>Challenge 1: SQLite Database Locking in Concurrent Operations:</b><br/>"
                "<i>Problem:</i> Simultaneous status check, photo upload aur inventory update se <code>sqlite3.OperationalError: database is locked</code> aata tha.<br/>"
                "<i>Fix:</i> SQLite default rollback journal hata kar <b>WAL (Write-Ahead Logging)</b> mode enable kiya (<code>PRAGMA journal_mode = WAL;</code>) aur connection busy timeout 5000ms set kiya. Isse readers aur writers ek dusre ko block nahi karte.",
                "<b>Challenge 2: Local Language & Slang Understanding in AI:</b><br/>"
                "<i>Problem:</i> Customers technical term ke bajaye colloquial Hindi bolte hain (<i>'danda ghumana padta hai'</i>, <i>'gar-gar awaz'</i>).<br/>"
                "<i>Fix:</i> Custom <b>Bilingual Domain NLP Normalizer</b> banaya jo 40+ phonetic Hindi terms ko standard diagnostic categories me map karta hai, jisse model accuracy 95% tak pahunch gayi.",
                "<b>Challenge 3: Inventory Overdraft & Race Conditions:</b><br/>"
                "<i>Problem:</i> Stock 1 bacha ho aur do technicians consume karein toh stock negative me ja sakta tha.<br/>"
                "<i>Fix:</i> Atomic SQL query (<code>UPDATE inventory SET quantity = quantity - ? WHERE id = ? AND quantity >= ?</code>) run kiya. Affected rows 0 hone par turant rollback aur 400 Insufficient Stock exception raise hoti hai."
            ]
        },
        {
            "num": "10",
            "q": "Future Enhancements (Scalability & Automation Scope)",
            "points": [
                "<b>Cloud Multi-Tenant SaaS:</b> Managed PostgreSQL (AWS RDS / Supabase) par migrate karna taaki 10,000+ repair shops apna independent portal chala sakein.",
                "<b>Computer Vision (Image-based Fault Detection):</b> Customer dwara upload ki gayi photo (jali hui PCB, cracked blade, burnt coil) par Vision/CNN model se automatic damage detection.",
                "<b>Two-Way WhatsApp Chatbot:</b> Customer direct WhatsApp par <i>'Status'</i> ya <i>'Bill'</i> type karke live updates aur payment link prapt kar sake.",
                "<b>Offline-First PWA (Progressive Web App):</b> Weak network / basement dukanon ke liye IndexedDB ke sath offline mode aur automatic background sync."
            ]
        }
    ]

    for item in qna_data:
        block_items = []
        heading_text = f"Q{item['num']}. {item['q']}"
        block_items.append(Paragraph(heading_text, q_style))
        for pt in item["points"]:
            block_items.append(Paragraph(f"• {pt}", bullet_style))
        block_items.append(Spacer(1, 8))
        story.append(KeepTogether(block_items))

    # Build PDF with custom NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"✅ PDF successfully generated at: {output_path}")

if __name__ == "__main__":
    desktop_path = "/Users/lakshya/Desktop/Mistri_Project_Interview_QnA.pdf"
    project_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Mistri_Project_Interview_QnA.pdf")

    create_pdf(desktop_path)
    create_pdf(project_path)
