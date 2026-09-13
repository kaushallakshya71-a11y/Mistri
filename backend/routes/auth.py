"""
Mistri Auth Routes - Register, Login, Profile
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import bcrypt as _bcrypt
from jose import jwt
from datetime import datetime, timedelta
from db.database import get_db
from middleware.auth import SECRET_KEY, ALGORITHM, get_current_user
from fastapi import Depends
import re

def _hash_pw(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()

def _verify_pw(password: str, hashed: str) -> bool:
    return _bcrypt.checkpw(password.encode(), hashed.encode())

router = APIRouter(prefix="/api/auth", tags=["auth"])

ACCESS_TOKEN_EXPIRE_HOURS = 24

class RegisterRequest(BaseModel):
    name: str
    email: str
    phone: str = None
    password: str
    role: str = "customer"  # customers self-register; admin creates staff

class LoginRequest(BaseModel):
    email: str
    password: str

def create_access_token(user_id: int, role: str):
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {"sub": str(user_id), "role": role, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

@router.post("/register")
def register(req: RegisterRequest):
    # Only customers can self-register; staff must be created by admin
    if req.role not in ("customer",):
        raise HTTPException(400, "Only customers can self-register.")

    if len(req.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters.")

    conn = get_db()
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (req.email,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(400, "Email already registered.")

    hashed = _hash_pw(req.password)
    cursor = conn.execute(
        "INSERT INTO users (name, email, phone, password_hash, role) VALUES (?,?,?,?,?)",
        (req.name, req.email, req.phone, hashed, req.role)
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()

    token = create_access_token(user_id, req.role)
    return {"access_token": token, "token_type": "bearer", "role": req.role, "name": req.name}

@router.post("/login")
def login(req: LoginRequest):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (req.email,)).fetchone()
    conn.close()

    if not user or not _verify_pw(req.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password.")

    token = create_access_token(user["id"], user["role"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user["role"],
        "name": user["name"],
        "user_id": user["id"]
    }

@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return {k: v for k, v in current_user.items() if k != "password_hash"}

@router.get("/users")
def list_users(current_user: dict = Depends(get_current_user)):
    """Admin only: list all users."""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Admins only.")
    conn = get_db()
    users = conn.execute("SELECT id, name, email, phone, role, created_at FROM users").fetchall()
    conn.close()
    return [dict(u) for u in users]

@router.post("/staff")
def create_staff(req: RegisterRequest, current_user: dict = Depends(get_current_user)):
    """Admin only: create staff accounts."""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Admins only.")
    conn = get_db()
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (req.email,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(400, "Email already registered.")
    hashed = _hash_pw(req.password)
    cursor = conn.execute(
        "INSERT INTO users (name, email, phone, password_hash, role) VALUES (?,?,?,?,?)",
        (req.name, req.email, req.phone, hashed, "staff")
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return {"message": "Staff created", "user_id": user_id}

class UserUpdate(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None

@router.put("/users/{user_id}")
def update_user(user_id: int, req: UserUpdate, current_user: dict = Depends(get_current_user)):
    """Admin only: edit any user's basic info."""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Admins only.")
    conn = get_db()
    # Check email collision with other users
    conflict = conn.execute("SELECT id FROM users WHERE email=? AND id!=?", (req.email, user_id)).fetchone()
    if conflict:
        conn.close()
        raise HTTPException(400, "Email already in use by another user.")
    conn.execute(
        "UPDATE users SET name=?, email=?, phone=? WHERE id=?",
        (req.name, req.email, req.phone, user_id)
    )
    conn.commit()
    conn.close()
    return {"message": "User updated successfully."}
