@echo off
REM PDF Redactor PRO - double-click to start (Windows)
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python is not installed. Install Python 3.11 or later from https://www.python.org/downloads/
    echo and tick "Add python.exe to PATH" during installation.
    pause
    exit /b 1
)

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 (
    echo This tool needs Python 3.11 or later. Install it from https://www.python.org/downloads/
    echo then delete the .venv folder here and run this launcher again.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo First run: setting up, this takes 2-3 minutes...
    python -m venv .venv
)

REM (Re)install libraries whenever requirements.txt has changed
fc /b requirements.txt ".venv\installed_requirements.txt" >nul 2>nul
if errorlevel 1 (
    echo Installing / updating libraries...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Installation failed. Check the internet connection and try again.
        pause
        exit /b 1
    )
    copy /y requirements.txt ".venv\installed_requirements.txt" >nul
)

echo Starting PDF Redactor PRO...
".venv\Scripts\python.exe" server.py
pause
