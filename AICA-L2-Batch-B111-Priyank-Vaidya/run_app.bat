@echo off
rem Starts the Raw Material Purchase & Production Planner in your browser.
cd /d "%~dp0"
python -m streamlit run app.py
pause
