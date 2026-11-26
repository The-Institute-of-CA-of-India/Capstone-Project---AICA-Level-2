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
