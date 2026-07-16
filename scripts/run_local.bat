@echo off
rem FITEVAL web - local single-user launcher
cd /d "%~dp0.."
if not exist .venv\Scripts\python.exe (
    echo Creating virtual environment...
    py -3 -m venv .venv
    .venv\Scripts\pip install -e ".[app]"
)
start "" http://127.0.0.1:8050
.venv\Scripts\python.exe -m waitress --host=127.0.0.1 --port=8050 --threads=4 fiteval_app.wsgi:server
