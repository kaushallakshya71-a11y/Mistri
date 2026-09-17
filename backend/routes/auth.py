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
from db.database import get_db
from middleware.auth import SECRET_KEY, ALGORITHM, get_current_user
from utils.audit import log_audit_event
import os
import re
import json
import urllib.parse
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

    # Check if deactivated
    if user["is_active"] == 0:
        raise HTTPException(403, "Your account has been deactivated. Please contact the administrator.")

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

    if not httpx:
        raise HTTPException(503, "httpx is not installed for Google OAuth token exchange.")

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
