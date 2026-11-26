-- =====================================================================
-- Migration 006: TDS (Tax Deducted at Source) support.
-- Scope: TDS on the client's payments to vendors/professionals (Section 26Q-type deductions on
-- purchase/expense invoices). Salary TDS (24Q) and non-resident TDS (27Q) are NOT covered — they
-- need payroll / foreign-remittance data this app does not collect.
-- =====================================================================
alter table clients add column if not exists tan text;
alter table clients add column if not exists is_tds_deductor boolean not null default false;

alter table invoices add column if not exists tds_section text;
alter table invoices add column if not exists tds_rate numeric(5,2) not null default 0;
alter table invoices add column if not exists tds_amount numeric(18,2) not null default 0;
alter table invoices add column if not exists tds_status text not null default 'not_applicable'
    check (tds_status in ('not_applicable','pending','deducted','not_deducted'));

create table if not exists tds_returns (
    id uuid primary key,
    firm_id uuid not null references firms(id) on delete cascade,
    client_id uuid not null references clients(id) on delete cascade,
    return_type text not null default '26Q' check (return_type in ('26Q')),
    quarter text not null,                     -- e.g. Q2-2025-26
    rules_version text not null,
    status text not null default 'draft' check (status in ('draft','prepared','approved','filed_externally')),
    data jsonb not null default '{}',
    warnings jsonb not null default '[]',
    external_ack_no text,
    prepared_by uuid references user_profiles(id),
    approved_by uuid references user_profiles(id),
    approved_at timestamptz,
    created_at timestamptz not null default now(),
    unique (client_id, return_type, quarter)
);
