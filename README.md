# FITEVAL web

Python web port of FITEVAL v3.0, the MATLAB desktop program for model
goodness-of-fit evaluation ((c) 2011 Axel Ritter & Rafael Muñoz-Carpena;
Ritter and Muñoz-Carpena, 2013, J. Hydrol. 480,
doi:10.1016/j.jhydrol.2012.12.004).

Two packages:

- `fiteval_core` — the computation engine (numpy/scipy/matplotlib only):
  NSE/KGE*/KGE/E1 + RMSE, 95% BCa bootstrap confidence intervals
  (Politis–Romano stationary block bootstrap or Efron IID), kernel-CDF fit
  classification, bias and Dixon-Q outlier diagnostics, desktop-compatible
  figures (4-panel PNG/PDF) and numerical reports.
- `fiteval_app` — the Dash web GUI mirroring the desktop layout: editable
  data table, file upload / paste, Run, zoom + numerical output views,
  configuration dialog, per-session workspaces, downloadable results.

## Quick start (development)

```bash
python -m venv .venv
.venv/bin/pip install -e ".[app,dev]"
.venv/bin/python -m fiteval_app.app        # http://127.0.0.1:8050
```

## Production serving

```bash
.venv/bin/python -m waitress --host=127.0.0.1 --port=8050 --threads=8 fiteval_app.wsgi:server
```

Runtime configuration is via environment variables (`FITEVAL_WORKSPACE`,
`FITEVAL_SESSION_HOURS`, `FITEVAL_URL_PREFIX`) — see the
[Command-line reference](#command-line-reference) below.

For a local single-user launch, use `scripts/run_local.sh` (macOS/Linux) or
`scripts/run_local.bat` (Windows) — each creates the virtual environment on
first run, starts waitress and opens the browser.

See `docs/deployment_windows.md` for Windows Server (NSSM service, IIS
reverse proxy) instructions and `docs/multiple_runs.md` for the batch
(multiple-runs) mode.

## Command-line reference

### `fiteval_core` — batch evaluation of one file

```bash
python -m fiteval_core INFILE [--config PATH] [--ext FORMAT]
                              [--norep] [--text "..."] [--seed N]
```

Reads `[Yobs Yprd (Ybenchmark)]` from `INFILE` and writes `<name>_out.txt`,
`<name>_out.png` and `<name>.pdf` (plus the optional individual figures)
next to it — the same outputs as the desktop app. The numerical report is
also echoed to stdout.

| Argument | Default | Meaning |
|----------|---------|---------|
| `INFILE` (positional) | — | Input `.in` data file, whitespace-separated `[Yobs Yprd]` or `[Yobs Yprd Ybenchmark]`. Required. |
| `--config PATH` | built-in defaults | `fitevalconfig.txt` to load (class limits, main index, bootstrap type / resamples, font, marker, **dpi**, …). Same 12-line format the GUI writes. |
| `--ext FORMAT` | *(none)* | Also save the individual panels (`<name>.<ext>`, `_cdf`, `_ds`, `_cb`) in this format. One of `pdf`, `png`, `jpg`, `eps`, `tif`. |
| `--norep` | off | Remove repeated `[Yprd Yobs]` cases before evaluating. |
| `--text "..."` | *(empty)* | Annotation text drawn on the scatter figure. |
| `--seed N` | random | RNG seed, for reproducible bootstrap confidence intervals. |

Examples:

```bash
python -m fiteval_core data_ex1.in                     # report + PNG/PDF
python -m fiteval_core data_ex1.in --ext png --seed 42 # + individual PNGs, reproducible
python -m fiteval_core data_ex3.in --norep --config fitevalconfig.txt
```

The CLI covers single-file, no-uncertainty runs. For measurement
uncertainty and batch (multiple-runs) mode, use the web GUI (uncertainty
methods are also available programmatically via
`fiteval_core.runner.run_evaluation_unc` and
`fiteval_core.multirun.run_multi`).

### `fiteval_app` — the Dash web GUI

Development server (Flask/Dash built-in, auto-reload):

```bash
python -m fiteval_app.app        # serves http://127.0.0.1:8050 with debug=True
```

Production server (waitress WSGI, `fiteval_app.wsgi:server` is the WSGI app):

```bash
python -m waitress --host=127.0.0.1 --port=8050 --threads=8 fiteval_app.wsgi:server
```

Neither entry point takes command-line flags; host/port/threads are
waitress options, and the application itself is configured through
environment variables:

| Variable | Default | Meaning |
|----------|---------|---------|
| `FITEVAL_WORKSPACE` | `<tempdir>/fiteval_workspace` | Root directory for per-session working directories (uploads, outputs). |
| `FITEVAL_SESSION_HOURS` | `24` | How long an idle session workspace is kept before the stale-session sweep removes it. |
| `FITEVAL_URL_PREFIX` | *(none)* | URL sub-path when hosted behind a reverse proxy, e.g. `/fiteval/` (sets Dash `requests_pathname_prefix`). Read by `fiteval_app.wsgi`. |

For a one-command local launch use `scripts/run_local.sh` (macOS/Linux) or
`scripts/run_local.bat` (Windows), which create the virtual environment on
first run, start waitress and open the browser.

## Tests

```bash
.venv/bin/python -m pytest
```

## Status / roadmap

- Phase 1 (done): core engine, single-run web GUI, configuration, outputs.
- Phase 2 (done): measurement-uncertainty methods — single PER, error-data
  file (per-point PER or lower/upper bound lengths), correction factors from
  Normal/Lognormal/Triangular/Uniform distributions (cases 9-14, Harmel et
  al. 2010) — with dual with/without-uncertainty outputs and a view toggle.
- Phase 3 (done): multi-run batch dialog (file + option rows, per-row logs,
  `<list>_summary.csv` in the desktop format, zip download); Windows
  deployment docs in `docs/deployment_windows.md`.
- Pending: golden-file validation against the desktop app on curated
  datasets (indices should match to the printed decimals; bootstrap CIs
  statistically).

### Relationship to the MATLAB source

The port is kept in sync with the current `FITEVAL_GUI.m`, including the
three corrected bugs (2026-07): the KGE*/NSE imbalance envelope now uses
NSE/KGE* (L3439), the BCa acceleration is computed per index rather than
pooled across the four (L4164), and the ρ/α timing/amplitude diagnostic
strings match (L3447-3452).

Remaining expected difference: bootstrap confidence intervals are
statistically (not bit-) equivalent to MATLAB because the RNG streams
differ.
