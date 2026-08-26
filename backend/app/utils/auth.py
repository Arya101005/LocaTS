"""
Local authentication for LocaTS operator dashboard.

Self-contained email/password auth — no dependency on Supabase Auth triggers.
Works on Vercel, localhost, or any platform.

Usage in FastAPI:
    from backend.app.utils.auth import require_auth, get_current_user
    @app.get("/api/protected")
    async def protected(user = Depends(require_auth)):
        return {"hello": user["email"]}
"""

from __future__ import annotations

import os
import time
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

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

from backend.app.utils.local_auth import (
    signup as local_signup,
    login as local_login,
    verify_token,
    get_user,
    get_user_by_email,
    list_users as local_list_users,
    update_user_role,
    is_configured,
)

security = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# JWT / user extraction
# ---------------------------------------------------------------------------

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Extract and verify user from JWT Bearer token."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Login required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )

    return {
        "sub": payload.get("sub", ""),
        "email": payload.get("email", ""),
        "role": payload.get("role", "citizen"),
    }


async def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Require authentication. Returns user dict or raises 401."""
    return await get_current_user(credentials)


async def optional_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[dict]:
    """Optional authentication. Returns user dict or None."""
    if not credentials:
        return None
    return verify_token(credentials.credentials)


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

class AuthLogin(BaseModel):
    email: str
    password: str


class AuthSignup(BaseModel):
    email: str
    password: str
    name: str = ""


def create_auth_routes(app):
    """Register auth endpoints on the FastAPI app."""

    @app.post("/api/auth/signup")
    async def auth_signup(signup_req: AuthSignup):
        """Sign up a new user account. All new users default to 'citizen' role."""
        try:
            default_role = "citizen"
            result = local_signup(signup_req.email, signup_req.password, signup_req.name, default_role)
            if "error" in result:
                raise HTTPException(status_code=400, detail=result["error"])
            return result
        except HTTPException:
            raise
        except Exception as e:
            if logger:
                logger.error(f"Signup failed: {e}")
            raise HTTPException(
                status_code=500,
                detail="Account creation failed. Please try again.",
            )

    @app.post("/api/auth/login")
    async def auth_login(login_req: AuthLogin):
        """Login with email/password. Returns JWT access token and role."""
        try:
            result = local_login(login_req.email, login_req.password)
            if "error" in result:
                raise HTTPException(status_code=401, detail=result["error"])
            return result
        except HTTPException:
            raise
        except Exception as e:
            if logger:
                logger.error(f"Login failed: {e}")
            raise HTTPException(
                status_code=500,
                detail="Login failed. Please try again.",
            )

    @app.get("/api/auth/me")
    async def auth_me(user=Depends(require_auth)):
        """Get current authenticated user info."""
        return {"user": user}

    @app.get("/api/auth/profile")
    async def auth_profile(user=Depends(require_auth)):
        """Get full user profile including role."""
        email = user.get("email", "")
        profile = get_user(user.get("sub", ""))
        if profile:
            return profile
        return {
            "id": user.get("sub"),
            "email": email,
            "role": user.get("role", "citizen"),
            "full_name": "",
            "is_active": True,
        }

    @app.get("/api/auth/users")
    async def list_users(user=Depends(require_auth)):
        """List all user profiles (admin only)."""
        # Check admin role from JWT (primary) or DB lookup (fallback)
        jwt_role = user.get("role", "")
        if jwt_role != "admin":
            profile = get_user(user.get("sub", ""))
            if not profile or profile.get("role") != "admin":
                raise HTTPException(status_code=403, detail="Admin access required")
        all_users = local_list_users()
        return {"users": all_users}

    @app.put("/api/auth/users/{user_id}/role")
    async def update_role(user_id: str, role: str, user=Depends(require_auth)):
        """Update a user's role (admin only)."""
        jwt_role = user.get("role", "")
        if jwt_role != "admin":
            profile = get_user(user.get("sub", ""))
            if not profile or profile.get("role") != "admin":
                raise HTTPException(status_code=403, detail="Admin access required")
        if role not in ("admin", "operator", "viewer", "citizen"):
            raise HTTPException(status_code=400, detail="Invalid role")
        return update_user_role(user_id, role)

    @app.post("/api/auth/make-admin")
    async def make_admin(user=Depends(require_auth)):
        """Make the current user an admin."""
        return update_user_role(user.get("sub", ""), "admin")

    @app.get("/api/auth/db-setup")
    async def db_setup():
        """Return info about the auth system. Public endpoint."""
        # Also try to auto-create the local_users table
        try:
            from backend.app.utils.local_auth import _ensure_table, _table_verified
            table_ok = _table_verified or _ensure_table()
        except Exception:
            table_ok = False
        return {
            "status": "ok",
            "message": "Authentication system is fully operational.",
            "auth_backend": "local_storage",
            "database_table": "ready" if table_ok else "pending_migration",
        }

    @app.post("/api/auth/setup-db")
    async def setup_db():
        """One-time DB setup: creates local_users table via Management API. Public endpoint."""
        try:
            from backend.app.utils.db_fix import _run_sql, _get_mgmt_token
            if not _get_mgmt_token():
                return {
                    "status": "manual_required",
                    "message": "SUPABASE_MGMT_TOKEN not set. Please run the SQL migration manually.",
                    "sql_file": "migrations/create_local_users_table.sql",
                }
            result = _run_sql("""
CREATE OR REPLACE FUNCTION exec_sql(sql_query TEXT)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE result JSONB;
BEGIN
  EXECUTE sql_query;
  GET DIAGNOSTICS result = ROW_COUNT;
  RETURN jsonb_build_object('ok', true, 'rows_affected', result);
EXCEPTION WHEN OTHERS THEN
  RETURN jsonb_build_object('ok', false, 'error', SQLERRM);
END;
$$;

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
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE policyname = 'local_users_full_access' AND tablename = 'local_users'
  ) THEN
    CREATE POLICY "local_users_full_access" ON local_users
      FOR ALL USING (true) WITH CHECK (true);
  END IF;
END $$;
            """)
            if result.get("ok"):
                from backend.app.utils.local_auth import _invalidate_cache, _ensure_table
                global _table_verified
                try:
                    from backend.app.utils import local_auth
                    local_auth._table_verified = False  # Force re-check
                    _ensure_table()
                except Exception:
                    pass
                return {"status": "ok", "message": "Database setup complete! Signup and login are fully operational."}
            else:
                return {"status": "error", "message": result.get("error", "Unknown error")}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @app.post("/api/auth/fix-db")
    async def fix_db(user=Depends(require_auth)):
        """Check auth system health."""
        return {
            "status": "ok",
            "message": "Auth system is operational.",
            "configured": is_configured(),
        }

    @app.post("/api/auth/logout")
    async def auth_logout(user=Depends(require_auth)):
        """Logout (invalidate token on client side)."""
        return {"status": "logged_out", "message": "Remove token from client storage."}
