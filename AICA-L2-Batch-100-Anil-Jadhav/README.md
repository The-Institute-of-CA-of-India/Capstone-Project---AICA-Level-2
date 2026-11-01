# CA Firm DSC Management Tool

> **AICA Level 2 Capstone Project** - Anil Jadhav, Batch 100. No real client data is included. Load the clearly marked sample data on first launch to try the app.

A Windows desktop app for tracking clients' Digital Signature Certificate (DSC) tokens: what the firm
receives (inward), who inside or outside the firm holds each token right now (custodian, staff or
consultant), what it returns (outward), which DSCs it is still waiting for, and when certificates
expire, to the minute.

It is built with Python, Tkinter and SQLite, exports its reports to Excel, and runs offline. Only
WhatsApp messages and the partners' Google Sheet need an internet connection.

> **Single user:** this application is for use on one PC by one user at a time. Keep the database on that
> PC, not in a folder that several PCs share. A second copy of the app trying to open the same database is
> refused.

## How to run

1. Install **Python 3.10 or newer** from python.org. During setup, tick "Add python.exe to PATH".
   Tkinter and SQLite come with Python.
2. Install two optional libraries: one reads DSC tokens, the other reads and writes Excel files for
   importing clients.

   ```
   pip install PyKCS11 openpyxl
   ```

   The rest of the app works without them. Without PyKCS11, **Read from Token** is unavailable; without
   openpyxl, the Excel template and import are unavailable.
3. Double-click **`Start DSC Manager.bat`** (or `run_dsc_manager.pyw`).
4. **First launch:**
   - Choose where to keep the database (the default is `data\dsc_manager.db` in this folder).
   - Choose whether to load sample data. Sample names end with "(Sample)"; remove them from
     **Backup Database → Remove Sample Data** before real work.
   - If no custodian is appointed, the app asks you to appoint one. Every DSC received goes to the
     custodian automatically, so inward entries are blocked until a custodian is appointed.

## Reading details from a DSC token

Click **Read from Token** on DSC Inward, Certificate Details or Record Renewal with the token
plugged in. The app fills in:

- token serial number
- holder name
- certificate serial number
- issue and expiry date **and time**
- certifying authority

If the token is already registered, its client is selected. Otherwise a client whose holder name
matches is selected, or you pick one.

**The app compares the token with its records** and says which of these it is:

| Message | Meaning | What happens on Save |
|---|---|---|
| **KNOWN TOKEN, SAME CERTIFICATE** | The same token and certificate as on record | Normal inward entry |
| **KNOWN TOKEN with a RENEWED CERTIFICATE** | The same token now carries a newer certificate | Saved as a renewal; the old certificate stays in Certificate History |
| **NEW TOKEN** | This token serial has never been recorded | If the client already has active tokens, the app lists them and asks which one the new token replaces (expired or soon-expiring ones are ticked). Each ticked token is made Inactive ("Replaced by new token …"). |
| **Token marked INACTIVE** | For example, it was reported lost earlier | The app asks whether to make it Active again before recording the receipt |

- **Any brand:** the app finds the drivers of the common Indian DSC tokens in the Windows system folder
  (ePass2003/HYP2003, ProxKey, mToken, Trust Key, Watchdata, SafeNet, Gemalto and others) and tries
  each one.
- **Other drivers:** if a brand isn't detected, add its driver DLL under **Settings → Token Drivers &
  Text Size**. That box also has a **Test: Read Tokens Now** button.
- **Several tokens:** with more than one token plugged in, you pick from a list.
- **Fallback:** if no driver works, the app reads the Windows certificate store instead. That way the
  token serial number can't be read and must be typed in.
- **Privacy:** no PIN is asked for or stored. Only the public certificate details are read.

## Custodian, staff and consultants

