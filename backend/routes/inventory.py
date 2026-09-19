"""
Mistri Inventory Routes - Electrical Repair Parts Management
Full CRUD with electrical categories, brand/SKU tracking, and stock status.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from db.database import get_db
from middleware.auth import get_current_user, require_role
from utils.audit import log_audit_event
import json
from datetime import date, timedelta, datetime

router = APIRouter(prefix="/api/inventory", tags=["inventory"])

ELECTRICAL_CATEGORIES = [
    'Fan Parts', 'Cooler Parts', 'Mixer Parts', 'Motor Parts', 'Geyser Parts',
    'Pump Parts', 'Wires & Cables', 'Switches & Sockets', 'Capacitors', 'MCB & Fuse',
    'Relays', 'Connectors', 'LED Bulbs', 'Tape & Insulation', 'Fasteners', 'Misc Electrical'
]

class InventoryItem(BaseModel):
    part_name: str
    part_code: str
    category: str
    compatible_devices: Optional[List[str]] = []
    quantity: int
    unit_price: float
    purchase_price: Optional[float] = None
    sell_price: Optional[float] = None
    brand: Optional[str] = None
    sku: Optional[str] = None
    unit: Optional[str] = 'piece'
    reorder_level: int = 5
    reorder_quantity: int = 10
    supplier: Optional[str] = None
    is_active: Optional[int] = 1

class StockUpdate(BaseModel):
    quantity_change: int
    reason: Optional[str] = "Manual adjustment"

class RestockRequest(BaseModel):
    part_id: Optional[int] = None
    item_id: Optional[int] = None
    quantity: Optional[int] = None
    quantity_added: Optional[int] = None
    unit_cost: Optional[float] = None
    supplier: Optional[str] = None
    reason: Optional[str] = None
    notes: Optional[str] = None

@router.get("/categories")
def get_categories(current_user: dict = Depends(get_current_user)):
    """Get all electrical inventory categories."""
    return {"categories": ELECTRICAL_CATEGORIES}

@router.get("/")
def list_inventory(current_user: dict = Depends(get_current_user)):
    """List all inventory items with stock status."""
    conn = get_db()
    items = conn.execute("SELECT * FROM inventory ORDER BY category, part_name").fetchall()
    conn.close()
    result = []
    for item in items:
        d = dict(item)
        qty = d.get('quantity', 0)
        reorder = d.get('reorder_level', 5)
        d['low_stock'] = qty <= reorder
        if qty == 0:
            d['stock_status'] = 'Out of Stock'
        elif qty <= reorder:
            d['stock_status'] = 'Low Stock'
        else:
            d['stock_status'] = 'In Stock'
        result.append(d)
    return result

@router.get("/low-stock")
def get_low_stock(current_user: dict = Depends(require_role("admin", "staff"))):
    conn = get_db()
    items = conn.execute(
        "SELECT * FROM inventory WHERE quantity <= reorder_level ORDER BY quantity ASC"
    ).fetchall()
    conn.close()
    return [dict(i) for i in items]

@router.get("/reorder-alerts")
def get_reorder_alerts(current_user: dict = Depends(require_role("admin"))):
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
            "suggested_reorder_qty": recommended_order,
            "estimated_cost": recommended_order * item["unit_price"] * 0.7,
            "supplier": item["supplier"] or "Standard Wholesaler"
        })
    return alerts

@router.get("/transactions")
def get_inventory_transactions(limit: int = 50, current_user: dict = Depends(require_role("admin", "staff"))):
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
    
    sell_price = item.sell_price if item.sell_price is not None else item.unit_price
    purchase_price = item.purchase_price if item.purchase_price is not None else item.unit_price * 0.6

    cursor = conn.execute("""
        INSERT INTO inventory (part_name, part_code, category, compatible_devices, quantity,
                              unit_price, purchase_price, sell_price, brand, sku, unit,
                              reorder_level, reorder_quantity, supplier, is_active, shop_id)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (item.part_name, item.part_code, item.category, json.dumps(item.compatible_devices),
          item.quantity, sell_price, purchase_price, sell_price,
          item.brand, item.sku, item.unit or 'piece',
          item.reorder_level, item.reorder_quantity, item.supplier, item.is_active or 1,
          current_user.get("shop_id", 1)))

    item_id = cursor.lastrowid

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

    return {"message": "Electrical inventory item added", "id": item_id}

@router.post("/restock")
def restock_item(req: RestockRequest, current_user: dict = Depends(require_role("admin"))):
    target_id = req.part_id if req.part_id is not None else req.item_id
    if not target_id:
        raise HTTPException(400, "Item ID is required for restock.")

    qty = req.quantity if req.quantity is not None else req.quantity_added
    if qty is None or qty <= 0:
        raise HTTPException(400, "Restock quantity must be positive.")

    conn = get_db()
    item = conn.execute("SELECT * FROM inventory WHERE id=?", (target_id,)).fetchone()
    if not item:
        conn.close()
        raise HTTPException(404, "Inventory item not found.")

    new_qty = item["quantity"] + qty
    supplier_val = req.supplier.strip() if (req.supplier and req.supplier.strip()) else item["supplier"]
    note_reason = req.reason or req.notes or "Restock shipment received"

    if req.unit_cost is not None and req.unit_cost > 0:
        conn.execute("""
            UPDATE inventory 
            SET quantity=?, supplier=?, purchase_price=?, updated_at=CURRENT_TIMESTAMP 
            WHERE id=?
        """, (new_qty, supplier_val, req.unit_cost, target_id))
    else:
        conn.execute("""
            UPDATE inventory 
            SET quantity=?, supplier=?, updated_at=CURRENT_TIMESTAMP 
            WHERE id=?
        """, (new_qty, supplier_val, target_id))

    conn.execute("""
        INSERT INTO inventory_transactions (part_id, quantity, transaction_type, staff_id, reason)
        VALUES (?, ?, 'IN', ?, ?)
    """, (target_id, qty, current_user["id"], note_reason))
    conn.commit()
    conn.close()

    log_audit_event(
        user=current_user,
        action="INVENTORY_RESTOCKED",
        entity="inventory",
        entity_id=target_id,
        details={
            "part_name": item["part_name"],
            "added": qty,
            "new_total": new_qty,
            "supplier": supplier_val,
            "unit_cost": req.unit_cost
        }
    )
    return {"message": f"Successfully restocked {qty} units.", "new_quantity": new_qty}

