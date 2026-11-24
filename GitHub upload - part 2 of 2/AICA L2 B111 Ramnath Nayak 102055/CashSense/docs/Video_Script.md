# CashSense - Zoom recording script (plain language, about 12 minutes)

How to use this script: each step says what to **DO** on screen and what to **SAY**. Read the "Say" lines in
your own natural voice - they are written to be spoken. Where you see **[read from screen]**, say the number
that is showing at that moment (numbers can change after each run, so do not memorise them).

ICAI needs **your face and the working app** in the video.

---

## Part 1 - Get ready (30 minutes before you record)

**Start everything**
1. Double-click `Start_CashSense.cmd` in the cashsense folder. Leave the three windows open (minimise them).
2. Wait for the dashboard to open and **sign in now**, before recording.
   - **Never open the `.env` file while recording** - it holds your passwords and keys.
3. On your phone: open Telegram > @cashsense_rn_bot > tap the newest "CashSense dashboard link" and sign in.

**Fresh approval cards for the demo** (optional, but makes the demo better)
4. Your earlier approvals are all done, so there is nothing left to tap. To get fresh cards, open PowerShell in
   the cashsense folder and run `python -m cashsense.cli phase3`.
   - This **resets the demo data** and proposes the 18 approvals again. Your earlier decisions are cleared from the
     app, but they are already saved in `database_snapshot\CashSense_Database_Snapshot.xlsx`.
   - It uses the free Gemini quota - after it finishes, **wait 10 minutes** before recording.

