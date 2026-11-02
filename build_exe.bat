@echo off
REM ==========================================================================
REM  FS Hard Copy Review - build a single self-contained .exe
REM  Output: dist\FS_Hard_Copy_Review.exe  (Python and all packages inside;
REM  the person receiving it needs nothing else installed)
REM ==========================================================================
setlocal EnableExtensions
cd /d "%~dp0"
title Build FS Hard Copy Review EXE
set "VPY=%~dp0.venv\Scripts\python.exe"

echo  [1/4] Preparing the Python environment ...
call "%~dp0run_tool.bat" --setup-only
if errorlevel 1 (
    echo  Environment setup failed.
    pause
    exit /b 1
)

echo  [2/4] Installing PyInstaller ...
"%VPY%" -m pip install --upgrade pyinstaller --disable-pip-version-check -q
if errorlevel 1 (
    echo  Could not install PyInstaller.
    pause
    exit /b 1
)

echo  [3/4] Creating the application icon ...
if not exist "%~dp0build" mkdir "%~dp0build"
"%VPY%" "%~dp0fs_hard_copy_review.py" --make-icon "%~dp0build\app.ico"

echo  [4/4] Building the EXE ^(takes a few minutes^) ...
"%VPY%" -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name "FS_Hard_Copy_Review" ^
    --icon "%~dp0build\app.ico" ^
    --collect-data docx ^
    --collect-data pdfminer ^
    --collect-all pypdfium2 ^
    --collect-all pypdfium2_raw ^
    --collect-all rapidocr_onnxruntime ^
    --collect-all onnxruntime ^
    --collect-data wordninja ^
    --exclude-module tkinter ^
    --distpath "%~dp0dist" ^
    --workpath "%~dp0build\work" ^
    --specpath "%~dp0build" ^
    "%~dp0fs_hard_copy_review.py"
if errorlevel 1 (
    echo.
    echo  Build failed - see the messages above.
    pause
    exit /b 1
)

echo.
echo  Done:  %~dp0dist\FS_Hard_Copy_Review.exe
echo  Share this single file. Each user sets their own AI key in Settings.
echo.
explorer "%~dp0dist"
pause
exit /b 0
