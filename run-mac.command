#!/bin/bash
set -e
cd "$(dirname "$0")"
trap 'echo; echo "Startup failed. Read the error above."; read -r -p "Press Return to close."' ERR

LEXISCOPE_PYTHON=""
for candidate in python3.14 python3.13 python3.12 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)' 2>/dev/null; then
    LEXISCOPE_PYTHON="$candidate"
    break
  fi
done
if [ -z "$LEXISCOPE_PYTHON" ]; then
  echo "Install Python 3.12 or newer from https://www.python.org/downloads/macos/ and run this again."
  read -r -p "Press Return to close."
  exit 1
fi

echo "Preparing LexiScope. First launch downloads dependencies."
"$LEXISCOPE_PYTHON" -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
echo
echo "Open http://127.0.0.1:8000 in your browser once Uvicorn says it is running."
echo "Keep this window open. Press Control+C to stop."
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
