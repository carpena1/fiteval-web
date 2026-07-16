"""Multi-run modal callbacks."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from dash import Input, Output, State, ctx, dcc, html, no_update

from fiteval_core.indices import INDEX_LABELS
from fiteval_core.multirun import parse_file_field, parse_list_file, run_multi

from ..session import session_dir
from .helpers import cfg_from_store, decode_upload

LIST_EXTS = (".txt", ".cf", ".mr", ".lst")


def _needed_files(rows: list[dict]) -> list[str]:
    """Data (.in) and error (.err) file names referenced by the run rows."""
    needed: list[str] = []
    for r in rows:
        field = (r.get("file") or "").strip()
        if not field:
            continue
        try:
            fname, _, _ = parse_file_field(field)
            if fname not in needed:
                needed.append(fname)
        except Exception:
            continue
        parts = (r.get("option") or "").split()
        if len(parts) > 1 and parts[0] in ("1", "2"):
            if parts[1] not in needed:
                needed.append(parts[1])
    return needed


def _missing_files(rows: list[dict], wdir: Path) -> list[str]:
    return [n for n in _needed_files(rows) if not (wdir / n).is_file()]


def register(app) -> None:

    @app.callback(
        Output("multirun-modal", "is_open"),
        Output("mr-active-cfg", "children"),
        Input("multirun-open", "n_clicks"),
        State("cfg-store", "data"),
        prevent_initial_call=True,
    )
    def open_modal(_n, cfg_store):
        cfg = cfg_from_store(cfg_store)
        idx = INDEX_LABELS[cfg.gof_index_effective].replace("E_1", "E1")
        thr = ", ".join(f"{t:g}" for t in cfg.class_lim)
        note = ""
        if cfg.gof_index_effective in (2, 3):
            note = (f" Note: uncertainty rows are evaluated with NSE instead "
                    f"of {idx} (uncertainty methods are defined on NSE); their "
                    f"results appear in the 'With Unc.' columns of the summary.")
        return True, (f"Runs use the current Configuration — main index: "
                      f"{idx}; class limits: {thr}. Change it in "
                      f"Configuration (click Done to save) before running."
                      + note)

    @app.callback(
        Output("mr-table", "data"),
        Output("mr-info", "children"),
        Input("mr-upload", "contents"),
        Input("mr-add-row", "n_clicks"),
        Input("mr-clear", "n_clicks"),
        State("mr-upload", "filename"),
        State("mr-table", "data"),
        State("session-id", "data"),
        prevent_initial_call=True,
    )
    def manage_rows(contents, _add, _clear, filenames, rows, sid):
        trig = ctx.triggered_id
        rows = rows or []
        if trig == "mr-clear":
            return [], ""
        if trig == "mr-add-row":
            return rows + [{"file": "", "option": "0", "logs": ""}], no_update
        if trig == "mr-upload" and contents:
            wdir = session_dir(sid)
            saved = 0
            list_rows: list[dict] = []
            data_files: list[str] = []
            for content, fname in zip(contents, filenames):
                name = Path(fname).name
                text = decode_upload(content)
                (wdir / name).write_text(text)
                saved += 1
                if name.lower().endswith(LIST_EXTS):
                    list_rows += [{"file": f, "option": o, "logs": ""}
                                  for f, o in parse_list_file(text)]
                else:
                    data_files.append(name)

            if list_rows:
                # a list file defines the whole run; its data/error files
                # must be uploaded too (the web app has no folder access)
                loaded = (f"{saved} file(s) uploaded, "
                          f"{len(list_rows)} run(s) loaded from list")
                missing = _missing_files(list_rows, wdir)
                if missing:
                    return list_rows, html.Span(
                        loaded + " — still need the data/error file(s): "
                        + ", ".join(missing) + ". Upload them with the same "
                        "button, then Run all.", className="msg-error")
                return list_rows, html.Span(loaded, className="msg-info")
            existing = {r["file"].split()[0] for r in rows if r.get("file")}
            added = 0
            for name in data_files:
                if not name.endswith(".err") and name not in existing:
                    rows.append({"file": name, "option": "0", "logs": ""})
                    added += 1
            return rows, (f"{saved} file(s) uploaded, {added} run row(s) added")
        return no_update, no_update

    @app.callback(
        Output("mr-table", "data", allow_duplicate=True),
        Output("mr-state", "data"),
        Output("mr-info", "children", allow_duplicate=True),
        Output("mr-dl-summary-btn", "disabled"),
        Output("mr-dl-zip-btn", "disabled"),
        Input("mr-run", "n_clicks"),
        State("mr-table", "data"),
        State("mr-listname", "value"),
        State("cfg-store", "data"),
        State("session-id", "data"),
        prevent_initial_call=True,
        running=[(Output("mr-run", "disabled"), True, False)],
    )
    def run_all(_n, rows, listname, cfg_store, sid):
        rows = [r for r in (rows or []) if (r.get("file") or "").strip()]
        if not rows:
            return no_update, no_update, html.Span(
                "First, load data", className="msg-error"), True, True
        cfg = cfg_from_store(cfg_store)
        wdir = session_dir(sid)
        missing = _missing_files(rows, wdir)
        if missing:
            return no_update, no_update, html.Span(
                "Cannot run — these data/error file(s) are not uploaded: "
                + ", ".join(missing) + ". Use the Load button to upload them "
                "(select them together with, or after, the list file).",
                className="msg-error"), True, True
        out = run_multi([(r["file"], r.get("option") or "0") for r in rows],
                        wdir, cfg, listname or "multi_run.cf")
        for r, log in zip(rows, out.logs):
            r["logs"] = log
        state = None
        info: object = "Run finished with errors — see the Logs column"
        ok = out.summary_path is not None
        if ok:
            state = {"summary": str(out.summary_path),
                     "files": sorted({str(f) for f in out.files})}
            info = html.Span(
                f"Numerical output saved in file {out.summary_path.name}",
                className="msg-info")
        return rows, state, info, not ok, not ok

    @app.callback(
        Output("mr-download-summary", "data"),
        Input("mr-dl-summary-btn", "n_clicks"),
        State("mr-state", "data"),
        prevent_initial_call=True,
    )
    def dl_summary(_n, state):
        if not state:
            return no_update
        return dcc.send_file(state["summary"])

    @app.callback(
        Output("mr-download-zip", "data"),
        Input("mr-dl-zip-btn", "n_clicks"),
        State("mr-state", "data"),
        prevent_initial_call=True,
    )
    def dl_zip(_n, state):
        if not state:
            return no_update
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in state["files"]:
                p = Path(f)
                if p.exists():
                    zf.write(p, p.name)
        buf.seek(0)
        return dcc.send_bytes(buf.getvalue(), filename="multirun_results.zip")
