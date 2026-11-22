# PracticeDesk — Client Document Pendency & Follow-up Manager

**Author:** Dipal, Chartered Accountant  
**Programme:** AICA Level 2  
**Edition:** Google Sheets + Apps Script, release 2.1  
**Project folder:** `Dipal-PracticeDesk`

## Problem and purpose

CA practices collect client documents in stages across engagements. Missing items, partial submissions and follow-up commitments can be difficult to track consistently. PracticeDesk provides an assignment-level register of requirements, receipt/review status, internal collection targets and client-contact outcomes.

## Features

- Client directory with validated CSV import, duplicate detection and an import preview.
- Audit, income tax, GST-review and bookkeeping starter checklists; custom assignments.
- Pending, Partially received, Received, Reviewed and Not applicable statuses.
- Required/optional flags, collection dates, received dates and supporting notes.
- Dashboard, search, filters, pending-document counts and overdue indicators.
- Editable reminder drafts and explicitly confirmed email submission through the authorized user's Google account.
- Persistent email-submission log, duplicate-send controls and an explicit Unknown outcome when confirmation is unavailable.
- Contact history, next-follow-up dates, CSV exports and JSON backup/restore.
- Separate fictional demo mode, with email sending and live database writes disabled.

## Faculty start — no code installation

Faculty user manual: **[FACULTY_USER_MANUAL.html](FACULTY_USER_MANUAL.html)** — includes startup, the assessment workflow, and remedies for known errors. Open it in a browser; Print / Save as PDF is available.

On Windows, double-click **START_WINDOWS.cmd** from the extracted folder. It requests a fresh temporary browser profile in private mode so your existing Google sessions are not reused. Sign in using one Google account. On other platforms, open **START.html** for the manual single-account launch method.

Hosted app:

https://script.google.com/macros/s/AKfycbxjD5ORkffzmQ92GhTaMXSDEktt-qFmWyF8YPw-yskHHLfIP6ncvc4FT0J_dYa1FD8G/exec

Sign in with your own Google account and review the requested Google permissions. After the owner deploys the included update, PracticeDesk automatically creates/reconnects your personal database and opens the dashboard. There is no faculty code installation, deployment, app password or API-key entry.

**One-time owner requirement:** apply the updated Index.html through **OWNER_UPDATE.html** and update the existing deployment to a new version. A local launcher cannot modify already deployed Google code. Keep the same /exec deployment URL.

The URL was supplied by the owner. Live authorization, actual deployed revision and email receipt could not be verified by the build environment. Google OAuth eligibility and account policies still apply.

For an independent source installation, use **SETUP.html** and deploy Code.gs, Index.html and appsscript.json as User accessing the web app.

## Independent accounts and permissions

The app runs as the accessing Google user. Per-user script properties identify that user's separately created Sheet. Server-side checks reject a mismatch between active and effective identities. The sender is the authorized account, not an arbitrary editable From address.

The manifest requests Google Sheets read/write access, mail sending and the account's email identity. The app does not request Gmail inbox-reading access. Google may show an unverified-app notice or restrict access according to its OAuth configuration and organizational policy. Resolve authorization eligibility before assessment; do not assume external-user access is already verified.

## Database and live refresh

The database is maintained in Google Sheets. `_Snapshots` contains versioned, checksum-verified committed state; `_Meta` holds ownership/view information. Clients, Assignments, Documents, Contacts and Activity are generated readable views. EmailLog records submission attempts.

Make record changes through the app. Direct edits to the readable views do not update authoritative snapshots. Do not edit/delete system tabs. Keep your Sheet private: manually granting Sheet access is outside the app's account-isolation controls.

Live refresh is **15-second polling while the app is open and idle**. It is not instant push synchronization, background scheduling or automatic client-receipt detection. Receipt and review statuses are entered by staff.

## Email status — exact meaning

| Status | Meaning |
| --- | --- |
| Sending | A submission was reserved; the final outcome has not yet been confirmed. |
| Sent (accepted) | Google's send call returned successfully. Inbox delivery and reading are not established. |
| Unknown | The outcome could not be confirmed. Check before making a new request. |

A persistent request ID prevents repeating the same request. An identical message with a new ID is blocked for ten minutes. The app never automatically retries email. It does **not** detect delivery, read receipts or incoming client replies.

## Demonstration

See [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md). All sample clients are fictional. [sample_data/clients_demo.csv](sample_data/clients_demo.csv) demonstrates import validation; expected results are in [sample_data/EXPECTED_RESULTS.md](sample_data/EXPECTED_RESULTS.md).

Do not send messages to sample addresses. Use Account → Test email to myself for an actual authorized test.

## Automated verification

Requirements for the test harness only: a current Node.js runtime supporting ES modules. The deployed app itself does not require Node.js or npm dependencies.

```sh
node tests/test.mjs
node tests/client-test.mjs
```

**44 simulated checks passed:** 32 server/schema/syntax checks and 12 asynchronous client/onboarding checks. Saved results are in TEST_RESULTS.json and CLIENT_TEST_RESULTS.json. Mocks simulate Google Sheets, identities, locks, properties, email and the document environment. Tests send no real email.

**Verification limit:** actual Google deployment, interactive browser operation and real email receipt were not verified by the build environment. Complete [docs/LIVE_ACCEPTANCE.md](docs/LIVE_ACCEPTANCE.md) before describing the integration as live-tested.

## AI contribution

AI assisted requirements analysis, implementation, debugging and test preparation. Tracking rules and reminder generation are deterministic. This release contains no live language-model API integration. Professional judgment remains necessary for checklist applicability, document review and communication.

## Limits

- Per-user prototype; not a shared-team production database.
- Internet, Google authorization, available quotas and external-user eligibility are required.
- Approximately 1 MB serialized workspace; up to 1,000 clients/assignments and 10,000 document/contact records.
- Snapshot history grows with saves; long-term production use needs archival design.
- Sheet records and activity logs are editable, not tamper-proof evidence.
- Checklist completion does not mean the audit, return or engagement itself is complete.
- Back up through JSON export. A conflict requires retaining local changes and reconciling with the newer saved revision.

## Files

| File/folder | Purpose |
| --- | --- |
| Code.gs | Server, identity checks, Sheets persistence and email submission |
| Index.html | Application interface |
| appsscript.json | Runtime, OAuth scopes and deployment identity |
| FACULTY_USER_MANUAL.html | Faculty start guide, workflow, status definitions and troubleshooting |
| START_WINDOWS.cmd | Windows launcher requesting an isolated private browser profile |
| START.html | Cross-platform instructions and direct app link |
| OWNER_UPDATE.html | One-time owner update with full Index.html copy button |
| SETUP.html | Independent source installation and acceptance instructions |
| tests/ | Reproducible simulated tests |
| sample_data/ | Fictional client-import examples |
| docs/ | Project overview, demo, live acceptance and development notes |
| SUBMISSION_GUIDE.md | Fork/PR workflow and repository-target discrepancy |
| PR_DESCRIPTION.md | Ready-to-use submission description |

## Author

Created by Dipal — Chartered Accountant, AICA Level 2 capstone project.

## Google access errors and launcher limits

A Google error before PracticeDesk loads cannot be repaired by the application code. The Windows launcher reduces account-session conflicts; it does not guarantee Google access or mail delivery. Managed browser policy can override profile settings or block private mode. Use organization-approved access and resolve deployment/OAuth issues with the owner. The launcher neither installs a browser nor alters normal profiles, signs users out, changes security policies or requests administrative rights. It leaves a temporary profile folder in Windows TEMP; no automatic recursive cleanup is performed.
