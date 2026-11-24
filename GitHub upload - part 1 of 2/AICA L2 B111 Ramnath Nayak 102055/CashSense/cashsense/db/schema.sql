-- CashSense schema. Plain SQL that runs on SQLite and PostgreSQL (Supabase).
-- Bank amounts are integer minor units of the account currency (paise for INR, cents for USD).
-- Columns ending _paise are always INR. Dates are ISO text (YYYY-MM-DD).

CREATE TABLE IF NOT EXISTS company (
    company_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    city TEXT, state TEXT, industry TEXT,
    fy_start TEXT, fy_end TEXT, currency TEXT,
    approval_threshold_paise BIGINT,
    note TEXT
);

CREATE TABLE IF NOT EXISTS bank_accounts (
    account_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    account_type TEXT NOT NULL,
    currency TEXT NOT NULL DEFAULT 'INR',
    bank_name TEXT, ifsc TEXT, account_no TEXT,
    opening_balance_minor BIGINT NOT NULL,
    opening_date TEXT NOT NULL,
    limit_minor BIGINT DEFAULT 0,
    interest_rate REAL DEFAULT 0,
    min_balance_minor BIGINT DEFAULT 0,
    statement_format TEXT
);

CREATE TABLE IF NOT EXISTS counterparties (
    party_id TEXT PRIMARY KEY,
    party_type TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT, ifsc TEXT, account_no TEXT,
    terms_days INTEGER DEFAULT 0,
    msme INTEGER DEFAULT 0,
    currency TEXT DEFAULT 'INR'
);

CREATE TABLE IF NOT EXISTS bank_holidays (
    holiday_date TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS book_entries (
    entry_id TEXT PRIMARY KEY,
    voucher_no TEXT NOT NULL,
    voucher_type TEXT NOT NULL,
    entry_date TEXT NOT NULL,
    account_id TEXT NOT NULL REFERENCES bank_accounts(account_id),
    currency TEXT NOT NULL DEFAULT 'INR',
    counter_ledger TEXT, party_id TEXT, narration TEXT,
    amount_minor BIGINT NOT NULL,
    inr_amount_paise BIGINT NOT NULL,
    mode TEXT, instrument_no TEXT
);

CREATE TABLE IF NOT EXISTS statement_imports (
    import_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES bank_accounts(account_id),
    period TEXT NOT NULL,
    currency TEXT NOT NULL DEFAULT 'INR',
    source_file TEXT, source_format TEXT,
    opening_balance_minor BIGINT, closing_balance_minor BIGINT,
    line_count INTEGER,
    status TEXT DEFAULT 'verified',
    issues TEXT,
    imported_at TEXT, imported_by TEXT
);

CREATE TABLE IF NOT EXISTS bank_lines (
    line_id TEXT PRIMARY KEY,
    import_id TEXT NOT NULL REFERENCES statement_imports(import_id),
    account_id TEXT NOT NULL REFERENCES bank_accounts(account_id),
    txn_date TEXT NOT NULL, value_date TEXT,
    description TEXT, ref_no TEXT,
    amount_minor BIGINT NOT NULL,
    balance_minor BIGINT,
    category TEXT, party_id TEXT,
    category_confidence REAL, category_reason TEXT,
    category_source TEXT,
    review_status TEXT
);

CREATE TABLE IF NOT EXISTS ar_open (
    invoice_no TEXT PRIMARY KEY,
    party_id TEXT NOT NULL,
    invoice_date TEXT, due_date TEXT, currency TEXT,
    amount_minor BIGINT NOT NULL,
    note TEXT
);

CREATE TABLE IF NOT EXISTS ap_open (
    bill_no TEXT PRIMARY KEY,
    party_id TEXT NOT NULL,
    bill_date TEXT, due_date TEXT,
    amount_paise BIGINT NOT NULL,
    msme INTEGER DEFAULT 0,
    note TEXT
);

CREATE TABLE IF NOT EXISTS commitments (
    commit_id TEXT PRIMARY KEY,
    due_date TEXT NOT NULL,
    account_id TEXT,
    description TEXT, category TEXT,
    amount_paise BIGINT NOT NULL,
    certainty TEXT
);

-- Phase 3: reconciliation, risks, approvals ---------------------------------------------

CREATE TABLE IF NOT EXISTS recon_links (
    link_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    line_id TEXT NOT NULL,
    entry_id TEXT NOT NULL,
    link_type TEXT NOT NULL,          -- auto_exact / fuzzy_approved / posted_from_line
    rule TEXT,
    run_id TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS recon_runs (
    run_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    as_of TEXT NOT NULL,
    created_at TEXT,
    book_balance_minor BIGINT,
    bank_balance_minor BIGINT,
    computed_bank_minor BIGINT,
    status TEXT,                      -- agreed / difference
    auto_matched INTEGER,
    summary TEXT,
    commentary TEXT
);

CREATE TABLE IF NOT EXISTS recon_items (
    item_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    category TEXT NOT NULL,
    side TEXT NOT NULL,               -- books_only / bank_only / both
    line_id TEXT, entry_id TEXT,
    item_date TEXT,
    amount_minor BIGINT,
    adjust_minor BIGINT,              -- amount to add to the book balance to reach the bank balance
    description TEXT,
    explanation TEXT,
    suggestion TEXT,                  -- JSON: proposed entry or action
    needs_approval INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS risk_flags (
    flag_id TEXT PRIMARY KEY,
    run_id TEXT,
    flag_type TEXT NOT NULL,
    severity TEXT,
    account_id TEXT,
    line_ids TEXT,
    party_id TEXT,
    bill_no TEXT,
    amount_minor BIGINT,
    flag_date TEXT,
    evidence TEXT,                    -- JSON (rule facts, browser verification, screenshot path)
    explanation TEXT,
    action TEXT,
    status TEXT DEFAULT 'open'
);

CREATE TABLE IF NOT EXISTS approvals (
    approval_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,               -- journal_entry / fuzzy_match / risk_flag
    ref_id TEXT,
    title TEXT,
    payload TEXT,                     -- JSON
    status TEXT NOT NULL,             -- pending / approved / rejected
    requested_at TEXT,
    decided_at TEXT,
    decided_by TEXT,
    channel TEXT,
    channel_message_id TEXT
);

CREATE TABLE IF NOT EXISTS app_state (
    state_key TEXT PRIMARY KEY,
    state_value TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    log_id TEXT PRIMARY KEY,
    ts TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    entity TEXT, entity_id TEXT,
    details TEXT
);
