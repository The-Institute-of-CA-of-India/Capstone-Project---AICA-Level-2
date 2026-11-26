@echo off
rem Builds dist\RM_FG_Planner.exe (single file). Needs: pip install pyinstaller
cd /d "%~dp0"
python -m PyInstaller --noconfirm --clean --onefile --console ^
  --name RM_FG_Planner ^
  --distpath dist --workpath "%TEMP%\rm_fg_planner_build" --specpath "%TEMP%\rm_fg_planner_build" ^
  --collect-all streamlit --copy-metadata streamlit ^
  --add-data "%~dp0app.py;." ^
  --add-data "%~dp0planner_engine.py;." ^
  --add-data "%~dp0Purchase_Plan_Standard_Revised.xlsx;." ^
  --add-data "%~dp0.streamlit\config.toml;.streamlit" ^
  --exclude-module matplotlib --exclude-module plotly --exclude-module scipy ^
  --exclude-module tkinter --exclude-module IPython --exclude-module pytest ^
  launcher.py
echo.
echo Done. The file to share is dist\RM_FG_Planner.exe
