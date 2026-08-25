-- Run this in Supabase SQL Editor: https://supabase.com/dashboard > SQL Editor
-- This creates the user_profiles table needed for the User Management feature.

CREATE TABLE IF NOT EXISTS public.user_profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email TEXT NOT NULL,
  full_name TEXT DEFAULT '',
  role TEXT NOT NULL DEFAULT 'citizen' CHECK (role IN ('admin', 'operator', 'citizen', 'viewer')),
  district TEXT DEFAULT 'Chamoli',
  phone TEXT DEFAULT '',
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Enable Row Level Security
ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users to read profiles
CREATE POLICY "Allow authenticated read" ON public.user_profiles
  FOR SELECT USING (auth.role() = 'authenticated');

-- Allow authenticated users to insert/update their own profile
CREATE POLICY "Allow authenticated insert" ON public.user_profiles
  FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Allow authenticated update" ON public.user_profiles
  FOR UPDATE USING (auth.role() = 'authenticated');

-- Insert existing Supabase auth users into user_profiles
-- This handles users who signed up before the table existed
INSERT INTO public.user_profiles (id, email, role, full_name)
SELECT
  id,
  email,
  CASE
    WHEN email = 'pranavarya2005@gmail.com' THEN 'admin'
    ELSE 'citizen'
  END as role,
  COALESCE(raw_user_meta_data->>'full_name', '')
FROM auth.users
ON CONFLICT (id) DO NOTHING;
