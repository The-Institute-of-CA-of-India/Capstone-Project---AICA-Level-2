# Project overview

## User and need

Intended user: a Chartered Accountant or engagement team member tracking client documents. The problem is fragmented document requests, partial receipt and follow-up outcomes across multiple assignments.

## Workflow

Add/import client → create assignment → tailor requirements → record receipt → prepare reminder → confirm email submission → record contact outcome → plan next contact → review documents → export backup.

## Core rules

- Required Pending/Partially received items count as outstanding.
- An outstanding item becomes overdue only when its effective internal collection date is before today.
- A document-specific date overrides the assignment date.
- Received is separate from Reviewed. Optional and Not applicable items are excluded from required totals.
- A scheduled follow-up is due when its date is today/earlier and required documents remain outstanding.
- All dates are internal collection targets; no statutory deadline engine is implemented.

## Architecture and controls

Browser interface → asynchronous google.script.run → Google Apps Script → current user's Google Sheet and MailApp.

User properties hold the per-user database reference. A script lock serializes writes. Expected revisions reject stale updates. Save request IDs support safe retry after a lost response. A checksum detects accidental snapshot corruption. Readable tabs are generated views.

Email reservations are written before invoking MailApp. Same-ID retries return the recorded outcome instead of sending again. Identical content is blocked for ten minutes. Uncertain send outcomes remain Unknown/Sending; they are not silently retried.

## Evidence and limits

44 mocked checks passed. Actual Google authorization, deployment, independent account operation and mailbox receipt require the live acceptance rehearsal. No time-saving percentage or compliance guarantee is claimed. A practical pilot can measure preparation time per follow-up and missed-document frequency.
