"""
Mistri Auth Routes - Register, Login, Profile, Google OAuth
Includes full validation: Gmail-only for customers, Indian phone format, strong passwords.
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional
import bcrypt as _bcrypt
from jose import jwt
from datetime import datetime, timedelta
from db.database import get_db
from middleware.auth import SECRET_KEY, ALGORITHM, get_current_user
import re
import os
import httpx
import json
import urllib.parse

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash_pw(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()

def _verify_pw(password: str, hashed: str) -> bool:
    return _bcrypt.checkpw(password.encode(), hashed.encode())

def validate_gmail(email: str, role: str = "customer") -> None:
    """Customers must use a valid Gmail address."""
    if role != "customer":
        return  # Admin/staff not restricted
    pattern = r'^[a-zA-Z0-9._%+\-]+@gmail\.com$'
    if not re.match(pattern, email.strip().lower()):
        raise HTTPException(
            400,
            "Customers must register with a valid Gmail address (e.g. yourname@gmail.com). "
            "Please use a Gmail account to continue."
        )

def validate_phone(phone: str) -> None:
    """Validate Indian mobile number: exactly 10 digits, starting with 6-9."""
    if not phone:
        return  # Phone is optional — skip if not provided
    digits = re.sub(r'[\s\-\+()]', '', phone)  # Strip spaces, dashes, brackets
    if digits.startswith('91') and len(digits) == 12:
        digits = digits[2:]  # Strip country code 91
    if not re.match(r'^[6-9][0-9]{9}$', digits):
        raise HTTPException(
            400,
            "Please enter a valid 10-digit Indian mobile number starting with 6, 7, 8, or 9 "
            "(e.g. 9876543210). Do not include country code or special characters."
        )

def validate_password_strength(password: str) -> None:
    """Enforce strong password policy."""
    errors = []
    if len(password) < 8:
        errors.append("at least 8 characters")
    if not re.search(r'[A-Z]', password):
        errors.append("at least 1 uppercase letter (A-Z)")
    if not re.search(r'[a-z]', password):
        errors.append("at least 1 lowercase letter (a-z)")
    if not re.search(r'[0-9]', password):
        errors.append("at least 1 number (0-9)")
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};:\'"|,.<>?/\\`~]', password):
        errors.append("at least 1 special character (!@#$%^&* etc.)")
    if errors:
        raise HTTPException(
            400,
            f"Password is too weak. It must have: {', '.join(errors)}. "
            "Example: MyPass@123"
        )

router = APIRouter(prefix="/api/auth", tags=["auth"])

ACCESS_TOKEN_EXPIRE_HOURS = 24

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    password: str
    role: str = "customer"

class LoginRequest(BaseModel):
    email: str
    password: str

class UserUpdate(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None

# ---------------------------------------------------------------------------
# Token
# ---------------------------------------------------------------------------

def create_access_token(user_id: int, role: str) -> str:
    from datetime import timezone
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {"sub": str(user_id), "role": role, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

@router.post("/register")
def register(req: RegisterRequest):
    # Only customers can self-register
    if req.role not in ("customer",):
        raise HTTPException(400, "Only customers can self-register. Staff accounts are created by admin.")

    # Validate email (Gmail-only for customers)
    validate_gmail(req.email.strip(), req.role)

    # Validate phone
    if req.phone and req.phone.strip():
        validate_phone(req.phone.strip())

    # Validate password strength
    validate_password_strength(req.password)

    conn = get_db()
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (req.email.strip().lower(),)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(400, "This Gmail address is already registered. Please login or use a different account.")

    hashed = _hash_pw(req.password)
    # Normalize phone digits
    phone_clean = None
    if req.phone and req.phone.strip():
        phone_clean = re.sub(r'[\s\-\+()]', '', req.phone.strip())
        if phone_clean.startswith('91') and len(phone_clean) == 12:
            phone_clean = phone_clean[2:]

    cursor = conn.execute(
        "INSERT INTO users (name, email, phone, password_hash, role, auth_provider) VALUES (?,?,?,?,?,?)",
        (req.name.strip(), req.email.strip().lower(), phone_clean, hashed, req.role, 'email')
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()

    token = create_access_token(user_id, req.role)
    return {"access_token": token, "token_type": "bearer", "role": req.role,
            "name": req.name.strip(), "user_id": user_id}

# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@router.post("/login")
def login(req: LoginRequest):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (req.email.strip().lower(),)).fetchone()
    conn.close()

    if not user:
        raise HTTPException(401, "Email address not found. Please register or check your email.")

    # Google-only accounts cannot login with password
    if user["auth_provider"] == "google" and not user["password_hash"]:
        raise HTTPException(401, "This account was created with Google Sign-In. Please use 'Continue with Google' to login.")

    if not _verify_pw(req.password, user["password_hash"]):
        raise HTTPException(401, "Incorrect password. Please try again.")

    token = create_access_token(user["id"], user["role"])
    return {
        "access_token": token, "token_type": "bearer",
        "role": user["role"], "name": user["name"], "user_id": user["id"]
    }

# ---------------------------------------------------------------------------
# Me / Profile
# ---------------------------------------------------------------------------

@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return {k: v for k, v in current_user.items() if k not in ("password_hash",)}

@router.get("/profile")
def get_profile(current_user: dict = Depends(get_current_user)):
    return {k: v for k, v in current_user.items() if k not in ("password_hash",)}

# ---------------------------------------------------------------------------
# Admin: List Users
# ---------------------------------------------------------------------------

@router.get("/users")
def list_users(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(403, "Admins only.")
    conn = get_db()
    users = conn.execute(
        "SELECT id, name, email, phone, role, auth_provider, created_at FROM users"
    ).fetchall()
    conn.close()
    return [dict(u) for u in users]

# ---------------------------------------------------------------------------
# Admin: Create Staff
# ---------------------------------------------------------------------------

@router.post("/staff")
def create_staff(req: RegisterRequest, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(403, "Admins only.")
    # Staff email not restricted to Gmail
    validate_password_strength(req.password)
    conn = get_db()
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (req.email.strip().lower(),)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(400, "Email already registered.")
    hashed = _hash_pw(req.password)
    cursor = conn.execute(
        "INSERT INTO users (name, email, phone, password_hash, role, auth_provider) VALUES (?,?,?,?,?,?)",
        (req.name.strip(), req.email.strip().lower(), req.phone, hashed, "staff", "email")
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return {"message": "Staff created", "user_id": user_id}

# ---------------------------------------------------------------------------
# Admin: Update User
# ---------------------------------------------------------------------------

@router.put("/users/{user_id}")
def update_user(user_id: int, req: UserUpdate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(403, "Admins only.")
    conn = get_db()
    conflict = conn.execute(
        "SELECT id FROM users WHERE email=? AND id!=?", (req.email.strip().lower(), user_id)
    ).fetchone()
    if conflict:
        conn.close()
        raise HTTPException(400, "Email already in use by another user.")
    conn.execute(
        "UPDATE users SET name=?, email=?, phone=? WHERE id=?",
        (req.name.strip(), req.email.strip().lower(), req.phone, user_id)
    )
    conn.commit()
    conn.close()
    return {"message": "User updated successfully."}

# ---------------------------------------------------------------------------
# Google OAuth
# ---------------------------------------------------------------------------

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback")

@router.get("/google/url")
def google_oauth_url():
    """Return Google OAuth authorization URL for frontend redirect."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            503,
            "Google Sign-In is not configured. Please contact administrator to set up Google OAuth credentials."
        )
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account"
    }
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    return {"url": auth_url}