| Movement | From → To | Recorded |
|---|---|---|
| Inward | Client → Custodian (automatic) | Inward date as entered, plus system time of entry |
| Issue to staff | Custodian → Staff | System date and time, purpose, expected return (default: end of that day) |
| Return from staff | Staff → Custodian | System date and time |
| Hand to consultant | Custodian → Consultant (e.g. a CS) | System date and time, purpose, expected return |
| Return from consultant | Consultant → Custodian | System date and time |
| Client collected from consultant | Consultant → Client | System date and time, collected by, note. Ends the firm's custody |
| Outward | Custodian → Client | Outward date as entered |

- **Through the custodian only:** no staff-to-staff transfers. Staff and consultants return tokens
  only to the custodian, and only the custodian returns a token to the client.
- **Overdue:** a token not back by its expected return shows as overdue on the dashboard.
- **Movement times:** stamped from the system clock and can't be edited. A wrong movement is
  cancelled with a reason; only the latest movement of a token can be cancelled.
- **One custodian at a time:** appointing a new custodian (**Settings → Custodian, Staff & Consultants**) relieves
  the previous one. All tokens held by the custodian are handed over automatically, recorded in the
  Movement Register. Tokens out with staff or consultants come back to the new custodian.

## Where the data is stored

- **Database:** a single SQLite file, `dsc_manager.db`. Its path is shown in the status bar and on the
  Backup Database screen.
- **Settings:** the database location and any extra token driver paths are saved in
  `dsc_config.json` next to the app.
- **Moving the database:** use **Backup Database → Change Database Location**.
- **Upgrades:** a database from the earlier version is upgraded automatically the first time it is
  opened. No records are lost.

## Backing up

- **Backup Now:** go to **Backup Database → Backup Now…** and pick a folder. The app writes a dated
  copy, e.g. `DSC_Backup_2026-10-26_153012.db`.
- **Automatic daily backup:** on the Backup Database screen, tick **Automatic daily backup** and choose
  a folder, ideally a USB drive or a Google Drive / OneDrive folder.
  - The app saves `DSC_AutoBackup_<date>.db` once a day, when it is opened, and again if it stays open
    past midnight.
  - The last 30 daily files are kept.
  - If the folder isn't available (for example, the USB drive is unplugged), a red message says so.
- **Reminder:** if there has been no backup for 7 days, it is listed in the message shown when the app
  opens.
- **Restore from Backup:** on the Backup Database screen, click **Restore from Backup…** and pick a
  backup file (manual or automatic).
  - The app first checks the file is a DSC Manager backup.
  - It shows what the backup holds next to the current data (clients, tokens, inward and outward
    entries, latest dates) and asks before going ahead.
  - All the current data is replaced by the backup's. Entries made after the backup was saved no longer
    show.
  - First, the current data is saved as `DSC_BeforeRestore_<date-time>.db` in the database folder. To
    undo a restore, restore that file.
  - A backup made by an older version of the app is brought up to date as it is opened.

## When the app opens

A short **"Needs attention today"** window lists anything that needs action, each with an **Open**
button:
- certificates expired or expiring within 7 days
- tokens overdue back from staff or consultants
- tokens overdue for return to clients
- awaited DSCs past their date
- no recent backup

If nothing needs attention, a brief "All clear" message appears instead. The dashboard refreshes itself
every 5 minutes while it is open.

## WhatsApp messages to clients

DSC Inward, DSC Outward and **Client Collected from CS** each have a **Send WhatsApp message to the
client** box, ticked by default. After saving, the app opens the client's WhatsApp chat with the
message already typed in. You check it and press **Send**; nothing is sent automatically.

- **WhatsApp Desktop app (recommended):** used automatically when it is installed. Every message opens
  in the app that is already running: no browser tab, no prompt.
- **WhatsApp Web:** used when the Desktop app isn't installed, or when chosen under Settings → "Open
  messages in". The message opens straight in the chat, but the browser opens a new tab for each one.
  WhatsApp Web may ask "Use here" in the newest tab; close older WhatsApp tabs to avoid this. Expiry Alerts has a **WhatsApp Reminder to Client** button.

