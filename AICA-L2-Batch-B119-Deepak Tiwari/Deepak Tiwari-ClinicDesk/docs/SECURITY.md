# Security notes

## Who can do what (enforced in `firestore.rules` / `storage.rules`)

| | Owner | Doctor | Front desk | Pending / none | Anyone (no sign-in) |
|---|---|---|---|---|---|
| Read patients, visits, appointments, prices | ✔ | ✔ | ✔ | ✘ | ✘ |
| Create / edit patients, visits, appointments, payments | ✔ | ✔ | ✔ | ✘ | ✘ |
| Write prescriptions | ✔ | ✔ | ✘ | ✘ | ✘ |
| Void / restore an invoice, edit a void invoice | ✔ | ✘ | ✘ | ✘ | ✘ |
| Change prices, settings, logo | ✔ | ✘ | ✘ | ✘ | ✘ |
| Manage users and invitations, read audit log | ✔ | ✘ | ✘ | ✘ | ✘ |
| Delete documents | ✔ | ✔ | ✘ | ✘ | ✘ |
| Open **one** invoice if they hold its 40-character link | | | | | ✔ (read-only snapshot) |
| Delete patients / visits | ✘ — not possible from the app for anyone |

The UI hides buttons a role cannot use, but the rules are the real protection.

## How access is granted
1. **First owner.** `meta/init`, the first `users` document (role `owner`) and `settings/clinic` are created in
   one atomic batch, allowed only while `meta/init` does not exist. Sign in yourself right after deploying.
2. **Invited users.** A user may create their own profile with the invited role only if `invites/<verified email
   or phone>` exists with that role. Email sign-ups must verify their email first (the app and rules both
   require `email_verified`).
3. **Everyone else** can only create a `pending` / `none` profile (a request) and see nothing else.
4. Users cannot change their own role or status. The owner cannot change their own role/status either, so the
   clinic cannot lock itself out by mistake.

## Public invoice links
`publicInvoices/{key}`: `get` is public, `list` is denied. The key is 40 random hex characters (160 bits), so it
cannot be guessed or enumerated. The document is a snapshot containing only invoice content. Treat the link like
a receipt: anyone who receives it can read that invoice. Rotating a key means voiding/re-issuing the invoice.

## Things the rules cannot do (be aware)
- Totals are computed in the browser; the rules cannot recompute them (see README, Known limits).
- Front-desk users can read clinical notes (same as the original).
- Counters only guarantee monotonic +1 steps; a staff member could burn numbers.

## Operational advice
- Keep the number of owners small; use Doctor/Front desk for staff. Remove people under **Team → Switch off**.
- Use the idle sign-out on shared devices (Settings → Features and security).
- Enable Firestore backups, and billing alerts if you use the Blaze plan.
- Consider enabling **Firebase App Check** (reCAPTCHA) to reduce abuse of your project's API key.
- Do not put service-account keys or admin credentials anywhere in this project.
