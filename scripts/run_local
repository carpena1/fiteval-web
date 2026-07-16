#!/usr/bin/env bash
# FITEVAL web - local single-user launcher (macOS / Linux).
set -euo pipefail

# Move to the project root (this script lives in scripts/).
cd "$(dirname "$0")/.."

HOST=127.0.0.1
PORT=8050

# Bail out early with a clear message if the port is already taken
# (otherwise waitress ends in an "Address already in use" traceback).
if lsof -nP -i:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port ${PORT} is already in use — FITEVAL may already be running at" \
         "http://${HOST}:${PORT}"
    echo "To restart, stop it first:  lsof -ti:${PORT} | xargs kill"
    exit 1
fi

# Create the virtual environment on first run.
if [ ! -x .venv/bin/python ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    .venv/bin/pip install -e ".[app]"
fi

URL="http://${HOST}:${PORT}"

# Open the browser once the server is up (macOS: open, Linux: xdg-open).
( sleep 2
  if command -v open >/dev/null 2>&1; then open "$URL"
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL"
  fi ) >/dev/null 2>&1 &

exec .venv/bin/python -m waitress --host="$HOST" --port="$PORT" \
    --threads=8 fiteval_app.wsgi:server
