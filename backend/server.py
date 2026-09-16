"""
Mistri - Smart Electronics Repair Management System
Main FastAPI Server Entry Point with Lifespan Handler, Health Diagnostics, and Comprehensive Routers.
"""
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from db.database import init_db, get_db
from routes import auth, repairs, inventory, bills, ai, reports, notifications, feedback, shop, warranties
from utils.qrcode_gen import generate_qr_base64

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    init_db()
    try:
        conn = get_db()
        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        conn.close()
        if user_count == 0:
            from db.seed import seed
            seed()
            print("🌱 Auto-seeded initial demo accounts and inventory!")
    except Exception as e:
        print(f"⚠️ Auto-seed notice: {e}")

    print("🚀 Mistri Enterprise API is running!")
    print("📖 API Docs: /api/docs")
    print("🌐 Frontend: /")
    yield
    # Shutdown logic
    print("🛑 Mistri API shutdown complete.")

# Initialize FastAPI app
app = FastAPI(
    title="Mistri API",
    description="Smart Electronics & Appliance Repair Management System - Enterprise Edition",
    version="1.2.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(repairs.router)
app.include_router(inventory.router)
app.include_router(bills.router)
app.include_router(ai.router)
app.include_router(reports.router)
app.include_router(notifications.router)
app.include_router(feedback.router)
app.include_router(shop.router)
app.include_router(warranties.router)

# Serve uploaded images
uploads_dir = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

# Health check endpoints
@app.get("/health")
@app.get("/api/health")
def health_check():
    db_status = "healthy"
    try:
        conn = get_db()
        conn.execute("SELECT 1").fetchone()
        conn.close()
    except Exception as e:
        db_status = f"unhealthy: {e}"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "service": "Mistri Enterprise API",
        "version": "1.2.0",
        "timestamp": datetime.now().isoformat(),
        "modules": [
            "auth_rbac", "repairs_lifecycle", "inventory_transactions",
            "dynamic_upi_qr", "warranties", "explainable_ai",
            "staged_photos", "smart_analytics", "audit_logging"
        ]
    }

@app.get("/api/qr/{repair_id}")
def get_qr_code(repair_id: str):
    """Generate QR code for a repair tracking URL."""
    tracking_url = f"http://localhost:8000/track/{repair_id}"
    qr_base64 = generate_qr_base64(tracking_url)
    return {"repair_id": repair_id, "qr_code": qr_base64, "tracking_url": tracking_url}

# Serve frontend static files
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=os.path.join(frontend_dir, "static")), name="static")

    @app.get("/", response_class=FileResponse)
    async def serve_root():
        return FileResponse(os.path.join(frontend_dir, "index.html"))

    @app.get("/{full_path:path}", response_class=FileResponse)
    async def serve_frontend(full_path: str):
        file_path = os.path.join(frontend_dir, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        # SPA fallback
        return FileResponse(os.path.join(frontend_dir, "index.html"))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