@router.get("/google/callback")
async def google_oauth_callback(code: str, state: Optional[str] = None, error: Optional[str] = None):
    """Handle Google OAuth callback, verify token, create/find user, return JWT."""
    if error:
        raise HTTPException(400, f"Google authentication was cancelled or failed: {error}")

    if not code:
        raise HTTPException(400, "Missing authorization code from Google.")

    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(503, "Google Sign-In is not configured on the server.")

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code"
            }
        )

    if token_resp.status_code != 200:
        raise HTTPException(400, "Failed to verify Google credentials. Please try again.")

    token_data = token_resp.json()
    id_token_str = token_data.get("id_token")
    if not id_token_str:
        raise HTTPException(400, "Google did not return an identity token.")

    # Verify the ID token using Google's public keys
    async with httpx.AsyncClient() as client:
        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {token_data.get('access_token')}"}
        )

    if userinfo_resp.status_code != 200:
        raise HTTPException(400, "Failed to fetch Google profile information.")

    google_user = userinfo_resp.json()
    google_id = google_user.get("sub")
    email = google_user.get("email", "").strip().lower()
    name = google_user.get("name", email.split("@")[0])
    email_verified = google_user.get("email_verified", False)

    if not email or not google_id:
        raise HTTPException(400, "Google did not provide a valid email address.")

    if not email_verified:
        raise HTTPException(400, "Your Google email address is not verified. Please verify your Google account first.")

    # Check if Gmail (customers should use Gmail)
    if not email.endswith("@gmail.com"):
        raise HTTPException(
            400,
            "Please use a Gmail account (ending with @gmail.com) to sign in with Google."
        )

    conn = get_db()

    # Find existing user by google_id or email
    existing = conn.execute(
        "SELECT * FROM users WHERE google_id=? OR email=?", (google_id, email)
    ).fetchone()

    if existing:
        # Link Google account if not already linked
        if not existing["google_id"]:
            conn.execute(
                "UPDATE users SET google_id=?, auth_provider='google' WHERE id=?",
                (google_id, existing["id"])
            )
            conn.commit()
        user_id = existing["id"]
        role = existing["role"]
        user_name = existing["name"]
    else:
        # Create new customer account
        cursor = conn.execute(
            "INSERT INTO users (name, email, google_id, password_hash, role, auth_provider) VALUES (?,?,?,?,?,?)",
            (name, email, google_id, "", "customer", "google")
        )
        conn.commit()
        user_id = cursor.lastrowid
        role = "customer"
        user_name = name

    conn.close()

    # Generate app JWT
    token = create_access_token(user_id, role)

    # Return HTML page that posts token to parent window / redirects
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><title>Logging in...</title></head>
    <body>
        <script>
            var token = {json.dumps(token)};
            var role = {json.dumps(role)};
            var name = {json.dumps(user_name)};
            var userId = {json.dumps(user_id)};
            // Store in localStorage
            localStorage.setItem('mistri_token', token);
            localStorage.setItem('mistri_user', JSON.stringify({{name: name, role: role, user_id: userId}}));
            // If opened in popup, notify parent
            if (window.opener) {{
                window.opener.postMessage({{type:'google_auth_success', token, role, name, user_id: userId}}, '*');
                window.close();
            }} else {{
                // Direct redirect
                if (role === 'admin') window.location.href = '/admin';
                else if (role === 'staff') window.location.href = '/staff';
                else window.location.href = '/customer';
            }}
        </script>
        <p>Logging you in... Please wait.</p>
    </body>
    </html>
    """

    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html)
