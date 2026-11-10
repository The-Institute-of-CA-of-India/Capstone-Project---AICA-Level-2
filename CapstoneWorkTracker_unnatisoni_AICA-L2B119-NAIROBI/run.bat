@echo off
title Work Tracker
cd /d "%~dp0"
echo ==========================================
echo   Work Tracker - starting
echo ==========================================
echo Folder: %CD%
echo.

if not exist app.py goto noapp

set PY=
for %%V in (3.14 3.13 3.12 3.11) do if not defined PY py -%%V --version >nul 2>nul && set PY=py -%%V
if not defined PY py -3 --version >nul 2>nul && set PY=py -3
if not defined PY python --version >nul 2>nul && set PY=python
if not defined PY goto nopython

echo Using Python:
%PY% --version
echo.

if not exist venv\Scripts\python.exe goto makevenv
venv\Scripts\python.exe --version >nul 2>nul
if errorlevel 1 goto oldvenv
goto havevenv

:oldvenv
echo Old environment from another computer found. Rebuilding it...
rmdir /s /q venv

:makevenv
if exist venv\Scripts\python.exe goto havevenv
echo Creating environment...
%PY% -m venv venv
if errorlevel 1 goto venvfail

:havevenv
echo Checking packages. The first time can take 3 to 10 minutes and needs internet.
echo Please wait, do not close this window...
venv\Scripts\python.exe -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto pipfail

if exist "%USERPROFILE%\.streamlit\credentials.toml" goto runapp
mkdir "%USERPROFILE%\.streamlit" >nul 2>nul
>"%USERPROFILE%\.streamlit\credentials.toml" echo [general]
>>"%USERPROFILE%\.streamlit\credentials.toml" echo email = ""

:runapp
echo.
echo Starting the app. Your browser will open. Keep this window open.
echo Employees on the same network use the Network URL shown below.
echo.
venv\Scripts\python.exe -m streamlit run app.py --server.address 0.0.0.0 --theme.base light --theme.primaryColor "#4F46E5" --theme.backgroundColor "#F6F7FB" --theme.secondaryBackgroundColor "#FFFFFF" --theme.textColor "#1F2340" --client.toolbarMode minimal --browser.gatherUsageStats false
echo.
echo The app stopped. Read any message above.
pause
exit /b 0

:noapp
echo [ERROR] app.py was not found in this folder.
echo Put run.bat in the same folder as app.py, database.py and ai_helper.py.
pause
exit /b 1

:nopython
echo [ERROR] Python is not installed, or it was not added to PATH.
echo 1. Download Python 3.14 from https://www.python.org/downloads/
echo 2. During install, tick Add python.exe to PATH
echo 3. Run this file again.
pause
exit /b 1

:venvfail
echo [ERROR] Could not create the environment.
echo Delete the venv folder, then run this file again.
pause
exit /b 1

:pipfail
echo.
echo [ERROR] Package install failed.
echo 1. Check the internet connection. Office firewalls can block it.
echo 2. If your Python is 3.15, install Python 3.14 as well, delete the venv folder and run again.
pause
exit /b 1
