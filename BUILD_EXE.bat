@echo off
setlocal
cd /d "%~dp0"
python -m pip install pyinstaller
if errorlevel 1 goto failed
python -m PyInstaller --noconfirm --onefile --console --name LedgerDesk --add-data "static;static" --hidden-import demo server.py
if errorlevel 1 goto failed
echo EXE created in dist\LedgerDesk.exe
pause
exit /b 0
:failed
echo Build failed. See the error above.
pause
exit /b 1
