-- Run this in Supabase SQL Editor to:
-- 1. Confirm your user (skip email verification)
-- 2. Set role to admin

-- First: confirm the user's email
UPDATE auth.users
SET email_confirmed_at = now(), confirmed_at = now()
WHERE email = 'pranavarya2005@gmail.com';

-- Second: set role to admin in user_profiles
UPDATE user_profiles
SET role = 'admin'
WHERE email = 'pranavarya2005@gmail.com';

-- If user_profiles row doesn't exist yet, create it:
INSERT INTO user_profiles (id, email, full_name, role)
SELECT id, email, 'Arya Pranav', 'admin'
FROM auth.users
WHERE email = 'pranavarya2005@gmail.com'
AND NOT EXISTS (SELECT 1 FROM user_profiles WHERE email = 'pranavarya2005@gmail.com');
