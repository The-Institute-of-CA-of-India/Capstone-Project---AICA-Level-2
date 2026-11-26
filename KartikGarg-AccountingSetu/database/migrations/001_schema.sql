-- =====================================================================
-- Accounting Setu — core schema (PostgreSQL / Supabase dialect)
-- Migration 001. This file is the single source of truth for tables.
-- The local SQLite backend translates this file automatically
-- (see services/db.py::pg_to_sqlite). Keep statements separated by ';'
-- and avoid PostgreSQL-only syntax outside the documented translations.
-- Money columns use numeric(18,2); never floating point.
-- =====================================================================

-- ---------- Platform level ----------
create table if not exists user_profiles (
    id uuid primary key,                       -- = auth.users.id on Supabase
    email text not null unique,
    full_name text not null default '',
    phone text,
    is_super_admin boolean not null default false,
    password_hash text,                        -- local backend only; NULL on Supabase
    is_active boolean not null default true,
    must_change_password boolean not null default false,
    failed_logins integer not null default 0,
    locked_until timestamptz,
    last_login_at timestamptz,
    created_at timestamptz not null default now()
);

create table if not exists password_reset_tokens (
    id uuid primary key,
    user_id uuid not null references user_profiles(id) on delete cascade,
    token_hash text not null unique,
    expires_at timestamptz not null,
    used_at timestamptz,
    created_at timestamptz not null default now()
);

create table if not exists subscription_plans (
    id uuid primary key,
    code text not null unique,
    name text not null,
    max_clients integer not null default 10,
    max_staff integer not null default 5,
    max_documents_per_month integer not null default 1000,
    price_monthly numeric(18,2) not null default 0,
    features jsonb not null default '{}',
    is_active boolean not null default true,
    created_at timestamptz not null default now()
);

create table if not exists platform_settings (
    key text primary key,
    value jsonb not null default '{}',
    updated_by uuid references user_profiles(id),
    updated_at timestamptz not null default now()
);

create table if not exists system_logs (
    id uuid primary key,
    level text not null default 'ERROR',
    source text not null default '',
    message text not null,
    context jsonb not null default '{}',
    firm_id uuid,
    user_id uuid,
    created_at timestamptz not null default now()
);

