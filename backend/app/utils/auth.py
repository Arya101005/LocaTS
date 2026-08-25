"""
Supabase Auth integration for LocaTS operator dashboard.

Provides JWT-based authentication using Supabase Auth.
Operators must log in before accessing the dashboard.
Community reporters (PWA) can remain anonymous.

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

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

security = HTTPBearer(auto_error=False)


def _get_supabase_client():
    """Get Supabase client for auth operations."""
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception:
        return None


def decode_jwt(token: str) -> Optional[dict]:
    """Decode a Supabase JWT token. Uses Supabase client to verify."""
    # Method 1: Use Supabase client to get user (most reliable)
    client = _get_supabase_client()
    if client:
        try:
            result = client.auth.get_user(token)
            if result and result.user:
                user = result.user
                return {
                    "sub": user.id,
                    "email": user.email,
                    "role": "operator",  # default; overridden by profile
                }
        except Exception as e:
            if logger: logger.debug(f"Supabase token verification failed: {e}")

    # Method 2: Manual decode (fallback)
    try:
        import jwt
        # Try ES256 first (Supabase default), then HS256
        for alg in ["ES256", "HS256"]:
            try:
                secret = os.environ.get("SUPABASE_JWT_SECRET", "") or os.environ.get("SUPABASE_KEY", "")
                if not secret:
                    continue
                payload = jwt.decode(token, secret, algorithms=[alg], options={"verify_aud": False})
                return payload
            except Exception:
                continue
    except ImportError:
        pass
    except Exception as e:
        if logger: logger.debug(f"JWT decode failed: {e}")
    return None


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

    payload = decode_jwt(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )

    return {
        "sub": payload.get("sub", ""),
        "email": payload.get("email", ""),
        "role": payload.get("role", "operator"),
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
    return decode_jwt(credentials.credentials)


# ------------------------------------------------------------------
# Auth endpoints
# ------------------------------------------------------------------

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
    async def auth_signup(signup: AuthSignup):
        """Sign up a new user account. All new users default to 'citizen' role."""
        client = _get_supabase_client()
        if not client:
            return {"error": "Supabase not configured. Set SUPABASE_URL and SUPABASE_KEY in .env."}

        # Determine default role: pranavarya2005@gmail.com is always admin
        default_role = "admin" if signup.email.lower() == "pranavarya2005@gmail.com" else "citizen"

        try:
            result = client.auth.sign_up({
                "email": signup.email,
                "password": signup.password,
                "options": {"data": {"full_name": signup.name, "role": default_role}},
            })
            # Upsert user profile with role
            try:
                client.table("user_profiles").upsert({
                    "id": result.user.id if result.user else "",
                    "email": signup.email,
                    "role": default_role,
                    "full_name": signup.name,
                    "is_active": True,
                }).execute()
            except Exception:
                pass  # Table may not exist
            if result.session:
                return {
                    "status": "signup_complete",
                    "access_token": result.session.access_token,
                    "refresh_token": result.session.refresh_token,
                    "expires_at": result.session.expires_at,
                    "user": {"email": result.user.email, "id": result.user.id},
                    "role": default_role,
                }
            if result.user:
                return {"status": "signup_pending", "email": signup.email, "role": default_role, "message": "Account created! You can now sign in. Your role: " + default_role}
            return {"error": "Signup failed"}
        except Exception as e:
            return {"error": str(e)}

    @app.post("/api/auth/login")
    async def auth_login(login: AuthLogin):
        """Login with email/password. Returns JWT access token."""
        client = _get_supabase_client()
        if not client:
            return {"error": "Supabase not configured."}

        try:
            result = client.auth.sign_in_with_password({"email": login.email, "password": login.password})
            if result.session:
                return {
                    "access_token": result.session.access_token,
                    "refresh_token": result.session.refresh_token,
                    "expires_at": result.session.expires_at,
                    "user": {"email": result.user.email, "id": result.user.id},
                }
            return {"error": "Invalid credentials"}
        except Exception as e:
            return {"error": str(e)}

    @app.get("/api/auth/me")
    async def auth_me(user=Depends(require_auth)):
        """Get current authenticated user info."""
        return {"user": user}

    @app.get("/api/auth/profile")
    async def auth_profile(user=Depends(require_auth)):
        """Get full user profile including role from user_profiles table."""
        email = user.get("email", "")
        # pranavarya2005@gmail.com is always admin
        if email.lower() == "pranavarya2005@gmail.com":
            return {
                "id": user.get("sub"),
                "email": email,
                "role": "admin",
                "full_name": "Arya",
                "is_active": True,
            }
        client = _get_supabase_client()
        if client:
            try:
                result = client.table("user_profiles").select("*").eq("id", user["sub"]).execute()
                if result.data and len(result.data) > 0:
                    return result.data[0]
            except Exception as e:
                if logger: logger.warning(f"Profile fetch failed (table may not exist): {e}")
        # Fallback: default to citizen role
        return {
            "id": user.get("sub"),
            "email": email,
            "role": "citizen",
            "full_name": "",
            "is_active": True,
        }

    @app.get("/api/auth/users")
    async def list_users(user=Depends(require_auth)):
        """List all user profiles (admin only)."""
        email = user.get("email", "")
        role = user.get("role", "operator")
        # Allow if admin or if email contains 'admin'
        if role != "admin" and "admin" not in email.lower():
            raise HTTPException(status_code=403, detail="Admin access required")
        client = _get_supabase_client()
        if client:
            try:
                result = client.table("user_profiles").select("*").execute()
                return {"users": result.data}
            except Exception as e:
                return {"users": [], "note": "user_profiles table may not exist. Run setup_auth.sql first."}
        return {"users": []}

    @app.put("/api/auth/users/{user_id}/role")
    async def update_user_role(user_id: str, role: str, user=Depends(require_auth)):
        """Update a user's role (admin only)."""
        email = user.get("email", "")
        if user.get("role") != "admin" and "admin" not in email.lower():
            raise HTTPException(status_code=403, detail="Admin access required")
        if role not in ("admin", "operator", "viewer", "citizen"):
            raise HTTPException(status_code=400, detail="Invalid role")
        client = _get_supabase_client()
        if client:
            try:
                client.table("user_profiles").update({"role": role}).eq("id", user_id).execute()
                return {"status": "updated", "user_id": user_id, "new_role": role}
            except Exception as e:
                return {"error": str(e)}
        return {"error": "Supabase not configured"}

    @app.post("/api/auth/make-admin")
    async def make_admin(user=Depends(require_auth)):
        """Make the current user an admin (if they're the first user or email contains 'admin')."""
        email = user.get("email", "")
        client = _get_supabase_client()
        # Try user_profiles table first
        if client:
            try:
                # Check if any admin exists already
                admins = client.table("user_profiles").select("*").eq("role", "admin").execute()
                if admins.data and len(admins.data) > 0 and admins.data[0].get("id") != user.get("sub"):
                    return {"error": "An admin already exists. Ask them to promote you."}
                # Upsert as admin
                client.table("user_profiles").upsert({
                    "id": user.get("sub"),
                    "email": email,
                    "role": "admin",
                    "full_name": "",
                    "is_active": True,
                }).execute()
                return {"status": "admin", "message": "You are now an admin."}
            except Exception as e:
                # Table doesn't exist — anyone can be admin
                pass
        return {"status": "admin", "message": "Admin role set (no user_profiles table)."}

    @app.post("/api/auth/logout")
    async def auth_logout(user=Depends(require_auth)):
        """Logout (invalidate token on client side)."""
        return {"status": "logged_out", "message": "Remove token from client storage."}

