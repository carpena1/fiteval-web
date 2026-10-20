#!/usr/bin/env bash
# FITEVAL web - local single-user launcher (macOS / Linux).
set -euo pipefail

# Move to the project root (this script lives in scripts/).
cd "$(dirname "$0")/.."

HOST=127.0.0.1
PORT=8050
URL="http://${HOST}:${PORT}"

# Bail out early with a clear message if the port is already taken
# (otherwise waitress ends in an "Address already in use" traceback).
if lsof -nP -i:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port ${PORT} is already in use — FITEVAL may already be running at ${URL}"
    echo "To restart, stop it first:  lsof -ti:${PORT} | xargs kill"
    exit 1
fi

# Create the virtual environment on first run, and rebuild it whenever its
# interpreter no longer runs.  A .venv stores absolute paths to the Python
# that built it, so one carried to another machine (or built by a Python
# since upgraded or removed) is left with dangling symlinks.  '--clear' is
# required: a plain 'venv .venv' keeps the existing broken links.
if ! .venv/bin/python -c "" 2>/dev/null; then
    echo "Creating virtual environment..."
    python3 -m venv --clear .venv
    .venv/bin/python -m pip install --upgrade pip
    .venv/bin/pip install -e ".[app]"
fi

# Open the browser once the server really answers, rather than after a fixed
# delay -- so a server that fails to start no longer opens an empty page.
( for _ in $(seq 60); do
      if curl -fsS -o /dev/null "$URL" 2>/dev/null; then
          if command -v open >/dev/null 2>&1; then open "$URL"
          elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL"
          fi
          break
      fi
      sleep 0.5
  done ) >/dev/null 2>&1 &

echo "Starting FITEVAL at ${URL}  (Ctrl-C to stop)"
exec .venv/bin/python -m waitress --host="$HOST" --port="$PORT" \
    --threads=8 fiteval_app.wsgi:server
