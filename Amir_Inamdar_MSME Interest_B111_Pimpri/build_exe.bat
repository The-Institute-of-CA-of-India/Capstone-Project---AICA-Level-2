@echo off
REM ============================================================
REM  Build MSME_Interest_Calculator.exe  (run from this folder)
REM ============================================================
setlocal
cd /d "%~dp0"

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv || goto :error
)
call venv\Scripts\activate.bat || goto :error

python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller==6.22.3 || goto :error

echo Running self-test...
python MSME_Interest_Calculator.py --selftest || goto :error

if not exist msme.ico python make_icon.py

echo Building single-file exe...
pyinstaller MSME_Interest_Calculator.spec --clean --noconfirm || goto :error

echo.
echo Done:  %~dp0dist\MSME_Interest_Calculator.exe
goto :eof

:error
echo.
echo BUILD FAILED - see the messages above.
exit /b 1
