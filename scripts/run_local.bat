@echo off
setlocal
rem FITEVAL web - local single-user launcher (Windows).
cd /d "%~dp0.."

set "HOST=127.0.0.1"
set "PORT=8050"

rem Bail out early if the port is already taken (otherwise waitress ends in a
rem "WinError 10048 address already in use" traceback).
netstat -ano -p tcp | findstr /c:":%PORT% " | findstr /c:"LISTENING" >nul
if not errorlevel 1 (
    echo Port %PORT% is already in use - FITEVAL may already be running at http://%HOST%:%PORT%
    echo To restart, close the console window running it, then try again.
    pause
    exit /b 1
)

rem Create the virtual environment on first run.
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    py -3 -m venv .venv || python -m venv .venv
    if not exist ".venv\Scripts\python.exe" (
        echo ERROR: could not create the virtual environment.
        echo Install Python 3 from https://www.python.org/downloads/ and retry.
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -e ".[app]"
    if errorlevel 1 (
        echo ERROR: dependency installation failed.
        pause
        exit /b 1
    )
)

rem Open the browser a couple of seconds later, once the server is listening.
start "" /b cmd /c "ping -n 3 127.0.0.1 >nul & start http://%HOST%:%PORT%"

".venv\Scripts\python.exe" -m waitress --host=%HOST% --port=%PORT% --threads=8 fiteval_app.wsgi:server
