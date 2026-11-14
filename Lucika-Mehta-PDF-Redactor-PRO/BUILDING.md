# Building and updating the Windows installer

People who **use** PDF Redactor PRO need nothing except the installer: Python, the libraries,
the OCR engine and its English, Hindi and Marathi data are all inside it.
Only the computer that **builds** the installer needs Python.

## One-time preparation (your build computer)

1. Python 3.11 or later from <https://www.python.org/downloads/> (tick *Add python.exe to PATH*).
2. Inno Setup 6, which turns the program into a single Setup file:
   `winget install JRSoftware.InnoSetup` or <https://jrsoftware.org/isdl.php>.
   (Without it the build still works and makes a portable ZIP instead.)

## Build

Double-click **Build_Installer_Windows.bat** (or run `python packaging\build.py`).
The first build takes about 10 minutes; later builds about 3 to 5.

Result: `dist\PDF-Redactor-PRO-Setup-<version>.exe`. Share this one file (Drive, OneDrive, e-mail, pen drive).

The build stops if the finished program fails its self-test (redaction keeps layout, OCR reads a test
line, interface files present), so a broken installer is never produced.

## Releasing an update

1. Make your changes and test them as usual (`Start_Redactor_Windows.bat`).
2. Raise `VERSION` in `redact\model.py`, for example `2.3.0` to `2.4.0`.
3. Run **Build_Installer_Windows.bat** again.
4. Share the new Setup file. Installing it over the old version replaces the program and keeps every
   user's settings (stored in `%APPDATA%\PDF Redactor PRO`). Do not change `AppId` in
   `packaging\installer.iss`, or Windows will treat updates as a different program.

## Adding a new library later

Add it to `requirements.txt`; the build installs it and bundles its data files automatically.
If the built program reports *No module named ...* for something the library loads dynamically,
add that module name to `EXTRA_HIDDEN_IMPORTS` in `packaging\pdf_redactor_pro.spec` and rebuild.


## "Windows protected your PC"

Windows shows this for programs that are not code-signed. Users click **More info → Run anyway**
once. To remove the message, sign the Setup file with a code-signing certificate
(for example Microsoft Trusted Signing) after building.

## Licences

PyMuPDF (PDF engine) is AGPL-3.0: sharing the program free of charge together with its source code is
fine; selling it, or including it in a paid product, needs a commercial licence from Artifex.
Tesseract data (Apache-2.0), OpenCV (Apache-2.0), Roboto (SIL OFL) and the other libraries permit
redistribution.

## If the installed program does not open

1. Look at `%APPDATA%\PDF Redactor PRO\app.log` (paste that address into File Explorer). Each start is logged as `--- start v...`, followed by `server ready`, `app window started` and, on failure, `FATAL` with the reason. Hard crashes are written there too.
2. To see everything live, build a console version: `set REDACTOR_CONSOLE=1` and then `python packaging\build.py --no-installer`, and start `dist\PDF Redactor PRO\PDF Redactor PRO.exe` from Command Prompt.
3. `"PDF Redactor PRO.exe" --browser` opens the interface in the default browser instead of the app window.
