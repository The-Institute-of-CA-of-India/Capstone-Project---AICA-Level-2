@echo off
setlocal
cd /d "%~dp0"
title LedgerDesk - Local Accounting
where python >nul 2>nul
if errorlevel 1 goto trypy
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 goto trypy
set "LEDGER_PYTHON=python"
goto start
:trypy
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 goto missing
set "LEDGER_PYTHON=py -3"
:start
echo.
echo LedgerDesk - Accounting workspace
echo Checking built-in dependencies...
%LEDGER_PYTHON% -c "import sqlite3, decimal, http.server, json, webbrowser"
if errorlevel 1 goto failed
echo All dependencies are available. No pip installation is required.
echo Opening your local accounting application...
echo Keep this window open while using the app.
%LEDGER_PYTHON% server.py %*
if errorlevel 1 goto failed
goto end
:missing
echo Python 3.10 or newer is required. Python 3.14 is supported.
echo Install Python from https://www.python.org/downloads/windows/
echo Enable 'Add Python to PATH', then double-click this file again.
pause
exit /b 1
:failed
echo.
echo Startup failed. Please copy the error shown above for troubleshooting.
pause
exit /b 1
:end
endlocal
