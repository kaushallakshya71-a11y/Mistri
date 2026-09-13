"""
Mistri Feedback Routes - Customer reviews, technician ratings, and admin aggregate summaries.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from db.database import get_db
from middleware.auth import get_current_user, require_role
from utils.audit import log_audit_event

router = APIRouter(prefix="/api/feedback", tags=["feedback"])

class FeedbackCreate(BaseModel):
    repair_job_id: int
    rating: int                 # 1-5 overall service rating
    technician_rating: Optional[int] = None  # 1-5 specific technician rating
    comment: Optional[str] = None

@router.post("/")
def submit_feedback(req: FeedbackCreate, current_user: dict = Depends(get_current_user)):
    """Customer submits feedback for a completed/delivered repair."""
    if current_user["role"] != "customer":
        raise HTTPException(403, "Only customers can submit feedback.")

    if req.rating < 1 or req.rating > 5:
        raise HTTPException(400, "Service rating must be between 1 and 5.")

    if req.technician_rating is not None and (req.technician_rating < 1 or req.technician_rating > 5):
        raise HTTPException(400, "Technician rating must be between 1 and 5.")

    conn = get_db()
    job = conn.execute(
        "SELECT id, status, customer_id, technician_id, repair_id FROM repair_jobs WHERE id=?",
        (req.repair_job_id,)
    ).fetchone()

    if not job:
        conn.close()
        raise HTTPException(404, "Repair job not found.")
    if job["customer_id"] != current_user["id"]:
        conn.close()
        raise HTTPException(403, "This repair does not belong to you.")
    if job["status"] not in ("Completed", "Delivered", "Ready"):
        conn.close()
        raise HTTPException(400, "Feedback can only be given for completed repairs.")

    # Check duplicate feedback
    existing = conn.execute(
        "SELECT id FROM feedback WHERE repair_job_id=? AND customer_id=?",
        (req.repair_job_id, current_user["id"])
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(400, "You have already submitted feedback for this repair.")

    tech_rating = req.technician_rating if req.technician_rating is not None else req.rating

    cursor = conn.execute("""
        INSERT INTO feedback (repair_job_id, customer_id, technician_id, rating, technician_rating, comment)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (req.repair_job_id, current_user["id"], job["technician_id"], req.rating, tech_rating, req.comment))

    feedback_id = cursor.lastrowid
    conn.commit()
    conn.close()

    log_audit_event(
        user=current_user,
        action="FEEDBACK_SUBMITTED",
        entity="feedback",
        entity_id=feedback_id,
        details={"repair_id": job["repair_id"], "rating": req.rating, "tech_rating": tech_rating}
    )

    return {"message": "Feedback submitted successfully! Thank you 🙏", "feedback_id": feedback_id}

@router.get("/")
def list_feedback(current_user: dict = Depends(require_role("admin"))):
    """Admin views all customer feedback."""
    conn = get_db()
    feedbacks = conn.execute("""
        SELECT f.*, u.name as customer_name, u.phone as customer_phone,
               rj.repair_id, d.brand, d.model, d.device_type,
               t.name as technician_name
        FROM feedback f
        JOIN users u ON f.customer_id = u.id
        JOIN repair_jobs rj ON f.repair_job_id = rj.id
        JOIN devices d ON rj.device_id = d.id
        LEFT JOIN users t ON f.technician_id = t.id
        ORDER BY f.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(f) for f in feedbacks]

@router.get("/summary")
def get_feedback_summary(current_user: dict = Depends(require_role("admin"))):
    """Aggregate customer satisfaction ratings and technician performance."""
    conn = get_db()
    total_reviews = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
    avg_rating = conn.execute("SELECT AVG(rating) FROM feedback").fetchone()[0]
    avg_tech_rating = conn.execute("SELECT AVG(technician_rating) FROM feedback").fetchone()[0]

    # Rating distribution
    dist = {}
    for stars in range(1, 6):
        count = conn.execute("SELECT COUNT(*) FROM feedback WHERE rating=?", (stars,)).fetchone()[0]
        dist[stars] = count

    # Ratings by technician
    tech_ratings = conn.execute("""
        SELECT t.id, t.name, COUNT(f.id) as reviews_count,
               AVG(COALESCE(f.technician_rating, f.rating)) as avg_rating
        FROM feedback f
        JOIN users t ON f.technician_id = t.id
        GROUP BY t.id
        ORDER BY avg_rating DESC
    """).fetchall()

    conn.close()
    return {
        "total_reviews": total_reviews,
        "avg_service_rating": round(float(avg_rating), 1) if avg_rating else 5.0,
        "avg_technician_rating": round(float(avg_tech_rating), 1) if avg_tech_rating else 5.0,
        "rating_distribution": dist,
        "technician_performance": [dict(tr) for tr in tech_ratings]
    }
