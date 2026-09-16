"""
Mistri Notifications Route
"""
from fastapi import APIRouter, Depends
from db.database import get_db
from middleware.auth import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

@router.get("/")
def get_notifications(current_user: dict = Depends(get_current_user)):
    conn = get_db()
    notifs = conn.execute("""
        SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 20
    """, (current_user["id"],)).fetchall()
    conn.close()
    result = []
    for n in notifs:
        item = dict(n)
        if item.get("created_at") and isinstance(item["created_at"], str) and not item["created_at"].endswith("Z"):
            item["created_at"] = item["created_at"].replace(" ", "T") + "Z"
        result.append(item)
    return result

@router.patch("/{notif_id}/read")
def mark_read(notif_id: int, current_user: dict = Depends(get_current_user)):
    conn = get_db()
    conn.execute("UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?", (notif_id, current_user["id"]))
    conn.commit()
    conn.close()
    return {"message": "Marked as read"}

@router.patch("/read-all")
def mark_all_read(current_user: dict = Depends(get_current_user)):
    conn = get_db()
    conn.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (current_user["id"],))
    conn.commit()
    conn.close()
    return {"message": "All marked as read"}
