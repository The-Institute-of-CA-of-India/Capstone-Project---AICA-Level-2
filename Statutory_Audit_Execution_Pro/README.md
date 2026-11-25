# Statutory Audit Execution Pro — Khare Deshmukh & Co., Chartered Accountants
Audit execution software for business entities (Company, LLP, Partnership Firm, Proprietorship, HUF, Trust / Society).

## What is new in v4
- **Exit company** button (left menu). It asks whether to save before leaving. Moving to another module, the dashboard, or signing out also asks to **Save and continue / Don't save / Stay here**, and saving really writes the work to the server. A **Save work** bar (and Ctrl+S) is shown inside each module.
- **Working papers are numbered 1, 2, 3 ...** in the order shown in the left menu (the old 3.1, 4.2 style codes are no longer shown). Bulk evidence upload now uses this number: start a file name with `8 ` or `WP8 `.
- **Applicable / Not applicable** is asked for every module. Applicable opens it for data entry. Not applicable needs a reason and the module counts as completed. The choice can be reversed at any time (the Partner must send a compiled/reviewed module back first).
- **Dates are editable**: "Work carried out on" for each audit step, the compilation date, and the review date. They default to today.
- Always-visible scrollbars in the module list and the work area, a module search box, collapsible groups, and Previous / Next module buttons.
- Product renamed **Statutory Audit Execution Pro**; refreshed visual styling.


## Install on the office server (Windows)
1. Install Python 3.10 or later (tick "Add Python to PATH").
2. Copy this folder to the server, e.g. `D:\AuditExec`.
3. Double-click `START_SERVER.bat`. It prints two addresses. Staff open the second one (e.g. `http://192.168.1.20:8765`) in Chrome / Edge.
4. Allow port 8765 in Windows Firewall (Inbound rule, TCP 8765). Give the server a fixed IP or a name in your router.
5. To run automatically at start-up: Task Scheduler → Create Task → "At startup" → run `START_SERVER.bat`.
Change the port with the environment variable `AUDITEXEC_PORT`. For access from outside the office use a VPN or an HTTPS reverse proxy; do not expose the port directly to the internet.

## First sign-in
Partner login is `vivek`. You are asked to set your own password at first sign-in. (The initial password was given to you separately and is not shown anywhere in the software.)
Partner → account menu → *Manage users & roles*: create logins, set roles (Partner / Sr Staff / Jr Staff), reset passwords, rename, disable. Only a Partner can do this. Users must change an issued password at first sign-in. After 5 wrong attempts a login is locked for 5 minutes.
If the Partner forgets the password: on the server computer only, double-click `RESET_PARTNER_PASSWORD.bat`. It cannot be used from the web interface.

## Work flow
1. Partner / Sr Staff create the engagement and assign modules to staff (with due dates).
2. Staff complete the four tabs of each module: Audit steps, Evidence, Queries, Conclusion (review-note tab clears automatically when no notes are open).
3. Staff press **Mark module as Compiled** → recorded as "Compiled by <name>", module locks.
4. The Partner opens each module (Review queue on the dashboard), examines the work, may add **review notes** or **send back**; when satisfied presses **Review Complete** → recorded as "Reviewed by <name>".
5. Dashboard → *Reports & tools*: Word working papers, print/PDF version, Partner summary, audit observations list, query tracker.

## Other features
Activity log per engagement · bulk evidence upload by file name · roll over to next year (prior-year conclusions shown, open queries carried forward) · daily automatic backup (last 14 kept) with download & restore · draft SA 705 / SA 706 paragraphs from the adverse register · stale-evidence flag (file dated before the audit year).

## Data
`runtime\` holds the database, evidence and backups. Copy the `runtime\backups` folder to another drive or cloud regularly.
This software is a documentation aid. Judgement on materiality, risk, accounting treatment and sufficiency of evidence stays with the engagement team and the Partner.