The wording of the four messages (received, returned, collected from consultant, expiry reminder) is
edited on the **Settings** screen. It can use these blanks: {name}, {token}, {date}, {purpose},
{returned_to}, {consultant} and {expiry}.

## Google Sheet for the partners

The app is installed on the custodian's PC. So that the partners can check the reports from their own
desks, it can send every report to a Google Sheet:

- **Tabs:** Dashboard, DSC in Custody, DSC Awaited, Expiry Alerts, Inward Register, Outward Register,
  Movement Register, Holdings by Person and Clients. Each report tab has the time of
  the update, filters on the heading row and the same row colours as the app. Dates are real dates,
  so they sort and filter properly.
- **Dashboard tab:** the counts (in custody; with the custodian, staff and consultants; overdue; awaited;
  expired and expiring in 7/15/30 days), a chart of who holds the tokens, the tokens now out with
  staff and consultants, and the certificates expiring in the next 30 days.
- **When:** about a minute after each entry (several entries in a row give one update), when the app
  starts, at the start of a new day and, for entries of the last minute, when the app is closed. With
  no internet it says so once and tries again every few minutes. **Update Google Sheet Now** sends at
  once.
- **Privacy:** PAN and mobile numbers are masked (ABCPX\*\*\*\*F, 98XXXXXX10). Share the sheet with the
  partners as **Viewer**.
- **One-way:** the sheet is only a view. Changes made in it are replaced at the next update and never
  come back to the app.

**Setting it up (once per firm), under Settings → Google Sheet for Partners:**

1. Sign in to the firm's Google account and create a blank Google Sheet (**Open Google Sheets**).
2. In the sheet: **Extensions → Apps Script**. Delete what is there, paste the script (**Copy Script**)
   and click Save.
3. **Deploy → New deployment → Web app.** Execute as: *Me*; Who has access: *Anyone*. Click Deploy and
   allow access. Google may warn "unverified app": click Advanced → Go to … (unsafe). It is the firm's
   own script.
4. Copy the **Web app URL**, paste it in the app and click **Save & Test**.
5. Share the sheet with the partners as Viewer.

The script holds a secret key, made by the app for each firm's database, and refuses updates without it.
The link and the key are kept in the firm's database. If the script is ever pasted again, deploy it
with **Deploy → Manage deployments → Edit → New version**, so the link stays the same. The script is in
`dsc_manager/assets/google_sheet_script.gs`.

## Ease of use

- **Search box at the top of every screen (Ctrl+F):** type a client name, PAN, mobile or token number.
  Choosing a client opens its Client Details; choosing a token opens its Token History.
- **Dashboard:**
  - Quick-action buttons: **+ New Inward**, **Read Token**, **Return a DSC**, **Issue to Staff**.
  - A **Today** strip shows today's receipts and returns, tokens due back today, certificates expiring
    today and awaited DSCs due today. Click any item to open it.
- **Menu counts:** the left menu shows *DSC in Custody (17 · 2 late)* (2 tokens overdue back to the
  custodian) and *Expiry Alerts (6)*.
- **DSC Inward:**
  - Starts with a large **Read from Token** button.
  - **Save & Add Another** keeps the client, date and purpose for the next token of the same client.
- **Undo:** the message after saving an inward, outward or movement has an **Undo** button for about
  10 seconds. The entry is then cancelled; it stays in its register marked "Cancelled".
- **Sample data:** a yellow strip warns while sample data is loaded.
- **Tables:**
  - Hover over a cut-off cell to see its full text.
  - Rows are lightly striped.
  - Column widths you set are remembered on this PC.
- **App icon, colours and Help:**
  - The app has its own icon on the window, taskbar and .exe.
  - Colours are calm: navy, one blue accent, and red or amber only where something needs attention.
  - The **Help** screen is a one-page staff guide.

- **Success messages** appear for a few seconds at the bottom right and close by themselves. Warnings
  and questions still need a click.
- **Keyboard:**
  - **Enter** moves to the next field in forms.
  - **Ctrl+S** saves the open form or window.
  - **F5** refreshes the screen.
