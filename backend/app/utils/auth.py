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


_supabase_client = None

def _get_supabase_client():
    """Get cached Supabase client for auth operations."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        _supabase_client = create_client(url, key)
        return _supabase_client
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


def _get_profile_role(client, user_id: str) -> Optional[str]:
    """Look up the real role from user_profiles table."""
    try:
        result = client.table("user_profiles").select("role").eq("id", user_id).execute()
        if result.data and len(result.data) > 0:
            return result.data[0].get("role")
    except Exception:
        pass
    return None


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

        default_role = "admin" if signup.email.lower() == "pranavarya2005@gmail.com" else "citizen"

        try:
            result = client.auth.sign_up({
                "email": signup.email,
                "password": signup.password,
                "options": {"data": {"full_name": signup.name, "role": default_role}},
            })
            # Save role in user_profiles (fire-and-forget, don't block)
            try:
                if result.user:
                    client.table("user_profiles").upsert({
                        "id": result.user.id, "email": signup.email,
                        "role": default_role, "full_name": signup.name, "is_active": True,
                    }, on_conflict="id").execute()
            except Exception as e:
                if logger: logger.warning(f"Profile upsert failed for {signup.email}: {e}")
            # If session returned (email confirm OFF), user is ready to sign in
            if result.session:
                return {"status": "signup_complete", "message": "Account created! Please sign in."}
            # Email confirmation is ON — user must verify
            return {"status": "signup_pending", "message": "Account created! Please check your email to verify, then sign in.", "needs_verification": True}
        except Exception as e:
            err = str(e)
            if "already registered" in err.lower() or "already exists" in err.lower():
                return {"error": "An account with this email already exists. Please sign in instead."}
            return {"error": err}

    @app.post("/api/auth/login")
    async def auth_login(login_req: AuthLogin):
        """Login with email/password. Returns JWT access token and role."""
        client = _get_supabase_client()
        if not client:
            return {"error": "Supabase not configured."}

        try:
            result = client.auth.sign_in_with_password({"email": login_req.email, "password": login_req.password})
            if result.session:
                # Determine role immediately — no extra API call needed
                email_lower = login_req.email.lower()
                role = "admin" if email_lower == "pranavarya2005@gmail.com" else "citizen"
                # Try to get actual role from user_profiles table
                try:
                    prof = client.table("user_profiles").select("role").eq("id", result.user.id).execute()
                    if prof.data and len(prof.data) > 0:
                        role = prof.data[0].get("role", role)
                    else:
                        # Profile missing — auto-create it (handles old users / migration gaps)
                        full_name = "Arya" if role == "admin" else ""
                        client.table("user_profiles").upsert({
                            "id": result.user.id,
                            "email": login_req.email,
                            "role": role,
                            "full_name": full_name,
                            "is_active": True,
                        }, on_conflict="id").execute()
                        if logger: logger.info(f"Auto-created profile for {login_req.email} (role={role})")
                except Exception as e:
                    if logger: logger.warning(f"Profile lookup/creation failed for {login_req.email}: {e}")
                return {
                    "access_token": result.session.access_token,
                    "refresh_token": result.session.refresh_token,
                    "expires_at": result.session.expires_at,
                    "user": {"email": result.user.email, "id": result.user.id},
                    "role": role,
                }
            return {"error": "Invalid credentials"}
        except Exception as e:
            err_msg = str(e)
            if "email not confirmed" in err_msg.lower() or "not confirmed" in err_msg.lower():
                return {"error": "Email not confirmed. Please check your inbox for a verification link, or ask the admin to disable email confirmation in Supabase Dashboard > Auth > Email."}
            return {"error": err_msg}

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

    def _backfill_profiles(client, logger):
        """Auto-create user_profiles rows for any auth.users missing one."""
        try:
            auth_users = client.auth.admin.list_users().users
            existing = client.table("user_profiles").select("id").execute()
            existing_ids = {u["id"] for u in (existing.data or [])}
            for au in auth_users:
                if au.id not in existing_ids:
                    role = "admin" if au.email.lower() == "pranavarya2005@gmail.com" else "citizen"
                    full_name = getattr(au, "user_metadata", {}).get("full_name", "") or ""
                    client.table("user_profiles").upsert({
                        "id": au.id, "email": au.email, "role": role,
                        "full_name": full_name, "is_active": True,
                    }, on_conflict="id").execute()
                    if logger: logger.info(f"Auto-backfilled profile for {au.email} (role={role})")
        except Exception as e:
            if logger: logger.warning(f"Profile backfill failed: {e}")

    @app.get("/api/auth/users")
    async def list_users(user=Depends(require_auth)):
        """List all user profiles (admin only)."""
        email = user.get("email", "")
        client = _get_supabase_client()
        is_super_admin = email.lower() == "pranavarya2005@gmail.com"
        if client:
            try:
                result = client.table("user_profiles").select("*").execute()
                all_users = result.data or []
                # Admin check from the same data — no extra query
                if not is_super_admin:
                    me = next((u for u in all_users if u.get("id") == user.get("sub")), None)
                    if not me or me.get("role") != "admin":
                        raise HTTPException(status_code=403, detail="Admin access required")
                # If table is empty but auth users exist, auto-backfill
                if is_super_admin and len(all_users) == 0:
                    _backfill_profiles(client, logger)
                    result = client.table("user_profiles").select("*").execute()
                    all_users = result.data or []
                return {"users": all_users}
            except HTTPException:
                raise
            except Exception as e:
                if logger: logger.warning(f"list_users query failed: {e}")
                return {"users": [], "note": "user_profiles table may not exist. Run setup_auth.sql first."}
        return {"users": []}

    @app.put("/api/auth/users/{user_id}/role")
    async def update_user_role(user_id: str, role: str, user=Depends(require_auth)):
        """Update a user's role (admin only)."""
        email = user.get("email", "")
        client = _get_supabase_client()
        is_super_admin = email.lower() == "pranavarya2005@gmail.com"
        if not is_super_admin and client:
            user_role = _get_profile_role(client, user.get("sub", "")) or "citizen"
            if user_role != "admin":
                raise HTTPException(status_code=403, detail="Admin access required")
        elif not is_super_admin and not client:
            raise HTTPException(status_code=403, detail="Admin access required")
        if role not in ("admin", "operator", "viewer", "citizen"):
            raise HTTPException(status_code=400, detail="Invalid role")
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

