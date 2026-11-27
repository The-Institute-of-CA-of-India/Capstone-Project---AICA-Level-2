# MSME Interest Calculator – Build a Windows .exe

## Files

| File | Purpose |
|---|---|
| `MSME_Interest_Calculator.py` | The application (GUI + calculation engine + self-test) |
| `requirements.txt` | Pinned runtime dependencies |
| `generate_sample_input.py` | Creates `Sample_MSME_Input.xlsx` covering every case and validation flag |
| `make_icon.py` | Creates `msme.ico` using PyQt5 (optional) |
| `MSME_Interest_Calculator.spec` | PyInstaller spec with hidden imports, excludes and UPX |
| `build_exe.bat` | One-click build: venv → install → self-test → icon → exe |

## A. Quick build (one click)

Double-click `build_exe.bat`, or run it in a Command Prompt from this folder. The exe is written to `dist\MSME_Interest_Calculator.exe`.

## B. Manual build, step by step (Command Prompt, from this folder)

1. **Create and activate a virtual environment** (Python 3.11 or later):
   ```bat
   python -m venv venv
   venv\Scripts\activate
   ```
2. **Install the dependencies and PyInstaller:**
   ```bat
   pip install -r requirements.txt pyinstaller==6.22.3
   ```
3. **Check the calculations before you build.** The test case must give ₹3,576.47 and ₹2,108.65:
   ```bat
   python MSME_Interest_Calculator.py --selftest
   ```
4. **(Optional) Create the icon and the sample data:**
   ```bat
   python make_icon.py
   python generate_sample_input.py
   ```
5. **Build with the command line:**
   ```bat
   pyinstaller --onefile --windowed --name "MSME_Interest_Calculator" ^
     --icon=msme.ico --add-data "msme.ico;." ^
     --hidden-import openpyxl --hidden-import openpyxl.cell._writer ^
     --hidden-import reportlab --hidden-import reportlab.graphics.barcode.common ^
     --hidden-import reportlab.graphics.barcode.code128 ^
     --exclude-module tkinter --exclude-module matplotlib --exclude-module scipy ^
     MSME_Interest_Calculator.py
   ```
   If you skipped the icon, leave out `--icon=msme.ico --add-data "msme.ico;."`.

   **Or build with the spec file** (it already lists the hidden imports and excludes, and is the recommended route):
   ```bat
   pyinstaller MSME_Interest_Calculator.spec --clean --noconfirm
   ```
6. **Output:** `dist\MSME_Interest_Calculator.exe`. This one file is all you need to distribute. The `build\` folder can be deleted.

## C. Using the application

1. **Download Template**, fill it in (or run `generate_sample_input.py`), then **Upload Excel**.
2. Set the **RBI Bank Rate**, choose **Written Agreement Yes/No** and set the **As-on Date**.
3. Click **Calculate**. Overdue rows are shown in red and flagged rows in yellow.
4. Use **Export to Excel** (4 sheets) or **Export to PDF**.
5. **Help → Run Self-Test** checks the statutory test case inside the exe.

Part payments go in repeated rows that share the same Party Name and Invoice Number, with one payment per row.

### Interest repayment / waiver (manual tab)

After you click **Calculate**, open the **Interest Repayment / Waiver (Manual)** tab:

1. Pick the invoice from the list. Type part of the party name or invoice number to search.
2. Choose **Interest Repaid to Vendor** or **Interest Waived by Vendor**.
3. Enter the date. For a repayment this is the repayment date; for a waiver it is the date of the vendor's waiver certificate. Leave **Amount** blank to mean the full interest balance.
4. For a waiver, tick **Waiver certificate received from vendor** only if the certificate is actually available.
5. Click **Add Entry**. The cards, the main table and both reports update straight away.

The rules:
- An entry dated after the As-on Date is not considered.
- **A waiver is considered only if the vendor's certificate is available as at the As-on Date.** Without it the interest stays payable. The entry is still kept and shown in yellow as "Not considered".
- A repayment or waiver larger than the interest balance is capped at the balance, and the row is flagged.

To keep your entries, click **Save Entries…** and reload them later with **Import Entries…**. You can also put them in an `Interest Adjustments` sheet inside the input workbook: the template includes this sheet, and the app loads it automatically when you upload the file.

The Excel export adds an **Interest Settlement** sheet showing each entry and whether it was considered. It also gives indicative **Sec. 22 MSMED Act** disclosure figures (principal unpaid, gross interest, interest paid, interest waived, net interest unpaid). The PDF includes the same information.

## D. Troubleshooting

| Problem | Fix |
|---|---|
| **Antivirus or SmartScreen flags the exe** (a false positive, common with PyInstaller one-file builds) | Build on a clean machine with the latest PyInstaller. Submit the exe to your AV vendor as a false positive (Microsoft: https://www.microsoft.com/wdsi/filesubmission). Code-sign it with a certificate (`signtool sign /a /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 dist\MSME_Interest_Calculator.exe`). Or distribute the `--onedir` build, which triggers fewer heuristics. |
| **"Failed to execute script" / missing DLL** (e.g. `VCRUNTIME140.dll`, `qwindows.dll`, `api-ms-win-crt-*`) | Install the *Microsoft Visual C++ 2015-2022 Redistributable (x64)* on the target PC. Rebuild with `--clean`. Keep Qt DLLs out of UPX (the spec already excludes them via `upx_exclude`). Check that you built inside the venv (`where python` should point to `venv\Scripts`). |
| **"No module named …" at runtime** | Add `--hidden-import <module>`, or add it to `hidden` in the `.spec`. To see the error, build once with `--console` instead of `--windowed`. |
| **.xls files will not open** | `xlrd` must be installed before building. You can also save the file as `.xlsx`. |
| **Large exe (should be about 24 MB)** | Build with the **spec file** (`pyinstaller MSME_Interest_Calculator.spec --clean`), not the long command line. The spec leaves out packages the app never uses (pandas, numpy, pyarrow, cryptography, lxml) and drops the Qt files a plain window does not need: software OpenGL (`opengl32sw.dll`), QML/Quick, translations and extra plugins. The app reads Excel with openpyxl and csv, so pandas is not needed. For a few MB more saving, download UPX (https://upx.github.io) and add `--upx-dir C:\upx`. Never UPX-compress `vcruntime140.dll` or Qt plugins. |
| **Slow first start** | Normal for `--onefile`, because it unpacks to `%TEMP%` on each start. Use `--onedir` for a near-instant start. |
| **Blurry on high-DPI screens** | High-DPI scaling is already enabled in `main()`. You can also right-click the exe → Properties → Compatibility → Change high DPI settings. |

## E. Legal note

Interest is computed u/s 16 of the MSMED Act, 2006. The supplier must hold valid Udyam registration on the invoice date. Traders are excluded from Sec. 15–16 benefits (MoMSME OM dated 02-07-2021). Verify the RBI Bank Rate at rbi.org.in before use.
