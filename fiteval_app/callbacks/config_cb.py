"""Configuration modal callbacks (Configuration_Callback, L257-485)."""

from __future__ import annotations

from dash import Input, Output, State, no_update

from fiteval_core.config import check_class_limits
from fiteval_core.indices import (e1_to_nse_threshold, kge_to_nse_threshold,
                                  nse_to_e1_threshold, nse_to_kge_threshold)

from .helpers import cfg_from_store, cfg_to_store, message

# Threshold scales per main-index flag: NSE(1), KGE family(2,3), E1(4).
# Class limits are stored in the selected index's scale, so switching index
# converts them; NSE is the pivot for every conversion.
_SCALES = {1: "nse", 2: "kge", 3: "kge", 4: "e1"}


def _scale(flag) -> str:
    return _SCALES.get(int(flag or 1), "nse")


def _to_nse(value: float, flag) -> float:
    """Express a threshold given in flag's scale as an NSE threshold."""
    s = _scale(flag)
    if s == "kge":
        return kge_to_nse_threshold(value)
    if s == "e1":
        return e1_to_nse_threshold(value)
    return value


def _from_nse(nse_value: float, flag) -> float:
    """Express an NSE threshold in flag's scale."""
    s = _scale(flag)
    if s == "kge":
        return nse_to_kge_threshold(nse_value)
    if s == "e1":
        return nse_to_e1_threshold(nse_value)
    return nse_value


def register(app) -> None:

    @app.callback(
        Output("config-modal", "is_open"),
        Output("cfg-thr1", "value"), Output("cfg-thr2", "value"),
        Output("cfg-thr3", "value"), Output("cfg-bias", "value"),
        Output("cfg-bm", "value"), Output("cfg-resamples", "value"),
        Output("cfg-gof", "value"), Output("cfg-fontsize", "value"),
        Output("cfg-markersize", "value"), Output("cfg-mcolor", "value"),
        Output("cfg-msymbol", "value"), Output("cfg-dpi", "value"),
        Output("cfg-gof-prev", "data"),
        Input("config-open", "n_clicks"),
        State("cfg-store", "data"),
        prevent_initial_call=True,
    )
    def open_config(_n, store):
        cfg = cfg_from_store(store)
        gof = cfg.gof_index_effective
        return (True, round(cfg.class_lim[0], 2), round(cfg.class_lim[1], 2),
                round(cfg.class_lim[2], 2), cfg.bias_value, cfg.bstype,
                cfg.n_resamples, gof, cfg.font_size, cfg.marker_size,
                cfg.marker_color, cfg.marker_symbol, cfg.dpi, gof)

    @app.callback(
        Output("cfg-thr1", "value", allow_duplicate=True),
        Output("cfg-thr2", "value", allow_duplicate=True),
        Output("cfg-thr3", "value", allow_duplicate=True),
        Output("cfg-gof-prev", "data", allow_duplicate=True),
        Input("cfg-gof", "value"),
        State("cfg-gof-prev", "data"),
        State("cfg-thr1", "value"), State("cfg-thr2", "value"),
        State("cfg-thr3", "value"),
        prevent_initial_call=True,
    )
    def convert_thresholds(val, prev, t1, t2, t3):
        """Live threshold conversion when the main index changes.

        Extends GoFIndexSelection (L299-312) with the E1 scale: NSE, the
        KGE family (KGE*/KGE) and E1 are three distinct scales, so every
        conversion pivots through NSE (e.g. KGE* -> NSE -> E1).
        """
        if prev is None or val == prev:
            return no_update, no_update, no_update, val
        if _scale(prev) == _scale(val):      # e.g. KGE* -> KGE: same scale
            return no_update, no_update, no_update, val
        try:
            thr = [round(_from_nse(_to_nse(float(t), prev), val), 2)
                   for t in (t1, t2, t3)]
        except (TypeError, ValueError):
            return no_update, no_update, no_update, val
        return thr[0], thr[1], thr[2], val

    @app.callback(
        Output("config-modal", "is_open", allow_duplicate=True),
        Output("cfg-store", "data"),
        Output("cfg-error", "children"),
        Output("message-bar", "children", allow_duplicate=True),
        Output("message-bar", "className", allow_duplicate=True),
        Input("config-done", "n_clicks"),
        State("cfg-thr1", "value"), State("cfg-thr2", "value"),
        State("cfg-thr3", "value"), State("cfg-bias", "value"),
        State("cfg-bm", "value"), State("cfg-resamples", "value"),
        State("cfg-gof", "value"), State("cfg-fontsize", "value"),
        State("cfg-markersize", "value"), State("cfg-mcolor", "value"),
        State("cfg-msymbol", "value"), State("cfg-dpi", "value"),
        State("cfg-store", "data"),
        prevent_initial_call=True,
    )
    def save_config(_n, t1, t2, t3, bias, bm, resamples, gof, fontsize,
                    markersize, mcolor, msymbol, dpi, store):
        defaults = (0.65, 0.80, 0.90)
        thr = tuple(float(t) if t is not None else d
                    for t, d in zip((t1, t2, t3), defaults))
        err = check_class_limits(thr)
        if err:
            return no_update, no_update, err, no_update, no_update

        cfg = cfg_from_store(store)
        cfg.class_lim = thr
        cfg.bias_value = float(bias) if bias is not None else 5.0
        cfg.bstype = int(bm or 0)
        cfg.n_resamples = max(5000, int(resamples or 20000))
        cfg.gof_index = int(gof or 1)
        cfg.font_size = float(fontsize) if fontsize else 10.0
        cfg.marker_size = float(markersize) if markersize else 5.0
        cfg.marker = (mcolor or "b") + (msymbol or "o")
        cfg.dpi = max(72, int(dpi or 100))
        msg, cls = message("Configuration saved")
        return False, cfg_to_store(cfg), "", msg, cls
