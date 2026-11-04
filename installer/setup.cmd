@echo off
setlocal EnableExtensions
title Investor Manager - setup
set "SRC=%~1"
set "DST=%~2"
set "VER=%~3"
if "%SRC%"=="" set "SRC=%~dp0."
if "%DST%"=="" set "DST=%LOCALAPPDATA%\ContractNoteManager"
if "%VER%"=="" (
  echo   Version missing. Start the program with "Investor Manager_vX.Y.exe".
  pause
  exit /b 1
)
echo.
echo   Investor Manager %VER% - setting up
echo   Installing to: %DST%
echo   Nothing is downloaded; everything comes from the "App Files" folder.
echo.
if not exist "%DST%" mkdir "%DST%"

if exist "%DST%\runtime\python\pythonw.exe" if exist "%DST%\runtime.ok" goto ocr
echo   [1/3] Python and libraries (one time only, about 1 to 2 minutes) ...
if exist "%DST%\runtime" rmdir /s /q "%DST%\runtime"
for %%Z in ("%SRC%\runtime_*.zip") do call :unzip "%%~fZ" || goto fail
echo ok> "%DST%\runtime.ok"

:ocr
if exist "%DST%\tesseract\tesseract.exe" goto app
echo   [2/3] OCR engine for scanned contract notes ...
call :unzip "%SRC%\tesseract.zip" || goto fail

:app
if exist "%DST%\app\%VER%\run.py" goto done
echo   [3/3] Application %VER% ...
if not exist "%SRC%\app_%VER%.zip" goto fail
call :unzip "%SRC%\app_%VER%.zip" || goto fail

:done
echo.
echo   Done. The application will open now.
timeout /t 2 >nul
exit /b 0

:unzip
echo         %~nx1
tar -xf "%~1" -C "%DST%" 2>nul && exit /b 0
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%~1' -DestinationPath '%DST%' -Force" && exit /b 0
exit /b 1

:fail
echo.
echo   Setup failed. Check free space on drive C: and try again.
pause
exit /b 1
