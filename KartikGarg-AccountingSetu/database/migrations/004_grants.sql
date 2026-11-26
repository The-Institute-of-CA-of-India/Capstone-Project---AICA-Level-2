-- =====================================================================
-- Migration 004 (Supabase only): table privileges for the API roles.
-- Projects created with "Grant API access to new tables automatically" OFF give
-- 'authenticated' no privileges, so RLS is never reached. Grant table privileges to
-- 'authenticated' (RLS policies then decide which ROWS are visible) and nothing to 'anon'.
-- =====================================================================
grant usage on schema public to authenticated;
grant select, insert, update, delete on all tables in schema public to authenticated;
grant usage, select on all sequences in schema public to authenticated;
alter default privileges in schema public grant select, insert, update, delete on tables to authenticated;

revoke all on all tables in schema public from anon;
alter default privileges in schema public revoke all on tables from anon;

-- never exposed through the API
revoke all on public.schema_migrations from anon, authenticated;
revoke all on public.password_reset_tokens from anon, authenticated;
