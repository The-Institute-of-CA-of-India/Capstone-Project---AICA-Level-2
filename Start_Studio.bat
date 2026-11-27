@echo off
if not exist "%~dp0Revenue_Cutoff_Testing_Studio\Start_Revenue_Cutoff_Studio.bat" (
  echo Extract the entire ZIP before running this file.
  pause
  exit /b 1
)
call "%~dp0Revenue_Cutoff_Testing_Studio\Start_Revenue_Cutoff_Studio.bat"
exit /b %errorlevel%
