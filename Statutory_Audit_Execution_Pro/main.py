"""Statutory Audit Execution Pro - Khare Deshmukh & Co.
Run on the office server; staff open  http://<server-name-or-ip>:8765  in their browser.
Settings (optional environment variables):  AUDITEXEC_HOST (default 0.0.0.0)   AUDITEXEC_PORT (default 8765)
"""
import os, socket, threading, time
from auditexec.core import database as db
from auditexec.server import create_app

HOST = os.environ.get("AUDITEXEC_HOST", "0.0.0.0")
PORT = int(os.environ.get("AUDITEXEC_PORT", "8765"))


def daily_backup():
    while True:
        try:
            if not any(p.stat().st_mtime > time.time() - 86400 for p in (db.RUNTIME / "backups").glob("AuditExec_backup_*.zip")): db.backup_now()
        except Exception as e: print("Backup problem:", e)
        time.sleep(3600)


if __name__ == "__main__":
    # refuse to start if an older copy is still holding the port (a common cause of "wrong" logins)
    with socket.socket() as t:
        if t.connect_ex(("127.0.0.1", PORT)) == 0:
            print(f"\n  STOP: something is already running on port {PORT}.\n  Close the other Statutory Audit Execution Pro window (or end 'python.exe' in Task Manager) and start again.\n"); input("Press Enter to close"); raise SystemExit(1)
    app = create_app()
    threading.Thread(target=daily_backup, daemon=True).start()
    try: ip = socket.gethostbyname(socket.gethostname())
    except OSError: ip = "<server-ip>"
    print(f"\n  Data folder in use: {db.RUNTIME}")
    print(f"\n  Statutory Audit Execution Pro is running.\n  On this computer : http://localhost:{PORT}\n  From staff PCs   : http://{ip}:{PORT}\n  Keep this window open. Press Ctrl+C to stop.\n")
    try:
        from waitress import serve
        serve(app, host=HOST, port=PORT, threads=16)
    except ImportError:
        app.run(host=HOST, port=PORT, threaded=True)
