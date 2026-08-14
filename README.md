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

### Local launch tips (macOS / Linux)

**Restarting.** `scripts/run_local.sh` refuses to start if port 8050 is
already taken, printing `Port 8050 is already in use` — usually a previous
instance still running in another terminal. Kill it and relaunch:

```bash
lsof -ti:8050 | xargs kill
./scripts/run_local.sh
```

**Safari on macOS.** If Safari reports

> Safari can't open the page "http://127.0.0.1:8050/" … Navigation failed
> because the request was for an HTTP URL with HTTPS-Only enabled
> (WebKitErrorDomain:305)

the server is running correctly — Safari's HTTPS-Only mode is refusing the
plain-HTTP loopback address before any connection is made. On Safari 26
(macOS 26) and later, open Safari → Settings (`Cmd+,`) → **Security** and
uncheck **"Warn before connecting to a website over HTTP"**. Alternatively,
open `http://127.0.0.1:8050` in another browser; Chrome and Firefox allow
loopback HTTP without changing any setting. To confirm the server itself is
healthy, this should print `200`:

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8050/
```

See `docs/deployment_windows.md` for Windows Server (NSSM service, IIS
reverse proxy) instructions and `docs/multiple_runs.md` for the batch
(multiple-runs) mode.

## Command-line reference

### `fiteval_core` — batch evaluation of one file

```bash
python -m fiteval_core INFILE [--multi] [--config PATH] [--ext FORMAT]
                              [--norep] [--text "..."] [--seed N]
```

Reads `[Yobs Yprd (Ybenchmark)]` from `INFILE` and writes `<name>_out.txt`,
`<name>_out.png` and `<name>.pdf` (plus the optional individual figures)
next to it — the same outputs as the desktop app. The numerical report is
also echoed to stdout.

| Argument | Default | Meaning |
|----------|---------|---------|
| `INFILE` (positional) | — | Input `.in` data file, whitespace-separated `[Yobs Yprd]` or `[Yobs Yprd Ybenchmark]` — or a batch list file with `--multi`. Required. |
| `--multi` | off | Treat `INFILE` as a multi-run **list file** (one `datafile [norep] [label] ; option` per line) and write `<list>_summary.csv` plus every per-run output into the list file's directory. See [Multiple runs](docs/multiple_runs.md). All referenced `.in`/`.err` files must sit next to the list file. |
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
python -m fiteval_core multi_run_test.txt --multi      # batch: <list>_summary.csv + all runs
```

Single-file mode covers deterministic runs; `--multi` runs a batch list
(including per-row measurement-uncertainty options) and writes the
two-section `<list>_summary.csv`. For interactive measurement-uncertainty on
a single file use the web GUI; the same methods are available
programmatically via `fiteval_core.runner.run_evaluation_unc` and
`fiteval_core.multirun.run_multi`.

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
- Phase 4 (done): golden-file validation against the desktop app on curated
  datasets (indices match to the printed decimals; bootstrap CIs
  statistically).

## Class-limit (threshold) scales

Class limits are entered in the **Configuration** dialog in the scale of the
selected main index, and are converted automatically when the index changes.
There are three distinct scales, and every conversion pivots through NSE
(e.g. KGE* → NSE → E1):

| Index | Conversion from NSE | Default limits |
|-------|---------------------|----------------|
| NSE | — (reference scale) | 0.65 / 0.80 / 0.90 |
| KGE*, KGE | `KGE = 1 - √2·(1 - √NSE)` | 0.73 / 0.85 / 0.93 |
| E1 | `E1 = 1 - √(1 - NSE)` | 0.41 / 0.55 / 0.68 |

E1 (Legates–McCabe) is built on absolute errors where NSE uses squared
errors, so the two are **not** on the same scale — the desktop app treats
them as equal, which understates the E1 thresholds; this port converts them.

## License

Copyright © 2011–2026 Axel Ritter and Rafael Muñoz-Carpena.

This work is licensed under a [Creative Commons
Attribution-NoDerivatives 4.0 International License (CC BY-ND
4.0)](https://creativecommons.org/licenses/by-nd/4.0/).

You are free to:

- **Share** — copy and redistribute the material in any medium or format for
  any purpose, even commercially.

The licensor cannot revoke these freedoms as long as you follow the license
terms.

Under the following terms:

- **Attribution** — You must give appropriate credit, provide a link to the
  license, and indicate if changes were made. You may do so in any reasonable
  manner, but not in any way that suggests the licensor endorses you or your
  use.
- **NoDerivatives** — If you remix, transform, or build upon the material,
  you may not distribute the modified material.
- **No additional restrictions** — You may not apply legal terms or
  technological measures that legally restrict others from doing anything the
  license permits.

Notices: You do not have to comply with the license for elements of the
material in the public domain or where your use is permitted by an applicable
exception or limitation. No warranties are given. The license may not give
you all of the permissions necessary for your intended use. For example,
other rights such as publicity, privacy, or moral rights may limit how you
use the material.

The full license text is available at
<https://creativecommons.org/licenses/by-nd/4.0/legalcode>.

### How to cite

> Ritter, A., and R. Muñoz-Carpena. 2013. Performance evaluation of
> hydrological models: Statistical significance for reducing subjectivity in
> goodness-of-fit assessments. *Journal of Hydrology* 480: 33–45.
> doi:[10.1016/j.jhydrol.2012.12.004](https://doi.org/10.1016/j.jhydrol.2012.12.004)
  
