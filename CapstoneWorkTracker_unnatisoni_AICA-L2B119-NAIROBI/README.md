# Work Allocation & Review Tracker

## Run (Windows)
1. Install Python 3.11+ (tick "Add Python to PATH").
2. Double-click `run.bat` (first run installs packages, then opens the app at http://localhost:8501).
3. Log in: **admin / admin123**, then change the password and add employees under *Team*.

## Optional AI (Google AI Studio)
Copy `.env.example` to `.env` and paste your Gemini key from aistudio.google.com.

## Let employees use it
Run on your PC (run.bat already allows network access). Employees open `http://YOUR-PC-IP:8501`
(find IP with `ipconfig`). Allow Python through Windows Firewall if asked.

## Backup
Copy `worktracker.db` and the `uploads` folder regularly.
