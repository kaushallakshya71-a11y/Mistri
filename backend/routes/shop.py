"""
Mistri Shop Routes - Buy & Sell products and orders
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
import json
import uuid
from db.database import get_db
from middleware.auth import get_current_user, require_role

router = APIRouter(prefix="/api/shop", tags=["shop"])

# --- Models ---
class ShopProduct(BaseModel):
    name: str
    description: Optional[str] = None
    category: str
    brand: Optional[str] = None
    size_variant: Optional[str] = None
    unit: Optional[str] = None
    price: float
    stock_qty: int
    image_url: Optional[str] = None
    is_active: bool = True

class OrderItem(BaseModel):
    product_id: int
    quantity: int
    price: float

class ShopOrder(BaseModel):
    items: List[OrderItem]
    total_amount: float
    delivery_address: Optional[str] = None
    payment_method: str = "Cash on Delivery"
    notes: Optional[str] = None

class OrderStatusUpdate(BaseModel):
    status: str

# --- Product Endpoints ---

@router.get("/products")
def list_products(category: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """List all active products for the shop. Admins get all products."""
    conn = get_db()
    query = "SELECT * FROM shop_products"
    params = []
    
    conditions = []
    if current_user.get("role") != "admin":
        conditions.append("is_active = 1")
    
    if category and category != 'All':
        conditions.append("category = ?")
        params.append(category)
        
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
        
    query += " ORDER BY category, name"
    
    items = conn.execute(query, tuple(params)).fetchall()
    conn.close()
    return [dict(i) for i in items]

@router.get("/products/{product_id}")
def get_product(product_id: int, current_user: dict = Depends(get_current_user)):
    """Get single product detail"""
    conn = get_db()
    item = conn.execute("SELECT * FROM shop_products WHERE id = ?", (product_id,)).fetchone()
    conn.close()
    if not item:
        raise HTTPException(404, "Product not found")
    return dict(item)

@router.post("/products")
def add_product(item: ShopProduct, current_user: dict = Depends(require_role("admin"))):
    """Add new shop product (Admin only)"""
    conn = get_db()
    conn.execute("""
        INSERT INTO shop_products (name, description, category, brand, size_variant, unit, price, stock_qty, image_url, is_active)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (item.name, item.description, item.category, item.brand, item.size_variant, item.unit, item.price, item.stock_qty, item.image_url, 1 if item.is_active else 0))
    conn.commit()
    conn.close()
    return {"message": "Product added successfully"}

@router.put("/products/{product_id}")
def update_product(product_id: int, item: ShopProduct, current_user: dict = Depends(require_role("admin"))):
    """Update a product (Admin only)"""
    conn = get_db()
    conn.execute("""
        UPDATE shop_products SET 
            name=?, description=?, category=?, brand=?, size_variant=?, unit=?, price=?, 
            stock_qty=?, image_url=?, is_active=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (item.name, item.description, item.category, item.brand, item.size_variant, item.unit, item.price, item.stock_qty, item.image_url, 1 if item.is_active else 0, product_id))
    conn.commit()
    conn.close()
    return {"message": "Product updated"}

@router.delete("/products/{product_id}")
def delete_product(product_id: int, current_user: dict = Depends(require_role("admin"))):
    """Delete a product (Admin only)"""
    conn = get_db()
    conn.execute("DELETE FROM shop_products WHERE id=?", (product_id,))
    conn.commit()
    conn.close()
    return {"message": "Product deleted"}


# --- Order Endpoints ---

@router.get("/orders")
def list_all_orders(current_user: dict = Depends(require_role("admin", "staff"))):
    """List all orders for admin/staff"""
    conn = get_db()
    items = conn.execute("""
        SELECT o.*, u.name as customer_name, u.phone as customer_phone
        FROM shop_orders o
        JOIN users u ON o.customer_id = u.id
        ORDER BY o.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(i) for i in items]

@router.get("/orders/mine")
def get_my_orders(current_user: dict = Depends(get_current_user)):
    """List logged-in user's orders"""
    conn = get_db()
    items = conn.execute("SELECT * FROM shop_orders WHERE customer_id = ? ORDER BY created_at DESC", 
                         (current_user["id"],)).fetchall()
    conn.close()
    return [dict(i) for i in items]

@router.post("/orders")
def place_order(order: ShopOrder, current_user: dict = Depends(get_current_user)):
    """Place a new shop order"""
    order_number = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Validate stock and deduct inventory
        for item in order.items:
            product = cursor.execute("SELECT stock_qty, name FROM shop_products WHERE id = ?", (item.product_id,)).fetchone()
            if not product:
                raise HTTPException(400, f"Product {item.product_id} not found")
            if product["stock_qty"] < item.quantity:
                raise HTTPException(400, f"Insufficient stock for {product['name']}. Available: {product['stock_qty']}")
                
            # Deduct stock
            new_qty = product["stock_qty"] - item.quantity
            cursor.execute("UPDATE shop_products SET stock_qty = ? WHERE id = ?", (new_qty, item.product_id))

        # Insert order
        items_json = json.dumps([i.dict() for i in order.items])
        cursor.execute("""
            INSERT INTO shop_orders (order_number, customer_id, items, total_amount, delivery_address, payment_method, notes)
            VALUES (?,?,?,?,?,?,?)
        """, (order_number, current_user["id"], items_json, order.total_amount, order.delivery_address, order.payment_method, order.notes))
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
        
    return {"message": "Order placed successfully", "order_number": order_number}

@router.patch("/orders/{order_id}/status")
def update_order_status(order_id: int, update: OrderStatusUpdate, current_user: dict = Depends(require_role("admin", "staff"))):
    """Update order status (Admin/Staff only)"""
    conn = get_db()
    cursor = conn.cursor()
    
    order = cursor.execute("SELECT * FROM shop_orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        conn.close()
        raise HTTPException(404, "Order not found")
        
    cursor.execute("UPDATE shop_orders SET status = ? WHERE id = ?", (update.status, order_id))
    
    # Send notification to customer
    cursor.execute("""
        INSERT INTO notifications (user_id, title, message)
        VALUES (?,?,?)
    """, (order["customer_id"], "Order Update", f"Your order {order['order_number']} is now {update.status}."))
    
    conn.commit()
    conn.close()
    
    return {"message": f"Order status updated to {update.status}"}
