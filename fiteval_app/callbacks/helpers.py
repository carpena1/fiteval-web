"""Shared helpers for Dash callbacks."""

from __future__ import annotations

import base64
from dataclasses import asdict

import numpy as np

from fiteval_core.config import FitevalConfig
from fiteval_core.dataio import DataError

TABLE_COLS = ("Yprd", "Yobs", "Bnchmrk")


def cfg_from_store(store: dict | None) -> FitevalConfig:
    if not store:
        return FitevalConfig()
    cfg = FitevalConfig(**{k: v for k, v in store.items()
                           if k in FitevalConfig.__dataclass_fields__})
    cfg.class_lim = tuple(cfg.class_lim)
    # The store is client-controlled; clamp cost-bearing fields to safe bounds.
    return cfg.validated()


def cfg_to_store(cfg: FitevalConfig) -> dict:
    return asdict(cfg)


def table_columns(ncol: int) -> list[dict]:
    return [{"name": TABLE_COLS[i], "id": f"c{i}", "type": "numeric"}
            for i in range(min(ncol, 3))]


def array_to_records(arr: np.ndarray) -> list[dict]:
    """Table records (predicted-first order expected by the caller)."""
    return [{f"c{j}": (None if np.isnan(row[j]) else row[j])
             for j in range(min(arr.shape[1], 3))} for row in arr]


def records_to_array(records: list[dict]) -> np.ndarray:
    """Table records -> float array; blank cells become NaN."""
    if not records:
        raise DataError("Load [Yprd Yobs] data first!")
    keys = [k for k in ("c0", "c1", "c2") if k in records[0]]
    out = np.full((len(records), len(keys)), np.nan)
    for i, rec in enumerate(records):
        for j, k in enumerate(keys):
            v = rec.get(k)
            if v is None or v == "":
                continue
            try:
                out[i, j] = float(v)
            except (TypeError, ValueError):
                raise DataError(f"Non-numeric value in table row {i + 1}")
    # drop an all-empty trailing benchmark column
    if out.shape[1] == 3 and np.isnan(out[:, 2]).all():
        out = out[:, :2]
    return out


def decode_upload(contents: str) -> str:
    _, b64 = contents.split(",", 1)
    return base64.b64decode(b64).decode("utf-8", errors="replace")


def img_src(png_path) -> str:
    data = base64.b64encode(png_path.read_bytes()).decode()
    return f"data:image/png;base64,{data}"


def message(text: str, error: bool = False) -> tuple[str, str]:
    """(children, className) pair for the message bar."""
    return text, ("msg-error" if error else "msg-info") + " mb-2 px-2"
