"""Run button: evaluate the table data and render outputs."""

from __future__ import annotations

from pathlib import Path

from dash import Input, Output, State, no_update

from fiteval_core.bootstrap import BootstrapError
from fiteval_core.dataio import DataError, swap_first_two, write_in_file
from fiteval_core.engine import EngineError
from fiteval_core.runner import run_evaluation, run_evaluation_unc
from fiteval_core.uncertainty import UncError

from ..session import session_dir
from .helpers import cfg_from_store, img_src, message, records_to_array
from .uncertainty_cb import spec_from_state


def register(app) -> None:

    @app.callback(
        Output("result-figure", "src"),
        Output("run-state", "data"),
        Output("result-view-box", "style"),
        Output("result-view", "value"),
        Output("zoom-open", "disabled"),
        Output("numout-open", "disabled"),
        Output("download-zip-btn", "disabled"),
        Output("download-pdf-btn", "disabled"),
        Output("message-bar", "children", allow_duplicate=True),
        Output("message-bar", "className", allow_duplicate=True),
        Input("run-btn", "n_clicks"),
        State("data-table", "data"),
        State("cfg-store", "data"),
        State("project-name", "data"),
        State("input-filename", "value"),
        State("no-repeated", "value"),
        State("fig-text", "value"),
        State("fig-ext", "value"),
        State("session-id", "data"),
        State("unc-collapse", "is_open"),
        State("unc-method", "value"),
        State("unc-per", "value"),
        State("unc-err-store", "data"),
        State("unc-err-type", "value"),
        State("unc-obs-on", "value"),
        State("unc-obs-dist", "value"),
        State("unc-obs-cv", "value"),
        State("unc-obs-lub", "value"),
        State("unc-obs-uub", "value"),
        State("unc-prd-on", "value"),
        State("unc-prd-dist", "value"),
        State("unc-prd-cv", "value"),
        State("unc-prd-lub", "value"),
        State("unc-prd-uub", "value"),
        prevent_initial_call=True,
        running=[(Output("run-btn", "disabled"), True, False)],
    )
    def run(_n, records, cfg_store, project, fname, norep, figtext, figext,
            sid, unc_open, unc_method, unc_per, err_data, err_type,
            obs_on, obs_dist, cvo, plubo, puubo,
            prd_on, prd_dist, cvp, plubp, puubp):
        err_out = (no_update,) * 8

        try:
            table = records_to_array(records)
        except DataError:
            msg, cls = message("Load [Yprd Yobs] data first!", error=True)
            return err_out + (msg, cls)

        cfg = cfg_from_store(cfg_store)
        name = (fname or project or "clipboard_1.in").strip()
        if "." not in name:
            name += ".in"
        wdir = session_dir(sid)
        data = swap_first_two(table)  # engine wants observed-first

        try:
            write_in_file(data, wdir / name)  # desktop rewrites the input file
            if unc_open:
                spec = spec_from_state(unc_method, unc_per, err_data, err_type,
                                       obs_on, obs_dist, cvo, plubo, puubo,
                                       prd_on, prd_dist, cvp, plubp, puubp)
                art_u, art_p = run_evaluation_unc(
                    data, spec, name, wdir, cfg, no_repeated=bool(norep),
                    fig_ext=figext or "", fig_text=figtext or "")
            else:
                art_u = None
                art_p = run_evaluation(data, name, wdir, cfg,
                                       no_repeated=bool(norep),
                                       fig_ext=figext or "",
                                       fig_text=figtext or "")
        except (EngineError, BootstrapError, DataError, UncError,
                ValueError) as exc:
            msg, cls = message(str(exc), error=True)
            return err_out + (msg, cls)

        views = {"": {"png": str(art_p.combined_png),
                      "txt": str(art_p.report_txt)}}
        files = [str(f) for f in art_p.files] + [str(wdir / name)]
        if art_u is not None:
            views["U"] = {"png": str(art_u.combined_png),
                          "txt": str(art_u.report_txt)}
            files = [str(f) for f in art_u.files] + files

        show = art_u.result if art_u is not None else art_p.result
        current = "U" if art_u is not None else ""
        state = {"nproy": name.rsplit(".", 1)[0], "views": views,
                 "current": current, "files": files}

        note = ""
        if show.repeated_cases:
            note = f" — {show.repeated_cases} repeated case(s) removed"
        if art_u is not None:
            note += " — evaluation includes uncertainty"
        msg, cls = message(
            f"{show.index_label} = {show.main_idx:.3f} "
            f"[{show.main_ci[0]:.3f} – {show.main_ci[1]:.3f}] — "
            f"{show.rating_text}{note}")
        view_style = {} if art_u is not None else {"display": "none"}
        png = views[current]["png"]
        return (img_src(Path(png)), state, view_style, current,
                False, False, False, False, msg, cls)

    @app.callback(
        Output("result-figure", "src", allow_duplicate=True),
        Output("run-state", "data", allow_duplicate=True),
        Input("result-view", "value"),
        State("run-state", "data"),
        prevent_initial_call=True,
    )
    def switch_view(view, state):
        if not state or view not in state.get("views", {}):
            return no_update, no_update
        state["current"] = view
        return img_src(Path(state["views"][view]["png"])), state
