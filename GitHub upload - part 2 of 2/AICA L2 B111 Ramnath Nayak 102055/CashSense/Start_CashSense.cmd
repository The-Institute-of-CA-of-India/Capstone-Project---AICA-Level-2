@echo off
title Start CashSense
cd /d "%~dp0"
if not defined CASHSENSE_PORT set CASHSENSE_PORT=8765
echo.
echo  Starting CashSense (SAMPLE data). Keep the windows that open; close them to stop CashSense.
echo.
if not exist ".env" (
    echo  CashSense is not set up on this computer yet.
    echo  Double-click Setup_For_Reviewers.cmd first, then run this file again.
    echo.
    pause
    exit /b 1
)
start "CashSense 1 - app (API)" powershell -NoExit -ExecutionPolicy Bypass -File "%~dp0scripts\start_cashsense.ps1"
echo  [1/3] App started. Waiting 10 seconds...
timeout /t 10 /nobreak >nul

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_n8n.ps1" -CheckOnly >nul 2>&1
if errorlevel 1 (
    echo  [2/3] n8n is not installed - skipped. It is optional: it runs the schedules, Telegram and the drop
    echo        folder. The dashboard, reconciliation, risks and forecast work without it.
) else (
    start "CashSense 2 - n8n workflows" powershell -NoExit -ExecutionPolicy Bypass -File "%~dp0scripts\start_n8n.ps1"
    echo  [2/3] n8n starting - it takes about a minute...
    timeout /t 45 /nobreak >nul
)

python scripts\start_tunnel.py --check >nul 2>&1
if errorlevel 1 (
    echo  [3/3] Phone link skipped - cloudflared is not installed ^(optional^).
) else (
    start "CashSense 3 - phone link" powershell -NoExit -ExecutionPolicy Bypass -Command "Set-Location '%~dp0'; python scripts\start_tunnel.py"
    echo  [3/3] Phone link starting - shown in its window, and sent to Telegram if a bot is set up.
)
timeout /t 5 /nobreak >nul
if not defined CASHSENSE_NO_BROWSER start "" "http://127.0.0.1:%CASHSENSE_PORT%/dashboard"
echo.
echo  Done. Dashboard: http://127.0.0.1:%CASHSENSE_PORT%/dashboard
echo  Sign in with DASHBOARD_PASSWORD from the .env file (open .env with Notepad).
echo.
pause
