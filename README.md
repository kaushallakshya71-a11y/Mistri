# 🔧 Mistri – Smart Electrical/Electronic Repair Management System

<p align="center">
  <img src="docs/banner.png" alt="Mistri Banner" width="100%" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python" />
  <img src="https://img.shields.io/badge/FastAPI-0.110+-green?style=for-the-badge&logo=fastapi" />
  <img src="https://img.shields.io/badge/Scikit--Learn-ML-orange?style=for-the-badge&logo=scikitlearn" />
  <img src="https://img.shields.io/badge/SQLite-WAL%20Mode-lightblue?style=for-the-badge&logo=sqlite" />
  <img src="https://img.shields.io/badge/Tests-14%2F14%20Passing-brightgreen?style=for-the-badge" />
</p>

> **Mistri** is an enterprise-grade, full-stack electrical/electronic repair shop management platform with bilingual (Hindi/Hinglish) AI-powered cost estimation, smart technician assignment, real-time repair tracking, atomic inventory management, and automated UPI billing.

---

## 🌟 Key Features

### 👤 Customer
- Submit repair requests with device photos & problem description (Hindi/English both supported)
- **Bilingual AI Cost Estimation** — type *"awaz aa rahi hai"* or *"capacitor weak hai"* and get instant price + turnaround estimate
- **11-Stage Visual Repair Timeline** with QR-based tracking
- Online UPI payment with auto-generated QR code
- PDF invoice download
- Warranty claims & revisit requests
- Repair history

### 🛠️ Staff / Technician
- Mobile-first interface for viewing assigned jobs
- Stage-wise photo upload (Before / During / After repair)
- Parts used logging per repair job
- Quick status updates

### 👑 Admin / Owner
- **AI Technician Recommender** — weighted scoring (Device Experience 40% + Rating 35% + Workload 25%)
- Duplicate-prevention technician assignment
- **Atomic Inventory Management** with stock deduction guards (no negative stock)
- Low-stock reorder alerts with 1-click restock
- Stock movement audit log
- Dynamic NPCI-compliant UPI QR code generation
- GST PDF invoice with embedded payment QR
- Automated WhatsApp status notifications
- Warranty issuance & claims management
- **Business Intelligence Dashboard** — Revenue, Gross Profit, Turnaround Hours, Staff Scorecard
- Enterprise tamper-evident Audit Logs (RBAC-restricted)

---

## 🏗️ Architecture

```
[ Browser / Mobile Client ]
         │  (HTTP Fetch API + JWT Bearer Token)
         ▼
[ FastAPI Server — Port 8000 ]
         │
    ┌────┴──────────────────────┐
    ▼                           ▼
[ Auth Middleware ]    [ Static SPA Router ]
  (JWT + RBAC Guards)   (Vanilla JS Single Page App)
         │
         ▼
[ API Route Handlers (/api/...) ]
   ├── /auth       → JWT token issuance
   ├── /repairs    → 11-stage lifecycle & photo upload
   ├── /ai         → Bilingual NLP + RandomForest estimator
   ├── /inventory  → Atomic deduction & reorder alerts
   ├── /bills      → Dynamic UPI QR & PDF invoice
   ├── /warranties → Issue, track, claims management
   └── /reports    → Analytics & audit trail
         │
         ▼
[ SQLite Database — WAL Mode ]
  18 Tables | 11 Indexes | Atomic Transactions
         │
         ▼
[ Background Utilities ]
   └── messaging.py → WhatsApp/SMS template dispatch
```

---

## 🧰 Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Backend** | FastAPI (Python 3.11+) | Async performance, auto OpenAPI docs, native ML integration |
| **Database** | SQLite + WAL Mode | Zero-config, concurrent-read safe, ANSI SQL (portable to PostgreSQL) |
| **ML Model** | Scikit-Learn RandomForestRegressor | Offline, sub-ms inference, no API cost |
| **NLP** | Custom Regex Bilingual Normalizer | 40+ Hindi/Hinglish slang → diagnostic keyword mapping |
| **Frontend** | Vanilla JS SPA | Zero build tools, ultra-fast on low-end devices |
| **PDF** | ReportLab | Dynamic GST invoice with embedded UPI QR |
| **QR Code** | `qrcode` + Pillow | NPCI-compliant UPI intent string generation |
| **Auth** | JWT (PyJWT) + bcrypt | Stateless auth, secure password hashing |

---

## 🗄️ Database Schema (18 Tables)

