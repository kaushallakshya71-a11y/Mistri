"""
Mistri Inventory Routes - CRUD, Reorder System, Low-stock Alerts, and Transaction Audit History
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from db.database import get_db
from middleware.auth import get_current_user, require_role
from utils.audit import log_audit_event
import json

router = APIRouter(prefix="/api/inventory", tags=["inventory"])

class InventoryItem(BaseModel):
    part_name: str
    part_code: str
    category: str
    compatible_devices: Optional[List[str]] = []
    quantity: int
    unit_price: float
    reorder_level: int = 5
    reorder_quantity: int = 10
    supplier: Optional[str] = None

class StockUpdate(BaseModel):
    quantity_change: int  # positive = restock, negative = use
    reason: Optional[str] = "Manual adjustment"

class RestockRequest(BaseModel):
    part_id: int
    quantity: int
    supplier: Optional[str] = None
    reason: Optional[str] = "Restock delivery"

@router.get("/")
def list_inventory(current_user: dict = Depends(get_current_user)):
    """List all inventory items with low-stock calculation."""
    conn = get_db()
    items = conn.execute("SELECT * FROM inventory ORDER BY category, part_name").fetchall()
    conn.close()
    result = []
    for item in items:
        d = dict(item)
        d["low_stock"] = d["quantity"] <= d["reorder_level"]
        result.append(d)
    return result

@router.get("/low-stock")
def get_low_stock(current_user: dict = Depends(require_role("admin", "staff"))):
    """Retrieve items currently at or below minimum reorder level."""
    conn = get_db()
    items = conn.execute(
        "SELECT * FROM inventory WHERE quantity <= reorder_level ORDER BY quantity ASC"
    ).fetchall()
    conn.close()
    return [dict(i) for i in items]

@router.get("/reorder-alerts")
def get_reorder_alerts(current_user: dict = Depends(require_role("admin"))):
    """Smart reorder recommendations for shop inventory."""
    conn = get_db()
    items = conn.execute("""
        SELECT id, part_name, part_code, category, quantity, reorder_level,
               reorder_quantity, supplier, unit_price
        FROM inventory
        WHERE quantity <= reorder_level
        ORDER BY (quantity - reorder_level) ASC
    """).fetchall()
    conn.close()

    alerts = []
    for item in items:
        deficit = max(0, item["reorder_level"] - item["quantity"])
        recommended_order = max(item["reorder_quantity"], deficit + 5)
        alerts.append({
            "id": item["id"],
            "part_id": item["id"],
            "part_name": item["part_name"],
            "part_code": item["part_code"],
            "category": item["category"],
            "current_stock": item["quantity"],
            "reorder_level": item["reorder_level"],
            "recommended_order": recommended_order,
            "estimated_cost": recommended_order * item["unit_price"] * 0.7,  # estimated wholesale cost
            "supplier": item["supplier"] or "Standard Wholesaler"
        })
    return alerts

@router.get("/transactions")
def get_inventory_transactions(limit: int = 50, current_user: dict = Depends(require_role("admin", "staff"))):
    """View chronological inventory movement audit (IN/OUT)."""
    conn = get_db()
    txs = conn.execute("""
        SELECT it.*, i.part_name, i.part_code, u.name as staff_name, rj.repair_id
        FROM inventory_transactions it
        JOIN inventory i ON it.part_id = i.id
        LEFT JOIN users u ON it.staff_id = u.id
        LEFT JOIN repair_jobs rj ON it.repair_job_id = rj.id
        ORDER BY it.created_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(t) for t in txs]

