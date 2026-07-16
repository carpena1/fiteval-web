"""Left panel: data input table and run controls."""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dash_table, dcc, html

FIG_EXT_OPTIONS = [{"label": "(none)", "value": ""}] + [
    {"label": e, "value": e} for e in ("pdf", "png", "jpg", "eps", "tif")]


def data_panel() -> dbc.Card:
    table = dash_table.DataTable(
        id="data-table",
        columns=[{"name": "Yprd", "id": "c0", "type": "numeric"},
                 {"name": "Yobs", "id": "c1", "type": "numeric"}],
        data=[],
        editable=True,
        row_deletable=True,
        virtualization=True,
        fixed_rows={"headers": True},
        style_table={"height": "320px", "overflowY": "auto"},
        style_cell={"textAlign": "right", "fontFamily": "monospace",
                    "fontSize": 13, "minWidth": 70},
        style_header={"fontWeight": "bold", "textAlign": "center"},
    )

    return dbc.Card(dbc.CardBody([
        dbc.Row([
            dbc.Col(dcc.Upload(
                id="upload-data",
                children=dbc.Button("Open file…", size="sm",
                                    color="secondary", className="w-100"),
                multiple=False), width=4),
            dbc.Col(dbc.Button("Paste values", id="paste-open", size="sm",
                               color="secondary", className="w-100"), width=4),
            dbc.Col(dbc.Button("Clear data", id="clear-data", size="sm",
                               color="secondary", className="w-100"), width=4),
        ], className="g-1 mb-2"),
        dbc.Row([
            dbc.Col(dbc.InputGroup([
                dbc.InputGroupText("Input file", style={"fontSize": 12}),
                dbc.Input(id="input-filename", value="", size="sm",
                          placeholder="data.in"),
            ], size="sm"), width=8),
            dbc.Col(dbc.Button("Save data", id="save-data", size="sm",
                               color="secondary", className="w-100"), width=4),
        ], className="g-1 mb-2"),
        table,
        html.Div(id="table-info", className="text-muted small mt-1"),
        dbc.Checkbox(id="no-repeated", value=False,
                     label="Remove repeated [Yprd Yobs] cases",
                     className="mt-2 small"),
        dbc.Row([
            dbc.Col(dbc.InputGroup([
                dbc.InputGroupText("Add text to plot", style={"fontSize": 12}),
                dbc.Input(id="fig-text", value="", size="sm"),
            ], size="sm"), width=8),
            dbc.Col(dcc.Dropdown(id="fig-ext", options=FIG_EXT_OPTIONS,
                                 value="", clearable=False,
                                 style={"fontSize": 13}), width=4),
        ], className="g-1 mt-2 align-items-center"),
        html.Hr(className="my-2"),
        dbc.Row([
            dbc.Col(dbc.Button("Uncertainty options", id="unc-open",
                               size="sm", color="secondary",
                               className="w-100"), width=6),
            dbc.Col(dbc.Button("Multiple runs", id="multirun-open",
                               size="sm", color="secondary",
                               className="w-100"), width=6),
        ], className="g-1 mb-2"),
        dbc.Row([
            dbc.Col(dbc.Button("Configuration", id="config-open", size="sm",
                               color="secondary", className="w-100"), width=6),
            dbc.Col(dbc.Button("Delete output files", id="delete-outputs",
                               size="sm", color="secondary",
                               className="w-100"), width=6),
        ], className="g-1 mb-2"),
        dbc.Button("RUN", id="run-btn", color="primary",
                   className="w-100 fw-bold"),
    ]), className="h-100")
