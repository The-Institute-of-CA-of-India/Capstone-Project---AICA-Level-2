# BG Tracker: 5-Minute Video Script

**Before you record**
1. Open the app and go to **Settings → Reset demo data** so every date is fresh relative to today.
2. Don't read numbers from this script. Read them off the screen, because they depend on the day you record.
3. Browser zoom around 90–100%, notifications off, desktop width.
4. If you need to re-record, click **Reset demo data** again. Running the daily check uses up the pending drafts.

Total speaking time is about 4:45. Pace is roughly 130 words per minute.

---

## 0:00 – 0:35 | The problem (Dashboard on screen, don't click yet)

"I'm a Chartered Accountant, and one task that quietly goes wrong in many offices is tracking bank guarantees. Two things happen. A guarantee lapses before it's renewed, which puts a contract at risk. Or the contract ends, but nobody follows up on getting the original back, so the bank keeps our client's margin or FDR blocked and keeps charging commission. Nothing 'expires' on the second one, so it's easy to miss. This is BG Tracker, a tool I built for my Level 2 AI training to fix that."

## 0:35 – 1:35 | Dashboard

"This is the dashboard. These cards show total exposure, the margin and FDR blocked with banks, guarantees expiring in the next 30 days, overdue releases, and commission falling due in 15 days. Hover over the info icon on a card to see exactly how it's calculated."

*(Point at "Needs attention".)*

"This table is the day's to-do list. Red means expired but the original hasn't come back. Amber means expiring soon. The top one is well past its expiry, and even the claim period is over, so that is the one to chase first."

*(Scroll to heat strip, then charts.)*

"This strip shows the next 90 days, one box per day, so I can see clusters of expiries at a glance. Below are exposure by bank, status mix, expiry timeline for the next twelve months and the split by guarantee type."

## 1:35 – 2:35 | BG Register

*(Click BG Register.)*

"Here is the full register. I can search by BG number, client or beneficiary, and filter by bank, type, status or expiry window."

*(Filter: Expiry ≤ 30 days, then clear it.)*

*(Click a row to open the drawer.)*

"Clicking a guarantee opens everything about it: amount, margin, FDR number, commission, the lifecycle timeline, any extensions, linked reminders and the audit trail. From here I can record an extension, mark the original as returned, request release, or mark it discharged."

*(Click Record extension, show the dialog, fill a new expiry, save.)*

"Recording an extension saves the amendment history, updates the expiry and the claim period, and writes to the audit log. There's also an Add BG form with validation: for example expiry must be after issue date, and the BG number must be unique."

## 2:35 – 4:10 | Reminders, the core of the tool

*(Click Reminders.)*

"This is the heart of the tool. The system works out what needs to be said, to whom and when, using five simple rules."

*(Click Run daily check.)*

"I click Run daily check, which simulates the job that would run every morning. It creates a batch of draft emails. The rules are: 60, 30, 15 and 7 days before expiry, it writes to my team and the client. On expiry day, it writes to the client. After expiry, if the original hasn't come back, it politely asks the beneficiary to return it or issue a release letter. Once the release letter is in, it drafts a formal request to the bank to cancel the guarantee, release the margin or FDR lien and confirm closure. And if the claim period is about to end with the original still outstanding, it escalates to my team."

*(Open one draft with View & edit.)*

"Each draft is a complete, professionally worded email with the guarantee details filled in. Nothing goes out automatically. I read it, edit it if needed, and then approve or dismiss."

*(Click Approve & send.)*

"In this demo, sending is simulated, and the app says so. In production the same approval would send a real email."

*(Click Dismiss on another, then show the Sent and Dismissed tabs.)*

## 4:10 – 4:35 | Audit Log

*(Click Audit Log.)*

"Every action lands in the audit log: the daily check, each approval, each dismissal and each extension. For a professional practice, that trail matters."

## 4:35 – 5:00 | Wrap-up

"To summarise: one dashboard for exposure and deadlines, a register with full history, and reminders that are drafted for me but approved by a human. It's built with Lovable and Supabase, with tests for the reminder rules. Next steps are running the daily check on a schedule with n8n, sending real emails, and reading BG documents with AI. Everything here uses fictional data, and any real use would need login and access controls. Thank you."

---

## Tips for a clean recording

- Rehearse once with Reset demo data between takes.
- If you want to show the AI angle, add one line: "The email drafting follows rule-based templates today; the roadmap adds LLM-based extraction of BG documents."
- Keep the cursor still while you talk, and move it only when you click.
- End on the Dashboard so the final frame is the strongest visual.
