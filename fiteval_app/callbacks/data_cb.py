"""Data input callbacks: upload, paste, clear, save."""

from __future__ import annotations

from dash import Input, Output, State, ctx, dcc, no_update

from fiteval_core.dataio import DataError, parse_numeric_text, swap_first_two

from .helpers import (array_to_records, decode_upload, message,
                      records_to_array, table_columns)


def register(app) -> None:

    @app.callback(
        Output("data-table", "data"),
        Output("data-table", "columns"),
        Output("project-name", "data"),
        Output("input-filename", "value"),
        Output("clipboard-counter", "data"),
        Output("message-bar", "children"),
        Output("message-bar", "className"),
        Output("paste-modal", "is_open"),
        Input("upload-data", "contents"),
        Input("paste-ok", "n_clicks"),
        Input("clear-data", "n_clicks"),
        Input("paste-open", "n_clicks"),
        Input("paste-cancel", "n_clicks"),
        State("upload-data", "filename"),
        State("paste-text", "value"),
        State("clipboard-counter", "data"),
        State("input-filename", "value"),
        prevent_initial_call=True,
    )
    def handle_data(_contents, _ok, _clear, _open, _cancel,
                    up_name, paste_text, counter, cur_name):
        trig = ctx.triggered_id
        if trig == "paste-open":
            return (no_update,) * 7 + (True,)
        if trig == "paste-cancel":
            return (no_update,) * 7 + (False,)

        if trig == "clear-data":
            msg, cls = message("Data cleared")
            return [], table_columns(2), "", "", no_update, msg, cls, False

        try:
            if trig == "upload-data":
                # files on disk are observed-first; table shows Yprd first
                disk = parse_numeric_text(decode_upload(_contents))
                if disk.shape[1] > 3:
                    disk = disk[:, :3]  # load_file truncates to 3 cols (L1712)
                table = swap_first_two(disk)
                name = up_name or "data.in"
                msg, cls = message(f"Loaded {name} ({table.shape[0]} rows)")
                return (array_to_records(table), table_columns(table.shape[1]),
                        name, name, no_update, msg, cls, False)

            if trig == "paste-ok":
                table = parse_numeric_text(paste_text or "")
                if table.shape[1] not in (2, 3):
                    raise DataError(
                        "Pasted data must have 2 or 3 columns [Yprd Yobs (Bnchmrk)]!")
                name = cur_name or f"clipboard_{counter}.in"
                new_counter = counter + (0 if cur_name else 1)
                msg, cls = message(f"Pasted {table.shape[0]} rows")
                return (array_to_records(table), table_columns(table.shape[1]),
                        name, name, new_counter, msg, cls, False)
        except DataError as exc:
            msg, cls = message(str(exc), error=True)
            return (no_update,) * 5 + (msg, cls, False)
        return (no_update,) * 8

    @app.callback(
        Output("table-info", "children"),
        Input("data-table", "data"),
    )
    def table_info(records):
        n = len(records or [])
        return f"N = {n} rows" if n else "No data loaded"

    @app.callback(
        Output("download-data", "data"),
        Output("message-bar", "children", allow_duplicate=True),
        Output("message-bar", "className", allow_duplicate=True),
        Input("save-data", "n_clicks"),
        State("data-table", "data"),
        State("input-filename", "value"),
        prevent_initial_call=True,
    )
    def save_data(_n, records, fname):
        try:
            table = records_to_array(records)
        except DataError:
            msg, cls = message("No [Yprd Yobs] data to save!", error=True)
            return no_update, msg, cls
        disk = swap_first_two(table)  # observed-first on disk
        fname = fname or "data.in"
        if not fname.endswith(".in"):
            fname += ".in"
        content = "\n".join("\t".join(f"{v:f}" for v in row) for row in disk)
        msg, cls = message(f"Data saved in {fname}")
        return dict(content=content + "\n", filename=fname), msg, cls
