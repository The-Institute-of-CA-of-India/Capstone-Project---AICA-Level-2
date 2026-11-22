@echo off
setlocal EnableExtensions DisableDelayedExpansion
title PracticeDesk - Isolated Google Session
rem Opens a separate temporary browser profile. No default profile is changed.
rem No credentials, downloads, administrator rights, or security-policy changes.
set "APP_URL=https://script.google.com/macros/s/AKfycbxjD5ORkffzmQ92GhTaMXSDEktt-qFmWyF8YPw-yskHHLfIP6ncvc4FT0J_dYa1FD8G/exec"
set "BROWSER="
set "PRIVATE_FLAG=--incognito"
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "BROWSER=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined BROWSER if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "BROWSER=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not defined BROWSER if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" set "BROWSER=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
if defined BROWSER goto browser_ready
set "PRIVATE_FLAG=--inprivate"
if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" set "BROWSER=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if not defined BROWSER if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" set "BROWSER=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
if not defined BROWSER if exist "%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe" set "BROWSER=%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"
if defined BROWSER goto browser_ready
echo Chrome or Microsoft Edge was not found in a standard installation location.
echo Open FACULTY_USER_MANUAL.html for the manual single-account method.
echo No browser or database has been changed.
pause
exit /b 2
:browser_ready
if /I "%~1"=="/check" goto check_only
if not defined TEMP goto temp_error
if not exist "%TEMP%\" goto temp_error
:new_profile
set "PD_PROFILE=%TEMP%\PracticeDesk-Session-%RANDOM%-%RANDOM%-%RANDOM%"
if exist "%PD_PROFILE%\" goto new_profile
md "%PD_PROFILE%" >nul 2>nul
if errorlevel 1 goto temp_error
echo PracticeDesk is requesting a NEW private browser session.
echo Sign in with ONE Google account in that new window.
echo Leave your normal browser windows and their existing accounts unchanged.
echo If an organization policy blocks separate profiles or private mode, contact its administrator.
echo Close the new private browser window when finished.
start "" "%BROWSER%" "--user-data-dir=%PD_PROFILE%" %PRIVATE_FLAG% --no-first-run --no-default-browser-check --new-window "%APP_URL%"
if errorlevel 1 goto launch_error
exit /b 0
:check_only
echo CHECK ONLY - no browser is launched and no profile directory is created.
echo Browser: "%BROWSER%"
echo Private flag: %PRIVATE_FLAG%
echo Temporary separate profile: enabled on each normal launch
echo URL: %APP_URL%
exit /b 0
:temp_error
echo A separate temporary browser profile could not be prepared.
echo No normal browser session was opened as a fallback.
echo Use the manual single-account procedure in FACULTY_USER_MANUAL.html.
pause
exit /b 3
:launch_error
echo The browser launch request failed. No default browser settings were changed.
echo Use the manual single-account procedure in FACULTY_USER_MANUAL.html.
pause
exit /b 4
