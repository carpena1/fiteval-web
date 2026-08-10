# FITEVAL web — security review

Pre-deployment review of the web application (`fiteval_app` + `fiteval_core`),
focused on code injection, path traversal, file disclosure and denial of
service. This document records what was found, how each item was fixed, and
the hardening still expected of the deployment environment.

## Summary

No classic code-injection vectors are present: there is no `eval`, `exec`,
`pickle`, `subprocess`, `os.system`, `shell=True` or `yaml.load` anywhere in
the codebase, no XML parsing (no XXE), and no archive *extraction* (no
zip-slip). The application does not execute or interpret user input.

The risk class that did apply is **client-controlled filesystem paths**. Dash
`dcc.Store` values are held in the browser and sent back to the server as
callback inputs, so any value read out of a store is attacker-controlled.
Several callbacks used store values (absolute file paths, filenames, project
names) directly as arguments to `read_text()`, `send_file()`, `write_text()`
and `open()` without confining them to the caller's session workspace. A
second group of issues let a single request request unbounded CPU/memory.

All items below have been fixed in code. Severities reflect the realistic
deployment (an authenticated, trusted-LAN Windows VM); on an app exposed
beyond a trusted network the file read/write items would be critical.

## Findings and fixes

### HIGH-1 — Arbitrary file read / download via client-controlled state

`run-state` and `mr-state` are in-memory `dcc.Store`s whose contents can be
edited in the browser. Callbacks used absolute paths taken straight from them:
`numout` (`read_text`), `zoom` and `switch_view` (`img_src` reads bytes),
`download_pdf` / `download_zip`, and the multi-run `dl_summary` / `dl_zip`.
Setting a store's path to `/etc/passwd` (or a Windows config file) made the
server read and return it.

**Fix.** A new helper `session_file(session_id, name)`
(`fiteval_app/session.py`) reduces any reference to its basename and verifies
the result sits directly inside the caller's session directory. Every
view/download callback now rebuilds paths through it and ignores anything that
resolves elsewhere or does not exist. Because all workspace outputs are flat
files in the session directory, this is behaviour-preserving for legitimate
use.

### HIGH-2 — Path traversal on write via the input filename

The `input-filename` field flowed unsanitized into
`write_in_file(data, wdir / name)` and into the output-file stem, so a name
like `../../../../tmp/evil` wrote outside the workspace and could create or
overwrite files and fill the disk.

**Fix.** The run callback now applies `Path(name).name` before use, confining
the write (and every derived output file) to the session directory. The
per-output "delete" action similarly reduces the client-supplied project stem
to its basename before globbing.

### MED-1 — Path traversal on read via multi-run list files

Multi-run rows can come from an uploaded list file. Data- and error-file names
parsed from it were joined as `workspace / name` with no sanitization, so a
list line such as `../../../../etc/passwd` was read by the engine (a limited
oracle, since the numeric parser echoes offending lines in the Logs column).

**Fix.** A core helper `safe_join(directory, name)`
(`fiteval_core/dataio.py`) performs the same basename + containment check and
is now used for every list-file data/error path, the summary-file path, and
the app-side "missing files" pre-check and upload writes. The uploaded-file
path was already basename-only; it now goes through `safe_join` too for
defence in depth.

### MED-2 — Unbounded compute / memory (denial of service)

`n_resamples` and figure `dpi` were floor-clamped only, so a crafted
configuration (the config store is client-controlled) could request a
billion-resample bootstrap or an enormous matplotlib canvas. There was no
request-size limit and no cap on multi-run batch size.

**Fix.** `FitevalConfig.validated()` now enforces upper bounds
(`MAX_RESAMPLES = 100000`, `MAX_DPI = 600`, plus marker/font caps), and
`cfg_from_store` calls `validated()` so every client-supplied configuration is
clamped before use — not just values entered through the dialog. The
Configuration dialog clamps to the same constants. A 32 MB request-body limit
(`MAX_CONTENT_LENGTH`) is set on the Flask server, and multi-run batches are
capped at 500 rows.

### LOW — session-id character set

`session_dir` accepted any `str.isalnum()` id, which includes Unicode letters
and digits, allowing odd (though non-traversing) workspace directory names.
The guard now also requires `isascii()`, restricting ids to `[0-9A-Za-z]`.
Session ids are server-generated `uuid4` hex; there is no server-side binding
of a session id to a browser, which is acceptable only behind authentication
(see below).

### Reviewed, no change needed

- **XSS.** Numerical output and status messages render as Dash `children`
  strings, which React escapes; no HTML sink was found.
- **Debug mode.** `debug=True` exists only in the `__main__` development path,
  not in `fiteval_app.wsgi`. Keep it that way — never serve the dev server.

## Deployment responsibilities (not code)

The application has **no authentication of its own** — anyone who can reach the
port can use it. Two environment controls are required:

1. **Do not expose the app directly.** Run waitress bound to `127.0.0.1` and
   put IIS (ARR reverse proxy) in front — option 3 in
   `deployment_windows.md`. Avoid the `--host=0.0.0.0` standalone binding for
   anything beyond a single-machine test.
2. **Put access control in front.** If the app is reachable by more than a
   trusted LAN, require authentication at IIS (Windows Authentication or UF
   SSO). Without it, the session isolation above still holds per browser
   session, but any user can start Runs and consume resources.

Operational notes: keep `FITEVAL_WORKSPACE` on a volume with quota, keep
`FITEVAL_SESSION_HOURS` short and let the startup sweep (or a nightly service
recycle) reclaim stale session directories, and serve over HTTPS at the IIS
tier.

## Verifying the fixes

```bash
.venv/bin/python -m pytest        # full suite (unchanged behaviour)
```

The guard functions can be checked directly: `session_file` and `safe_join`
reduce `../../etc/passwd` and `/etc/passwd` to a basename inside the session
directory (so the read/write simply misses and fails safely) and reject `''`,
`.` and `..`; `FitevalConfig(n_resamples=10**9, dpi=100000).validated()`
returns the clamped `100000` / `600`.
