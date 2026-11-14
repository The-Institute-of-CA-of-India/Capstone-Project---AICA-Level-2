@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
%PY% -m venv .venv
if errorlevel 1 goto failed
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 goto failed
python -m pip install -r requirements.txt "pyinstaller>=6,<7"
if errorlevel 1 goto failed
python -m PyInstaller --noconfirm --clean --onedir --windowed --name SmartCertificates --paths src --hidden-import itr_schema_parser src\Smart_Certificates_V54.py
if errorlevel 1 goto failed
echo.
echo SUCCESS: dist\SmartCertificates\SmartCertificates.exe
pause
exit /b 0
:failed
echo BUILD FAILED. Read the error above. Check Python 64-bit and internet.
pause
exit /b 1
