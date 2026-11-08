@echo off
setlocal
title Build MSME CertiFetch (slim build + installer)
set "HERE=%~dp0"
cd /d "%HERE%"

rem ---- Everything is built OUTSIDE OneDrive, so nothing heavy gets synced ----
set "OUT=%USERPROFILE%\MSME_CertiFetch_Build"
set "VENV=%OUT%\venv"
set "APP=%OUT%\dist\MSME CertiFetch"
set "INT=%APP%\_internal"

echo.
echo  Looking for Python 3.13 or 3.12...
set "PY="
py -3.13 --version >nul 2>nul && set "PY=py -3.13"
if not defined PY (py -3.12 --version >nul 2>nul && set "PY=py -3.12")
if not defined PY set "PY=python"
echo  Using: %PY%

echo.
echo  Step 1 of 4: creating a clean, private Python environment for the build...
if not exist "%VENV%\Scripts\python.exe" %PY% -m venv "%VENV%"
set "VPY=%VENV%\Scripts\python.exe"
for %%P in (pyinstaller selenium openpyxl customtkinter Pillow) do (
  "%VPY%" -m pip install --upgrade --disable-pip-version-check -q %%P >nul 2>nul && (echo    [OK]      %%P) || (echo    [FAILED]  %%P)
)

echo.
echo  Step 2 of 4: building the app (1 to 3 minutes)...
"%VPY%" -m PyInstaller --noconfirm --clean --onedir --windowed --optimize 1 --log-level WARN ^
  --name "MSME CertiFetch" --icon "%HERE%Art\autumn_icon.ico" ^
  --distpath "%OUT%\dist" --workpath "%OUT%\work" --specpath "%OUT%" ^
  --add-data "%HERE%Art\*.png;Art" ^
  --add-data "%HERE%Art\autumn_icon.ico;Art" ^
  --collect-data customtkinter ^
  --collect-submodules selenium.webdriver.chrome --collect-submodules selenium.webdriver.chromium ^
  --collect-submodules selenium.webdriver.remote --collect-submodules selenium.webdriver.support ^
  --collect-submodules selenium.webdriver.common ^
  --exclude-module selenium.webdriver.common.devtools ^
  --exclude-module numpy --exclude-module pandas --exclude-module matplotlib --exclude-module scipy ^
  --exclude-module lxml --exclude-module unittest --exclude-module pydoc ^
  --exclude-module setuptools --exclude-module pip ^
  "%HERE%MSME_CertiFetch.py"
if not exist "%APP%\MSME CertiFetch.exe" (
  echo  BUILD FAILED. Scroll up for the first error line.
  if /i not "%~1"=="/nopause" pause
  exit /b 1
)

echo.
echo  Step 3 of 4: removing files the app never uses...
call "%HERE%Trim_Build.bat" "%INT%"
for /f "tokens=3" %%S in ('dir /s /-c "%APP%" ^| findstr /c:"File(s)"') do set "BYTES=%%S"
echo    App folder size: %BYTES% bytes

echo.
echo  Step 4 of 4: making the one-file installer (needs the free "Inno Setup")...
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if defined ISCC (
  "%ISCC%" /Q /DSourceDir="%APP%" /O"%HERE%..\Installer" "%HERE%MSME_CertiFetch_Installer.iss"
  echo    Installer created in the Installer folder.
) else (
  echo    Inno Setup not found, skipped. Install it once with:  winget install JRSoftware.InnoSetup
)

echo.
echo  DONE. Share ONLY the Setup .exe from the Installer folder.
if /i not "%~1"=="/nopause" pause
