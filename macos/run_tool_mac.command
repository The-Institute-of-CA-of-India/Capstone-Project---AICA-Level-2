#!/bin/bash
# ==========================================================================
#  FS Hard Copy Review - run the tool on macOS
#  First run: creates a private Python environment (.venv-mac) next to this
#  file and installs the packages. Later runs start the tool directly.
# ==========================================================================
cd "$(dirname "$0")" || exit 1
VENV="$PWD/.venv-mac"
VPY="$VENV/bin/python"

find_python() {
  for c in python3.12 python3.11 python3.10 /opt/homebrew/bin/python3.12 /usr/local/bin/python3.12 \
           /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 python3; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] else 1)' 2>/dev/null; then
      echo "$c"; return 0
    fi
  done
  return 1
}

if [ ! -x "$VPY" ]; then
  PY=$(find_python) || {
    echo
    echo " Python 3.12 was not found on this Mac."
    echo " Install it from https://www.python.org/downloads/macos/ (Python 3.12), then run this file again."
    echo
    read -r -p " Press Enter to close…"; exit 1; }
  echo " First run - creating the Python environment with $PY …"
  "$PY" -m venv "$VENV" || { echo " Could not create the environment."; read -r; exit 1; }
fi

if ! cmp -s "$VENV/.deps_ok" requirements.txt; then
  echo " Installing required packages (first run only, needs internet) …"
  "$VPY" -m pip install --upgrade pip -q --disable-pip-version-check
  "$VPY" -m pip install -r requirements.txt --disable-pip-version-check || {
    echo " Package installation failed - check the internet connection and run again."; read -r; exit 1; }
  cp requirements.txt "$VENV/.deps_ok"
fi

[ "$1" = "--setup-only" ] && exit 0
nohup "$VPY" fs_hard_copy_review.py >/dev/null 2>&1 &
exit 0
