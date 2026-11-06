@echo off
cd /d "%~dp0"
python -m pip install -q -r requirements_desktop.txt
start "" pythonw ats_cv_filter.py
