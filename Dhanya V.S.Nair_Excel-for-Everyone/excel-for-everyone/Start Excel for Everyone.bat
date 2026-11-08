@echo off
setlocal
title Excel for Everyone
set "APP_DIR=%~dp0"
if exist "%APP_DIR%app.py" goto find_python
set "APP_DIR=%~dp0excel-for-everyone\"
if exist "%APP_DIR%app.py" goto find_python
echo Excel for Everyone could not be found.
echo Extract Excel-for-Everyone.zip first.
echo Put this BAT file beside app.py or beside the extracted excel-for-everyone folder.
echo.
pause
exit /b 1

:find_python
py -3 -c "import sys; assert sys.version_info >= (3,10)" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON=py -3"
    goto prepare
)
python -c "import sys; assert sys.version_info >= (3,10)" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON=python"
    goto prepare
)
echo Python 3.10 or newer is required.
echo Install Python from https://www.python.org/downloads/windows/
echo Include pip and enable Add Python to PATH, then run this file again.
echo.
pause
exit /b 1

:prepare
pushd "%APP_DIR%"
if errorlevel 1 goto folder_error
echo Checking Flask...
%PYTHON% -c "import flask" >nul 2>&1
if not errorlevel 1 goto launch
echo Installing the application dependency. Internet access is needed for this step.
%PYTHON% -m pip install -r requirements.txt
if errorlevel 1 goto install_error

:launch
echo.
echo Starting Excel for Everyone at http://127.0.0.1:5000
echo Your browser will open automatically.
echo Keep this window open while learning. Press Ctrl+C to stop the app.
echo.
%PYTHON% -c "import threading, webbrowser; from app import create_app; threading.Timer(2.0, lambda: webbrowser.open('http://127.0.0.1:5000')).start(); create_app().run(host='127.0.0.1', port=5000, debug=False)"
set "APP_EXIT=%ERRORLEVEL%"
popd
if "%APP_EXIT%"=="0" exit /b 0
echo.
echo The app stopped. If port 5000 is busy, close the previous app window and try again.
pause
exit /b %APP_EXIT%

:install_error
echo.
echo Flask could not be installed. Check your internet connection and Python installation.
popd
pause
exit /b 1

:folder_error
echo The application folder could not be opened.
pause
exit /b 1
