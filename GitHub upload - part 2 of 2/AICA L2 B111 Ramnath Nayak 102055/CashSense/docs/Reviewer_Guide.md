# CashSense - running it on your own computer (for reviewers)

You do not need to run anything to review CashSense. The explainer (`docs/CashSense_Explainer.html`), the video, the
review workbooks in `data.zip` and `database_snapshot/CashSense_Database_Snapshot.xlsx` show every result.
If you want to run it yourself, this takes about 10 minutes. All data is fictitious SAMPLE data.

## What you need

| Item | Needed? | What it is for |
|---|---|---|
| Windows 10 or 11 | Yes | The start files are Windows files |
| Python 3.11 or newer ([python.org](https://www.python.org/downloads/)) - tick **"Add python.exe to PATH"** | Yes | The app, the agents and the dashboard |
| Microsoft Edge | Already on Windows | Offline browser agent (beneficiary checks) |
| Gemini API key (free, Google AI Studio) | Optional | AI reading of photo statements, AI explanations, the Ask box and voice |
| Telegram bot (free, BotFather) | Optional | Approvals and alerts on the phone |
| Node.js 20+ and n8n (free) | Optional | Scheduled daily run, Telegram polling, drop folder |
| cloudflared (free) | Optional | Temporary link to open the dashboard on a phone |

Node.js, n8n and cloudflared are separate programs and cannot be included in the GitHub upload. CashSense starts
without them and says which optional parts were skipped.

## Steps

1. Download the folder from GitHub (Code > Download ZIP) and unzip it, for example to `D:\CashSense`.
2. Double-click **`Setup_For_Reviewers.cmd`** (once). It installs the Python packages, unpacks the sample data,
   creates the settings file `.env`, builds a local database and runs the reconciliation and risk checks. No
   account or key is needed; it ends with "Setup complete".
3. Double-click **`Start_CashSense.cmd`**. The dashboard opens at http://127.0.0.1:8765/dashboard.
4. Sign in with the password shown after `DASHBOARD_PASSWORD=` in the `.env` file (right-click `.env` >
   Open with > Notepad). The password is created on your computer during setup; none is shared in the upload.
5. To stop CashSense, close the windows that opened.

## What works without any key

- Dashboard: cash position, 13-week forecast with scenarios and the 85% alert, bank reconciliation (BRS) for all
  four accounts, risk flags (changed vendor bank details, Sunday payment to an unknown payee, split payments,
  duplicate debit, MSME bills beyond 45 days and others), with the browser agent's verification where Edge allows.
- Reading CSV and PDF statements, rule-based categorisation, reconciliation, risk checks, forecast, Power BI export
  (`python -m cashsense.cli phase4 --no-ai`) and the automated tests (`python -m unittest discover -s tests -t .`).

## Optional: switch on the AI and Telegram

Open `.env` with Notepad and paste after the `=`:
- `GEMINI_API_KEY=` your free key from https://aistudio.google.com/apikey, then run
  `python -m cashsense.cli gemini-check`.
- `TELEGRAM_BOT_TOKEN=` a token from @BotFather, then run `python -m cashsense.cli telegram-check --wait` and send
  your bot any message to link your chat.

## Optional: n8n (scheduled workflows)

Install Node.js 20 LTS from https://nodejs.org, then in PowerShell (replace the folder with the one *next to* your
CashSense folder, for example `D:\n8n-runtime` when CashSense is in `D:\CashSense`):

```powershell
npm.cmd install -g n8n --prefix "D:\n8n-runtime"
```

Use `npm.cmd` (Windows may block plain `npm` in PowerShell). Then run `python scripts\setup_n8n.py` once (creates
the CashSense workflows; n8n asks for an owner account at http://localhost:5678 the first time). After that,
`Start_CashSense.cmd` starts n8n too.

## If something goes wrong

| Message | What to do |
|---|---|
| "Python was not found" | Install Python and tick "Add python.exe to PATH", then run the setup again |
| "CashSense is not set up on this computer yet" | Run `Setup_For_Reviewers.cmd` first |
| "n8n is not installed - skipped" | Nothing - n8n is optional (see above) |
| Port 8765 already in use | Another program uses it; close it, or run `set CASHSENSE_PORT=8770` in a Command Prompt and start `Start_CashSense.cmd` from that window |
| Dashboard page does not open | Wait 10 seconds and refresh; check the "CashSense 1 - app" window for errors |
