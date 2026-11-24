# CashSense - user guide in plain language

CashSense runs on your laptop. Your phone talks to it through Telegram and a temporary web link.
**The laptop must be on, with CashSense started, for the phone to work.** All data is SAMPLE data.

---

## Part A - Start CashSense on the laptop

1. Open the folder `D:\Ramnath AI\Captone project\cashsense` in File Explorer.
2. Double-click **`Start_CashSense.cmd`**.
   - Three windows open (the app, n8n workflows, the phone link). **Leave all three open** - you can minimise them.
   - Wait about 1 minute. The dashboard then opens in your browser by itself.
   - If Windows asks "Do you want to allow this app?" for Python, Node or cloudflared, click **Allow**.
3. Sign in to the dashboard:
   - Open the file `.env` (in the same folder) with **Notepad**.
   - Find the line `DASHBOARD_PASSWORD=...` and copy what is after the `=`.
   - Paste it into the dashboard's password box and click **Sign in**.
4. You now see: cash balances, cash-credit use, the 13-week forecast chart, bank reconciliation status and risk flags.

**To stop CashSense:** close the three windows.
**Tip:** right-click `Start_CashSense.cmd` > **Send to > Desktop (create shortcut)** to start it from the desktop.

---

## Part B - Upload a bank statement (on the laptop)

You can give CashSense a statement in two ways. It accepts a bank **CSV** file, a **PDF** statement, or **photos**
of a printed statement.

### Way 1 - the drop folder (easiest on the laptop)
1. Open `cashsense\data\inbox\drop`.
2. Copy the statement file into it.
   - For a photographed statement with several pages, put all page photos in **one new folder** and copy that
     folder into `drop`.
3. Wait about 30 seconds. CashSense reads it, checks every balance, categorises every line and reconciles it.
4. A Telegram message tells you the result, and the file moves to `drop\processed` (or `drop\failed` with the reason).

### Way 2 - Telegram on the laptop
1. Open **web.telegram.org** (or the Telegram app) and open the chat with **@cashsense_rn_bot**.
2. Click the **paper clip**, choose the file (or select all photos of the statement together) and send.
3. The bot replies "Received... reading and checking" and then gives the result.

### Sample files to try
These sample statements are ready in `cashsense\data\phase2\statements`. Each month of each account can be
uploaded **once**; uploading the same month again is refused as a duplicate (a safety check):
- `CA01_2025-10_bank_export.csv` or `CA01_2026-03_bank_export.csv` - bank CSV
- `CC01_2025-10.pdf` or `CC01_2026-03.pdf` - bank PDF
- `CL01_2026-03_photo_page1.jpg` and `..._page2.jpg` - phone photos of one statement (send both together, or put
  both in one folder for the drop folder)
- `EF01_2026-03.pdf` - USD (EEFC) statement. (`EF01_2025-10.pdf` was used to test this guide, so it will now be
  refused as a duplicate - that shows the safety check.)

**Note:** CashSense only accepts statements for the sample company's four bank accounts. A real bank statement
is refused because its account number is not set up - this is a safety check, not an error.

### Other data
The books (ledgers, customers, suppliers, bills, commitments) come from the company's accounting system and are
already loaded. You do not upload them by hand.

---

## Part C - Run the daily check whenever you want

CashSense runs the full daily check automatically at **8:00 am** (if the laptop is on). To run it now:
1. Open **http://localhost:5678** in the browser and sign in to n8n with the account you created.
2. Open the workflow **"CashSense - Daily treasury run"** and click **Execute workflow**.
3. Within about a minute Telegram receives the summary, the approval cards and any urgent alert, and the
   briefing email arrives in Gmail.

---

## Part D - Use CashSense on your mobile

### 1. Telegram - approvals, questions and voice
Open Telegram on the phone and the chat with **@cashsense_rn_bot**.
- **Approve or reject:** each approval card has buttons - **Approve / Reject** for accounting entries,
  **Reviewed / Escalate** for risks. The card updates within about 10 seconds. Nothing is posted to the books
  without your tap.
- **Ask a question by typing:** for example "What is my cash credit utilisation today?"
- **Ask by voice:** hold the **microphone** button and speak, e.g. "What happens if customers pay 15 days late?"
  You get the answer as text and as a voice message (amounts in crore and lakh).
- **Send a statement:** paper clip > Gallery > select all pages > send.
- **Shortcuts:** `/status` (summary), `/risks` (risk flags), `/pending` (resend waiting approvals), `/help`.

### 2. Dashboard on the phone
1. When CashSense starts, a message **"CashSense dashboard link"** arrives in Telegram. Tap the link.
2. Sign in with the same dashboard password (type it once; the phone may offer to remember it).
3. Use it like the laptop dashboard - tap the scenario buttons to change the forecast, tap the **microphone** to ask
   a question aloud, and listen to the answer.
4. Optional: in Chrome, tap **⋮ > Add to Home screen** for an app-like icon.
   - The link **changes every time CashSense is started** - always use the newest link from Telegram.

### 3. Email
The daily briefing arrives in your Gmail each morning, with reminders at 6 pm if approvals or high risks are
waiting, and a summary every Monday.

---

## If something does not work

| Problem | What to do |
|---|---|
| The bot does not reply | Check the three CashSense windows are still open; if not, double-click `Start_CashSense.cmd` again |
| Dashboard link does not open on the phone | Use the newest link in Telegram (it changes on every start); the laptop must be on |
| "Gemini busy" or the assistant is slow | The free AI quota is busy - wait a minute and try again |
| A statement is refused | Read the reason in the reply: duplicate month, unknown account number, or balances that do not agree |
| Forgot the dashboard password | Open `.env` with Notepad and copy `DASHBOARD_PASSWORD` |
| "n8n was not found" | Install n8n once into the `n8n-runtime` folder next to the project: open Windows PowerShell and run the command the n8n window prints (it uses `npm.cmd ... --prefix "...\n8n-runtime"`; use `npm.cmd`, not `npm` - Windows blocks the `npm` script by default). Wait 5-10 minutes, then start CashSense again |
