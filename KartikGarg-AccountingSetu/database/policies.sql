-- =====================================================================
-- Accounting Setu — Row Level Security (Supabase / PostgreSQL only)
-- Migration 002. Applied only on the Supabase backend.
--
-- Tenant identity is derived from auth.uid() (the authenticated user's JWT)
-- via membership tables — never from firm_id/client_id supplied by a client.
-- Helper functions are SECURITY DEFINER so policies do not recurse.
-- =====================================================================

create or replace function public.is_super_admin() returns boolean
language sql stable security definer set search_path = public as $$
  select coalesce((select is_super_admin and is_active from user_profiles where id = auth.uid()), false);
$$;

-- Firms where the current user is active staff (and the firm itself is active)
create or replace function public.staff_firm_ids() returns setof uuid
language sql stable security definer set search_path = public as $$
  select fs.firm_id from firm_staff fs join firms f on f.id = fs.firm_id
  where fs.user_id = auth.uid() and fs.is_active and f.status = 'active';
$$;

create or replace function public.staff_role(p_firm uuid) returns text
language sql stable security definer set search_path = public as $$
  select role from firm_staff where firm_id = p_firm and user_id = auth.uid() and is_active limit 1;
$$;

-- Effective permission check, mirrors utils/permissions.py ROLE_PERMISSIONS
create or replace function public.has_permission(p_firm uuid, p_perm text) returns boolean
language plpgsql stable security definer set search_path = public as $$
declare
  r text; perms jsonb; base text[];
begin
  select role, permissions into r, perms from firm_staff
   where firm_id = p_firm and user_id = auth.uid() and is_active;
  if r is null then return false; end if;
  if perms ? 'revoke' and (perms->'revoke') ? p_perm then return false; end if;
  if perms ? 'grant' and (perms->'grant') ? p_perm then return true; end if;
  base := case r
    when 'firm_admin' then array['view','manage_firm','manage_staff','manage_clients','view_all_clients','upload_documents','review_documents','approve_documents','prepare_vouchers','approve_vouchers','manage_ledgers','bank_reconcile','gst_prepare','gst_approve','generate_reports','approve_reports','export_tally','finalize_period','reopen_period','view_audit']
    when 'partner' then array['view','manage_clients','view_all_clients','upload_documents','review_documents','approve_documents','prepare_vouchers','approve_vouchers','manage_ledgers','bank_reconcile','gst_prepare','gst_approve','generate_reports','approve_reports','export_tally','finalize_period','reopen_period','view_audit']
    when 'accountant' then array['view','upload_documents','review_documents','approve_documents','prepare_vouchers','manage_ledgers','bank_reconcile','generate_reports','export_tally']
    when 'audit_staff' then array['view','review_documents','generate_reports','view_audit']
    when 'gst_executive' then array['view','review_documents','gst_prepare','generate_reports']
    when 'reviewer' then array['view','review_documents','approve_documents','approve_vouchers','approve_reports','generate_reports']
    when 'read_only' then array['view']
    else array[]::text[] end;
  return p_perm = any(base);
end $$;

-- Can the current user (staff) see this client?
create or replace function public.staff_can_access_client(p_client uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from clients c
    join firm_staff fs on fs.firm_id = c.firm_id and fs.user_id = auth.uid() and fs.is_active
    join firms f on f.id = c.firm_id and f.status = 'active'
    where c.id = p_client
      and (public.has_permission(c.firm_id, 'view_all_clients')
           or exists (select 1 from client_staff_assignments a where a.client_id = c.id and a.staff_id = fs.id))
  );
$$;

create or replace function public.is_client_user(p_client uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from client_users cu join firms f on f.id = cu.firm_id and f.status = 'active'
    where cu.client_id = p_client and cu.user_id = auth.uid() and cu.is_active
  );
$$;

create or replace function public.can_access_client(p_client uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select public.staff_can_access_client(p_client) or public.is_client_user(p_client);
$$;

-- Is the accounting period containing p_date finalized for p_client?
create or replace function public.period_locked(p_client uuid, p_date date) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from accounting_periods
    where client_id = p_client and year = extract(year from p_date)::int
      and month = extract(month from p_date)::int and status = 'finalized');
$$;

-- ---------- enable RLS everywhere ----------
do $$
declare t text;
begin
  foreach t in array array[
    'user_profiles','password_reset_tokens','subscription_plans','platform_settings','system_logs',
    'firms','firm_subscriptions','firm_staff','clients','client_users','client_invitations',
    'client_staff_assignments','financial_years','accounting_periods','document_submissions','documents',
    'document_notes','processing_jobs','extracted_document_data','clarification_requests','ledgers',
    'ledger_mappings','cost_centres','invoices','invoice_items','voucher_sequences','accounting_vouchers',
    'accounting_voucher_entries','opening_balances','closing_stock','bank_accounts','bank_statements',
    'bank_transactions','bank_matches','gst_returns','gst_return_items','gstr2b_uploads','gstr2b_records',
    'gst_reconciliations','gst_reconciliation_items','reports','tally_exports','notifications','audit_logs']
  loop
    execute format('alter table public.%I enable row level security', t);
    execute format('alter table public.%I force row level security', t);
  end loop;
end $$;

-- ---------- platform tables ----------
create policy up_self on user_profiles for select using (id = auth.uid() or public.is_super_admin()
  or exists (select 1 from firm_staff me join firm_staff other on other.firm_id = me.firm_id
             where me.user_id = auth.uid() and other.user_id = user_profiles.id)
  or exists (select 1 from client_users cu where cu.user_id = user_profiles.id
             and public.staff_can_access_client(cu.client_id)));
create policy up_update_self on user_profiles for update using (id = auth.uid() or public.is_super_admin());

create policy plans_read on subscription_plans for select using (auth.uid() is not null);
create policy plans_admin on subscription_plans for all using (public.is_super_admin()) with check (public.is_super_admin());
create policy settings_admin on platform_settings for all using (public.is_super_admin()) with check (public.is_super_admin());
create policy syslog_admin on system_logs for select using (public.is_super_admin());
create policy syslog_insert on system_logs for insert with check (auth.uid() is not null);

-- ---------- firms ----------
create policy firms_read on firms for select using (public.is_super_admin() or id in (select public.staff_firm_ids())
  or exists (select 1 from client_users cu where cu.firm_id = firms.id and cu.user_id = auth.uid()));
create policy firms_update on firms for update using (public.is_super_admin() or public.has_permission(id, 'manage_firm'));
create policy firms_admin_insert on firms for insert with check (public.is_super_admin());

create policy subs_read on firm_subscriptions for select using (public.is_super_admin() or public.has_permission(firm_id, 'manage_firm'));
create policy subs_admin on firm_subscriptions for all using (public.is_super_admin()) with check (public.is_super_admin());

create policy staff_read on firm_staff for select using (public.is_super_admin() or firm_id in (select public.staff_firm_ids()));
create policy staff_manage on firm_staff for all using (public.has_permission(firm_id, 'manage_staff'))
  with check (public.has_permission(firm_id, 'manage_staff'));

-- ---------- clients ----------
create policy clients_read on clients for select using (public.can_access_client(id));
create policy clients_manage on clients for all using (public.has_permission(firm_id, 'manage_clients'))
  with check (public.has_permission(firm_id, 'manage_clients'));

create policy cu_read on client_users for select using (user_id = auth.uid() or public.staff_can_access_client(client_id));
create policy cu_manage on client_users for all using (public.has_permission(firm_id, 'manage_clients'))
  with check (public.has_permission(firm_id, 'manage_clients'));
create policy inv_manage on client_invitations for all using (public.has_permission(firm_id, 'manage_clients'))
  with check (public.has_permission(firm_id, 'manage_clients'));
create policy csa_read on client_staff_assignments for select using (firm_id in (select public.staff_firm_ids()));
create policy csa_manage on client_staff_assignments for all using (public.has_permission(firm_id, 'manage_clients'))
  with check (public.has_permission(firm_id, 'manage_clients'));

-- ---------- generic tenant tables: read = can_access_client, write = staff with access ----------
do $$
declare t text;
begin
  foreach t in array array[
    'financial_years','accounting_periods','document_notes','processing_jobs','extracted_document_data',
    'ledgers','ledger_mappings','cost_centres','invoices','invoice_items','voucher_sequences',
    'accounting_vouchers','accounting_voucher_entries','opening_balances','closing_stock','bank_accounts',
    'bank_statements','bank_transactions','bank_matches','gst_returns','gst_return_items','gstr2b_uploads',
    'gstr2b_records','gst_reconciliations','gst_reconciliation_items','tally_exports']
  loop
    execute format($f$create policy %1$s_staff_read on %1$I for select using (public.staff_can_access_client(client_id))$f$, t);
    execute format($f$create policy %1$s_staff_write on %1$I for all using (public.staff_can_access_client(client_id) and public.staff_role(firm_id) <> 'read_only')
                    with check (public.staff_can_access_client(client_id) and public.staff_role(firm_id) <> 'read_only')$f$, t);
  end loop;
end $$;

-- Internal notes are staff-only; clients never see them.
-- Clients may read their own period status (finalization) but not snapshots of other clients.
create policy periods_client_read on accounting_periods for select using (public.is_client_user(client_id));

-- Finalized periods cannot be modified except by reopen-capable users (defence in depth;
-- the application also enforces this in services/period_service.py).
create or replace function public.guard_locked_voucher() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  if public.period_locked(coalesce(new.client_id, old.client_id), coalesce(new.voucher_date, old.voucher_date)) then
    raise exception 'Accounting period is finalized and locked';
  end if;
  return coalesce(new, old);
end $$;
drop trigger if exists trg_guard_locked_voucher on accounting_vouchers;
create trigger trg_guard_locked_voucher before insert or update or delete on accounting_vouchers
  for each row execute function public.guard_locked_voucher();

-- Never allow an approved voucher whose debits and credits differ.
create or replace function public.guard_balanced_voucher() returns trigger
language plpgsql security definer set search_path = public as $$
declare d numeric; c numeric;
begin
  if new.status = 'approved' then
    select coalesce(sum(amount) filter (where dr_cr='Dr'),0), coalesce(sum(amount) filter (where dr_cr='Cr'),0)
      into d, c from accounting_voucher_entries where voucher_id = new.id;
    if d <> c or d = 0 then raise exception 'Unbalanced voucher cannot be approved (Dr %, Cr %)', d, c; end if;
  end if;
  return new;
end $$;
drop trigger if exists trg_guard_balanced_voucher on accounting_vouchers;
create trigger trg_guard_balanced_voucher before update on accounting_vouchers
  for each row execute function public.guard_balanced_voucher();

-- ---------- client-facing tables ----------
create policy subm_read on document_submissions for select using (public.can_access_client(client_id));
create policy subm_client_write on document_submissions for insert with check (public.is_client_user(client_id) or public.staff_can_access_client(client_id));
create policy subm_update on document_submissions for update using (public.is_client_user(client_id) or public.staff_can_access_client(client_id));

create policy docs_read on documents for select using (public.can_access_client(client_id));
create policy docs_insert on documents for insert with check (public.is_client_user(client_id) or public.has_permission(firm_id,'upload_documents') and public.staff_can_access_client(client_id));
create policy docs_staff_update on documents for update using (public.staff_can_access_client(client_id));

create policy notes_staff on document_notes for all using (public.staff_can_access_client(client_id)) with check (public.staff_can_access_client(client_id));

create policy clar_read on clarification_requests for select using (public.can_access_client(client_id));
create policy clar_staff on clarification_requests for insert with check (public.staff_can_access_client(client_id));
create policy clar_update on clarification_requests for update using (public.can_access_client(client_id));

create policy reports_staff on reports for all using (public.staff_can_access_client(client_id)) with check (public.staff_can_access_client(client_id));
create policy reports_client on reports for select using (public.is_client_user(client_id) and status = 'shared');

create policy notif_read on notifications for select using (user_id = auth.uid());
create policy notif_update on notifications for update using (user_id = auth.uid());
create policy notif_insert on notifications for insert with check (auth.uid() is not null);

-- Audit log: append-only. Readable by super admin and firm users with view_audit.
create policy audit_insert on audit_logs for insert with check (auth.uid() is not null and user_id = auth.uid());
create policy audit_read on audit_logs for select using (public.is_super_admin() or (firm_id is not null and public.has_permission(firm_id,'view_audit')));
create or replace function public.audit_immutable() returns trigger language plpgsql as $$
begin raise exception 'audit_logs is append-only'; end $$;
drop trigger if exists trg_audit_immutable on audit_logs;
create trigger trg_audit_immutable before update or delete on audit_logs for each row execute function public.audit_immutable();

create policy reset_tokens_none on password_reset_tokens for all using (false);
-- =====================================================================
-- Accounting Setu — private Supabase Storage bucket + tenant policies
-- Migration 003 (Supabase only).
-- Object path convention:  {firm_id}/{client_id}/{yyyy}/{mm}/{document_id}{ext}
--                          {firm_id}/_firm/logo{ext}       (firm branding)
-- =====================================================================
insert into storage.buckets (id, name, public, file_size_limit)
values ('documents', 'documents', false, 26214400)
on conflict (id) do update set public = false;

create policy docs_bucket_read on storage.objects for select using (
  bucket_id = 'documents' and (
    (storage.foldername(name))[2] = '_firm' and (storage.foldername(name))[1]::uuid in (select public.staff_firm_ids())
    or ((storage.foldername(name))[2] <> '_firm' and public.can_access_client(((storage.foldername(name))[2])::uuid)
        and exists (select 1 from clients c where c.id = ((storage.foldername(name))[2])::uuid
                    and c.firm_id = ((storage.foldername(name))[1])::uuid))
  )
);

create policy docs_bucket_insert on storage.objects for insert with check (
  bucket_id = 'documents' and (
    ((storage.foldername(name))[2] = '_firm' and public.has_permission(((storage.foldername(name))[1])::uuid, 'manage_firm'))
    or ((storage.foldername(name))[2] <> '_firm' and public.can_access_client(((storage.foldername(name))[2])::uuid)
        and exists (select 1 from clients c where c.id = ((storage.foldername(name))[2])::uuid
                    and c.firm_id = ((storage.foldername(name))[1])::uuid))
  )
);

-- Originals are retained: no update/delete policy for ordinary users.
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
