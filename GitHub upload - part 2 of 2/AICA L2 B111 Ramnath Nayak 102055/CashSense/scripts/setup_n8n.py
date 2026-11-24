"""Import the CashSense credential and workflows into the local n8n (run once, n8n stopped or running).

    python scripts/setup_n8n.py

* The API key is read from .env, written to a temporary file only for the import (n8n stores it
  encrypted), and the temporary file is deleted straight away.
* Workflows are imported inactive; activate them in the n8n editor (toggle top right).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cashsense.api import api_key  # noqa: E402

def fresh_path() -> str:
    """The saved Windows PATH plus the npm global folder and the Node.js folder - so n8n is found even from a
    window that carries an out-of-date PATH."""
    # n8n-runtime next to the project (on D:) comes first: an install made from inside the Claude desktop app lands
    # in the app's private copy of AppData, which normal windows cannot see.
    parts = [str(ROOT.parent / "n8n-runtime"), os.environ.get("PATH", "")]
    if os.name == "nt":
        import winreg

        for hive, key in ((winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
                          (winreg.HKEY_CURRENT_USER, "Environment")):
            try:
                with winreg.OpenKey(hive, key) as k:
                    parts.append(os.path.expandvars(winreg.QueryValueEx(k, "Path")[0]))
            except OSError:
                pass
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Node.js") as k:
                parts.append(winreg.QueryValueEx(k, "InstallPath")[0])
        except OSError:
            pass
        parts.append(os.path.join(os.environ.get("APPDATA", ""), "npm"))
    return os.pathsep.join(p for p in parts if p)


PATH = fresh_path()
N8N = shutil.which("n8n.cmd", path=PATH) or shutil.which("n8n", path=PATH)


def run(args: list[str]) -> None:
    env = {**os.environ, "PATH": PATH, "NODE_USE_SYSTEM_CA": "1", "N8N_DIAGNOSTICS_ENABLED": "false"}
    res = subprocess.run([N8N, *args], capture_output=True, text=True, env=env)
    out = (res.stdout + res.stderr).strip().splitlines()
    print("  " + "\n  ".join(line for line in out[-4:] if line))
    if res.returncode != 0:
        raise SystemExit(f"n8n {' '.join(args[:1])} failed")


def publish_only() -> None:
    """Make sure every CashSense workflow is published (run before each n8n start)."""
    for name, wid in existing_workflows().items():
        if name.startswith("CashSense"):
            run(["publish:workflow", f"--id={wid}"])


def main() -> None:
    if not N8N:
        raise SystemExit("n8n is not installed. Run: npm install -g n8n")
    if "--publish-only" in sys.argv:
        publish_only()
        return
    drop = ROOT / "data" / "inbox" / "drop"
    drop.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        cred = Path(tmp) / "cred.json"
        cred.write_text(json.dumps([{"id": "cashsenseApiKey01", "name": "CashSense API key", "type": "httpHeaderAuth",
                                     "data": {"name": "X-CashSense-Key", "value": api_key()}}]), encoding="utf-8")
        print("Importing credential 'CashSense API key' (stored encrypted by n8n)")
        run(["import:credentials", f"--input={cred}"])
        cred.unlink()
        existing = existing_workflows()
        ids = []
        for wf in sorted((ROOT / "n8n").glob("*.json")):
            data = json.loads(wf.read_text(encoding="utf-8"))
            if data["name"] in existing:          # overwrite the same workflow instead of adding a duplicate
                data["id"] = existing[data["name"]]
            tmp_wf = Path(tmp) / wf.name
            tmp_wf.write_text(json.dumps(data), encoding="utf-8")
            print(f"Importing workflow {wf.name}" + (" (update)" if "id" in data else ""))
            run(["import:workflow", f"--input={tmp_wf}"])
        for name, wid in existing_workflows().items():
            if name.startswith("CashSense"):
                print(f"Publishing {name}")
                run(["publish:workflow", f"--id={wid}"])
                ids.append(wid)
    print(f"Done: {len(ids)} workflows published. Restart n8n (scripts\\start_n8n.ps1) if it was running.")


def existing_workflows() -> dict[str, str]:
    env = {**os.environ, "PATH": PATH, "NODE_USE_SYSTEM_CA": "1"}
    res = subprocess.run([N8N, "list:workflow"], capture_output=True, text=True, env=env)
    out = {}
    for line in res.stdout.splitlines():
        if "|" in line:
            wid, name = line.split("|", 1)
            out[name.strip()] = wid.strip()
    return out


if __name__ == "__main__":
    main()
