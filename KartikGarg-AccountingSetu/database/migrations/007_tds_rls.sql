-- =====================================================================
-- Migration 007 (Supabase only): RLS + grants for the new tds_returns table (migration 006).
-- Same pattern as the generic tenant-table policies in 002_rls.sql.
-- =====================================================================
alter table public.tds_returns enable row level security;
alter table public.tds_returns force row level security;

create policy tds_returns_staff_read on tds_returns for select using (public.staff_can_access_client(client_id));
create policy tds_returns_staff_write on tds_returns for all
  using (public.staff_can_access_client(client_id) and public.staff_role(firm_id) <> 'read_only')
  with check (public.staff_can_access_client(client_id) and public.staff_role(firm_id) <> 'read_only');

grant select, insert, update, delete on public.tds_returns to authenticated;
