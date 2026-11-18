# AI-assisted development notes

AI assisted requirements refinement, application generation, code changes and simulated tests in the project conversation.

The following are reconstructed explanatory prompt examples, not a verbatim training or development transcript:

1. Build a practical client document pendency manager for a CA practice, with assignment checklists, partial receipt, internal collection dates and reminder drafts.
2. Add validated bulk client CSV import, contact history and next-follow-up dates, keeping demo data separate.
3. Use Google Sheets for persistence and authorize each Google account independently; submit email only after recipient/content review.
4. Protect against stale saves, repeated email requests, connection failures and unknown send outcomes.

## Debugging lessons

- Apps Script rejected nullish assignment syntax in Code.gs; explicit null/undefined checks replaced it, with a server source guard added.
- Onboarding required an explicit project-brief helper declaration and direct Account recovery controls for connecting/creating the database.
- Mock-based checks do not establish real browser or Google authorization compatibility. A separate live acceptance checklist is required.

No live AI model, reply detector, document-content analysis or automatic audit conclusion is claimed.
