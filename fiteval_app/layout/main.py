"""Page skeleton: header, two panels, message bar, modals, stores."""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dcc, html

from ..session import new_session_id
from .config_modal import config_modal
from .data_panel import data_panel
from .multirun_modal import multirun_modal
from .results_panel import results_panel
from .uncertainty_panel import uncertainty_panel

ABOUT_LINES = [
    "PROGRAM FOR MODEL GOODNESS-OF-FIT EVALUATION",
    "v4.0 (web)",
    "(c)2011 - Axel Ritter & Rafael Muñoz-Carpena",
    "Universidad de La Laguna & University of Florida",
    "aritter@ull.es & carpena@ufl.edu",
]
REFERENCES = [
    ("Ritter and Mu\N{LATIN SMALL LETTER N WITH TILDE}oz-Carpena. 2013. "
     "J. Hydrol. 480, doi:10.1016/j.jhydrol.2012.12.004",
     "https://doi.org/10.1016/j.jhydrol.2012.12.004"),
    ("Ritter and Mu\N{LATIN SMALL LETTER N WITH TILDE}oz-Carpena. 2026. "
     "Env. Mod. & Softw. 107239. doi: 10.1016/j.envsoft.2026.107239",
     "https://doi.org/10.1016/j.envsoft.2026.107239"),
]
HELP_URL = "https://abe.ufl.edu/carpena/software/fiteval/"


def _about_modal() -> dbc.Modal:
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("About FITEVAL")),
        dbc.ModalBody([
            html.Img(src="/assets/Logo2_FITEVAL.png",
                     style={"maxWidth": "160px", "display": "block",
                            "margin": "0 auto 12px"}),
            *[html.P(t, className="mb-1 text-center small")
              for t in ABOUT_LINES],
            html.P("References:", className="text-center small mt-2 mb-1"),
            *[html.P(html.A(text, href=url, target="_blank"),
                     className="text-center small mb-1")
              for text, url in REFERENCES],
        ]),
    ], id="about-modal", is_open=False)


def _paste_modal() -> dbc.Modal:
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Paste [Yprd Yobs] values")),
        dbc.ModalBody([
            html.P("Paste 2 or 3 numeric columns (Yprd Yobs [Bnchmrk]), "
                   "one row per line — e.g. copied from Excel.",
                   className="small text-muted"),
            dbc.Textarea(id="paste-text", rows=12,
                         style={"fontFamily": "monospace"}),
        ]),
        dbc.ModalFooter([
            dbc.Button("Cancel", id="paste-cancel", size="sm",
                       color="secondary"),
            dbc.Button("OK", id="paste-ok", size="sm", color="primary"),
        ]),
    ], id="paste-modal", is_open=False)


def _zoom_modal() -> dbc.Modal:
    return dbc.Modal(
        dbc.ModalBody(html.Img(id="zoom-figure", style={"width": "100%"})),
        id="zoom-modal", size="xl", is_open=False)


def _numout_modal() -> dbc.Modal:
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Numerical output")),
        dbc.ModalBody(html.Pre(id="numout-text",
                               style={"fontFamily": "monospace",
                                      "fontSize": 13})),
    ], id="numout-modal", size="lg", is_open=False)


def build_layout() -> dbc.Container:
    """Built per page load so each browser tab gets its own session id."""
    header = dbc.Row([
        dbc.Col(html.Img(src="/assets/Logo1_FITEVAL.png",
                         style={"height": "48px"}), width="auto"),
        dbc.Col(html.H4("FITEVAL — Program for model goodness-of-fit "
                        "evaluation", className="mb-0"), width=True),
        dbc.Col(dbc.ButtonGroup([
            dbc.Button("About", id="about-open", size="sm", color="light"),
            dbc.Button("Help", href=HELP_URL, target="_blank", size="sm",
                       color="light"),
        ]), width="auto"),
    ], className="align-items-center py-2 border-bottom mb-2")

    return dbc.Container([
        dcc.Store(id="session-id", storage_type="session",
                  data=new_session_id()),
        dcc.Store(id="project-name", data=""),
        dcc.Store(id="cfg-store", storage_type="session"),
        dcc.Store(id="clipboard-counter", data=1),
        dcc.Store(id="run-state"),
        header,
        html.Div(id="message-bar", className="msg-info mb-2 px-2"),
        uncertainty_panel(),
        dbc.Row([
            dbc.Col(data_panel(), lg=4, md=5),
            dbc.Col(results_panel(), lg=8, md=7),
        ], className="g-2"),
        _about_modal(), _paste_modal(), _zoom_modal(), _numout_modal(),
        config_modal(), multirun_modal(),
    ], fluid=True)
