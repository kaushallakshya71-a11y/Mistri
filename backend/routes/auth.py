"""
Mistri Auth Routes - Register, Login, Profile, Google OAuth
Includes full validation: Gmail-only for customers, Indian phone format, strong passwords.
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional
import bcrypt as _bcrypt
from jose import jwt
from datetime import datetime, timedelta, date
from pathlib import Path
import os
import re
import json
import secrets
import time
import urllib.parse
from db.database import get_db
from middleware.auth import SECRET_KEY, ALGORITHM, get_current_user
from utils.audit import log_audit_event

# Load environment variables from .env
try:
    from dotenv import load_dotenv
    _b_dir = Path(__file__).resolve().parent.parent
    load_dotenv(_b_dir / ".env")
    load_dotenv(_b_dir.parent / ".env")
except ImportError:
    pass

try:
    import httpx
except ImportError:
    httpx = None

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
    monthly_salary: Optional[float] = None
    is_active: Optional[int] = None
    address: Optional[str] = None
    landmark: Optional[str] = None
    pincode: Optional[str] = None

class CompleteProfileRequest(BaseModel):
    phone: str
    address: str
    landmark: Optional[str] = None
    pincode: str

class StaffCreateRequest(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    password: str
    monthly_salary: Optional[float] = 20000.0
    joining_date: Optional[str] = None
    minimum_commitment_months: Optional[int] = 6

class StaffDeactivateRequest(BaseModel):
    replacement_staff_id: Optional[int] = None
    reason: Optional[str] = None
    force: bool = False  # If True, bypasses 15-day notice with mandatory reason

class StaffTerminationNoticeRequest(BaseModel):
    reason: str

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
    return {
        "access_token": token, "token_type": "bearer", "role": req.role,
        "name": req.name.strip(), "user_id": user_id,
        "needs_profile_completion": not bool(phone_clean)
    }

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

    # Check if deactivated
    if user["is_active"] == 0:
        raise HTTPException(403, "Your account has been deactivated. Please contact the administrator.")

    # Google-only accounts cannot login with password
    if user["auth_provider"] == "google" and not user["password_hash"]:
        raise HTTPException(401, "This account was created with Google Sign-In. Please use 'Continue with Google' to login.")

    if not _verify_pw(req.password, user["password_hash"]):
        raise HTTPException(401, "Incorrect password. Please try again.")

    has_phone = bool(user["phone"] and str(user["phone"]).strip())
    has_address = bool(user["address"] and str(user["address"]).strip())
    has_pincode = bool(user["pincode"] and str(user["pincode"]).strip())
    needs_profile = (user["role"] == "customer") and (not has_phone or not has_address or not has_pincode)

    token = create_access_token(user["id"], user["role"])
    return {
        "access_token": token, "token_type": "bearer",
        "role": user["role"], "name": user["name"], "user_id": user["id"],
        "needs_profile_completion": needs_profile
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
    users = conn.execute("""
        SELECT id, name, email, phone, role, auth_provider, created_at,
               COALESCE(monthly_salary, 0) as monthly_salary,
               joining_date,
               COALESCE(is_active, 1) as is_active,
               COALESCE(minimum_commitment_months, 6) as minimum_commitment_months,
               COALESCE(resignation_status, 'None') as resignation_status,
               resignation_notice_date, resignation_last_date, resignation_reason,
               termination_notice_date, termination_effective_date
        FROM users
        ORDER BY id DESC
    """).fetchall()
    conn.close()
    return [dict(u) for u in users]

# ---------------------------------------------------------------------------
# Admin: Create Staff
# ---------------------------------------------------------------------------

@router.post("/staff")
def create_staff(req: StaffCreateRequest, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(403, "Admins only.")
    validate_password_strength(req.password)
    conn = get_db()
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (req.email.strip().lower(),)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(400, "Email already registered.")
    
    hashed = _hash_pw(req.password)
    join_dt = req.joining_date or date.today().isoformat()
    min_months = req.minimum_commitment_months if req.minimum_commitment_months is not None else 6

    cursor = conn.execute("""
        INSERT INTO users (name, email, phone, password_hash, role, auth_provider,
                           monthly_salary, joining_date, is_active, minimum_commitment_months)
        VALUES (?, ?, ?, ?, 'staff', 'email', ?, ?, 1, ?)
    """, (req.name.strip(), req.email.strip().lower(), req.phone, hashed,
          req.monthly_salary or 0.0, join_dt, min_months))
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()

    log_audit_event(
        current_user,
        action="STAFF_CREATED",
        entity="users",
        entity_id=user_id,
        details={
            "name": req.name.strip(),
            "email": req.email.strip().lower(),
            "monthly_salary": req.monthly_salary,
            "joining_date": join_dt,
            "minimum_commitment_months": min_months
        }
    )
    return {"message": "Staff created successfully", "user_id": user_id}

# ---------------------------------------------------------------------------
# Admin: Deactivate Staff (With Active Repairs Reassignment & 15-Day Notice Check)
# ---------------------------------------------------------------------------

@router.put("/staff/{staff_id}/deactivate")
def deactivate_staff(staff_id: int, req: StaffDeactivateRequest, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(403, "Admins only.")

    conn = get_db()
    staff = conn.execute("SELECT * FROM users WHERE id=? AND role='staff'", (staff_id,)).fetchone()
    if not staff:
        conn.close()
        raise HTTPException(404, "Staff member not found.")

    # 1. Check active repairs
    active_repairs = conn.execute("""
        SELECT id, repair_id FROM repair_jobs
        WHERE technician_id=? AND status NOT IN ('Completed', 'Delivered', 'Cancelled', 'Rejected')
    """, (staff_id,)).fetchall()

    if active_repairs and not req.replacement_staff_id:
        conn.close()
        repair_codes = ", ".join([r["repair_id"] for r in active_repairs])
        raise HTTPException(
            400,
            f"This staff member has {len(active_repairs)} active assigned repair(s) ({repair_codes}). "
            "Please select a replacement technician to reassign active repairs before deactivation."
        )

    # If replacement staff provided, verify and reassign
    if req.replacement_staff_id:
        repl_staff = conn.execute(
            "SELECT id, name, is_active FROM users WHERE id=? AND role='staff'",
            (req.replacement_staff_id,)
        ).fetchone()
        if not repl_staff or repl_staff["is_active"] == 0:
            conn.close()
            raise HTTPException(400, "Replacement technician must be an active staff member.")

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for r in active_repairs:
            conn.execute("""
                UPDATE repair_jobs SET technician_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?
            """, (req.replacement_staff_id, r["id"]))
            conn.execute("""
                INSERT INTO repair_status_history (repair_job_id, from_status, to_status, changed_by, note)
                VALUES (?, (SELECT status FROM repair_jobs WHERE id=?), (SELECT status FROM repair_jobs WHERE id=?), ?, ?)
            """, (r["id"], r["id"], current_user["id"],
                  f"Reassigned from {staff['name']} to {repl_staff['name']} due to staff deactivation."))
            conn.execute("""
                INSERT INTO notifications (user_id, repair_job_id, title, message)
                VALUES (?, ?, 'Repair Reassigned to You', ?)
            """, (req.replacement_staff_id, r["id"], f"Repair {r['repair_id']} reassigned to you from {staff['name']}."))

    # 2. Check 15-Day Termination Notice rule
    if not req.force:
        notice_dt = staff["termination_notice_date"]
        if not notice_dt:
            conn.close()
            raise HTTPException(
                400,
                "15-day termination notice has not been issued to this staff member. "
                "Please issue a 15-day notice first, or select 'Immediate Deactivation' with a mandatory critical reason."
            )
        try:
            n_date = datetime.strptime(str(notice_dt)[:10], "%Y-%m-%d").date()
            diff_days = (date.today() - n_date).days
            if diff_days < 15:
                rem = 15 - diff_days
                conn.close()
                raise HTTPException(
                    400,
                    f"Termination notice period is still active ({rem} day(s) remaining until the 15-day period completes). "
                    "To force immediate exit, select 'Immediate Deactivation' with critical reason."
                )
        except ValueError:
            pass
    else:
        if not req.reason or len(req.reason.strip()) < 10:
            conn.close()
            raise HTTPException(400, "For immediate deactivation without 15-day notice, a clear critical reason (min 10 chars) is mandatory.")

    # 3. Mark inactive
    conn.execute("UPDATE users SET is_active=0 WHERE id=?", (staff_id,))
    conn.commit()
    conn.close()

    log_audit_event(
        current_user,
        action="STAFF_DEACTIVATED",
        entity="users",
        entity_id=staff_id,
        details={
            "staff_name": staff["name"],
            "reason": req.reason or "15-day notice completed",
            "forced": req.force,
            "reassigned_count": len(active_repairs),
            "replacement_staff_id": req.replacement_staff_id
        }
    )

    return {
        "message": f"Staff member {staff['name']} deactivated successfully.",
        "reassigned_repairs": len(active_repairs)
    }

# ---------------------------------------------------------------------------
# Admin: Activate Staff
# ---------------------------------------------------------------------------

@router.put("/staff/{staff_id}/activate")
def activate_staff(staff_id: int, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(403, "Admins only.")
    conn = get_db()
    staff = conn.execute("SELECT * FROM users WHERE id=? AND role='staff'", (staff_id,)).fetchone()
    if not staff:
        conn.close()
        raise HTTPException(404, "Staff member not found.")
    conn.execute("""
        UPDATE users SET is_active=1, termination_notice_date=NULL, termination_effective_date=NULL WHERE id=?
    """, (staff_id,))
    conn.commit()
    conn.close()

    log_audit_event(current_user, "STAFF_ACTIVATED", "users", staff_id, {"name": staff["name"]})
    return {"message": f"Staff member {staff['name']} reactivated successfully."}

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
    
    old_user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not old_user:
        conn.close()
        raise HTTPException(404, "User not found.")

    # Check if salary changed
    if req.monthly_salary is not None and old_user["monthly_salary"] != req.monthly_salary:
        conn.execute("""
            INSERT INTO salary_audit_logs (staff_id, old_salary, new_salary, changed_by, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, old_user["monthly_salary"] or 0, req.monthly_salary, current_user["id"], "Salary updated via user edit"))

    conn.execute("""
        UPDATE users
        SET name=?, email=?, phone=?,
            monthly_salary=COALESCE(?, monthly_salary),
            is_active=COALESCE(?, is_active)
        WHERE id=?
    """, (req.name.strip(), req.email.strip().lower(), req.phone, req.monthly_salary, req.is_active, user_id))
    conn.commit()
    conn.close()
    return {"message": "User updated successfully."}

