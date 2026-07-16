"""Multi-run batch dialog (desktop MR_fig menu)."""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dash_table, dcc, html

OPTION_HELP = (
    "Option: 0 = none; 0<value<1 = common PER; '1 file.err' / '2 file.err' "
    "= error-data file; '3 <case> oN 10 [pL 20]' / '4 <case> pN 10' = "
    "correction factors (N/L/T/U distributions). Add 'norep' and/or a "
    "figure label after the file name. You can also upload a list file "
    "(.txt/.cf), one 'datafile [norep] label ; option' per line, together "
    "with its data/error files to fill the table automatically "
    "(see docs/multiple_runs.md).")


def multirun_modal() -> dbc.Modal:
    table = dash_table.DataTable(
        id="mr-table",
        columns=[
            {"name": "File Name", "id": "file", "editable": True},
            {"name": "Option", "id": "option", "editable": True},
            {"name": "Logs", "id": "logs", "editable": False},
        ],
        data=[],
        row_deletable=True,
        style_table={"height": "300px", "overflowY": "auto"},
        style_cell={"textAlign": "left", "fontFamily": "monospace",
                    "fontSize": 13, "minWidth": 120},
        style_header={"fontWeight": "bold"},
        style_data_conditional=[
            {"if": {"filter_query": '{logs} contains "ERROR" || '
                                    '{logs} contains "not found"',
                    "column_id": "logs"},
             "color": "#a3142e", "fontWeight": "bold"},
        ],
    )
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Multiple runs")),
        dbc.ModalBody([
            html.Div(id="mr-active-cfg",
                     className="small fst-italic text-primary mb-2"),
            dbc.Row([
                dbc.Col(dcc.Upload(
                    id="mr-upload",
                    children=dbc.Button("Load list / data / error files…",
                                        size="sm", color="secondary",
                                        className="w-100"),
                    multiple=True), width=4),
                dbc.Col(dbc.Button("Add row", id="mr-add-row", size="sm",
                                   color="secondary", className="w-100"),
                        width=2),
                dbc.Col(dbc.Button("Clear", id="mr-clear", size="sm",
                                   color="secondary", className="w-100"),
                        width=2),
                dbc.Col(dbc.InputGroup([
                    dbc.InputGroupText("List", style={"fontSize": 12}),
                    dbc.Input(id="mr-listname", value="multi_run.cf",
                              size="sm"),
                ], size="sm"), width=4),
            ], className="g-1 mb-2"),
            table,
            html.Div(OPTION_HELP, className="text-muted small mt-2"),
            html.Div(id="mr-info", className="small mt-2"),
            dcc.Store(id="mr-state"),
            dcc.Download(id="mr-download-summary"),
            dcc.Download(id="mr-download-zip"),
        ]),
        dbc.ModalFooter([
            dbc.Button("Download summary CSV", id="mr-dl-summary-btn",
                       size="sm", color="secondary", disabled=True),
            dbc.Button("Download all results (zip)", id="mr-dl-zip-btn",
                       size="sm", color="secondary", disabled=True),
            dcc.Loading(dbc.Button("Run all", id="mr-run", size="sm",
                                   color="primary"), type="dot"),
        ]),
    ], id="multirun-modal", size="xl", is_open=False)
