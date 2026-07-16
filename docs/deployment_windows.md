# Deploying FITEVAL web on Windows Server

The app is a plain WSGI application (`fiteval_app.wsgi:server`) served by
waitress. Three options, from simplest to most integrated.

## 0. Install (all options)

```bat
cd C:\fiteval_web
py -3.11 -m venv .venv
.venv\Scripts\pip install -e ".[app]"
```

Choose a workspace root with enough disk for user sessions:

```bat
setx FITEVAL_WORKSPACE D:\fiteval_workspace /M
```

## 1. Local single-user (double-click)

`scripts\run_local.bat` starts waitress on 127.0.0.1:8050 and opens the
browser. No server configuration needed.

## 2. Standalone service on a port (recommended first deployment)

Serve with waitress and register it as a Windows service with NSSM
(https://nssm.cc):

```bat
nssm install FITEVAL C:\fiteval_web\.venv\Scripts\python.exe ^
    -m waitress --host=0.0.0.0 --port=8050 --threads=8 fiteval_app.wsgi:server
nssm set FITEVAL AppDirectory C:\fiteval_web
nssm set FITEVAL AppStdout D:\fiteval_logs\out.log
nssm set FITEVAL AppStderr D:\fiteval_logs\err.log
nssm set FITEVAL AppEnvironmentExtra FITEVAL_WORKSPACE=D:\fiteval_workspace
nssm start FITEVAL
```

Open the port in Windows Firewall:

```bat
netsh advfirewall firewall add rule name="FITEVAL web" dir=in action=allow protocol=TCP localport=8050
```

Users browse to `http://server-name:8050`.

## 3. Behind IIS (HTTPS + university domain)

1. Install IIS with **Application Request Routing (ARR)** and **URL
   Rewrite** modules.
2. Run the waitress service as in option 2 but bound to `127.0.0.1`.
3. In ARR server proxy settings: enable proxy, raise the timeout to 120 s
   (long bootstrap runs on large datasets).
4. Add a rewrite rule on the site (or a `/fiteval` application):
   - Pattern: `fiteval/(.*)`  →  Rewrite to `http://127.0.0.1:8050/{R:1}`
5. When hosted under the `/fiteval/` subpath, set the environment variable
   `FITEVAL_URL_PREFIX=/fiteval/` for the service and restart it.

Websockets are not required (Dash uses plain HTTP requests).

## Housekeeping

- Per-session files live under `FITEVAL_WORKSPACE\<session-id>\`; sessions
  older than `FITEVAL_SESSION_HOURS` (default 24) are removed at app start.
  For long-running services add a scheduled task that recycles the service
  (or deletes stale dirs) nightly.
- Updating: stop the service, `git pull` / copy the new code,
  `.venv\Scripts\pip install -e ".[app]"`, start the service.
