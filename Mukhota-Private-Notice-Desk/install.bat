@echo off
setlocal
cd /d "%~dp0"
title Mukhota - Private Notice Desk : Install
echo ==================================================
echo   Mukhota - Private Notice Desk
echo   Mask it. Check it. Answer it.          Installer
echo ==================================================
echo.

where py >nul 2>nul
if errorlevel 1 goto :nopy
py -3.12 --version >nul 2>nul
if errorlevel 1 goto :nopy

if exist "venv\Scripts\python.exe" goto :haveenv
echo Creating virtual environment with Python 3.12 ...
py -3.12 -m venv venv
if errorlevel 1 goto :fail
:haveenv

echo Upgrading pip ...
"venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :fail

echo Installing Mukhota libraries - this can take several minutes ...
"venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :fail

echo Creating the Mukhota icon ...
"venv\Scripts\python.exe" -m mukhota.gui.icon
if errorlevel 1 goto :fail

echo.
echo Mukhota is installed. Double-click run.bat to start it.
pause
exit /b 0

:nopy
echo Python 3.12 was not found.
echo Install Python 3.12 64-bit from python.org - tick "Add python.exe to PATH" - then run this again.
pause
exit /b 1

:fail
echo.
echo Installation did not complete. Check your internet connection and run install.bat again.
pause
exit /b 1
