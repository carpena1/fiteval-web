"""Data file IO and column-order conventions.

Convention (matches the desktop app):
- On disk (.in files) and inside the engine, data are observed-first:
  [Yobs, Yprd, ...extra columns...].
- In the GUI table, data are predicted-first: [Yprd, Yobs, Bnchmrk].
The swap between the two happens ONLY here (swap_first_two).
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np


class DataError(ValueError):
    """User-facing data problem (message mirrors the desktop app wording)."""


def safe_join(directory: str | Path, name: str) -> Path:
    """Join `name` onto `directory` using only its basename.

    All workspace files are flat (direct children of the session directory),
    so a legitimate reference is always a bare filename. Stripping to the
    basename and verifying the result stays directly inside `directory`
    prevents a crafted value ('../../etc/passwd', '/etc/passwd') — e.g. one
    round-tripped through a browser store or a multi-run list file — from
    escaping the workspace.
    """
    directory = Path(directory)
    # Treat '\' as a separator too, so a Windows-style name is reduced the
    # same way on any OS the tests or server run on.
    base = Path(str(name).replace("\\", "/")).name
    if not base or base in (".", ".."):
        raise DataError(f"Invalid file name: {name!r}")
    candidate = directory / base
    if candidate.resolve().parent != directory.resolve():
        raise DataError(f"Invalid file name: {name!r}")
    return candidate


def parse_numeric_text(text: str) -> np.ndarray:
    """Parse whitespace/comma-separated numeric rows (files or pasted data).

    Mirrors MATLAB importdata/str2num tolerance: blank lines are skipped and
    all rows must have the same number of columns.
    """
    rows: list[list[float]] = []
    for line in text.splitlines():
        line = line.strip().replace(",", " ")
        if not line:
            continue
        try:
            values = [float(tok) for tok in re.split(r"\s+", line)]
        except ValueError as exc:
            raise DataError(f"Non-numeric value in data: {line!r}") from exc
        rows.append(values)
    if not rows:
        raise DataError("No numeric data found!")
    ncol = len(rows[0])
    if any(len(r) != ncol for r in rows):
        raise DataError("All data rows must have the same number of columns!")
    return np.asarray(rows, dtype=float)


def read_in_file(path: str | Path) -> np.ndarray:
    """Read a .in data file (observed-first column order)."""
    return parse_numeric_text(Path(path).read_text(encoding="utf-8", errors="replace"))


def write_in_file(data: np.ndarray, path: str | Path) -> None:
    """Write tab-separated %f rows, as writeTofile/SaveDataToFile do."""
    data = np.atleast_2d(np.asarray(data, dtype=float))
    lines = ["\t".join(f"{v:f}" for v in row) for row in data]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def swap_first_two(data: np.ndarray) -> np.ndarray:
    """Swap columns 1 and 2: disk [Yobs Yprd ...] <-> table [Yprd Yobs ...]."""
    data = np.array(data, dtype=float, copy=True)
    if data.ndim != 2 or data.shape[1] < 2:
        raise DataError("Data must have at least 2 columns!")
    data[:, [0, 1]] = data[:, [1, 0]]
    return data


def drop_nan_rows(*cols: np.ndarray) -> tuple[list[np.ndarray], int]:
    """Drop rows where the sum across columns is NaN (fitevaluation L3385)."""
    stacked = np.column_stack([c for c in cols if c is not None and c.size])
    keep = ~np.isnan(stacked.sum(axis=1))
    out = [c[keep] if (c is not None and c.size) else c for c in cols]
    return out, int((~keep).sum())


def drop_repeated_rows(data: np.ndarray) -> tuple[np.ndarray, int]:
    """Remove repeated cases, keeping first occurrences (fiteval_2 L3145-3159).

    Rows are considered identical when the hash key
    2*|c1| + 3*|c2| + c2/pi matches (c1, c2 = first two columns, obs-first).
    Replicates the MATLAB loop exactly, including its side effect of moving
    rows that had duplicates to the front of the array.
    """
    data = np.atleast_2d(np.asarray(data, dtype=float))
    key = 2 * np.abs(data[:, 0]) + 3 * np.abs(data[:, 1]) + data[:, 1] / math.pi
    temp = list(range(data.shape[0]))  # row indices standing in for TEMP rows
    for i in range(data.shape[0]):
        matches = [j for j in temp if key[j] == key[i]]
        if len(matches) > 1:
            temp = [i] + [j for j in temp if key[j] != key[i]]
    removed = data.shape[0] - len(temp)
    return data[temp], removed
