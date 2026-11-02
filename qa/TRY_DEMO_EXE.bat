@echo off
cd /d "%~dp0"
LedgerDesk.exe --demo
if errorlevel 1 pause
