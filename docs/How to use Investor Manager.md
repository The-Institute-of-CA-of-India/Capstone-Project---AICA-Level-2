# Investor Manager: how to use

## Name
From v1.9 the app is called **Investor Manager** (earlier versions were "Contract Note Manager"). Your data is
the same; the old exes still work as before for their own versions.

## Versions
Each version has its own program: **Investor Manager_v1.9.exe** (earlier: Contract Note Manager_v1.1.exe ... v1.8.exe) and so on
(Phase 2 will be v2.1, v2.2 ...). Use the newest one. If a new version has a problem, just double-click the
previous exe: your data (the `Data` folder) is shared, so nothing is lost either way.

* The app opens maximised; make the window smaller as with any window.
* Only one copy runs at a time. Clicking the same version again brings its window to the front. Clicking a
  different version closes the running one (and its window) and opens the one you clicked.
* The version is shown at the bottom left of the app.
* Keep the `App Files` folder next to the exes (it holds Python, the OCR engine and every version's program).
* If Windows shows "Windows protected your PC", click **More info** then **Run anyway**.
* If an exe is ever blocked: `App Files\Start_v1.13.bat` (or the bat of the version you use) does the same.
* First run of a new version: a black window appears for a few seconds while it sets up.
* **v1.7 reorganises the Data folder** (see "Where things are"). After you open v1.7 (or later) once, v1.6 and older
  versions will not find your data (they will open empty). Use v1.7 or later from then on.

## First run: registration
The first time v1.7 opens, it asks for Name, Organisation, Email, Mobile, WhatsApp, City, PIN, State, Country,
the Administrator's name, user id and password, and the Licence No. (leave blank for now; activation by licence
comes later). The licensee's name and **Valid Upto** date then show in the top bar. Settings > Registration shows
the details; changing them needs the Administrator's password.

## Bottom bar
**CA Atul Mathuria** at the bottom left opens the developer's page (address, email, mobile; email and mobile are
clickable).

## Messages
* While the app is working (updating prices, importing, backing up, sending to Tally, opening a screen), a
  **Please wait** message stays on the screen until it is finished; the other buttons wait meanwhile.
* Every screen has a yellow **Close** button at the top right that takes you back to where you came from.
* After every import a **green** message confirms what was imported.
* If anything fails, a **red** message says what failed, why, and what to do. The same list stays on the page in a
  red box, and everything is kept in the Import Log.

## Top bar
* **Period**: All periods, a financial year or **Custom range...**. Every screen follows it.
* **Person / PAN**: all persons, one PAN, or a name from a holdings sheet that has no PAN yet.

## Left panel
* **Dashboard**
* **Investment**
* **Contract Notes**: Import Contract Notes, List of Contract Notes, Script Register, Daily Summary, Scrip Master,
  Opening Holdings
* **Reconciliation**: Contract Note, Holding, Cost (Tally)
* **Imports**: Import Market Masters, Import Tally Masters, Import Market Rates, Grandfathering FMV, Broker Portal Download
* **Reports & Export**
* Persons and PAN, Export to Tally, Import Log, **Data Maintenance**, **Delete Data** (in red), Settings

## Screens
0. **Investment**: the holding and cost statement. Every script held, alphabetically: Name, Quantity, Average
   cost per unit, Cost, Market price, Market value, Gain / loss in rupees and %, Weight % and Holding since, with a
   **TOTAL** row at the bottom and the totals in a strip at the top. Gains are green, losses red. Switch on **More
   details** for day change, ISIN, asset class, industry and price date. Choose any "as on" date; click a script
   for its purchases and sales; click a column heading to sort; **Open in Excel** keeps the colours and the total.
   **Update prices now** gets the latest prices from Yahoo Finance (it turns green when prices are not from today;
   the app also tries this by itself once a day when it starts). Cost is FIFO cost in whole rupees: opening
   holdings plus purchases with all charges, less the cost of shares sold.
0a. **Dashboard**: Investment boxes (invested, market value, gain / loss) come first, then a script-wise list with Cost, Market value, Gain (Rs) and Gain % beside each green / red bar, and the "where the money is" chart, then the contract note figures. Every chart can be clicked: a bar or slice opens its contract note lines in a window (with a
   button to open them in the Script Register). Once market rates are imported, it also shows holdings at cost,
   market value and gain / loss (green gain, red loss) with a gain / loss chart by script.
1. **Import Contract Notes**: the box at the top shows, for the person chosen at the top, each broker's
   **Imported up to** date and **last contract note**, so you know which new notes to import. Then click
   **Upload contract note file(s)** or drop files on the box; or import a folder.
2. **Contract Notes**: tick notes and click **Delete selected notes**. Click a note to open it: edit the yellow cells
   (quantity, value, any charge, ISIN, script), tick items and **Delete selected items**, or correct the dates.
   Totals and the check against the printed amount are recalculated; every change goes to the Import Log.
   A deleted note can be imported again from its file.
