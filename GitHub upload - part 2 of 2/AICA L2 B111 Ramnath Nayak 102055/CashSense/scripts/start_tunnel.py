"""Open a temporary public https link to the CashSense dashboard (Cloudflare quick tunnel, free, no account)
and send the link to the CA's Telegram. The link works while this window stays open; it changes every run.

    python scripts/start_tunnel.py

Security: the dashboard needs the dashboard password (lock-out after 10 wrong tries); every API route needs the
X-CashSense-Key; the link is random and temporary. Close the window to take it offline.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cashsense.messaging.telegram import TelegramClient, TelegramError  # noqa: E402


def find_cloudflared() -> str | None:
    exe = shutil.which("cloudflared")
    if exe:
        return exe
    for p in (Path("C:/Program Files (x86)/cloudflared/cloudflared.exe"), Path("C:/Program Files/cloudflared/cloudflared.exe")):
        if p.exists():
            return str(p)
    return None


def main() -> None:
    exe = find_cloudflared()
    if "--check" in sys.argv:          # used by Start_CashSense.cmd: is the optional phone link available?
        raise SystemExit(0 if exe else 1)
    if not exe:
        raise SystemExit("cloudflared not found (optional). Install it: winget install --id Cloudflare.cloudflared")
    port = os.environ.get("CASHSENSE_PORT", "8765")
    proc = subprocess.Popen([exe, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{port}"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    url = None
    for line in proc.stdout:
        m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
        if m and not url:
            url = m.group(0)
            print(f"\nDashboard on your phone: {url}/dashboard\n(keep this window open; Ctrl+C to stop)\n", flush=True)
            try:
                t = TelegramClient()
                if t.available and t.chat_id:
                    t.send_message(f"📱 <b>CashSense dashboard link</b> (temporary, SAMPLE data):\n{url}/dashboard\n"
                                   "Sign in with the dashboard password.")
                else:
                    print("(No Telegram bot set up - open the link above on your phone yourself.)", flush=True)
            except TelegramError as exc:
                print("Could not send the link to Telegram:", exc)
    proc.wait()


if __name__ == "__main__":
    main()
