LEDGERDESK - WINDOWS EXE

1. Extract this ZIP to a writable folder, such as Documents\LedgerDesk.
2. Double-click LedgerDesk.exe. Python is included; no installation is needed.
3. Your default browser opens the local accounting interface.
4. Keep the LedgerDesk console window open while working. Press Ctrl+C there to stop.

Your records are saved in the data folder beside LedgerDesk.exe, not inside the EXE.
Always keep the data folder when updating, moving or backing up the application.
Do not run directly inside the ZIP or from Program Files.

EXISTING BOOKS
If you used the Python version, close it first. Copy its entire data folder into
this extracted folder, beside LedgerDesk.exe. Keep the original as a backup.
The EXE will load those companies. Do not overwrite an existing data folder
unless you have checked which database contains your latest records.

DEMO
Double-click TRY_DEMO.bat. Demo records use data\demo.sqlite3, separate from
live records in data\ledgerdesk.sqlite3.

This is the same first-release accounting application described in README.md
and FEATURE_MATRIX.md, with an embedded Windows runtime. No enterprise
accounting features have been added merely by converting it to EXE.

BUILD VALIDATION
15 accounting/API tests passed. The compiled EXE self-test PASSED for
embedded interface files, SQLite, demo postings and balanced financial reports.
A full live-browser test remains limited by the build environment's loopback
network restrictions. Test demo workflows before using real company records.

Windows 64-bit executable. No digital code-signing certificate is included.
