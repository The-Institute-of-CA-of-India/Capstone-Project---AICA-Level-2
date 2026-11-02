# LedgerDesk feature coverage and enterprise roadmap

This checklist distinguishes working functions from gaps. It is not a claim of feature parity with established accounting suites.

| Area | Included in this release | Remaining work for a full commercial / multinational system |
|---|---|---|
| Companies | Create/select separate books, currencies, legal/tax details | Editable profiles, branches, departments, groups and access restrictions |
| General ledger | Chart of accounts, journals, opening balances, draft/post/reverse | Subaccounts, recurring journals, accrual/reversal scheduling, budget controls |
| Sales | Multi-line invoices, discounts, taxes, customer credit notes, printing | Quotes, orders, delivery notes, price lists, recurring invoices, customer statements |
| Purchases | Bills, supplier debit notes, expenses | Requisitions, purchase orders, GRNs, three-way matching, approval limits |
| Receipts / payments | Single-source partial/full allocation, direct bank entries, realised FX | Multi-invoice allocation, advances, refunds, payment proposals, payment gateway |
| AR/AP | Invoice-level as-at aging and control accounts | Opening-item migration, statements, collection reminders, credit limits |
| Items / inventory | Reusable item catalogue; inventory GL account | Stock quantities, FIFO/weighted average, warehouses, batches/serials, landed costs, COGS automation |
| Assets | Linked cost register, residual value, daily SL depreciation, NBV | Disposals, revaluation, impairment, transfers, component accounting, historical register |
| Banking | Manual cleared-item reconciliation, cash/bank accounts | Bank-file imports, feeds, matching rules, statement attachments, foreign-currency bank revaluation |
| Tax | Configurable line percentage, input/output controls and ledger summary | Jurisdiction rules, tax codes, return boxes, imports/reverse charge, recoverability, UAE CT bridge, e-invoicing |
| Financial statements | TB, P&L, BS, GL, management cash-flow summary | Comparative statutory statements, indirect CFS, equity statement, notes/disclosures, account mapping |
| Currency | Manual invoice/settlement rates and realised gains/losses | Live/historical feeds, currency-precision registry, unrealised revaluation, hedging |
| Group reporting | Rate-based management aggregation | Ownership/NCI, intercompany matching/elimination, FX translation reserve, consolidation adjustments |
| Payroll | Manual payroll journals | Payroll processing, WPS, leave/gratuity, employee subledgers and country compliance |
| Projects | Memo fields and dedicated accounts | Cost centres, project budgets, time sheets, allocations and profitability |
| Controls | Company checks, balanced/atomic posting, immutability through UI, locks, activity log | User identities/RBAC, maker-checker, attachments, immutable audit log, encryption, retention, segregation |
| Reporting / data | CSV report exports, print/PDF, SQLite backup and manual restore | Bulk data import, XLSX exports, report designer, automated backups, restore UI, migration tools |
| Deployment | One local workstation; Python/JS/SQLite; offline operation | Multi-user server architecture, PostgreSQL, SSO, APIs, monitoring, recovery/scale testing |

Recommended next build order:
1. Validate opening-balance migration, control-account reconciliation and invoice requirements with a pilot entity.
2. Add user roles/approvals, attachment storage, validated imports, automated backups and disaster-recovery tests.
3. Implement inventory and procurement cycle if this is a trading business; add projects/payroll as required.
4. Add country tax modules and compliant document templates with jurisdiction-specific test cases.
5. Implement group consolidation with reporting mappings, rates by account class, eliminations, ownership and audit working papers.
6. Move to a multi-user database/server architecture before rollout across multinational finance teams.
