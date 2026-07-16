"""Right panel: results figure, inspection views and downloads."""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dcc, html


def results_panel() -> dbc.Card:
    return dbc.Card(dbc.CardBody([
        html.Div(dbc.RadioItems(
            id="result-view",
            options=[{"label": "With uncertainty", "value": "U"},
                     {"label": "Without uncertainty", "value": ""}],
            value="U", inline=True, className="small"),
            id="result-view-box", style={"display": "none"}),
        dcc.Loading(
            html.Div(
                html.Img(id="result-figure", style={"width": "100%"}),
                id="result-figure-box"),
            type="default"),
        dbc.Row([
            dbc.Col(dbc.Button("Zoom figure", id="zoom-open", size="sm",
                               color="secondary", disabled=True,
                               className="w-100"), width=3),
            dbc.Col(dbc.Button("Numerical output", id="numout-open", size="sm",
                               color="secondary", disabled=True,
                               className="w-100"), width=3),
            dbc.Col(dbc.Button("Download results (zip)", id="download-zip-btn",
                               size="sm", color="secondary", disabled=True,
                               className="w-100"), width=3),
            dbc.Col(dbc.Button("Download PDF", id="download-pdf-btn",
                               size="sm", color="secondary", disabled=True,
                               className="w-100"), width=3),
        ], className="g-1 mt-2"),
        dcc.Download(id="download-zip"),
        dcc.Download(id="download-pdf"),
        dcc.Download(id="download-data"),
    ]), className="h-100")
