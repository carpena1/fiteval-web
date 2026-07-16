"""FITEVAL web application factory."""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import Dash

from .callbacks import register_all
from .layout import build_layout
from .session import sweep_stale_sessions


def create_app(url_prefix: str | None = None) -> Dash:
    kwargs = {}
    if url_prefix:
        kwargs["requests_pathname_prefix"] = url_prefix
    app = Dash(
        __name__,
        title="FITEVAL",
        external_stylesheets=[dbc.themes.FLATLY],
        **kwargs,
    )
    app.layout = build_layout  # callable: fresh session id per page load
    register_all(app)
    sweep_stale_sessions()
    return app


if __name__ == "__main__":
    create_app().run(debug=True, port=8050)
