# AI usage and project lifecycle

**Student:** Deepak Tiwari  **Course:** AICA Level 2  **Project:** Clinic Manager (Kenya and India)

This file explains which AI tools were used, what each one did, and what I did myself.

## Tools and their roles

| Tool | Role in this project |
|---|---|
| **Claude** | Development partner. From my written requirements it proposed the design, wrote the application code (React + TypeScript), the Firebase security rules, the automated tests and the documentation, and fixed type and build errors. |
| **Firebase** | Backend: Authentication (Google, email/password), Firestore database, security rules. Storage is not enabled because it needs a paid plan. I created and configured my own Firebase project. |
| **Google AI Studio** | I imported the finished project, supplied my Firebase settings, previewed it and published it. I told it not to rewrite the project. |

## Lifecycle

1. **Plan:** I wrote the requirements (features, roles, Kenya and India support, privacy, installable on phones and tablets).
2. **Design:** architecture and data model (see `docs/DATA_MODEL.md`, `docs/SECURITY.md`).
3. **Build:** code, 31 automated tests (`npm test`), type-check and production build (`npm run build`).
4. **Configure:** Firebase project, sign-in methods, Firestore database, published security rules.
5. **Publish:** imported to AI Studio, set environment variables, published, added the published address to Firebase authorised domains.
6. **Test:** end-to-end test of the live app: sign in, create a patient, record a visit and payment, view the invoice, send via WhatsApp, receipt, void.

## What I did myself
- Wrote and refined the requirements and checked the AI output against them.
- Created and configured the Firebase project and published the security rules.
- Imported and published the app in AI Studio and authorised the domain.
- Tested the live app and found issues (see below).

## Findings and limitations
- The **Email** buttons open the user's email program with a ready message; they do not send automatically, because the app has no server.
- **Logo and document upload** are off because Firebase Storage needs a paid plan.
- Invoice totals are calculated in the browser; this is not an e-invoicing system.
- Tax and regulatory defaults are starting points only, not legal or tax advice.

## Security
No Firebase keys, project IDs or patient data are in this repository. Configuration is supplied through environment variables (`.env.example`) or a git-ignored file. See `README.md` for set-up.
