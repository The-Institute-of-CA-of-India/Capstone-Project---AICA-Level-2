-- =====================================================================
-- Migration 005: CA firm serial number + secret client-link code; client self-registration fields.
-- Applied to Supabase by scripts/apply_migrations.py; the SQLite backend adds the same
-- columns automatically (services/db.py::SQLiteDatabase.EXTRA_COLUMNS).
-- =====================================================================
alter table firms add column if not exists serial_no text;
alter table firms add column if not exists client_code text;
alter table firms add column if not exists client_code_updated_at timestamptz;
create unique index if not exists uq_firms_serial on firms(serial_no) where serial_no is not null;
create unique index if not exists uq_firms_client_code on firms(client_code) where client_code is not null;

alter table clients add column if not exists contact_person text;
alter table clients add column if not exists aadhaar_masked text;      -- only last 4 digits are stored
alter table clients add column if not exists signup_source text not null default 'firm';