3. **Import Masters**: click **Update all masters now** (needs internet, about a minute). It downloads the official
   BSE list of all securities (equity, ETFs, mutual fund units, debentures, bonds, commercial papers), the NSE
   equity, SME and ETF lists, the Nifty industry lists and the AMFI mutual fund list. Each file is kept in
   `Data\Masters` with its date. Update weekly: IPOs, bonus issues, splits, rights and mergers happen all the
   time. When the masters are more than 7 days old, the app asks at start-up: **Update now** (green, default)
   or **Not now** (red). If a site is busy, use the buttons to open
   its page, download the file and upload it, or import a whole folder of lists.
4. **Scrip Master**: the scrips you hold, with name, industry and asset class filled from the masters. Yellow cells
   can be edited and are never overwritten by later master updates.
5. **Opening Holdings**: click **Upload opening holdings file** (or drop it). **Assumed past purchases**: a
   script sold that was neither bought in a contract note nor shown in the holdings is treated as bought in the
   past; the app adds a lot marked "Assumed" for the quantity short at that sale, dated 3 years before the sale, at
   80% of the sale proceeds. These are rebuilt after every import, so real holdings replace them as soon as you
   upload them. Switch them off or rebuild them on the same screen.
    Your own layout is read as it is.
   Names are matched to PAN, missing ISINs and company names come from the masters, purchases already in a contract
   note are skipped. The result window lists every problem, and the Import Log keeps them. Yellow cells can be
   edited; tick rows and **Delete selected** to remove them.
6. **Persons and PAN**: type the PAN for each name, or click **Add person / PAN** to add a new one.
7. **Reports & Export**: choose person / PAN and period, then Excel, PDF, XML, CSV or JSON. The file opens by itself.
7a. **Import Market Rates**: **Import closing prices** for a date (official NSE and BSE bhavcopy, published around
   7 pm on trading days; mutual funds use the latest AMFI NAV), or **Get live prices** from Yahoo Finance for the
   scripts held. Prices are kept date-wise, so holdings can be valued on any date with prices.
7b. **Grandfathering FMV**: upload the FMV sheet (31-Jan-2018 quotations and NAVs, 01-Apr-2001 prices). Each script
   in the app is matched to its 31-Jan-2018 value; click a row to choose the right name if it is not matched.
   Capital gains in Phase 2 use these values.
8. **Import Tally Masters**: press **Import ledgers from Tally** (Tally open with the company, Connectivity set to
   act as Both on port 9000). Every script is matched to its Tally ledger even when the names differ (TATATECH =
   "Tata Tech", JIOFIN = "Jio Finance", AXISBANK = "Axis Bank Shares"); the Match % shows how close the names are.
   Scripts with no ledger are shown in **red**: click one to choose the right ledger or to **create it in Tally**
   (after you confirm, it is created in the same group as your other share ledgers, e.g. Shares Investments), or
   use **Create all missing ledgers**. A ledger you choose is remembered. Import again after adding ledgers in Tally.
8a. **Export to Tally**: one Journal voucher per contract note for the person and period at the top: purchases
   debited to the script's ledger at cost (charges added to cost, or to a charges ledger if you switch that off),
   sales credited at FIFO cost with the profit or loss to the Short / Long Term Capital Gain ledger, and the broker's
   ledger for the net amount. **Voucher settings** sets the voucher type, the gain and charges ledgers and the
   broker ledgers (IIFL Capital Services = "IIFL" is found by itself). Anything missing is listed in red with
   **Create in Tally**. **Send to Tally** creates the vouchers (each note only once; **Mark sent notes as not sent**
   if you delete them in Tally and want to send again), or **Save as Tally XML file** for Gateway > Import.
8a. **Reconciliation** (three sub-menus):
    * **Contract Note Reconciliation**: every note's computed total against its printed net amount.
    * **Holding Reconciliation**: choose the person and the statement date (and the broker / DP if the statement
      covers only that account), click **Upload holding statement** (PDF, Excel or CSV from CDSL, NSDL, CAMS,
      KFintech or your broker; the help section has buttons to their download pages), check the columns the app
      picked, and press **Reconcile**. Each script shows quantity as per the app, as per the statement, the
      difference and a status: Matched, Difference, Opening holding missing (sold more than bought in the app),
      Only in app, Only in statement, each with what to do. Every run is saved and can be reopened or opened in Excel.
    * **Cost Reconciliation (Tally)**: choose the person, the as-on date and (only if Tally keeps ledgers per broker)
      the broker. Then either **Read balances from Tally** (Tally Prime open with the company, and F1 Help >
      Settings > Connectivity set to act as **Both** on port **9000**), or **Upload Tally export** (Trial Balance or
      Group Summary of Investments exported to Excel). The app works out the cost of what is held on that date by
      FIFO (opening holdings + purchases with charges, less the cost of shares sold; same-day sales come out of
      earlier holdings) in whole rupees, and puts it next to each script's Tally ledger balance with the difference
      and a status: Matched (within Re 1), Difference, Ledger not found, Opening holding missing (cost incomplete
      because sales came from shares bought before the first contract note), Only in Tally. Ledgers are matched by
      the investment ledger name set on Export to Tally (e.g. "Investment in {script}"), then by company name or
      symbol; **Match ledgers to scripts** lets you choose the ledger for any script, and the choice is remembered.
      Quantities are checked on Holding Reconciliation; this screen checks cost.
