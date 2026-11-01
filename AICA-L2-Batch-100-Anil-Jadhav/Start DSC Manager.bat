@echo off
rem Starts the DSC Management Tool without a console window.
cd /d "%~dp0"
start "" pythonw run_dsc_manager.pyw