| Table | Purpose |
|---|---|
| `users` | Multi-role users (admin, staff, customer) |
| `shops` | Multi-tenant branch support |
| `devices` | Customer devices (Fan, Motor, Mixer, etc.) |
| `repair_jobs` | Core job lifecycle with 11-stage status machine |
| `repair_status_history` | Immutable status change log |
| `repair_photos` | Before / During / After photo evidence |
| `inventory` | Spare parts stock with reorder thresholds |
| `inventory_transactions` | Every stock IN/OUT movement audit |
| `bills` + `payments` | GST billing, UPI QR, payment tracking |
| `warranties` + `warranty_claims` | Warranty lifecycle & customer revisit claims |
| `feedback` | Dual rating (service + technician) |
| `notifications` | In-app & WhatsApp alert log |
| `shop_products` + `shop_orders` | Product store (wires, switches, plugs) |
| `audit_logs` | Enterprise tamper-evident action log |

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/kaushallakshya71-a11y/Mistri.git
cd Mistri

# Install dependencies
pip install -r backend/requirements.txt

# Set up environment variables
cp backend/.env.example backend/.env
# Edit .env with your secrets (JWT secret, UPI ID, etc.)

# Run the server
cd backend
python server.py
```

### Access
- **Web App:** http://localhost:8000
- **API Docs (Swagger):** http://localhost:8000/api/docs

### Demo Accounts

| Role | Email | Password |
|---|---|---|
| Admin | admin@mistri.com | Admin@123 |
| Technician | raju@mistri.com | Staff@123 |
| Customer | arun@example.com | Customer@123 |

---

## 🧪 Running Tests

```bash
cd backend
python -m pytest tests/test_suite.py -v
# or
python tests/test_suite.py
```

**Test Results: 14/14 Passing ✅**

```
test_01_database_tables_and_multi_tenant_shop .......... ok
test_02_ai_cost_estimator_english ...................... ok
test_03_ai_cost_estimator_hinglish_and_hindi ........... ok
test_04_billing_and_tax_math ........................... ok
test_05_dynamic_upi_qr_generation ...................... ok
test_06_auth_password_hashing .......................... ok
test_07_whatsapp_notification_dispatch ................. ok
test_08_technician_assignment_and_workload ............. ok
test_09_atomic_inventory_deduction_and_guard ........... ok
test_10_inventory_reorder_alerts_and_restock ........... ok
test_11_warranty_lifecycle_and_claims .................. ok
test_12_ai_technician_recommendation_algorithm ......... ok
test_13_audit_trail_logging ............................ ok
test_14_security_and_rbac_boundaries ................... ok

Ran 14 tests in 0.749s — OK
```

---

## 🔑 Key API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/login` | JWT token issuance |
| POST | `/api/ai/estimate` | Bilingual AI cost estimation |
| GET | `/api/ai/recommend-technician/{id}` | Smart technician matching |
| POST | `/api/repairs/{id}/assign` | Assign technician (duplicate-safe) |
| POST | `/api/repairs/{id}/add-part` | Atomic inventory deduction |
| GET | `/api/bills/{id}/upi-qr` | Dynamic NPCI UPI QR code |
| GET | `/api/bills/{id}/pdf` | GST PDF invoice download |
| POST | `/api/warranties/claim` | Customer warranty revisit claim |
| GET | `/api/reports/analytics` | BI dashboard — revenue, profit, staff scorecard |
| GET | `/api/reports/audit-logs` | Tamper-evident audit trail (admin only) |

---

## 🧠 AI Modules

### 1. Bilingual Cost Estimator
- **NLP Layer:** 40+ Hindi/Hinglish symptom terms normalized to diagnostic categories
  - *"awaz aa rahi hai"* → `noise bearing vibration`
  - *"dhuan nikla, jal gaya"* → `burnt smoke winding`
  - *"dheema chal raha hai"* → `slow capacitor humming stuck`
- **ML Layer:** RandomForestRegressor trained on 9 device categories × 35+ fault scenarios
- **Output:** Min/Max cost range, labour/parts breakdown, turnaround hours, confidence %, human-readable explanation

### 2. Smart Technician Recommender
- **Scoring Formula:** `(Device Experience × 0.4) + (Customer Rating × 0.35) + (Low Workload × 0.25)`
- Returns ranked candidates with match score (0–100) and rationale

---

## 🔮 Future Enhancements

- [ ] **Cloud Deployment:** PostgreSQL (AWS RDS / Supabase) for multi-shop SaaS
- [ ] **Computer Vision:** CNN-based fault detection from uploaded device photos
- [ ] **Two-Way WhatsApp Chatbot:** Customer replies for live status & bill retrieval
- [ ] **Offline-First PWA:** IndexedDB + Service Workers for weak-network shops
- [ ] **Mobile App (React Native / Flutter):** Dedicated technician app

---

## 📄 License

This project is built for educational and portfolio purposes.

---

<p align="center">Built with ❤️ by <strong>Lakshya Kaushal</strong></p>
