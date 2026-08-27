"""
Self-contained authentication system for LocaTS.

Provides email/password signup and login with JWT sessions.
User data is persisted via Supabase database (most reliable on Vercel)
with in-memory and local-file fallbacks.

No dependency on Supabase Auth — works on any platform.

Provides:
  - Email/password signup and login
  - JWT-based session management
  - User profile management
  - Admin user listing
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import logging
    logger = logging.getLogger(__name__)
except ImportError:
    logger = None

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Supabase client (database-based persistence)
# ---------------------------------------------------------------------------

_supabase_client = None
_client_lock = threading.Lock()
_TABLE_NAME = "local_users"
_table_verified = False


def _get_client():
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        with _client_lock:
            if _supabase_client is None:
                _supabase_client = create_client(url, key)
        return _supabase_client
    except Exception as e:
        if logger:
            logger.warning(f"Supabase client creation failed: {e}")
        return None


def _ensure_table():
    """Ensure the local_users table exists. Uses RPC or falls back gracefully."""
    global _table_verified
    if _table_verified:
        return True
    client = _get_client()
    if not client:
        return False
    try:
        # Try to read from the table — if it works, it exists
        result = client.table(_TABLE_NAME).select("id").limit(1).execute()
        _table_verified = True
        return True
    except Exception:
        pass
    # Table doesn't exist — try to create it via SQL RPC
    try:
        sql = """
CREATE TABLE IF NOT EXISTS local_users (
  id TEXT PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  full_name TEXT DEFAULT '',
  role TEXT DEFAULT 'citizen',
  district TEXT DEFAULT 'Chamoli',
  phone TEXT DEFAULT '',
  is_active BOOLEAN DEFAULT true,
  password_hash TEXT NOT NULL,
  salt TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_local_users_email ON local_users (email);
ALTER TABLE local_users ENABLE ROW LEVEL SECURITY;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'local_users_full_access' AND tablename = 'local_users') THEN
    CREATE POLICY "local_users_full_access" ON local_users FOR ALL USING (true) WITH CHECK (true);
  END IF;
