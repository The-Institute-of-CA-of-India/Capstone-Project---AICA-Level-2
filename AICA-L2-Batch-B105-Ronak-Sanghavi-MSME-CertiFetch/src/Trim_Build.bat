@echo off
rem Called by Build_EXE.bat with the _internal folder as its argument.
rem Removes Linux and Mac helpers and image formats this Windows app never uses.
set "INT=%~1"
for /d %%D in ("%INT%\selenium\webdriver\common\linux*") do rmdir /s /q "%%D" >nul 2>nul
for /d %%D in ("%INT%\selenium\webdriver\common\macos*") do rmdir /s /q "%%D" >nul 2>nul
del /q "%INT%\selenium\webdriver\common\selenium-manager.cdx.json" >nul 2>nul
del /q "%INT%\PIL\_avif*.pyd" >nul 2>nul
del /q "%INT%\PIL\_webp*.pyd" >nul 2>nul
del /q "%INT%\PIL\_imagingcms*.pyd" >nul 2>nul
