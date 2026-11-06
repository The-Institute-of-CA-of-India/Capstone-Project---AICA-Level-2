@echo off
rem AppealIQ setup for Windows - submission (compiled) edition.
rem The core ships as compiled .pyd modules built for CPython 3.14 (64-bit),
rem so this edition requires 64-bit Python 3.14. No admin rights are needed.
setlocal
cd /d "%~dp0"

set "PY="
py -3.14 --version >nul 2>&1 && set "PY=py -3.14"
if not defined PY (
    py -3.14-64 --version >nul 2>&1 && set "PY=py -3.14-64"
)
if not defined PY (
    python -c "import sys;sys.exit(sys.version_info[:2]!=(3,14))" >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo ERROR: 64-bit Python 3.14 was not found.
    echo        This compiled edition runs only on Python 3.14 ^(the version its
    echo        core modules were built for^). Install 64-bit Python 3.14 from
    echo        python.org and run setup.bat again.
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    %PY% -m venv .venv || exit /b 1
)

echo Installing packages...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt || exit /b 1

where tesseract >nul 2>&1
if errorlevel 1 (
    if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
        echo Tesseract found in C:\Program Files\Tesseract-OCR.
    ) else (
        echo NOTE: Tesseract OCR was not found. Scanned pages will be flagged NO_TEXT.
        echo       To enable OCR, install Tesseract 5 with the English and Hindi language data.
    )
) else (
    echo Tesseract found on PATH.
)

echo Creating the AppealIQ desktop shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\create_shortcut.ps1
if errorlevel 1 echo NOTE: The desktop shortcut could not be created. Start AppealIQ with run.bat.

echo.
echo Setup complete. Start AppealIQ from the "AppealIQ" desktop shortcut, or with run.bat.
endlocal