# ---------------------------------------------------------------------------
# Google OAuth 2.0 / OpenID Connect
# ---------------------------------------------------------------------------

_OAUTH_STATES = {}  # state -> timestamp for CSRF protection

def _clean_expired_states():
    now = time.time()
    expired = [s for s, ts in _OAUTH_STATES.items() if now - ts > 600]
    for s in expired:
        _OAUTH_STATES.pop(s, None)

async def _exchange_google_code(code: str, cfg: dict) -> dict:
    post_data = {
        "code": code,
        "client_id": cfg["client_id"],
        "client_secret": cfg["client_secret"],
        "redirect_uri": cfg["redirect_uri"],
        "grant_type": "authorization_code"
    }
    if httpx:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post("https://oauth2.googleapis.com/token", data=post_data, timeout=15.0)
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
    # urllib fallback
    import urllib.request
    encoded_data = urllib.parse.urlencode(post_data).encode("utf-8")
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=encoded_data,
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "Mistri/1.0"}
    )
    with urllib.request.urlopen(req, timeout=15.0) as resp:
        return json.loads(resp.read().decode("utf-8"))

async def _fetch_google_userinfo(access_token: str) -> dict:
    if httpx:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://www.googleapis.com/oauth2/v3/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=15.0
                )
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
    # urllib fallback
    import urllib.request
    req = urllib.request.Request(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {access_token}", "User-Agent": "Mistri/1.0"}
    )
    with urllib.request.urlopen(req, timeout=15.0) as resp:
        return json.loads(resp.read().decode("utf-8"))