-- ---------- Firms (tenants) ----------
create table if not exists firms (
    id uuid primary key,
    name text not null,
    legal_name text,
    frn text,                                  -- ICAI firm registration number
    gstin text,
    pan text,
    email text not null,
    phone text,
    address text,
    city text,
    state text,
    state_code text,
    pincode text,
    logo_path text,
    status text not null default 'pending' check (status in ('pending','active','suspended','deactivated')),
    settings jsonb not null default '{}',
    created_by uuid references user_profiles(id),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists firm_subscriptions (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    plan_id uuid not null references subscription_plans(id),
    status text not null default 'trial' check (status in ('trial','active','past_due','cancelled','expired')),
    start_date date not null,
    end_date date,
    billing_cycle text not null default 'monthly',
    amount numeric(18,2) not null default 0,
    notes text,
    created_at timestamptz not null default now()
);
create index if not exists idx_firm_subscriptions_firm on firm_subscriptions(firm_id);

create table if not exists firm_staff (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    user_id uuid not null references user_profiles(id) on delete cascade,
    role text not null check (role in ('firm_admin','partner','accountant','audit_staff','gst_executive','reviewer','read_only')),
    permissions jsonb not null default '{}',   -- {"grant": [...], "revoke": [...]}
    designation text,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    unique (firm_id, user_id)
);
create index if not exists idx_firm_staff_user on firm_staff(user_id);

-- ---------- Clients ----------
create table if not exists clients (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    name text not null,
    legal_name text,
    gstin text,
    pan text,
    business_type text,
    gst_registration_type text not null default 'regular' check (gst_registration_type in ('regular','composition','unregistered','sez')),
    state_code text,
    email text,
    phone text,
    address text,
    fy_start_month integer not null default 4,
    submission_deadline_day integer,           -- overrides firm default when set
    status text not null default 'active' check (status in ('active','inactive')),
    settings jsonb not null default '{}',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index if not exists idx_clients_firm on clients(firm_id);

create table if not exists client_users (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    user_id uuid not null references user_profiles(id) on delete cascade,
    is_primary boolean not null default false,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    unique (client_id, user_id)
);
create index if not exists idx_client_users_user on client_users(user_id);

create table if not exists client_invitations (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    email text not null,
    token_hash text not null unique,
    invited_by uuid references user_profiles(id),
    expires_at timestamptz not null,
    accepted_at timestamptz,
    created_at timestamptz not null default now()
);

create table if not exists client_staff_assignments (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    staff_id uuid not null references firm_staff(id) on delete cascade,
    created_at timestamptz not null default now(),
    unique (client_id, staff_id)
);

-- ---------- Periods ----------
create table if not exists financial_years (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    label text not null,                       -- e.g. 2025-26
    start_date date not null,
    end_date date not null,
    is_closed boolean not null default false,
    created_at timestamptz not null default now(),
    unique (client_id, label)
);

create table if not exists accounting_periods (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    fy_label text not null,
    year integer not null,
    month integer not null check (month between 1 and 12),
    status text not null default 'open' check (status in ('open','finalized','reopened')),
    finalized_by uuid references user_profiles(id),
    finalized_at timestamptz,
    reopened_by uuid references user_profiles(id),
    reopened_at timestamptz,
    reopen_reason text,
    snapshot jsonb,
    snapshot_hash text,
    created_at timestamptz not null default now(),
    unique (client_id, year, month)
);

-- ---------- Documents ----------
create table if not exists document_submissions (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    period_year integer not null,
    period_month integer not null,
    reference_no text unique,
    status text not null default 'draft' check (status in ('draft','submitted','processing','completed')),
    due_date date,
    submitted_by uuid references user_profiles(id),
    submitted_at timestamptz,
    notes text,
    created_at timestamptz not null default now()
);
create index if not exists idx_submissions_client_period on document_submissions(client_id, period_year, period_month);

create table if not exists documents (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    submission_id uuid references document_submissions(id) on delete set null,
    parent_document_id uuid references documents(id) on delete cascade,
    period_year integer not null,
    period_month integer not null,
    doc_type text not null default 'other',
    original_filename text not null,
    storage_path text not null,
    mime_type text,
    file_ext text,
    file_size integer not null default 0,
    sha256 text not null,
    page_count integer,
    page_from integer,
    page_to integer,
    status text not null default 'uploaded' check (status in ('uploaded','processing','processed','needs_review','approved','rejected','finalized','split')),
    classification_confidence numeric(5,2),
    error_message text,
    review_flags jsonb not null default '[]',
    uploaded_by uuid references user_profiles(id),
    uploaded_at timestamptz not null default now(),
    reviewed_by uuid references user_profiles(id),
    reviewed_at timestamptz,
    retention_until date
);
create index if not exists idx_documents_client_period on documents(client_id, period_year, period_month);
create index if not exists idx_documents_status on documents(firm_id, status);
create index if not exists idx_documents_sha on documents(client_id, sha256);

create table if not exists document_notes (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    document_id uuid not null references documents(id) on delete cascade,
    user_id uuid references user_profiles(id),
    note text not null,
    is_internal boolean not null default true,
    created_at timestamptz not null default now()
);

create table if not exists processing_jobs (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    document_id uuid references documents(id) on delete cascade,
    job_type text not null,
    status text not null default 'queued' check (status in ('queued','running','succeeded','failed')),
    attempts integer not null default 0,
    log jsonb not null default '[]',
    error text,
    started_at timestamptz,
    finished_at timestamptz,
    created_by uuid references user_profiles(id),
    created_at timestamptz not null default now()
);

create table if not exists extracted_document_data (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    document_id uuid not null references documents(id) on delete cascade,
    version integer not null default 1,
    source text not null check (source in ('ocr','ai','rules','import','manual')),
    provider text,
    raw_text text,
    data jsonb not null default '{}',
    field_confidence jsonb not null default '{}',
    overall_confidence numeric(5,2),
    validation jsonb not null default '{}',
    is_current boolean not null default true,
    created_by uuid references user_profiles(id),
    created_at timestamptz not null default now(),
    unique (document_id, version)
);

create table if not exists clarification_requests (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    document_id uuid references documents(id) on delete set null,
    raised_by uuid references user_profiles(id),
    question text not null,
    status text not null default 'open' check (status in ('open','answered','closed')),
    response text,
    responded_by uuid references user_profiles(id),
    responded_at timestamptz,
    created_at timestamptz not null default now()
);

-- ---------- Ledgers ----------
create table if not exists ledgers (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    name text not null,
    group_name text not null,
    nature text not null check (nature in ('asset','liability','income','expense','equity')),
    party_gstin text,
    state_code text,
    is_system boolean not null default false,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    unique (client_id, name)
);

create table if not exists ledger_mappings (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    mapping_key text not null,
    ledger_id uuid not null references ledgers(id) on delete cascade,
    created_at timestamptz not null default now(),
    unique (client_id, mapping_key)
);

create table if not exists cost_centres (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    name text not null,
    unique (client_id, name)
);

-- ---------- Invoices ----------
create table if not exists invoices (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    document_id uuid references documents(id) on delete set null,
    category text not null check (category in ('sales','purchase','expense')),
    note_type text not null default 'invoice' check (note_type in ('invoice','credit_note','debit_note')),
    invoice_no text not null,
    invoice_date date not null,
    party_name text not null,
    party_gstin text,
    party_state_code text,
    place_of_supply text,
    supply_type text not null default 'taxable' check (supply_type in ('taxable','export_wpay','export_wopay','sez_wpay','sez_wopay','nil','exempt','non_gst','deemed_export')),
    reverse_charge boolean not null default false,
    original_invoice_no text,
    original_invoice_date date,
    taxable_value numeric(18,2) not null default 0,
    cgst numeric(18,2) not null default 0,
    sgst numeric(18,2) not null default 0,
    igst numeric(18,2) not null default 0,
    cess numeric(18,2) not null default 0,
    discount numeric(18,2) not null default 0,
    round_off numeric(18,2) not null default 0,
    total numeric(18,2) not null default 0,
    expense_head text,
    itc_eligibility text not null default 'pending' check (itc_eligibility in ('eligible','ineligible','blocked','pending','not_applicable')),
    itc_reason text,
    status text not null default 'draft' check (status in ('draft','approved','cancelled')),
    created_by uuid references user_profiles(id),
    approved_by uuid references user_profiles(id),
    approved_at timestamptz,
    created_at timestamptz not null default now()
);
create index if not exists idx_invoices_client_date on invoices(client_id, invoice_date);
create unique index if not exists uq_invoices_dedupe on invoices(client_id, category, note_type, coalesce(party_gstin, party_name), invoice_no) where status <> 'cancelled';

create table if not exists invoice_items (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    invoice_id uuid not null references invoices(id) on delete cascade,
    line_no integer not null,
    description text,
    hsn_sac text,
    quantity numeric(18,3),
    unit text,
    unit_price numeric(18,2),
    taxable_value numeric(18,2) not null default 0,
    gst_rate numeric(5,2) not null default 0,
    cgst numeric(18,2) not null default 0,
    sgst numeric(18,2) not null default 0,
    igst numeric(18,2) not null default 0,
    cess numeric(18,2) not null default 0
);

-- ---------- Vouchers ----------
create table if not exists voucher_sequences (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    voucher_type text not null,
    fy_label text not null,
    next_no integer not null default 1,
    unique (client_id, voucher_type, fy_label)
);

create table if not exists accounting_vouchers (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    voucher_type text not null check (voucher_type in ('Sales','Purchase','Receipt','Payment','Journal','Contra','Credit Note','Debit Note')),
    voucher_no text not null,
    voucher_date date not null,
    fy_label text not null,
    narration text,
    party_ledger_id uuid references ledgers(id),
    reference_no text,
    source_type text not null default 'manual' check (source_type in ('invoice','bank','manual','opening','adjustment')),
    source_id uuid,
    status text not null default 'draft' check (status in ('draft','approved','rejected','cancelled')),
    needs_review boolean not null default false,
    review_reason text,
    total_amount numeric(18,2) not null default 0,
    created_by uuid references user_profiles(id),
    approved_by uuid references user_profiles(id),
    approved_at timestamptz,
    created_at timestamptz not null default now(),
    unique (client_id, voucher_type, voucher_no)
);
create index if not exists idx_vouchers_client_date on accounting_vouchers(client_id, voucher_date);
create unique index if not exists uq_vouchers_source on accounting_vouchers(client_id, source_type, source_id) where source_id is not null and status <> 'cancelled' and status <> 'rejected';

create table if not exists accounting_voucher_entries (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    voucher_id uuid not null references accounting_vouchers(id) on delete cascade,
    line_no integer not null,
    ledger_id uuid not null references ledgers(id),
    dr_cr text not null check (dr_cr in ('Dr','Cr')),
    amount numeric(18,2) not null check (amount >= 0),
    cost_centre_id uuid references cost_centres(id),
    bill_ref text
);
create index if not exists idx_voucher_entries_voucher on accounting_voucher_entries(voucher_id);
create index if not exists idx_voucher_entries_ledger on accounting_voucher_entries(ledger_id);

create table if not exists opening_balances (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    fy_label text not null,
    ledger_id uuid not null references ledgers(id) on delete cascade,
    dr_cr text not null check (dr_cr in ('Dr','Cr')),
    amount numeric(18,2) not null default 0,
    created_by uuid references user_profiles(id),
    created_at timestamptz not null default now(),
    unique (client_id, fy_label, ledger_id)
);

create table if not exists closing_stock (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    as_of_date date not null,
    amount numeric(18,2) not null default 0,
    basis text,
    created_by uuid references user_profiles(id),
    created_at timestamptz not null default now(),
    unique (client_id, as_of_date)
);

-- ---------- Bank ----------
create table if not exists bank_accounts (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    ledger_id uuid not null references ledgers(id),
    bank_name text not null,
    account_no_masked text,
    ifsc text,
    created_at timestamptz not null default now()
);

create table if not exists bank_statements (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    bank_account_id uuid not null references bank_accounts(id) on delete cascade,
    document_id uuid references documents(id) on delete set null,
    period_from date,
    period_to date,
    opening_balance numeric(18,2),
    closing_balance numeric(18,2),
    status text not null default 'imported',
    created_by uuid references user_profiles(id),
    created_at timestamptz not null default now()
);

create table if not exists bank_transactions (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    bank_account_id uuid not null references bank_accounts(id) on delete cascade,
    statement_id uuid references bank_statements(id) on delete cascade,
    txn_date date not null,
    value_date date,
    narration text not null default '',
    reference text,
    debit numeric(18,2) not null default 0,
    credit numeric(18,2) not null default 0,
    balance numeric(18,2),
    category text not null default 'unknown',
    category_confidence numeric(5,2),
    party_ledger_id uuid references ledgers(id),
    match_status text not null default 'unmatched' check (match_status in ('matched','unmatched','partially_matched','duplicate','suspense','needs_review')),
    match_score numeric(5,2),
    voucher_id uuid references accounting_vouchers(id) on delete set null,
    txn_hash text not null,
    created_at timestamptz not null default now()
);
create index if not exists idx_bank_txn_client_date on bank_transactions(client_id, txn_date);
create index if not exists idx_bank_txn_hash on bank_transactions(bank_account_id, txn_hash);

create table if not exists bank_matches (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    transaction_id uuid not null references bank_transactions(id) on delete cascade,
    target_type text not null check (target_type in ('invoice','voucher')),
    target_id uuid not null,
    amount numeric(18,2) not null,
    score numeric(5,2) not null default 0,
    reasons jsonb not null default '[]',
    status text not null default 'suggested' check (status in ('suggested','confirmed','rejected')),
    confirmed_by uuid references user_profiles(id),
    confirmed_at timestamptz,
    created_at timestamptz not null default now()
);
create index if not exists idx_bank_matches_txn on bank_matches(transaction_id);

-- ---------- GST ----------
create table if not exists gst_returns (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    return_type text not null check (return_type in ('GSTR1','GSTR3B')),
    period text not null,                      -- MMYYYY
    rules_version text not null,
    status text not null default 'draft' check (status in ('draft','prepared','approved','filed_externally')),
    data jsonb not null default '{}',
    warnings jsonb not null default '[]',
    external_arn text,                         -- recorded only when the user declares it was filed on the portal
    prepared_by uuid references user_profiles(id),
    approved_by uuid references user_profiles(id),
    approved_at timestamptz,
    created_at timestamptz not null default now(),
    unique (client_id, return_type, period)
);

create table if not exists gst_return_items (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    return_id uuid not null references gst_returns(id) on delete cascade,
    section text not null,
    invoice_id uuid references invoices(id) on delete set null,
    data jsonb not null default '{}'
);

create table if not exists gstr2b_uploads (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    period text not null,
    source_filename text,
    record_count integer not null default 0,
    uploaded_by uuid references user_profiles(id),
    created_at timestamptz not null default now()
);

create table if not exists gstr2b_records (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    upload_id uuid not null references gstr2b_uploads(id) on delete cascade,
    section text not null default 'B2B',
    supplier_gstin text not null,
    supplier_name text,
    invoice_no text not null,
    invoice_date date,
    invoice_value numeric(18,2) not null default 0,
    taxable_value numeric(18,2) not null default 0,
    igst numeric(18,2) not null default 0,
    cgst numeric(18,2) not null default 0,
    sgst numeric(18,2) not null default 0,
    cess numeric(18,2) not null default 0,
    itc_available boolean not null default true,
    reason text,
    supplier_period text
);

create table if not exists gst_reconciliations (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    period text not null,
    upload_id uuid references gstr2b_uploads(id) on delete cascade,
    summary jsonb not null default '{}',
    created_by uuid references user_profiles(id),
    created_at timestamptz not null default now()
);

create table if not exists gst_reconciliation_items (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    reconciliation_id uuid not null references gst_reconciliations(id) on delete cascade,
    status text not null,
    invoice_id uuid references invoices(id) on delete set null,
    record_id uuid references gstr2b_records(id) on delete set null,
    details jsonb not null default '{}'
);

-- ---------- Reports, exports, notifications, audit ----------
create table if not exists reports (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    report_type text not null,
    title text not null,
    period_from date,
    period_to date,
    file_format text not null,
    storage_path text not null,
    status text not null default 'draft' check (status in ('draft','approved','shared','withdrawn')),
    is_provisional boolean not null default true,
    generated_by uuid references user_profiles(id),
    approved_by uuid references user_profiles(id),
    shared_at timestamptz,
    created_at timestamptz not null default now()
);

create table if not exists tally_exports (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    period_from date not null,
    period_to date not null,
    voucher_ids jsonb not null default '[]',
    voucher_count integer not null default 0,
    storage_path text,
    created_by uuid references user_profiles(id),
    created_at timestamptz not null default now()
);

create table if not exists notifications (
    id uuid primary key,
    firm_id uuid references firms(id) on delete cascade,
    client_id uuid references clients(id) on delete cascade,
    user_id uuid references user_profiles(id) on delete cascade,
    audience text not null default 'user' check (audience in ('user','firm','client','platform')),
    title text not null,
    body text,
    link text,
    is_read boolean not null default false,
    created_at timestamptz not null default now()
);
create index if not exists idx_notifications_user on notifications(user_id, is_read);

create table if not exists audit_logs (
    id uuid primary key,
    firm_id uuid,
    client_id uuid,
    user_id uuid,
    action text not null,
    entity_type text not null,
    entity_id text,
    before_data jsonb,
    after_data jsonb,
    created_at timestamptz not null default now()
);
create index if not exists idx_audit_firm on audit_logs(firm_id, created_at);
