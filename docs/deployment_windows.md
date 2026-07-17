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

## 4. University (UF) hosting: product choice and sizing

UF IT offers two relevant products (https://it.ufl.edu/hosting/pricing/):

- **IIS Website Hosting** ($5/mo, 20 GB doc root, ASP/PHP/.NET 4.0, shared
  load-balanced servers). This is a managed *document root* — it cannot run
  a long-lived Python/waitress process, so **FITEVAL cannot be hosted here.**
- **Virtual Machine Hosting** (unit-based) — a Windows Server VM you
  administer yourself. This is the one to use: install Python, waitress and
  (optionally) IIS as the reverse proxy exactly as in sections 0–3.

### Why FITEVAL is light

The app is CPU-bound only during a Run: one evaluation holds a single
waitress thread for ~1–3 s (20 000-resample BCa bootstrap for N ≤ 1000,
chunked to 2 000, plus matplotlib rendering) and numpy releases the GIL, so
concurrent runs spread across cores. Between runs the browser is idle. Users
load data, Run, then read and tweak for a minute or more, so at any instant
only a small fraction are mid-Run — with 8 cores the app can finish ~8
bootstraps genuinely in parallel, and further Runs queue briefly on the
thread pool rather than failing. Memory is a ~300–400 MB resident process
plus ~100–200 MB of transient bootstrap arrays per concurrent Run; even 8
overlapping Runs sit around ~3 GB alongside Windows Server (~1.5 GB idle),
well inside 8 GB. Disk is the app + venv (~0.5 GB) plus small per-session
workspaces (a few MB each, swept after `FITEVAL_SESSION_HOURS`).

### Recommended VM (maps to UF units)

| Resource | Recommended | Minimum | UF unit / cost |
|----------|-------------|---------|----------------|
| vCPU | 8 | 2 | free up to 8 vCPU (no cost) |
| RAM | 8 GB | 4 GB | $8/mo per 2 GB unit → 4 units = $32/mo (min 2 = $16/mo) |
| Disk | 80 GB "Gold" | 80 GB "Gold" | $15/mo |
| OS | Windows Server (latest LTSC) | — | included with VM |

Recommended build ≈ **$47/mo** (8 vCPU, 8 GB, 80 GB Gold). vCPUs are free up
to 8, so take all 8 — the only cost is the 8 GB of RAM ($32/mo) and the Gold
disk ($15/mo), and the extra cores let overlapping Runs finish in parallel
(each bootstrap is CPU-bound and releases the GIL) at no extra charge. 8 is
the free ceiling; more triggers UF's "proof of need" review.

**Capacity of this build.** The binding resource is CPU — the ~8-core limit
means ~8 simultaneous Runs before latency starts to climb. Because users
don't all submit at once (each active user contributes only a small fraction
of a concurrent Run during their think time), this comfortably serves on the
order of **40–50 interactive users**, with RAM and disk to spare. That is
plenty of headroom for the foreseeable demand, all within the $47/mo cost.
The number scales with workload: very large datasets or the default 20 000
resamples push Run time toward 3 s and lower the ceiling; dropping to 5 000
resamples raises it. Set waitress `--threads=16` on this build so the pool
can admit ~8 concurrent Runs plus idle-user requests.

**Growing beyond this at no added cost is limited** — 8 vCPU is already the
free ceiling. If sustained bursts routinely exceed ~8 concurrent Runs, add
RAM ($8 per 2 GB) only if you also raise `--threads`; the real scale-out step
is a second VM behind UF's load balancer, which does add cost.

### Tuning knobs if you need to fit smaller

- Lower `--threads` (e.g. 4) to cap simultaneous Runs and peak memory.
- Reduce bootstrap resamples in `fitevalconfig.txt` (default 20 000; 5 000
  is the floor the app enforces) to cut per-Run CPU time.
- Shorten `FITEVAL_SESSION_HOURS` and run the nightly cleanup (below) to
  keep workspace disk near zero.

## Housekeeping

- Per-session files live under `FITEVAL_WORKSPACE\<session-id>\`; sessions
  older than `FITEVAL_SESSION_HOURS` (default 24) are removed at app start.
  For long-running services add a scheduled task that recycles the service
  (or deletes stale dirs) nightly.
- Updating: stop the service, `git pull` / copy the new code,
  `.venv\Scripts\pip install -e ".[app]"`, start the service.