@router.post("/")
def add_item(item: InventoryItem, current_user: dict = Depends(require_role("admin"))):
    conn = get_db()
    existing = conn.execute("SELECT id FROM inventory WHERE part_code=?", (item.part_code,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(400, "Part code already exists.")

    cursor = conn.execute("""
        INSERT INTO inventory (part_name, part_code, category, compatible_devices, quantity,
                              unit_price, reorder_level, reorder_quantity, supplier, shop_id)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (item.part_name, item.part_code, item.category, json.dumps(item.compatible_devices),
          item.quantity, item.unit_price, item.reorder_level, item.reorder_quantity, item.supplier,
          current_user.get("shop_id", 1)))

    item_id = cursor.lastrowid

    # Record initial stock IN transaction if quantity > 0
    if item.quantity > 0:
        conn.execute("""
            INSERT INTO inventory_transactions (part_id, quantity, transaction_type, staff_id, reason)
            VALUES (?, ?, 'IN', ?, 'Initial stock setup')
        """, (item_id, item.quantity, current_user["id"]))

    conn.commit()
    conn.close()

    log_audit_event(
        user=current_user,
        action="INVENTORY_ITEM_CREATED",
        entity="inventory",
        entity_id=item_id,
        details={"part_name": item.part_name, "quantity": item.quantity}
    )

    return {"message": "Inventory item added", "id": item_id}

@router.post("/restock")
def restock_item(req: RestockRequest, current_user: dict = Depends(require_role("admin"))):
    """Admin restocks spare parts inventory with audit trail."""
    if req.quantity <= 0:
        raise HTTPException(400, "Restock quantity must be positive.")

    conn = get_db()
    item = conn.execute("SELECT * FROM inventory WHERE id=?", (req.part_id,)).fetchone()
    if not item:
        conn.close()
        raise HTTPException(404, "Inventory item not found.")

    new_qty = item["quantity"] + req.quantity
    conn.execute("UPDATE inventory SET quantity=?, supplier=COALESCE(?, supplier), updated_at=CURRENT_TIMESTAMP WHERE id=?",
                 (new_qty, req.supplier, req.part_id))

    conn.execute("""
        INSERT INTO inventory_transactions (part_id, quantity, transaction_type, staff_id, reason)
        VALUES (?, ?, 'IN', ?, ?)
    """, (req.part_id, req.quantity, current_user["id"], req.reason or "Restock shipment received"))

    conn.commit()
    conn.close()

    log_audit_event(
        user=current_user,
        action="INVENTORY_RESTOCKED",
        entity="inventory",
        entity_id=req.part_id,
        details={"part_name": item["part_name"], "added": req.quantity, "new_total": new_qty}
    )

    return {"message": f"Successfully restocked {req.quantity} units.", "new_quantity": new_qty}

@router.put("/{item_id}")
def update_item(item_id: int, item: InventoryItem, current_user: dict = Depends(require_role("admin"))):
    conn = get_db()
    conn.execute("""
        UPDATE inventory SET part_name=?, part_code=?, category=?, compatible_devices=?,
        quantity=?, unit_price=?, reorder_level=?, reorder_quantity=?, supplier=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (item.part_name, item.part_code, item.category, json.dumps(item.compatible_devices),
          item.quantity, item.unit_price, item.reorder_level, item.reorder_quantity, item.supplier, item_id))
    conn.commit()
    conn.close()
    return {"message": "Item updated"}

@router.patch("/{item_id}/stock")
def update_stock(item_id: int, update: StockUpdate, current_user: dict = Depends(require_role("admin", "staff"))):
    """Manually adjust stock with strict negative quantity prevention."""
    conn = get_db()
    item = conn.execute("SELECT * FROM inventory WHERE id=?", (item_id,)).fetchone()
    if not item:
        conn.close()
        raise HTTPException(404, "Item not found")

    new_qty = item["quantity"] + update.quantity_change
    if new_qty < 0:
        conn.close()
        raise HTTPException(400, f"Insufficient stock: cannot reduce stock below zero (current: {item['quantity']}).")

    conn.execute("UPDATE inventory SET quantity=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                 (new_qty, item_id))

    tx_type = "IN" if update.quantity_change > 0 else "OUT"
    conn.execute("""
        INSERT INTO inventory_transactions (part_id, quantity, transaction_type, staff_id, reason)
        VALUES (?, ?, ?, ?, ?)
    """, (item_id, abs(update.quantity_change), tx_type, current_user["id"], update.reason or "Manual adjustment"))

    conn.commit()
    conn.close()

    return {"message": "Stock updated", "new_quantity": new_qty, "low_stock": new_qty <= item["reorder_level"]}

@router.delete("/{item_id}")
def delete_item(item_id: int, current_user: dict = Depends(require_role("admin"))):
    conn = get_db()
    conn.execute("DELETE FROM inventory WHERE id=?", (item_id,))
    conn.commit()
    conn.close()
    return {"message": "Item deleted"}
