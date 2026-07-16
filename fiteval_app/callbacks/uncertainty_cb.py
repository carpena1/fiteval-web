"""Uncertainty panel callbacks: visibility, error-file upload, spec build."""

from __future__ import annotations

import numpy as np
from dash import Input, Output, State, no_update

from fiteval_core.dataio import DataError, parse_numeric_text
from fiteval_core.uncertainty import UncError, UncSpec

from .helpers import decode_upload, message

HIDE = {"display": "none"}
SHOW = {}


def spec_from_state(method, per, err_records, err_type,
                    obs_on, obs_dist, cvo, plubo, puubo,
                    prd_on, prd_dist, cvp, plubp, puubp) -> UncSpec:
    """Build an UncSpec from panel state; raises UncError on bad input
    (mirrors ChkUncParam, L1898-1926)."""
    if method == "per":
        if per is None or not (0 < float(per) < 1):
            raise UncError("PER must >0 and <1")
        return UncSpec(method="per", per=float(per))
    if method == "errfile":
        if not err_records:
            raise UncError("Load an error data file first!")
        err = np.asarray(err_records, dtype=float)
        if err.shape[1] != err_type:
            raise UncError(
                f"Column Nr. in Error Data ({err.shape[1]}) is different to "
                f"column Nr. required ({err_type})")
        return UncSpec(method="errfile", err_data=err)
    if method == "cf":
        spec = UncSpec(method="cf")
        if obs_on:
            if not obs_dist:
                raise UncError("Select Obs distribution!")
            spec.obs_dist = int(obs_dist)
            if obs_dist in (1, 2):
                if cvo is None or float(cvo) <= 0:
                    raise UncError("Invalid CVo(%) value!")
                spec.cvo = float(cvo)
            else:
                if plubo is None or puubo is None:
                    raise UncError("Invalid LUBo/UUBo(%) value!")
                spec.plubo, spec.puubo = float(plubo), float(puubo)
        if prd_on:
            if not prd_dist:
                raise UncError("Select Prd distribution!")
            spec.prd_dist = int(prd_dist)
            if prd_dist in (1, 2):
                if cvp is None or float(cvp) <= 0:
                    raise UncError("Invalid CVp(%) value!")
                spec.cvp = float(cvp)
            else:
                if plubp is None or puubp is None:
                    raise UncError("Invalid LUBp/UUBp(%) value!")
                spec.plubp, spec.puubp = float(plubp), float(puubp)
        if not obs_on and not prd_on:
            raise UncError("Select Obs and/or Prd uncertainty!")
        return spec
    raise UncError("Select an uncertainty method")


def register(app) -> None:

    @app.callback(
        Output("unc-collapse", "is_open"),
        Output("unc-open", "color"),
        Input("unc-open", "n_clicks"),
        State("unc-collapse", "is_open"),
        prevent_initial_call=True,
    )
    def toggle_panel(_n, is_open):
        new = not is_open
        return new, ("info" if new else "secondary")

    @app.callback(
        Output("unc-per-block", "style"),
        Output("unc-err-block", "style"),
        Output("unc-cf-block", "style"),
        Input("unc-method", "value"),
    )
    def method_blocks(method):
        return (SHOW if method == "per" else HIDE,
                SHOW if method == "errfile" else HIDE,
                SHOW if method == "cf" else HIDE)

    for prefix in ("obs", "prd"):
        @app.callback(
            Output(f"unc-{prefix}-cv-group", "style"),
            Output(f"unc-{prefix}-bounds-row", "style"),
            Input(f"unc-{prefix}-dist", "value"),
            Input(f"unc-{prefix}-on", "value"),
        )
        def dist_fields(dist, on):
            if not on or not dist:
                return HIDE, HIDE
            if dist in (1, 2):        # Normal / Lognormal -> CV(%)
                return SHOW, HIDE
            return HIDE, SHOW         # Triangular / Uniform -> LUB/UUB(%)

    @app.callback(
        Output("unc-err-store", "data"),
        Output("unc-err-info", "children"),
        Output("unc-err-type", "value"),
        Output("message-bar", "children", allow_duplicate=True),
        Output("message-bar", "className", allow_duplicate=True),
        Input("unc-err-upload", "contents"),
        State("unc-err-upload", "filename"),
        prevent_initial_call=True,
    )
    def load_err_file(contents, fname):
        try:
            err = parse_numeric_text(decode_upload(contents))
        except DataError as exc:
            msg, cls = message(f"Error in loading Error Data file! ({exc})",
                               error=True)
            return no_update, no_update, no_update, msg, cls
        if err.shape[1] not in (1, 2):
            msg, cls = message("Error data must have 1 (PER) or 2 (bounds) "
                               "columns!", error=True)
            return no_update, no_update, no_update, msg, cls
        info = f"{fname}: {err.shape[0]} rows x {err.shape[1]} col(s)"
        msg, cls = message(f"Error data loaded from {fname}")
        return err.tolist(), info, err.shape[1], msg, cls
