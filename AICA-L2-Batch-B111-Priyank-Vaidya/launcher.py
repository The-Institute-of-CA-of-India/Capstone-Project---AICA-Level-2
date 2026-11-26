"""Entry point for the packaged .exe: starts the Streamlit app and opens it in the browser.

Built with build_exe.bat (PyInstaller). Not needed when running `streamlit run app.py`.
"""
import os
import socket
import sys

# Imported here only so PyInstaller bundles everything app.py needs
# (app.py itself is shipped as a data file and run by Streamlit).
import decimal  # noqa: F401
import html  # noqa: F401

import openpyxl  # noqa: F401
import pandas  # noqa: F401
import pandas.io.formats.style  # noqa: F401
import planner_engine  # noqa: F401
from streamlit.web import cli as stcli


def free_port(start: int = 8501) -> int:
    """First port from `start` upward that nothing is listening on."""
    for port in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start


if __name__ == "__main__":
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    os.chdir(base)  # so .streamlit/config.toml (colour theme) is picked up
    port = free_port()
    print("=" * 62)
    print("  RM Purchase & FG Production Planner")
    print(f"  Opening in your browser at http://localhost:{port}")
    print("  Keep this window open while you use the application.")
    print("  Close this window to stop the application.")
    print("=" * 62, flush=True)
    sys.argv = [
        "streamlit", "run", os.path.join(base, "app.py"),
        "--global.developmentMode=false",
        "--server.headless=false",
        "--server.address=localhost",
        f"--server.port={port}",
        "--server.fileWatcherType=none",
        "--browser.gatherUsageStats=false",
    ]
    sys.exit(stcli.main())