def get_google_oauth_config() -> dict:
    """Retrieve Google OAuth configuration from environment."""
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback").strip()
    is_configured = bool(client_id and client_secret and not client_id.startswith("your-google-client-id"))
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "is_configured": is_configured
    }

@router.get("/google/config")
def google_oauth_config():
    """Check if Google OAuth is configured on the server."""
    cfg = get_google_oauth_config()
    return {
        "configured": cfg["is_configured"],
        "client_id": cfg["client_id"] if cfg["is_configured"] else None,
        "redirect_uri": cfg["redirect_uri"]
    }

@router.get("/google/url")
def google_oauth_url():
    """Return Google OAuth authorization URL with secure state token for CSRF protection."""
    cfg = get_google_oauth_config()
    if not cfg["is_configured"]:
        raise HTTPException(
            503,
            "Google Sign-In is not configured. Please contact administrator to set up Google OAuth credentials in .env file."
        )
    _clean_expired_states()
    state = secrets.token_urlsafe(32)
    _OAUTH_STATES[state] = time.time()

    params = {
        "client_id": cfg["client_id"],
        "redirect_uri": cfg["redirect_uri"],
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "select_account"
    }
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    return {"url": auth_url, "state": state, "configured": True}

@router.get("/google/callback")
async def google_oauth_callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    """Handle Google OAuth callback, exchange token, link/create user, return JWT and profile completeness."""
    from fastapi.responses import HTMLResponse

    def _render_error_html(msg: str):
        safe_msg = json.dumps(msg)
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head><title>Google Login Error</title></head>
        <body style="font-family:sans-serif;padding:24px;background:#0d1117;color:#c9d1d9">
            <script>
                if (window.opener) {{
                    window.opener.postMessage({{type:'google_auth_error', message: {safe_msg}}}, '*');
                    setTimeout(function() {{ window.close(); }}, 2500);
                }} else {{
                    setTimeout(function() {{ window.location.href = '/login?error=' + encodeURIComponent({safe_msg}); }}, 2500);
                }}
            </script>
            <div style="background:#161b22;padding:20px;border-radius:8px;border:1px solid #f85149">
                <h3 style="color:#f85149;margin-top:0">Google Sign-In Failed</h3>
                <p>{msg}</p>
                <p style="color:#8b949e;font-size:13px">Returning to login window...</p>
            </div>
        </body>
        </html>
        """, status_code=400)

    if error:
        return _render_error_html(f"Google authentication was cancelled or failed: {error}")

    if not code:
        return _render_error_html("Missing authorization code from Google.")

    # State validation
    if state:
        _clean_expired_states()
        # If server has recorded states, ensure state is valid
        if _OAUTH_STATES and state not in _OAUTH_STATES:
            return _render_error_html("OAuth state mismatch or session expired. Please try signing in again.")
        _OAUTH_STATES.pop(state, None)

    cfg = get_google_oauth_config()
    if not cfg["is_configured"]:
        raise HTTPException(503, "Google Sign-In is not configured on the server.")

    # Exchange code for tokens (httpx with urllib fallback)
    token_data = None
    try:
        token_data = await _exchange_google_code(code, cfg)
    except Exception as e:
        return _render_error_html(f"Failed to verify Google credentials: {str(e)}")

    if not token_data or not token_data.get("access_token"):
        return _render_error_html("Failed to verify Google credentials. The authorization code may be expired or invalid.")

    access_token = token_data.get("access_token")

    # Fetch user profile using userinfo endpoint (httpx with urllib fallback)
    google_user = None
    try:
        google_user = await _fetch_google_userinfo(access_token)
    except Exception as e:
        return _render_error_html(f"Could not fetch Google user profile: {str(e)}")

    if not google_user:
        return _render_error_html("Failed to fetch Google profile information.")
    google_id = google_user.get("sub")
    email = google_user.get("email", "").strip().lower()
    name = google_user.get("name", email.split("@")[0] if email else "Customer")
    email_verified = google_user.get("email_verified", False)

    if not email or not google_id:
        return _render_error_html("Google did not provide a valid email address.")

    if not email_verified:
        return _render_error_html("Your Google email address is not verified. Please verify your Google account first.")

    # Enforce Gmail address format for customer sign in
    if not email.endswith("@gmail.com"):
        return _render_error_html("Please use a Gmail account (ending with @gmail.com) to sign in with Google.")

    conn = get_db()

    # Find existing user by google_id or email
    row = conn.execute(
        "SELECT * FROM users WHERE google_id=? OR email=?", (google_id, email)
    ).fetchone()
    existing = dict(row) if row else None

    needs_profile_completion = False

    if existing:
        user_id = existing["id"]
        role = existing["role"]
        user_name = existing["name"]
        curr_provider = existing["auth_provider"] or "email"

        # Check if deactivated
        if existing.get("is_active") == 0:
            conn.close()
            return _render_error_html("Your account has been deactivated. Please contact administrator.")

        # Link Google account if not already linked
        if not existing["google_id"]:
            new_provider = "email+google" if "email" in curr_provider else "google"
            conn.execute(
                "UPDATE users SET google_id=?, auth_provider=? WHERE id=?",
                (google_id, new_provider, user_id)
            )
            conn.commit()

        # Check profile completion (phone, address, pincode)
        has_phone = bool(existing["phone"] and str(existing["phone"]).strip())
        has_address = bool(existing["address"] and str(existing["address"]).strip())
        has_pincode = bool(existing["pincode"] and str(existing["pincode"]).strip())
        if role == "customer" and (not has_phone or not has_address or not has_pincode):
            needs_profile_completion = True
    else:
        # Create new customer account strictly with role='customer'
        cursor = conn.execute(
            """INSERT INTO users (name, email, google_id, password_hash, role, auth_provider)
               VALUES (?, ?, ?, '', 'customer', 'google')""",
            (name, email, google_id)
        )
        conn.commit()
        user_id = cursor.lastrowid
        role = "customer"
        user_name = name
        needs_profile_completion = True

    conn.close()

    # Generate Mistri JWT token
    token = create_access_token(user_id, role)

    # Return HTML that stores credentials and notifies parent window or redirects
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><title>Logging in...</title></head>
    <body style="font-family:sans-serif;padding:24px;background:#0d1117;color:#c9d1d9;text-align:center">
        <script>
            var authData = {{
                type: 'google_auth_success',
                token: {json.dumps(token)},
                role: {json.dumps(role)},
                name: {json.dumps(user_name)},
                user_id: {json.dumps(user_id)},
                needs_profile_completion: {json.dumps(needs_profile_completion)}
            }};
            localStorage.setItem('mistri_token', authData.token);
            localStorage.setItem('mistri_user', JSON.stringify({{
                name: authData.name,
                role: authData.role,
                user_id: authData.user_id,
                needs_profile_completion: authData.needs_profile_completion
            }}));
            if (window.opener) {{
                window.opener.postMessage(authData, '*');
                window.close();
            }} else {{
                if (authData.needs_profile_completion) {{
                    window.location.href = '/customer?complete_profile=1';
                }} else if (authData.role === 'admin') {{
                    window.location.href = '/admin';
                }} else if (authData.role === 'staff') {{
                    window.location.href = '/staff';
                }} else {{
                    window.location.href = '/customer';
                }}
            }}
        </script>
        <p>Logging you in securely... Please wait.</p>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

# ---------------------------------------------------------------------------
# Complete Profile (Customer Phone, Address, Landmark, Pincode)
# ---------------------------------------------------------------------------

@router.post("/complete-profile")
def complete_profile(req: CompleteProfileRequest, current_user: dict = Depends(get_current_user)):
    """Complete customer profile with phone, address, and pincode."""
    # 1. Validate Indian phone
    validate_phone(req.phone.strip())

    # 2. Validate Indian 6-digit PIN code
    pin_clean = req.pincode.strip()
    if not re.match(r'^[1-9][0-9]{5}$', pin_clean):
        raise HTTPException(
            400,
            "Please enter a valid 6-digit Indian PIN code (e.g. 110001, 302001)."
        )

    # 3. Validate address
    addr_clean = req.address.strip()
    if len(addr_clean) < 5:
        raise HTTPException(
            400,
            "Address must be at least 5 characters long."
        )

    # Clean phone digits
    phone_digits = re.sub(r'[\s\-\+()]', '', req.phone.strip())
    if phone_digits.startswith('91') and len(phone_digits) == 12:
        phone_digits = phone_digits[2:]

    conn = get_db()
    conn.execute("""
        UPDATE users
        SET phone=?, address=?, landmark=?, pincode=?
        WHERE id=?
    """, (phone_digits, addr_clean, req.landmark.strip() if req.landmark else None, pin_clean, current_user["id"]))
    conn.commit()

    updated = conn.execute("SELECT * FROM users WHERE id=?", (current_user["id"],)).fetchone()
    conn.close()

    return {
        "message": "Profile completed successfully.",
        "user": {k: v for k, v in dict(updated).items() if k not in ("password_hash",)}
    }
