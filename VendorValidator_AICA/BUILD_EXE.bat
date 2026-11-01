@echo off
cd /d "%~dp0"
echo Building VendorValidator.exe ...
python -m pip install -q -r requirements.txt
python -m PyInstaller --noconfirm --clean --onefile --windowed --name VendorValidator --collect-all playwright --hidden-import tkinter app.py
echo.
echo Done. EXE is in the dist folder.
pause
