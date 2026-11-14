#!/bin/bash
# PDF Redactor PRO - double-click to start (macOS)
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is not installed. Install it from https://www.python.org/downloads/"
  read -n 1 -s -r -p "Press any key to close"
  exit 1
fi

if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"; then
  echo "This tool needs Python 3.11 or later: https://www.python.org/downloads/"
  echo "Then delete the .venv folder here and run this launcher again."
  read -n 1 -s -r -p "Press any key to close"
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "First run: setting up, this takes 2-3 minutes..."
  python3 -m venv .venv
fi

# (Re)install libraries whenever requirements.txt has changed
if ! cmp -s requirements.txt .venv/installed_requirements.txt; then
  echo "Installing / updating libraries..."
  .venv/bin/python -m pip install --upgrade pip >/dev/null
  .venv/bin/python -m pip install -r requirements.txt && cp requirements.txt .venv/installed_requirements.txt
fi

echo "Starting PDF Redactor PRO..."
.venv/bin/python server.py