END $$;
"""
        result = client.rpc("exec_sql", {"sql_query": sql}).execute()
        _table_verified = True
        if logger:
            logger.info("local_users table created via RPC")
        return True
    except Exception:
        # exec_sql RPC may not exist yet — table will be created via migration SQL
        pass
    return False


# ---------------------------------------------------------------------------
# User persistence: database (primary) + memory (fallback)
# ---------------------------------------------------------------------------

_lock = threading.Lock()

# In-memory cache — fast, survives within same process
_users_cache: Optional[dict] = None
_cache_time: float = 0
_cache_lock = threading.Lock()
CACHE_TTL: float = 30.0  # seconds

# Local file path (fallback for local dev)
_LOCAL_FILE: Optional[Path] = None


def _get_local_file() -> Optional[Path]:
    global _LOCAL_FILE
    if _LOCAL_FILE is not None:
        return _LOCAL_FILE
    try:
        project_root = Path(__file__).parent.parent.parent.parent
        auth_file = project_root / ".locats_auth_users.json"
        _LOCAL_FILE = auth_file
        return _LOCAL_FILE
    except Exception:
        return None


def _invalidate_cache():
    global _users_cache, _cache_time
    with _cache_lock:
        _users_cache = None
        _cache_time = 0


def _db_read_users() -> Optional[dict]:
    """Read all users from Supabase database table."""
    client = _get_client()
    if not client:
        return None
    if not _ensure_table():
        return None
    try:
        result = client.table(_TABLE_NAME).select("*").execute()
        users = {}
        for row in result.data:
            users[row["id"]] = row
        return users
    except Exception as e:
        if logger:
            logger.warning(f"DB read failed: {e}")
        return None


def _db_write_user(user: dict) -> bool:
    """Write a single user to Supabase database table."""
    client = _get_client()
    if not client:
        return False
    if not _ensure_table():
        return False
    try:
        client.table(_TABLE_NAME).upsert(user, on_conflict="id").execute()
        return True
    except Exception as e:
        if logger:
            logger.warning(f"DB write failed: {e}")
        return False


def _read_users() -> dict:
    """Read users from cache, database, or local file.
    
    Priority: memory cache > database > local file
    Always returns a valid dict (never raises).
    """
    global _users_cache, _cache_time
    now = time.time()

    # Fast path: serve from memory cache
    with _cache_lock:
        if _users_cache is not None and (now - _cache_time) < CACHE_TTL:
            return _users_cache

    # Try database
    db_users = _db_read_users()
    if db_users is not None:
        with _cache_lock:
            _users_cache = db_users
            _cache_time = time.time()
        # Also save to local file for fast access
        local_file = _get_local_file()
        if local_file:
            try:
                local_file.write_text(json.dumps(db_users, indent=2, default=str), encoding="utf-8")
            except Exception:
                pass
        return db_users

    # Try local file
    local_file = _get_local_file()
    if local_file and local_file.exists():
        try:
            data = json.loads(local_file.read_text(encoding="utf-8"))
            if isinstance(data, dict) and len(data) > 0:
                with _cache_lock:
                    _users_cache = data
                    _cache_time = time.time()
                return data
        except Exception:
            pass

    # Fallback to whatever is in memory
    with _cache_lock:
        return _users_cache or {}


def _write_user(user: dict):
    """Write a user to ALL available persistence layers.
    
    Updates memory cache first (always succeeds), then tries
    database and local file (best-effort).
    NEVER raises — auth always works even if persistence fails.
    """
    global _users_cache, _cache_time

    # Layer 1: Update memory cache (always succeeds)
    with _cache_lock:
        if _users_cache is None:
            _users_cache = {}
        _users_cache[user["id"]] = user
        _cache_time = time.time()

    # Layer 2: Write to database (reliable, for cross-invocation persistence)
    _db_write_user(user)

    # Layer 3: Write to local file (fast, for local dev)
    local_file = _get_local_file()
    if local_file:
        try:
            local_file.write_text(
                json.dumps(_users_cache, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as e:
            if logger:
                logger.warning(f"Local file write failed: {e}")


def preload_users():
    """Preload users into memory on startup. Also seeds a default admin if no users exist."""
    try:
        _read_users()
        with _cache_lock:
            count = len(_users_cache) if _users_cache else 0
        if logger:
            logger.info(f"Auth cache preloaded: {count} users")

        # Always ensure the demo admin account exists
        admin_email = os.environ.get("ADMIN_EMAIL", "admin@locats.gov.in")
        admin_pass = os.environ.get("ADMIN_PASSWORD", "admin123")
        admin_user = get_user_by_email(admin_email)
        if not admin_user:
            result = signup(admin_email, admin_pass, "Admin", "admin")
            if result.get("status") == "signup_complete":
                if logger:
                    logger.info(f"Seeded default admin: {admin_email}")
            else:
                if logger:
                    logger.info(f"Admin seed: {result.get('error', 'skipped')}")
        else:
            # Ensure the existing admin has the admin role
            if admin_user.get("role") != "admin":
                update_user_role(admin_user["id"], "admin")
                if logger:
                    logger.info(f"Elevated {admin_email} to admin role")
    except Exception as e:
        if logger:
            logger.warning(f"Auth preload failed: {e}")


# ---------------------------------------------------------------------------
# Password hashing (SHA-256 + salt)
# ---------------------------------------------------------------------------

def _hash_password(password: str, salt: str = "") -> tuple[str, str]:
    if not salt:
        salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return h, salt


def _verify_password(password: str, stored_hash: str, salt: str) -> bool:
    h, _ = _hash_password(password, salt)
    return h == stored_hash


# ---------------------------------------------------------------------------
# JWT helpers (simple HS256)
# ---------------------------------------------------------------------------

_jwt_secret: Optional[str] = None


def _get_jwt_secret() -> str:
    global _jwt_secret
    if _jwt_secret is not None:
        return _jwt_secret
    secret = os.environ.get("LOCAL_AUTH_SECRET", "")
    if not secret:
        key = os.environ.get("SUPABASE_KEY", "locats-default-secret")
        secret = hashlib.sha256(("locats-auth-secret:" + key).encode()).hexdigest()
    _jwt_secret = secret
    return secret


def _encode_jwt(payload: dict) -> str:
    import base64
    secret = _get_jwt_secret()
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps(payload, default=str).encode()).decode().rstrip("=")
    signing_input = f"{header}.{body}"
    sig = hashlib.sha256((signing_input + secret).encode()).hexdigest()
    signature = base64.urlsafe_b64encode(bytes.fromhex(sig)).decode().rstrip("=")
    return f"{header}.{body}.{signature}"


def _decode_jwt(token: str) -> Optional[dict]:
    import base64
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, body_b64, sig_b64 = parts
        body_b64_padded = body_b64 + "=" * (4 - len(body_b64) % 4) if len(body_b64) % 4 else body_b64
        payload = json.loads(base64.urlsafe_b64decode(body_b64_padded))
        exp = payload.get("exp")
        if exp and time.time() > exp:
            return None
        secret = _get_jwt_secret()
        signing_input = f"{header_b64}.{body_b64}"
        expected_sig = hashlib.sha256((signing_input + secret).encode()).hexdigest()
        sig_b64_padded = sig_b64 + "=" * (4 - len(sig_b64) % 4) if len(sig_b64) % 4 else sig_b64
        actual_sig = base64.urlsafe_b64decode(sig_b64_padded).hex()
        if actual_sig != expected_sig:
            return None
        return payload
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def signup(email: str, password: str, full_name: str = "", role: str = "citizen") -> dict:
    """Create a new user account. Always succeeds if the system is running."""
    email_lower = email.lower().strip()

    if not email_lower or "@" not in email_lower:
        return {"error": "Please provide a valid email address."}
    if len(password) < 6:
        return {"error": "Password must be at least 6 characters."}

    with _lock:
        users = _read_users()

        for uid, u in users.items():
            if u.get("email", "").lower() == email_lower:
                return {"error": "An account with this email already exists. Please sign in instead."}

        # Auto-elevate first user to admin so there's always an admin
        if len(users) == 0:
            role = "admin"
            if logger:
                logger.info(f"First user {email_lower} auto-elevated to admin")

        user_id = str(uuid.uuid4())
        password_hash, salt = _hash_password(password)
        now = datetime.now(timezone.utc).isoformat()

        user = {
            "id": user_id,
            "email": email_lower,
            "full_name": full_name,
            "role": role,
            "district": "Chamoli",
            "phone": "",
            "is_active": True,
            "password_hash": password_hash,
            "salt": salt,
            "created_at": now,
            "updated_at": now,
        }
        _write_user(user)

    token = _encode_jwt({
        "sub": user_id,
        "email": email_lower,
        "role": role,
        "exp": int(time.time()) + 86400 * 7,
    })

    return {
        "status": "signup_complete",
        "message": "Account created successfully! Please sign in.",
        "access_token": token,
        "user": {"email": email_lower, "id": user_id},
        "role": role,
    }


def login(email: str, password: str) -> dict:
    """Login with email/password. Returns JWT access token and role."""
    email_lower = email.lower().strip()
    # Always read fresh on login — critical for Vercel serverless
    # where memory cache might be stale across invocations
    _invalidate_cache()
    users = _read_users()

    for uid, u in users.items():
        if u.get("email", "").lower() == email_lower:
            if not u.get("is_active"):
                return {"error": "Account is deactivated. Contact an administrator."}
            if not _verify_password(password, u.get("password_hash", ""), u.get("salt", "")):
                return {"error": "Invalid email or password."}

            token = _encode_jwt({
                "sub": uid,
                "email": email_lower,
                "role": u.get("role", "citizen"),
                "exp": int(time.time()) + 86400 * 7,
            })

            return {
                "access_token": token,
                "refresh_token": "",
                "expires_at": int(time.time()) + 86400 * 7,
                "user": {"email": email_lower, "id": uid},
                "role": u.get("role", "citizen"),
            }

    return {"error": "Invalid email or password."}


def verify_token(token: str) -> Optional[dict]:
    return _decode_jwt(token)


def get_user(user_id: str) -> Optional[dict]:
    users = _read_users()
    u = users.get(user_id)
    if u:
        return {k: v for k, v in u.items() if k not in ("password_hash", "salt")}
    return None


def get_user_by_email(email: str) -> Optional[dict]:
    email_lower = email.lower().strip()
    users = _read_users()
    for uid, u in users.items():
        if u.get("email", "").lower() == email_lower:
            return {k: v for k, v in u.items() if k not in ("password_hash", "salt")}
    return None


def list_users() -> list[dict]:
    # Always read fresh for admin user management
    _invalidate_cache()
    users = _read_users()
    return [
        {k: v for k, v in u.items() if k not in ("password_hash", "salt")}
        for u in users.values()
    ]


def update_user_role(user_id: str, new_role: str) -> dict:
    with _lock:
        users = _read_users()
        if user_id not in users:
            return {"error": "User not found"}
        users[user_id]["role"] = new_role
        users[user_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        _write_user(users[user_id])
    return {"status": "updated", "user_id": user_id, "new_role": new_role}


def change_password(user_id: str, current_password: str, new_password: str) -> dict:
    """Change a user's password. Requires current password verification."""
    if len(new_password) < 6:
        return {"error": "New password must be at least 6 characters."}

    with _lock:
        users = _read_users()
        user = users.get(user_id)
        if not user:
            return {"error": "User not found."}

        # Verify current password
        if not _verify_password(current_password, user.get("password_hash", ""), user.get("salt", "")):
            return {"error": "Current password is incorrect."}

        # Set new password
        new_hash, new_salt = _hash_password(new_password)
        users[user_id]["password_hash"] = new_hash
        users[user_id]["salt"] = new_salt
        users[user_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        _write_user(users[user_id])

    return {"status": "updated", "message": "Password changed successfully."}


# ---------------------------------------------------------------------------
# Password Reset
# ---------------------------------------------------------------------------

# In-memory reset tokens (short-lived, 15 min expiry)
_reset_tokens: dict = {}  # token -> {user_id, email, expires_at}
_reset_lock = threading.Lock()
RESET_TOKEN_EXPIRY = 900  # 15 minutes


def forgot_password(email: str) -> dict:
    """Generate a password reset code for the given email."""
    email_lower = email.lower().strip()
    if not email_lower or "@" not in email_lower:
        return {"error": "Please provide a valid email address."}

    users = _read_users()
    user_id = None
    for uid, u in users.items():
        if u.get("email", "").lower() == email_lower:
            user_id = uid
            break

    # Always return success to prevent email enumeration
    if not user_id:
        return {
            "status": "sent",
            "message": "If an account exists with that email, a reset code has been sent.",
        }

    # Generate a 6-digit reset code
    import random
    code = f"{random.randint(100000, 999999)}"
    token = _encode_jwt({
        "sub": user_id,
        "email": email_lower,
        "purpose": "password_reset",
        "code": code,
        "exp": int(time.time()) + RESET_TOKEN_EXPIRY,
    })

    with _reset_lock:
        _reset_tokens[token] = {
            "user_id": user_id,
            "email": email_lower,
            "code": code,
            "expires_at": int(time.time()) + RESET_TOKEN_EXPIRY,
        }

    if logger:
        logger.info(f"Password reset code for {email_lower}: {code}")

    return {
        "status": "sent",
        "message": "If an account exists with that email, a reset code has been sent.",
        # In production, remove the code below — it would be sent via email
        "_debug_code": code,
        "_debug_token": token,
    }


def reset_password(token: str, code: str, new_password: str) -> dict:
    """Reset a user's password using the reset code."""
    if len(new_password) < 6:
        return {"error": "New password must be at least 6 characters."}

    # Verify the JWT token
    payload = _decode_jwt(token)
    if not payload:
        return {"error": "Reset code has expired or is invalid."}

    if payload.get("purpose") != "password_reset":
        return {"error": "Invalid reset token."}

    # Check expiry
    exp = payload.get("exp", 0)
    if time.time() > exp:
        return {"error": "Reset code has expired. Please request a new one."}

    # Verify the code matches
    with _reset_lock:
        stored = _reset_tokens.get(token)
        if not stored:
            return {"error": "Reset code has already been used or is invalid."}
        if stored["code"] != code:
            return {"error": "Incorrect reset code."}
        # Delete the token (one-time use)
        del _reset_tokens[token]

    # Update the password
    user_id = payload["sub"]
    with _lock:
        users = _read_users()
        if user_id not in users:
            return {"error": "User not found."}
        new_hash, new_salt = _hash_password(new_password)
        users[user_id]["password_hash"] = new_hash
        users[user_id]["salt"] = new_salt
        users[user_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        _write_user(users[user_id])

    return {"status": "updated", "message": "Password reset successful. You can now sign in."}


def is_configured() -> bool:
    """Check if Supabase is available (auth works regardless)."""
    return _get_client() is not None
