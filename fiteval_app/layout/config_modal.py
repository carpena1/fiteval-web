"""Configuration dialog (Configuration_Callback, FITEVAL_GUI.m L257-485)."""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dcc, html

from fiteval_core.config import MARKER_COLORS, MARKER_SYMBOLS

GOF_OPTIONS = [{"label": "NSE", "value": 1}, {"label": "KGE*", "value": 2},
               {"label": "KGE", "value": 3}, {"label": "E1", "value": 4}]
BM_OPTIONS = [{"label": "Block bootstrapping", "value": 0},
              {"label": "Efron's bootstrapping", "value": 1}]


def _num_row(id_: str, label: str, step: float = 0.01) -> dbc.Row:
    return dbc.Row([
        dbc.Col(dbc.Input(id=id_, type="number", size="sm", step=step),
                width=4),
        dbc.Col(dbc.Label(label, className="small mb-0"), width=8),
    ], className="g-1 mb-1 align-items-center")


def config_modal() -> dbc.Modal:
    body = [
        _num_row("cfg-thr1", "Acceptable GoF index threshold value"),
        _num_row("cfg-thr2", "Good GoF index threshold value"),
        _num_row("cfg-thr3", "Very good GoF index threshold value"),
        _num_row("cfg-bias", "BiasValue (%)", step=0.1),
        dbc.Row([
            dbc.Col(dcc.Dropdown(id="cfg-bm", options=BM_OPTIONS,
                                 clearable=False, style={"fontSize": 13}),
                    width=6),
            dbc.Col(dbc.InputGroup([
                dbc.InputGroupText("Resamples", style={"fontSize": 12}),
                dbc.Input(id="cfg-resamples", type="number", size="sm",
                          min=5000, step=1000),
            ], size="sm"), width=6),
        ], className="g-1 mb-1"),
        dbc.Row([
            dbc.Col(dcc.Dropdown(id="cfg-gof", options=GOF_OPTIONS,
                                 clearable=False, style={"fontSize": 13}),
                    width=6),
            dbc.Col(dbc.Label("Main GoF index", className="small mb-0"),
                    width=6),
        ], className="g-1 mb-1 align-items-center"),
        _num_row("cfg-fontsize", "Font size value", step=1),
        _num_row("cfg-markersize", "Series marker size", step=1),
        dbc.Row([
            dbc.Col(dcc.Dropdown(
                id="cfg-mcolor",
                options=[{"label": c, "value": c} for c in MARKER_COLORS],
                clearable=False, style={"fontSize": 13}), width=3),
            dbc.Col(dbc.Label("Series marker color", className="small mb-0"),
                    width=9),
        ], className="g-1 mb-1 align-items-center"),
        dbc.Row([
            dbc.Col(dcc.Dropdown(
                id="cfg-msymbol",
                options=[{"label": s, "value": s} for s in MARKER_SYMBOLS],
                clearable=False, style={"fontSize": 13}), width=3),
            dbc.Col(dbc.Label("Series marker symbol", className="small mb-0"),
                    width=9),
        ], className="g-1 mb-1 align-items-center"),
        _num_row("cfg-dpi", "Resolution of figures (dpi)", step=1),
        html.Div(id="cfg-error", className="text-danger small mt-2"),
        dcc.Store(id="cfg-gof-prev"),
    ]
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Configuration parameters")),
        dbc.ModalBody(body),
        dbc.ModalFooter(dbc.Button("Done", id="config-done", color="primary",
                                   size="sm")),
    ], id="config-modal", is_open=False)
