"""Zoom / numerical-output views, downloads, output housekeeping."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from dash import Input, Output, State, dcc, no_update

from fiteval_core.runner import delete_output_files

from ..session import session_dir
from .helpers import img_src, message


def register(app) -> None:

    def _view(state):
        return state["views"][state.get("current", "")]

    @app.callback(
        Output("zoom-modal", "is_open"),
        Output("zoom-figure", "src"),
        Input("zoom-open", "n_clicks"),
        State("run-state", "data"),
        prevent_initial_call=True,
    )
    def zoom(_n, state):
        if not state:
            return no_update, no_update
        return True, img_src(Path(_view(state)["png"]))

    @app.callback(
        Output("numout-modal", "is_open"),
        Output("numout-text", "children"),
        Input("numout-open", "n_clicks"),
        State("run-state", "data"),
        prevent_initial_call=True,
    )
    def numout(_n, state):
        if not state:
            return no_update, no_update
        return True, Path(_view(state)["txt"]).read_text()

    @app.callback(
        Output("about-modal", "is_open"),
        Input("about-open", "n_clicks"),
        prevent_initial_call=True,
    )
    def about(_n):
        return True

    @app.callback(
        Output("download-pdf", "data"),
        Input("download-pdf-btn", "n_clicks"),
        State("run-state", "data"),
        prevent_initial_call=True,
    )
    def download_pdf(_n, state):
        if not state:
            return no_update
        want = state["nproy"] + state.get("current", "") + ".pdf"
        pdf = [f for f in state["files"] if f.endswith(want)]
        if not pdf:
            pdf = [f for f in state["files"] if f.endswith(".pdf")]
        return dcc.send_file(pdf[0]) if pdf else no_update

    @app.callback(
        Output("download-zip", "data"),
        Input("download-zip-btn", "n_clicks"),
        State("run-state", "data"),
        prevent_initial_call=True,
    )
    def download_zip(_n, state):
        if not state:
            return no_update
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in state["files"]:
                p = Path(f)
                if p.exists():
                    zf.write(p, p.name)
        buf.seek(0)
        return dcc.send_bytes(buf.getvalue(),
                              filename=f"{state['nproy']}_results.zip")

    @app.callback(
        Output("message-bar", "children", allow_duplicate=True),
        Output("message-bar", "className", allow_duplicate=True),
        Output("run-state", "data", allow_duplicate=True),
        Output("zoom-open", "disabled", allow_duplicate=True),
        Output("numout-open", "disabled", allow_duplicate=True),
        Output("download-zip-btn", "disabled", allow_duplicate=True),
        Output("download-pdf-btn", "disabled", allow_duplicate=True),
        Input("delete-outputs", "n_clicks"),
        State("run-state", "data"),
        State("session-id", "data"),
        prevent_initial_call=True,
    )
    def delete_outputs(_n, state, sid):
        if not state:
            msg, cls = message("No output files to delete")
            return (msg, cls) + (no_update,) * 5
        n = delete_output_files(session_dir(sid), state["nproy"] + ".in")
        msg, cls = message(f"{n} output file(s) deleted "
                           f"(input .in and .err files kept)")
        return msg, cls, None, True, True, True, True