- **Dates** can be typed without dashes: `29102026`, `291026` and `29-10-26` all mean 29-10-2026.
- **Right-click** any row for its actions (Token History, Certificate History, Return, Issue, WhatsApp
  reminder and so on). **Double-click** a token row to open its Token History, or a client to open the
  **Client Details** view (details, tokens, full history and awaited DSCs).
- **Empty lists** say why they are empty instead of showing a blank table.
- **Small screens:** a screen too tall for the window shows a scrollbar on the right (the mouse wheel
  works too), so nothing is cut off.
- **Text size:** Settings → Text Size → **Large** for bigger text. It takes effect the next time the app
  starts.

## Screens

| Menu | What it does |
|---|---|
| Dashboard | Cards for inward/outward in a chosen period, live custody, DSC awaited, tokens with the custodian / staff / consultants, overdue returns to the custodian, and expiry alerts. Click a card to open the matching list. |
| Clients | Client master. Mobile number is required; PAN is optional (filter "PAN pending"). A client with transactions can only be marked Inactive. The client's token list has Mark Token Inactive, Mark Token Active and Token History. **Download Excel Template** and **Import from Excel** add clients in bulk (see below). |
| DSC Inward | Record a token received (it goes to the custodian). Read from Token fills the details. |
| DSC Outward | The custodian returns a token to the client. Only tokens with the custodian are listed. |
| DSC in Custody | Every token the firm holds and who has it now (custodian, staff or consultant), with filters and Excel export. Select a token and use the buttons (or right-click) to issue to staff, return from staff, hand to consultant, return from consultant, record that the client collected it directly from the consultant, return it to the client, mark it lost/inactive, cancel the last movement or see its history. Second tab: DSC awaited from clients. |
| Reports | Inward, Outward and Movement registers, Holdings by Person, DSC Awaited. Search by DSC holder or client name. Filters reset each time you come back to a screen. All exportable to Excel. |
| Expiry Alerts | 7, 15 and 30-day, expires today, expired, unknown and renewal lists, checked to the minute. Update a certificate, record a renewal, view certificate history. |
| Backup Database | Backup now, automatic daily backup, restore, database location, sample data. |
| Settings | **Custodian, Staff & Consultants:** appoint the custodian (with history), keep the staff list, add, edit and deactivate consultants. Also WhatsApp message wording, the partners' Google Sheet, text size and DSC token drivers. |

## Importing clients from Excel

1. On the Clients screen, click **Download Excel Template**.
2. Fill in the **Clients** sheet, one DSC holder per row. The **Instructions** sheet explains each
   column and shows examples. The columns are DSC Holder Name\*, Mobile Number\*, Firm/Company Name,
   PAN, Email and Remarks.
3. Click **Import from Excel** and choose the file. Only this template is accepted.
4. A preview shows every row before anything is saved:

| Row | Result |
|---|---|
| DSC Holder Name or Mobile Number missing | Skipped |
| Mobile number not 10 digits starting with 6–9 (+91 or 0 in front is fine) | Skipped |
| Same name and mobile already in the app, or earlier in the file | Skipped |
| PAN already in the app, or earlier in the file | Skipped |
| PAN not valid for an individual (4th character not "P") | Imported without the PAN, with a note |
| Email not valid | Imported without the email, with a note |
| Everything else | Imported |

The report can be saved as an Excel file. Clients are imported only when you click **Import**. Importing
the same file twice adds nobody the second time.

## Typing to search

- **Client boxes:** in any client box (DSC Inward, Add Expected DSC, reports and so on), a list of
  matching clients drops down as you type. A client matches by name, firm, client ID or PAN, and the
  typed text can appear anywhere in it. Use the arrow keys and Enter, or click a name, to choose; Esc
  closes the list.
- **Staff and token boxes:** staff name boxes and the token serial box suggest names the same way.
- **Search boxes:** every "Holder / client name" search box filters its table as you type.

## Business rules

- **Nothing is deleted:** every inward, outward and movement entry is kept. Mistakes are cancelled
  with a reason, or corrected (see below).
