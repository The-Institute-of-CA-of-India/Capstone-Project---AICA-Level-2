@echo off
REM Builds "PDF-Redactor-PRO-Setup-<version>.exe" in the dist folder. Run on Windows with Python 3.11+.
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
    echo Python 3.11 or later is needed to BUILD the installer: https://www.python.org/downloads/
    pause
    exit /b 1
)
python packaging\build.py %*
echo.
pause
