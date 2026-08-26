-- =============================================================================
-- CREATE local_users TABLE for custom authentication
-- =============================================================================
-- This table stores user accounts for LocaTS auth (bypasses Supabase Auth).
-- Run this in: https://supabase.com/dashboard > SQL Editor
-- =============================================================================

-- Step 1: Create the exec_sql helper function (needed for programmatic setup)
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

-- Step 2: Create the local_users table
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

-- Step 3: Create index for email lookups
CREATE INDEX IF NOT EXISTS idx_local_users_email ON local_users (email);

-- Step 4: Enable RLS with a permissive policy (auth handles its own security)
ALTER TABLE local_users ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE policyname = 'local_users_full_access' AND tablename = 'local_users'
  ) THEN
    CREATE POLICY "local_users_full_access" ON local_users
      FOR ALL USING (true) WITH CHECK (true);
  END IF;
END $$;

-- Step 5: Backfill any existing demo users
INSERT INTO local_users (id, email, full_name, role, district, phone, is_active, password_hash, salt, created_at, updated_at)
VALUES
  ('00000000-0000-0000-0000-000000000001', 'admin@locats.gov.in', 'Admin', 'admin', 'Chamoli', '', true,
   'dummy', 'dummy', NOW()::text, NOW()::text)
ON CONFLICT (id) DO NOTHING;

-- Verify
SELECT jsonb_build_object(
  'table_exists', EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'local_users'),
  'exec_sql_exists', EXISTS(SELECT 1 FROM pg_proc WHERE proname = 'exec_sql'),
  'row_count', (SELECT count(*) FROM local_users)
) as verification;
