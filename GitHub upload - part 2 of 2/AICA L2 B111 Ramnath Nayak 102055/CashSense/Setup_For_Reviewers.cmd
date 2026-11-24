@echo off
title CashSense - one-time setup
cd /d "%~dp0"
echo.
echo  CashSense one-time setup (SAMPLE data only - no accounts or keys needed)
echo  ------------------------------------------------------------------------
echo  1. installs the Python packages listed in requirements.txt
echo  2. unpacks the sample data, creates the settings file (.env)
echo  3. builds a local database and runs reconciliation and risk checks
echo.
where python >nul 2>&1
if errorlevel 1 (
    echo  Python was not found. Install Python 3.11 or newer from https://www.python.org/downloads/
    echo  and tick "Add python.exe to PATH" during installation. Then run this file again.
    echo.
    pause
    exit /b 1
)
echo  [1/2] Installing Python packages (a few minutes the first time)...
python -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo.
    echo  Package installation failed - see the messages above.
    pause
    exit /b 1
)
echo.
echo  [2/2] Preparing the sample data and the local database...
python -m cashsense.cli reviewer-setup
if errorlevel 1 (
    echo.
    echo  Setup did not finish - see the messages above.
    pause
    exit /b 1
)
echo.
echo  Next: double-click Start_CashSense.cmd
echo.
pause
