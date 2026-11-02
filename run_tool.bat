@echo off
REM ==========================================================================
REM  FS Hard Copy Review - run the tool
REM  First run: creates a private Python environment (.venv) next to this file
REM  and installs the required packages. Later runs start the tool directly.
REM ==========================================================================
setlocal EnableExtensions
cd /d "%~dp0"
title FS Hard Copy Review
set "VENV=%~dp0.venv"
set "VPY=%VENV%\Scripts\python.exe"
set "PY="

if exist "%VPY%" goto deps

call :findpython
if not defined PY (
    echo.
    echo  Python 3.10 or newer was not found on this computer.
    echo  Install it from https://www.python.org/downloads/
    echo  ^(tick "Add python.exe to PATH" during installation^), then run this file again.
    echo.
    pause
    exit /b 1
)
echo  First run - creating the Python environment ...
%PY% -m venv "%VENV%"
if errorlevel 1 (
    echo  Could not create the Python environment.
    pause
    exit /b 1
)

:deps
if exist "%VENV%\.deps_ok" (
    fc /b "%VENV%\.deps_ok" "%~dp0requirements.txt" >nul 2>&1
    if not errorlevel 1 goto run
)
echo  Installing required packages ^(first run only, needs internet^) ...
"%VPY%" -m pip install --upgrade pip --disable-pip-version-check -q
"%VPY%" -m pip install -r "%~dp0requirements.txt" --disable-pip-version-check
if errorlevel 1 (
    echo.
    echo  Package installation failed - check the internet connection and run this file again.
    pause
    exit /b 1
)
copy /y "%~dp0requirements.txt" "%VENV%\.deps_ok" >nul

:run
if /i "%~1"=="--setup-only" exit /b 0
if exist "%VENV%\Scripts\pythonw.exe" (
    start "" "%VENV%\Scripts\pythonw.exe" "%~dp0fs_hard_copy_review.py"
) else (
    start "" "%VPY%" "%~dp0fs_hard_copy_review.py"
)
exit /b 0

:findpython
for %%V in (3.12 3.13 3.11 3.10) do (
    py -%%V -c "import sys" >nul 2>&1
    if not errorlevel 1 (
        set "PY=py -%%V"
        goto :eof
    )
)
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 set "PY=python"
goto :eof