- **Correct Entry:** in Previous Inward Entries and Outward History, **Correct Entry…** fixes an
  entry's details with a reason.
  - **Inward:** date, Received From, purpose, expected return date and remarks.
  - **Outward:** date, Returned To, purpose and remarks. The date of a return taken from the system
    clock (collected from a consultant, token made inactive) stays fixed.
  - **Not correctable:** the client and the token. For those, cancel the entry and enter it again.
  - **Dates stay consistent:** an inward date can't be in the future, after the token's first
    hand-over or return, or before its previous return. An outward date can't be before the inward
    date or the token's last return to the custodian, or after it was received again.
  - **Record kept:** every change is kept with its old value, new value, reason and system time. It
    shows in Token History, and the register marks the entry "(corrected)". Cancelled entries can't be
    corrected.
- **Calculated, not stored:** live custody and the current holder of each token are worked out from
  the transactions. A token is in custody while it has a receipt with no return against it. Its
  holder is given by its latest movement; with no movement, it is with the custodian.
- **Duplicate receipts:** receiving a token already in custody needs confirmation. The earlier receipt
  is then marked Superseded, so the token is still counted once.
- **Expiry to the minute:** a certificate expiring at 11:00 AM shows **Expired** from 11:00 AM that day.
  An expiry entered without a time is taken as 12:00 AM (start of that day), so alerts come early
  rather than late.
- **Lists:**
  - The 7, 15 and 30-day lists count from now and overlap.
  - Revoked or Inactive certificates show only under "All tokens".
- **Custody and expiry are separate:** an expired token stays in custody until returned.
- **Renewals keep history:** a renewal never overwrites the old certificate.
- **Clients:**
  - Mobile number is required.
  - PAN is optional and can be added later. Clients without one show under the "PAN pending" filter.
  - When a PAN is given, it must be unique and be an individual's, with "P" as its 4th character.
  - Several DSC holders may share a mobile number (family members), but only with different names.
    Names are compared ignoring case, spaces and dots, so "R. K. Sharma" and "RK Sharma" count as the
    same name.
- **Token status:** every token is **Active** or **Inactive**.
  - Making a token Inactive (lost, replaced, damaged, surrendered …) records the reason and time.
  - It also removes the token from the expiry alerts; it still shows under "All tokens".
  - If the firm holds the token at that moment, the firm's custody ends. The Outward Register shows
    this as "Token made inactive", naming who had the token.
  - **Mark Token Active** brings a found token back, with a reason.
  - Every status change appears in Token History.
- **No secrets:** no DSC PINs, passwords or private keys are stored anywhere.

## Project layout

```
build_exe.py               builds a standalone DSC Manager.exe
Start DSC Manager.bat      launcher (no console window)
run_dsc_manager.pyw        entry point
dsc_manager/
  firm_info.py             the heading shown in the title and reports (blank here)
  database.py              SQLite schema, upgrades, business rules, reports, backup
  token_reader.py          reads DSC tokens (PKCS#11 drivers, any brand; Windows store fallback)
  dates.py                 DD-MM-YYYY / time handling
  config.py                database location and token driver settings
  gsheet.py                the reports sent to the partners' Google Sheet
  assets/google_sheet_script.gs   the Apps Script pasted into that sheet
  sample_data.py           demonstration data (marked "(Sample)")
  ui/                      Tkinter screens and dialogs
tests/
  test_core.py             automated tests of the business rules and token reading
  smoke_gui.py             opens the real window and drives the main workflows
  sheet_script_mock.js     runs the Google Sheet script against a mock (needs Node.js; skipped otherwise)
TEST_CHECKLIST.md          test checklist with results
```

## Running the tests

```
python -m unittest discover -s tests -v
python tests\smoke_gui.py
```

Both use a temporary database and a simulated token, so they never touch real data.

## Not included

As agreed for the prototype, it does not include email/SMS alerts, digital signing, portal
integrations, user logins or permissions, or an installer.
