"""
Auto-fix Supabase database triggers on startup.

Uses the Supabase Management API to execute SQL that fixes the
on_auth_user_created trigger (SECURITY DEFINER) and RLS policies.

Requires SUPABASE_MGMT_TOKEN env var (Personal Access Token from
https://supabase.com/dashboard/account/tokens).

The project ref is extracted from SUPABASE_URL automatically.
"""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from pathlib import Path

try:
    import logging
    logger = logging.getLogger(__name__)
except ImportError:
    logger = None


def _get_project_ref() -> str:
    """Extract Supabase project ref from SUPABASE_URL."""
    url = os.environ.get("SUPABASE_URL", "")
    # URL format: https://<project-ref>.supabase.co
    if "://" in url:
        host = url.split("://")[1].split("/")[0]
        ref = host.split(".")[0]
        return ref
    return ""


def _get_mgmt_token() -> str:
    """Get the Management API token."""
    return os.environ.get("SUPABASE_MGMT_TOKEN", "")


def _run_sql(sql: str) -> dict:
    """Execute SQL via Supabase Management API (pg-meta)."""
    ref = _get_project_ref()
    token = _get_mgmt_token()

    if not ref:
        return {"ok": False, "error": "Cannot extract project ref from SUPABASE_URL"}
    if not token:
        return {"ok": False, "error": "SUPABASE_MGMT_TOKEN not set"}

    url = f"https://api.supabase.com/v1/projects/{ref}/database/query"
    payload = json.dumps({"query": sql}).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return {"ok": True, "data": body}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"ok": False, "error": f"HTTP {e.code}: {body[:500]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# The critical SQL fix — must drop before recreate (CREATE OR REPLACE doesn't
# change SECURITY DEFINER attribute).
FIX_SQL = """\
-- Fix the on_auth_user_created trigger to use SECURITY DEFINER
-- This allows the trigger to bypass RLS when inserting into user_profiles during signup

-- Step 1: Drop the existing trigger and function
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
DROP FUNCTION IF EXISTS handle_new_user();

-- Step 2: Recreate with SECURITY DEFINER (bypasses RLS)
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO public.user_profiles (id, email, full_name, role, is_active)
  VALUES (
    NEW.id,
    NEW.email,
    COALESCE(NEW.raw_user_meta_data->>'full_name', ''),
    COALESCE(NEW.raw_user_meta_data->>'role', 'citizen'),
    true
  )
  ON CONFLICT (id) DO UPDATE SET
    email = EXCLUDED.email,
    full_name = COALESCE(NULLIF(EXCLUDED.full_name, ''), public.user_profiles.full_name),
    role = EXCLUDED.role;
  RETURN NEW;
END;
$$;

-- Step 3: Recreate the trigger
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION handle_new_user();

-- Step 4: Ensure RLS policies exist
ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow authenticated read' AND tablename = 'user_profiles') THEN
    CREATE POLICY "Allow authenticated read" ON public.user_profiles
      FOR SELECT USING (auth.role() = 'authenticated');
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow authenticated insert' AND tablename = 'user_profiles') THEN
    CREATE POLICY "Allow authenticated insert" ON public.user_profiles
      FOR INSERT WITH CHECK (auth.role() = 'authenticated');
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow authenticated update' AND tablename = 'user_profiles') THEN
    CREATE POLICY "Allow authenticated update" ON public.user_profiles
      FOR UPDATE USING (auth.role() = 'authenticated');
  END IF;
END $$;

-- Step 5: Backfill missing profiles
INSERT INTO public.user_profiles (id, email, full_name, role, is_active)
SELECT
  au.id,
  au.email,
  COALESCE(au.raw_user_meta_data->>'full_name', ''),
  COALESCE(au.raw_user_meta_data->>'role',
    CASE WHEN au.email = 'pranavarya2005@gmail.com' THEN 'admin' ELSE 'citizen' END
  ),
  true
FROM auth.users au
LEFT JOIN public.user_profiles up ON au.id = up.id
WHERE up.id IS NULL
ON CONFLICT (id) DO NOTHING;

-- Step 6: Create exec_sql RPC for future programmatic fixes
CREATE OR REPLACE FUNCTION exec_sql(sql_query TEXT)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  result JSONB;
BEGIN
  EXECUTE sql_query;
  GET DIAGNOSTICS result = ROW_COUNT;
  RETURN jsonb_build_object('ok', true, 'rows_affected', result);
EXCEPTION WHEN OTHERS THEN
  RETURN jsonb_build_object('ok', false, 'error', SQLERRM);
END;
$$;

-- Step 7: Create local_users table for custom auth (bypasses Supabase Auth triggers)
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

-- Step 8: Verify the fix
SELECT jsonb_build_object(
  'trigger_exists', EXISTS(
    SELECT 1 FROM pg_trigger WHERE tgname = 'on_auth_user_created'
  ),
  'function_security_definer', EXISTS(
    SELECT 1 FROM pg_proc p
    JOIN pg_namespace n ON p.pronamespace = n.oid
    WHERE n.nspname = 'public' AND p.proname = 'handle_new_user'
    AND p.prosecdef = true
  ),
  'local_users_table', EXISTS(
    SELECT 1 FROM information_schema.tables WHERE table_name = 'local_users'
  )
) as verification;
"""


def check_trigger_health() -> dict:
    """Check if the signup trigger is healthy."""
    result = _run_sql("""\
SELECT jsonb_build_object(
  'trigger_exists', EXISTS(
    SELECT 1 FROM pg_trigger WHERE tgname = 'on_auth_user_created'
  ),
  'function_security_definer', EXISTS(
    SELECT 1 FROM pg_proc p
    JOIN pg_namespace n ON p.pronamespace = n.oid
    WHERE n.nspname = 'public' AND p.proname = 'handle_new_user'
    AND p.prosecdef = true
  ),
  'table_exists', EXISTS(
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'user_profiles'
  )
) as health
""")
    return result


def auto_fix() -> dict:
    """
    Automatically fix the Supabase database trigger.
    Returns {"ok": True/False, "message": "..."}
    """
    if not _get_mgmt_token():
        return {
            "ok": False,
            "message": (
                "SUPABASE_MGMT_TOKEN not set. To enable auto-fix:\n"
                "1. Go to https://supabase.com/dashboard/account/tokens\n"
                "2. Create a new access token\n"
                "3. Add SUPABASE_MGMT_TOKEN=<token> to your environment variables\n"
                "4. Redeploy"
            ),
        }

    if not _get_project_ref():
        return {"ok": False, "message": "Cannot extract project ref from SUPABASE_URL"}

    # Check health first
    health = check_trigger_health()
    if health.get("ok"):
        try:
            data = health.get("data", {})
            if data.get("trigger_exists") and data.get("function_security_definer"):
                return {"ok": True, "message": "Database trigger is healthy. No fix needed."}
        except Exception:
            pass

    # Apply the fix
    if logger:
        logger.info("Applying database fix via Management API...")
    result = _run_sql(FIX_SQL)
    if result.get("ok"):
        if logger:
            logger.info("Database fix applied successfully")
        return {"ok": True, "message": "Database fix applied. Signup should now work."}
    else:
        msg = f"Fix failed: {result.get('error', 'unknown')}"
        if logger:
            logger.error(msg)
        return {"ok": False, "message": msg}
