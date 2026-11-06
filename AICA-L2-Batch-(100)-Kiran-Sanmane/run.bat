@echo off
rem Start AppealIQ on this computer only (127.0.0.1) and open the browser.
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
    echo AppealIQ is not set up yet. Run setup.bat first.
    exit /b 1
)
call ".venv\Scripts\activate.bat"
start "" /min powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 4; Start-Process 'http://127.0.0.1:8501'"
streamlit run app.py --server.address 127.0.0.1 --server.port 8501
endlocal