8b. **Broker Portal Download**: choose the broker and click **Open portal and log in**. A separate Edge window opens
    the broker's site and the app fills your user id and password (it never presses Login). Type the OTP / CAPTCHA
    / PIN yourself, log in, choose the period on the site and click its download buttons for contract notes, ledger,
    P&L and holdings. Every file downloaded in that window is picked up at once: contract notes are imported
    straight away (green / red message for each), the rest are filed in `Data\Downloads\<broker>\Ledger`,
    `Profit and Loss`, `Holdings`, `Tradebook` or `Other`. Use a downloaded holding statement on Holding
    Reconciliation. Press **Finish session** when done (closing the window also ends it). Brokers change their
    sites often, so the address is editable in Settings.
9. **Import Log**: everything imported, skipped, edited, deleted or failed.
9b. **Delete Data** (red): delete one PAN for one financial year, one PAN for all years, or all PANs; tick to also
   delete opening holdings and the stored contract note files. The app shows what will be deleted, then asks
   again with a blinking red warning. A backup is always made first, and **Undo: bring the deleted data back**
   restores it at once (or later from Data Maintenance > Backup). Masters, prices, settings and registration are
   never deleted.
9a. **Data Maintenance**: size of each Data sub folder; **Delete temporary files**; **Delete chosen source files**
   (contract note files, portal downloads, holding statements, Tally exports; all, or only those saved before a
   date; the imported data stays in the app); **Delete old reports**; **Compact database**. **Backup**: automatic
   every 7 days (change the days), kept for 2 years (change the years), optionally with Master Data and source
   files; **Back up now**; **Restore** any backup (a backup of the present data is made first, so a restore can be
   undone). **Write CSV copies now** refreshes each person's CSV files.
10. **Settings**:
    * **PDF passwords**: one row per broker: choose the broker, type its password, **Save passwords**. Add rows with
      **Add another password**, remove with the red bin. Every saved password (and every PAN and client code
      already known) is tried automatically on protected contract notes.
    * **Registration, Administrator and users**: view or edit the registration; **Change Administrator password**
      (the Administrator cannot be deleted); **Add user**, change or delete other users (sign-in by user comes
      with user roles later). Password boxes are no longer filled in by the browser by itself.
    * **Brokers**: the list used in every broker drop-down. If a broker is missing, type its name in **New broker
      name** and click **Add broker**; it appears everywhere at once. Brokers you added (yellow) can be removed with
      the x. A broker typed straight into a password row is also added, and brokers found in imported contract notes
      appear automatically.
    * **Broker web portal logins**: broker, user id / client code, password and portal address (filled in for
      known brokers; change it if the broker's login page moves), then **Save portal logins**. The password is
      encrypted with your Windows login (DPAPI): it cannot be read from the database on another computer or by
      another Windows user. Leave the password box blank to keep the saved password.

## Where things are
Everything is in the `Data` folder next to the exes:

| Sub folder | What it holds |
|---|---|
| `Master Data` | Reference lists from Import Masters and the grandfathering sheet, as .md tables |
| `Client Data` | The database (`contract_notes.db`), a CSV copy of each person's data in `<PAN>_<name>`, broker sign-ins |
| `Transaction Data` | Imported source files: `Contract Notes` (per client and year), `Portal Downloads`, `Holding Statements`, `Tally Exports` |
| `Reports` | Reports and reconciliations opened in Excel |
| `Temporary Data` | Uploads in progress and logs: safe to delete at any time |
| `Backup` | Backup zips |
| `App Files` (next to the exes) | Program files for all versions |

Do not open `Client Data\contract_notes.db` while the app is running.

## Rules the app follows
* A contract note is saved only if gross purchases minus gross sales plus all levies equals the printed net amount
  (5 paise tolerance). Notes changed by hand are re-checked and marked "Edited manually".
* Purchases and sales are never netted; nothing is treated as speculative.
* STT and stamp duty are allocated the way the broker charged them; brokerage from the per-unit rate; other levies
  by turnover; GST on taxable charges. Charges in paise; net cost / proceeds per script in whole rupees.
* The same file, contract note, exchange trade or holding lot can never be recorded twice.
