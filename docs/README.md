# Mistri – Smart Electrical/Electronic Repair Management System

## 🚀 Quick Start

```bash
# 1. Go to backend
cd mistri/backend

# 2. Install dependencies (one-time)
pip3 install fastapi uvicorn "python-jose[cryptography]" passlib bcrypt python-multipart aiofiles Pillow qrcode reportlab scikit-learn

# 3. Seed the database
python3 db/seed.py

# 4. Start the server
python3 server.py
```

**Open in browser:** http://localhost:8000

---

## 🔑 Demo Login Credentials

| Role | Email | Password |
|---|---|---|
| 🔴 Admin | admin@mistri.com | Admin@123 |
| 🟡 Staff (Raju) | raju@mistri.com | Staff@123 |
| 🟡 Staff (Priya) | priya@mistri.com | Staff@123 |
| 🟢 Customer | arun@example.com | Customer@123 |
| 🟢 Customer | meena@example.com | Customer@123 |

---

## 📁 Project Structure

```
mistri/
├── backend/
│   ├── server.py               # FastAPI entry point
│   ├── db/
│   │   ├── database.py         # SQLite schema & connection
│   │   └── seed.py             # Demo data seeder
│   ├── middleware/
│   │   └── auth.py             # JWT auth & RBAC
│   ├── routes/
│   │   ├── auth.py             # Register, Login, Users
│   │   ├── repairs.py          # Repair jobs CRUD
│   │   ├── inventory.py        # Inventory management
│   │   ├── bills.py            # Invoices & PDF generation
│   │   ├── ai.py               # AI cost estimator
│   │   ├── reports.py          # Analytics & CSV export
│   │   └── notifications.py    # User notifications
│   └── utils/
│       └── qrcode_gen.py       # QR code generator
├── frontend/
│   ├── index.html              # SPA shell
│   └── static/
│       ├── css/styles.css      # Full design system
│       └── js/
│           ├── api.js          # API client with JWT
│           ├── router.js       # Client-side router & utilities
│           ├── app.js          # Route registration & init
│           └── views/
│               ├── auth.js     # Landing, Login, Register, Tracker
│               ├── customer.js # Customer dashboard + AI submit
│               ├── admin.js    # Admin panel (full-featured)
│               └── staff.js    # Staff job management
├── ai_model/
│   └── estimator.py            # Python scikit-learn reference model
└── docs/
    ├── README.md               # This file
    └── API.md                  # API documentation
```

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3 + FastAPI + Uvicorn |
| Database | SQLite (compatible with PostgreSQL) |
| Auth | JWT (python-jose) + bcrypt passwords |
| PDF | ReportLab |
| QR Code | qrcode library |
| AI (prod) | Keyword NLP (built-in, zero deps) |
| AI (ref) | scikit-learn RandomForestRegressor |
| Frontend | Vanilla HTML + CSS + JavaScript (SPA) |
| Charts | Chart.js 4.x (CDN) |

---

## 🌐 API Reference

Interactive docs available at: **http://localhost:8000/api/docs**

### Auth
| Method | Endpoint | Description |
|---|---|---|
| POST | /api/auth/register | Register customer |
| POST | /api/auth/login | Login (any role) |
| GET | /api/auth/me | Get current user |
| GET | /api/auth/users | List all users (admin) |
| POST | /api/auth/staff | Create staff (admin) |

### Repairs
| Method | Endpoint | Description |
|---|---|---|
| POST | /api/repairs/submit | Submit new repair |
| GET | /api/repairs/ | List repairs (role-filtered) |
| GET | /api/repairs/track/{repair_id} | Public tracker |
| GET | /api/repairs/stats/dashboard | Admin KPIs |
| PUT | /api/repairs/{id}/status | Update status |
| PUT | /api/repairs/{id}/parts | Update parts used |

### AI
| Method | Endpoint | Description |
|---|---|---|
| POST | /api/ai/estimate | Get cost estimate |
| GET | /api/ai/repair-tips/{device} | Common repairs + costs |

### Inventory
| Method | Endpoint | Description |
|---|---|---|
| GET | /api/inventory/ | List all items |
| POST | /api/inventory/ | Add item (admin) |
| PATCH | /api/inventory/{id}/stock | Update stock level |

### Bills & Reports
| Method | Endpoint | Description |
|---|---|---|
| POST | /api/bills/generate | Generate invoice |
| GET | /api/bills/{id}/pdf | Download PDF |
| GET | /api/reports/revenue | Revenue analytics |
| GET | /api/reports/export/csv | Export CSV |

---

## 🔒 Security

- Passwords hashed with **bcrypt** (cost factor 12)
- JWT tokens expire in **24 hours**
- Role-Based Access Control: `admin`, `staff`, `customer`
- CORS configured (restrict origins in production)
- Input validation via Pydantic models

---

## 📊 AI Cost Estimator

The production estimator uses keyword NLP:
1. Maps `device_type` + `problem_description` to repair categories
2. Matches keywords (screen, battery, motherboard, water damage, etc.)
3. Returns `{min_cost, max_cost, confidence, time_estimate, primary_part}` in INR

The `ai_model/estimator.py` script trains a RandomForestRegressor reference model using synthetic data. Run it with `python3 ai_model/estimator.py`.

---

## 🚢 Deployment

### Production (Linux VPS)
```bash
# Install dependencies
pip3 install -r requirements.txt

# Set environment variables
export MISTRI_SECRET="your-very-long-secret-key"

# Run with gunicorn
pip3 install gunicorn
gunicorn server:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Switch to PostgreSQL
Replace `better-sqlite3` with `asyncpg` and update `db/database.py`:
```python
# Change DB_PATH to PostgreSQL connection string
DATABASE_URL = "postgresql://user:pass@localhost/mistri"
```

---

*Built with ⚡ by Mistri*