@router.put("/{item_id}")
def update_item(item_id: int, item: InventoryItem, current_user: dict = Depends(require_role("admin"))):
    conn = get_db()
    sell_price = item.sell_price if item.sell_price is not None else item.unit_price
    purchase_price = item.purchase_price if item.purchase_price is not None else item.unit_price * 0.6
    conn.execute("""
        UPDATE inventory SET part_name=?, part_code=?, category=?, compatible_devices=?,
        quantity=?, unit_price=?, purchase_price=?, sell_price=?, brand=?, sku=?, unit=?,
        reorder_level=?, reorder_quantity=?, supplier=?, is_active=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (item.part_name, item.part_code, item.category, json.dumps(item.compatible_devices),
          item.quantity, sell_price, purchase_price, sell_price,
          item.brand, item.sku, item.unit or 'piece',
          item.reorder_level, item.reorder_quantity, item.supplier, item.is_active or 1, item_id))
    conn.commit()
    conn.close()
    log_audit_event(user=current_user, action="INVENTORY_UPDATED", entity="inventory",
        entity_id=item_id, details={"part_name": item.part_name})
    return {"message": "Item updated"}

@router.patch("/{item_id}/toggle")
def toggle_item_status(item_id: int, current_user: dict = Depends(require_role("admin"))):
    conn = get_db()
    item = conn.execute("SELECT * FROM inventory WHERE id=?", (item_id,)).fetchone()
    if not item:
        conn.close()
        raise HTTPException(404, "Item not found")
    new_status = 0 if item["is_active"] == 1 else 1
    conn.execute("UPDATE inventory SET is_active=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (new_status, item_id))
    conn.commit()
    conn.close()
    return {"message": "Item status toggled", "is_active": new_status}

@router.patch("/{item_id}/stock")
def update_stock(item_id: int, update: StockUpdate, current_user: dict = Depends(require_role("admin", "staff"))):
    conn = get_db()
    item = conn.execute("SELECT * FROM inventory WHERE id=?", (item_id,)).fetchone()
    if not item:
        conn.close()
        raise HTTPException(404, "Item not found")

    if update.quantity_change < 0:
        deduct_qty = abs(update.quantity_change)
        cursor = conn.execute(
            "UPDATE inventory SET quantity = quantity - ?, updated_at=CURRENT_TIMESTAMP WHERE id = ? AND quantity >= ?",
            (deduct_qty, item_id, deduct_qty)
        )
        if cursor.rowcount == 0:
            current_qty = conn.execute("SELECT quantity FROM inventory WHERE id=?", (item_id,)).fetchone()["quantity"]
            conn.close()
            raise HTTPException(400, f"Insufficient stock: cannot reduce below zero (current: {current_qty}, requested deduction: {deduct_qty}).")
    elif update.quantity_change > 0:
        conn.execute(
            "UPDATE inventory SET quantity = quantity + ?, updated_at=CURRENT_TIMESTAMP WHERE id = ?",
            (update.quantity_change, item_id)
        )

    updated_item = conn.execute("SELECT quantity, reorder_level FROM inventory WHERE id=?", (item_id,)).fetchone()
    new_qty = updated_item["quantity"]
    tx_type = "IN" if update.quantity_change > 0 else "OUT"
    conn.execute("""
        INSERT INTO inventory_transactions (part_id, quantity, transaction_type, staff_id, reason)
        VALUES (?, ?, ?, ?, ?)
    """, (item_id, abs(update.quantity_change), tx_type, current_user["id"], update.reason or "Manual adjustment"))
    conn.commit()
    conn.close()
    return {"message": "Stock updated", "new_quantity": new_qty, "low_stock": new_qty <= updated_item["reorder_level"]}

@router.delete("/{item_id}")
def delete_item(item_id: int, hard: bool = False, current_user: dict = Depends(require_role("admin"))):
    conn = get_db()
    item = conn.execute("SELECT id, part_name FROM inventory WHERE id=?", (item_id,)).fetchone()
    if not item:
        conn.close()
        raise HTTPException(404, "Inventory item not found.")

    if hard:
        conn.execute("DELETE FROM inventory_transactions WHERE part_id=?", (item_id,))
        conn.execute("DELETE FROM inventory WHERE id=?", (item_id,))
        msg = f"Item '{item['part_name']}' permanently deleted."
    else:
        conn.execute("UPDATE inventory SET is_active=0, updated_at=CURRENT_TIMESTAMP WHERE id=?", (item_id,))
        msg = f"Item '{item['part_name']}' deactivated."

    conn.commit()
    conn.close()
    return {"message": msg}
