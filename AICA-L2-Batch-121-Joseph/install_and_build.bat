@echo off
title ATS CV Filter - Install and Build
cd /d "%~dp0"

echo ============================================
echo   ATS CV Filter - installing libraries
echo ============================================
python -m pip install --upgrade pip
python -m pip install -r requirements_desktop.txt
if errorlevel 1 (
    echo.
    echo Library installation failed. Make sure Python is installed and on PATH.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Building "ATS CV Filter.exe"
echo ============================================
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name "ATS CV Filter" ^
    --add-data "data;data" ^
    --hidden-import ats_engine ^
    --hidden-import PyQt6.QtPrintSupport ^
    ats_cv_filter.py
if errorlevel 1 (
    echo.
    echo Build failed.
    pause
    exit /b 1
)

copy /Y "dist\ATS CV Filter.exe" "ATS CV Filter.exe" >nul
echo.
echo Done! Double-click "ATS CV Filter.exe" in this folder to start the app.
pause