**Keep these ready**
5. Open these and keep them minimised:
   - n8n (http://localhost:5678), already signed in;
   - Gmail;
   - the Supabase table editor;
   - Claude desktop;
   - `docs\CashSense_Explainer.html`;
   - File Explorer at `cashsense\data\phase2\statements`.
6. Turn on phone screen mirroring on the laptop, or plan to hold the phone up to the camera.
7. Close everything else: email pop-ups, WhatsApp, other browser tabs. Silence the phone ringer.

**Practise once.** Do one full rehearsal without recording. It shows you where Gemini is slow.

**Start Zoom**
8. Start a meeting alone and turn the **camera on**.
9. Click **Share screen > Screen 1** (the whole desktop).
10. Click **Record > Record on this computer**.

---

## Part 2 - The script

### Step 1 - Introduction (0:00, about 1 minute)
**DO:** Camera on you, full screen. Then share the explainer page (`docs\CashSense_Explainer.html`).

**SAY:**
"Hello, I am [your name], a Chartered Accountant, from the AI for CA Level 2 batch.
My project is called **CashSense**. It is an AI assistant for a company's bank and treasury work.

Every month, accountants spend days on the same jobs:
- reading bank statements;
- matching them with the books;
- checking for wrong or fraudulent payments;
- working out how much cash the company will have in the coming weeks.

CashSense does this work with AI, and **a human, the CA, approves every entry before it touches the books**.

All the data you will see is **sample data** for an imaginary company, 'Sample Precision Components Private
Limited', a manufacturer in Pune with four bank accounts. Every tool I used is free."

### Step 2 - The big picture (1:00, about 1 minute)
**DO:** Scroll slowly through the flow diagram on the explainer page.

**SAY:**
"Here is how it works in one picture.
- **What goes in:** bank statements, as a bank file, a PDF, or even photos taken on a phone. The books come from
  the accounting system.
- **What happens in the middle:** CashSense reads each statement and checks every balance. Three AI agents then do
  the work: one **matches the bank with the books**, one **looks for risky payments**, and one **forecasts cash**
  for the next 13 weeks.
- **What comes out:** approvals on my phone, a dashboard, a daily email, and answers to my questions, even by voice.

One rule runs through the whole design: **AI does the work, Python checks the AI's work, and the CA decides.**"

### Step 3 - The sample company and the test answers (2:00, about 45 seconds)
**DO:** Open `data\phase1\Phase1_Review_SAMPLE.xlsx` (inside data.zip in the ICAI copy), then the bank
reconciliation sheet showing "Agreed".

**SAY:**
"I built the project in five phases, and each phase had its own test file.
- I created a full year of sample transactions: salaries, GST, TDS, customers and suppliers.
- Then I planted mistakes and frauds in March **on purpose**: a cheque not yet presented, an amount typed wrongly,
  a duplicate debit, a payment to an unknown person on a Sunday, and a vendor whose bank account was quietly changed.
- I kept a separate answer key, so I could prove that CashSense finds exactly these and nothing extra."

### Step 4 - Reading a photo of a bank statement (2:45, about 1 minute)
**DO:** On the phone (or web.telegram.org), open the bot chat. Tap the paper clip and send **both**
`CL01_2026-03_photo_page1.jpg` and `..._page2.jpg` together. Wait for the reply.

**SAY:**
"Now, **computer vision**. Many small businesses only have a printed statement. I am sending two phone photos of a
statement to my CashSense bot on Telegram.
- The AI, Google Gemini, reads the photo **twice**. If the two readings differ, it reads a third time.
- Then Python adds up every line and checks that each running balance and the closing balance are correct.
  If even one rupee does not agree, the statement is rejected.

…and here is the reply: **[read from screen]**."

*(If it says the month is already imported, say: "It refuses the same month twice - that is a safety check
against double entry.")*

### Step 5 - The daily run in n8n (3:45, about 45 seconds)
**DO:** Open n8n and show the three CashSense workflows. Open **"CashSense - Daily treasury run (08:00 IST)"** and click
**Execute workflow**.

**SAY:**
"This is **n8n**, a free workflow tool, running on my laptop. It has three workflows:
- one checks Telegram every 10 seconds for my replies;
- one picks up statements dropped into a folder;
- this one runs the **full daily check at 8 every morning**.

I'll run it now. It reconciles all four bank accounts, scans for risks, asks the AI to explain what it found, and
sends me approval requests."

### Step 6 - The offline browser agent catches a fraud (4:30, about 1 minute)
**DO:** Open `data\phase3\evidence` and show `verify_CA01-202603-0032.png` (the browser agent's check of the
Deccan Castings payment).

**SAY:**
"This is the part I like most. CashSense has an **offline browser agent**: a robot that opens a web browser,
types the vendor's bank account, clicks 'verify' and reads the name the bank holds for that account.

It checked every vendor we paid. Look at this one:
- The vendor is Deccan Castings.
- The bank says the account belongs to **DEEPAK TRADING COMPANY**.
- The bank details were changed just a few days before the payment, by a user called ops.user2.

This is the classic **payment diversion fraud**. A person checking hundreds of payments could easily miss it."

### Step 7 - Approvals on the phone (5:30, about 1 minute)
**DO:** Show the phone with the Telegram approval cards:
1. Tap **Approve** on a bank-charges entry.
2. Tap **Escalate** on the vendor-bank risk.
3. Show the card updating.

**SAY:**
"Here are the results on my phone.
- Simple exact matches are approved automatically and recorded.
- Everything else waits for me. Here, bank charges and the GST on them, which are not yet in the books. CashSense
  has prepared the journal entry. I tap **Approve**, and only then is it posted.
- For the suspicious vendor payment I tap **Escalate**.

This is **maker-checker**: the AI is the maker, I am the checker. Every tap is written to an audit log with the
time and who did it. **Nothing reaches the books without the CA's tap.**"

### Step 8 - Asking by voice (6:30, about 1 minute)
**DO:** In Telegram, hold the microphone button and ask: *"What happens to my cash credit if customers pay 15 days
late?"* Play the voice reply.

**SAY (before asking):**
"Now the **voice agent**. A finance head does not want to open reports, they want to just ask."

**SAY (after the reply):**
"It understood my voice, looked up the forecast, and answered in text and in voice, in **crore and lakh**, not
millions: **[read from screen]**.

It can only read data. It cannot approve or change anything, and Python checks that every amount in the answer
really exists in the data, so the AI cannot invent numbers."

### Step 9 - The dashboard on mobile (7:30, about 1 minute)
**DO:** On the phone (or the laptop browser at phone size), show the dashboard:
- the cash cards;
- tap the scenario buttons: base, 15 days late, largest customer does not pay, capex now;
- the chart with the 85% line;
- the bank reconciliation and risk list.

**SAY:**
"This is the dashboard, opened on my phone through a secure temporary link and protected by a password.
- Today's cash and cash-credit use: **[read from screen]**.
- This chart is the **13-week cash forecast**. When I tap '15 days late', you can see when the cash credit crosses
  the **85% warning line**. I see the problem weeks before it happens, not after.
- Below are the bank reconciliations for all four accounts and the open risks."

### Step 10 - Daily email from Google Apps Script (8:30, about 30 seconds)
**DO:** Open Gmail, then the CashSense briefing email. Briefly show the Google Sheet log.

**SAY:**
"Every morning a short briefing arrives by email, sent by a **Google Apps Script** that I wrote. It also:
- logs each day in a Google Sheet;
- reminds me at 6 pm if approvals are waiting;
- warns me if the daily run did not happen;
- sends a summary every Monday."

### Step 11 - Claude plugin, skills and MCP (9:00, about 45 seconds)
**DO:** In Claude desktop, type `/cashsense:treasury-briefing` and show the answer.

**SAY:**
"I also packaged CashSense as a **Claude plugin**. It has **skills**, which are the written instructions the AI
follows, ready-made **commands** like this treasury briefing, and an **MCP server**, which is the connector that
lets Claude read CashSense's data. It is read-only: approvals still happen only on my phone."

### Step 12 - Where the data lives (9:45, about 30 seconds)
**DO:** Show the Supabase table editor with the tables. If you built the Power BI report, show it; otherwise show
the `data\phase4\powerbi` folder.

**SAY:**
"The data is stored in **Supabase**, a free cloud database. Every table is locked so that only CashSense, with its
secret key on my laptop, can read it. For management reporting, CashSense exports the data for **Power BI**."

### Step 13 - Controls, money-making and close (10:15, about 1.5 minutes)
**DO:** Show the test results in `docs\BUILD_LOG.md` ("74 tests OK" and the issues-fixed list). End on camera,
full screen.

**SAY:**
"A few words on **controls**, because as CAs this matters most.
- After every AI step there is a Python check: balances must agree, amounts must exist, and the AI can never lower
  a risk or invent a number.
- Every change needs my approval, and everything is logged.
- No passwords or keys are in the code; they stay in a private settings file.
- 74 automated tests prove the results match the answer keys. For example, all 8 planted risks were found, with no
  false alarms.

On **monetisation**: a renamed commercial version can be sold as a monthly subscription per company to CA firms
and finance heads, priced per bank account, with a paid setup for connecting their accounting system.

This project used everything from the five days:
- agents and skills;
- connectors, plugins and MCP;
- schedulers and n8n workflows;
- computer vision, the offline browser agent and the voice agent;
- Google Apps Script and Python.

Thank you."

**DO:** Stop the recording.

---

## Part 3 - If something goes wrong during recording

| Problem | What to do and say |
|---|---|
| Gemini is slow or "busy" | Say: "The free AI tier is busy right now - this is why every AI step has a rule-based backup." Show the saved result in the Phase 2 or Phase 3 review workbook. |
| Telegram does not reply | Wait 20 seconds. If still nothing, show `data\phase3\Phase3_Review_SAMPLE.xlsx`, "Approvals" sheet. |
| Phone link does not open | Show the dashboard on the laptop: http://127.0.0.1:8765/dashboard |
| You stumble on words | Pause, then repeat the sentence. Small mistakes are fine; you can trim the start and end only. |

## Part 4 - After recording

1. Zoom saves an MP4 file when the meeting ends (usually in `Documents\Zoom`).
2. Watch it once. Make sure your face, the screen and the sound are all clear, and that no password or key appeared.
3. Upload it to Google Drive. Set sharing to the access the ICAI guide asks for, and copy the link.
4. Paste the GitHub link and the video link into the ICAI Google Form (see `docs\Submission_Checklist.md`).
