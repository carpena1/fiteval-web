"""Collapsible uncertainty-options panel (desktop UncertaintyGroup)."""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dcc, html

DIST_OPTIONS = [
    {"label": "(none)", "value": 0},
    {"label": "Normal", "value": 1},
    {"label": "Lognormal", "value": 2},
    {"label": "Triangular", "value": 3},
    {"label": "Uniform", "value": 4},
]


def _dist_block(prefix: str, title: str) -> html.Div:
    """One Obs/Prd uncertainty sub-block of the CF method."""
    return html.Div([
        dbc.Switch(id=f"unc-{prefix}-on", label=title, value=False,
                   className="small"),
        dbc.Row([
            dbc.Col(dcc.Dropdown(id=f"unc-{prefix}-dist", options=DIST_OPTIONS,
                                 value=0, clearable=False,
                                 style={"fontSize": 13}), width=5),
            dbc.Col(dbc.InputGroup([
                dbc.InputGroupText(f"CV{prefix[0]}(%)=",
                                   id=f"unc-{prefix}-cv-label",
                                   style={"fontSize": 12}),
                dbc.Input(id=f"unc-{prefix}-cv", type="number", size="sm",
                          min=0, step=0.1),
            ], size="sm", id=f"unc-{prefix}-cv-group"), width=7),
        ], className="g-1 align-items-center"),
        dbc.Row([
            dbc.Col(dbc.InputGroup([
                dbc.InputGroupText(f"LUB{prefix[0]}(%)=",
                                   style={"fontSize": 12}),
                dbc.Input(id=f"unc-{prefix}-lub", type="number", size="sm",
                          min=0, step=0.1),
            ], size="sm"), width=6),
            dbc.Col(dbc.InputGroup([
                dbc.InputGroupText(f"UUB{prefix[0]}(%)=",
                                   style={"fontSize": 12}),
                dbc.Input(id=f"unc-{prefix}-uub", type="number", size="sm",
                          min=0, step=0.1),
            ], size="sm"), width=6),
        ], className="g-1 mt-1", id=f"unc-{prefix}-bounds-row"),
    ], id=f"unc-{prefix}-block", className="border rounded p-2 mb-2")


def uncertainty_panel() -> dbc.Collapse:
    per_block = html.Div([
        dbc.InputGroup([
            dbc.InputGroupText("PER =", style={"fontSize": 12}),
            dbc.Input(id="unc-per", type="number", size="sm", min=0, max=1,
                      step=0.01, placeholder="0 < PER < 1"),
        ], size="sm", style={"maxWidth": "260px"}),
        html.Div("Probable error range, fraction of each observation "
                 "(Harmel et al. 2007)", className="text-muted small mt-1"),
    ], id="unc-per-block")

    err_block = html.Div([
        dbc.Row([
            dbc.Col(dcc.Upload(
                id="unc-err-upload",
                children=dbc.Button("Load error data file…", size="sm",
                                    color="secondary", className="w-100"),
                multiple=False), width=6),
            dbc.Col(html.Div(id="unc-err-info",
                             className="small text-muted"), width=6),
        ], className="g-1 align-items-center"),
        dbc.RadioItems(
            id="unc-err-type",
            options=[{"label": "PER values (1 column)", "value": 1},
                     {"label": "Boundaries: lower/upper error lengths "
                               "(2 columns)", "value": 2}],
            value=1, className="small mt-1"),
    ], id="unc-err-block")

    cf_block = html.Div([
        _dist_block("obs", "Observation uncertainty"),
        _dist_block("prd", "Prediction (model) uncertainty"),
        html.Div("Correction factors from probability distributions "
                 "(Harmel et al. 2010)", className="text-muted small"),
    ], id="unc-cf-block")

    return dbc.Collapse(dbc.Card(dbc.CardBody([
        html.H6("Uncertainty options", className="mb-2"),
        dbc.RadioItems(
            id="unc-method",
            options=[
                {"label": "Single PER (common to all observations)",
                 "value": "per"},
                {"label": "Error data file (specific to each observation)",
                 "value": "errfile"},
                {"label": "Correction factors (CF) from distributions",
                 "value": "cf"},
            ],
            value="per", className="small mb-2"),
        per_block, err_block, cf_block,
        dcc.Store(id="unc-err-store"),
    ]), className="mt-2"), id="unc-collapse", is_open=False)
