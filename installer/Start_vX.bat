@echo off
rem Same as "Investor Manager_vX.Y.exe", for use if the exe is ever blocked. Replace v1.13 below with the version.
setlocal
set "HERE=%~dp0.."
set "BASE=%LOCALAPPDATA%\ContractNoteManager"
if not exist "%BASE%\runtime\python\pythonw.exe" goto setup
if not exist "%BASE%\app\v1.13\run.py" goto setup
if not exist "%BASE%\tesseract\tesseract.exe" goto setup
goto start
:setup
call "%~dp0setup.cmd" "%~dp0." "%BASE%" v1.13 || exit /b 1
:start
set "CNM_VERSION=v1.13"
set "CNM_DATA=%HERE%\Data"
set "CNM_PROJECT=%HERE%"
set "NICEGUI_STORAGE_PATH=%HERE%\Data\.app"
set "CNM_TESSERACT=%BASE%\tesseract\tesseract.exe"
set "TESSDATA_PREFIX=%BASE%\tesseract\tessdata"
if not exist "%CNM_DATA%" mkdir "%CNM_DATA%"
cd /d "%BASE%\app\v1.13"
start "" "%BASE%\runtime\python\pythonw.exe" "%BASE%\app\v1.13\run.py"
