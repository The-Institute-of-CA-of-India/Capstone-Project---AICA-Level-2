# Mini CFO (Python / Streamlit version)

A CA-controlled finance assistant for small business owners. DEMO with dummy data only.

## Run
```
pip install -r requirements.txt
streamlit run app.py
```
Demo logins (password `Demo@12345`): `ca@demo.com` (CA), `owner@demo.com` (Sharma Traders, Amber), `owner2@demo.com` (Verma Foods, Red).
The demo database is created automatically on first run. To reset it, stop the app and delete the files inside the `data` folder.

To use it on a phone: host free on Streamlit Community Cloud (push to GitHub), open the link in Chrome/Safari and use "Add to Home screen".

## Check the numbers
Run `pytest -q` from inside the project folder. It runs 17 checks, including hand-calculated figures (Sharma Traders Oct 2026: sales 8,90,000; profit 5,07,000; after fixed costs 3,47,000; cash 5,16,700; runway 5.0 weeks; receivables 5,90,000; GST estimate 96,300), role isolation, the Ask-my-CA flow and draft-note hiding. NOTE: the tests reset the demo data folder.

## How it is built
- `calc.py`: every calculation, in plain Python. The AI never calculates.
- `qa.py`: answers to the 10 suggested questions (from calc numbers) and the note draft. Optional Gemini call for other questions (CA enters an API key in the sidebar, or set GEMINI_API_KEY). Only masked summary numbers are sent: party names become Customer A / Supplier A, no raw rows, no PAN/Aadhaar/bank/phone.
- `db.py`: SQLite + CSV storage and demo seed.  `app.py`: screens and roles.

## Conventions (state these in your report)
- Profit uses Amount (excl. GST). Cash, receivables, payables use Amount + GST.
- Fixed costs are deducted from cash for each month in the data.
- "As of" date = last day of the latest month in the data.
- GST figure = GST collected minus GST on purchases/expenses for the latest month; always an estimate.
- Forecast uses known unpaid items and fixed costs only.

## Limitations (honest list for the report)
- Not a native Android/iOS app: a web app used through the phone browser.
- Demo login is simple (hashed passwords in SQLite); production would need proper authentication, encryption and a hosted database.
- No voice input; free-text questions outside the 10 chips need a Gemini key, otherwise the app says it does not know and offers "Ask my CA". Hindi replies need the Gemini key.
- No Tally integration; the CA uploads a CSV/Excel file.

## Privacy and governance
Dummy data only. Consent tick on first owner login; names masked before any AI call; owner sees only CA-approved notes; every upload, question, reply and approval is in the activity log (exportable). Aligns with DPDP Act 2023, ICAI Code of Ethics (confidentiality), SA 200 (judgement stays with the CA) and SA 230 (documentation).
