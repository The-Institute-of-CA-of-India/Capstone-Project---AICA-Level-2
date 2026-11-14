# Build and Share Smart Certificates EXE

## For the developer (one time)
Windows 10/11 64-bit, Python 3.10+ 64-bit, internet, preferably 8 GB RAM and 2 GB+ free disk.
1. Extract project to a short path, e.g. `C:\ICAI_Smart_Certificates`.
2. Double-click `BUILD_WINDOWS_EXE.bat`. It creates `.venv`, installs requirements and PyInstaller, and builds a folder distribution.
3. Locate `dist\SmartCertificates\SmartCertificates.exe`.
4. Test the EXE on the build PC and on a **second clean Windows PC without Python**. Confirm import, database persistence, certificate generation and Word output.
5. Compress the **entire** `dist\SmartCertificates` folder as ZIP. Do not share only the `.exe` file.

## For other Chartered Accountants
Download the EXE distribution ZIP, extract it and double-click `SmartCertificates.exe`. Python and pip libraries are bundled. MS Word is recommended for editing DOCX output but not required to generate DOCX. The app uses local user Documents storage.

## Limitations
This ZIP includes **EXE builder**, not a compiled EXE. Windows compilation/testing must be performed on Windows. Tesseract OCR executable/language data may need separate installation for scanned images; searchable PDF/JSON workflows do not need it. Unsigned applications can trigger Windows security warnings; do not disable security protection. Never include your `clients.sqlite3` database when sharing.
