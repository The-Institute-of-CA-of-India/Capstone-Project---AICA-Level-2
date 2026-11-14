@echo off
setlocal
cd /d "%~dp0src"
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 Smart_Certificates_V54.py
) else (
  where python >nul 2>&1
  if %errorlevel%==0 (
    python Smart_Certificates_V54.py
  ) else (
    echo Python 3.10 or later is required. Install Python from https://www.python.org/downloads/
    pause
    exit /b 1
  )
)
if errorlevel 1 pause
