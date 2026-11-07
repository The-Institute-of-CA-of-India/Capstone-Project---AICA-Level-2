@echo off
cd /d "%~dp0"
title Mukhota - Private Notice Desk
if not exist "venv\Scripts\activate.bat" goto :notinstalled
call "venv\Scripts\activate.bat"
start "Mukhota" pythonw -m mukhota.web
exit /b 0

:notinstalled
echo Mukhota is not installed yet. Double-click install.bat first.
pause
exit /b 1
