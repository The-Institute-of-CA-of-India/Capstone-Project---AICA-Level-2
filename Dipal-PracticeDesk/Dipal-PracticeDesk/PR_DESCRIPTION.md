# Pull Request title

Add AICA Level 2 Project - Dipal - PracticeDesk

# Pull Request body

## Project

PracticeDesk — Client Document Pendency & Follow-up Manager  
Author: Dipal, Chartered Accountant

A practical CA workflow tool for client/assignment checklists, partial document receipt, review status, internal collection targets and follow-up outcomes. The Google Edition uses Apps Script and a separately created Google Sheet for each authorized user.

Features include validated client CSV import, dashboard and overdue indicators, editable reminder drafts, explicitly confirmed email submission, persistent submission status, duplicate-send controls, contact history, next-follow-up dates and backup/exports.

## Start and assessment

- Project folder: `Dipal-PracticeDesk`
- Faculty start: `Dipal-PracticeDesk/START.html`; owner update: `OWNER_UPDATE.html`
- Deploy as the user accessing the web app. Assessors use their own Google account and create an independent database.
- Tests: `node tests/test.mjs` and `node tests/client-test.mjs`
- Evidence: 44 simulated checks passed; test results and limitations are included.
- Fictional client-import sample and expected results, project overview, demo script and live acceptance checklist are included.

## Verification boundary

Mocked tests do not establish real Google deployment, browser operation or mailbox delivery. An owner-supplied /exec launch URL is included. The auto-setup update still requires one-time owner deployment; live acceptance evidence has not been supplied. Google authorization and real self-test email receipt must be checked separately. Sent (accepted) is not a delivered/read status; reply detection and live AI model integration are not implemented.

AI assisted development; the runtime uses deterministic rules and reminder templates.
