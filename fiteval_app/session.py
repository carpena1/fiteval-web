"""Per-browser-session workspaces (uploads and generated outputs)."""

from __future__ import annotations

import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path

WORKSPACE_ROOT = Path(os.environ.get(
    "FITEVAL_WORKSPACE",
    Path(tempfile.gettempdir()) / "fiteval_workspace"))

MAX_AGE_HOURS = float(os.environ.get("FITEVAL_SESSION_HOURS", "24"))


def new_session_id() -> str:
    return uuid.uuid4().hex


def session_dir(session_id: str) -> Path:
    """Workspace directory for a session (created on demand)."""
    if not session_id or not session_id.isalnum():
        raise ValueError("Invalid session id")
    p = WORKSPACE_ROOT / session_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def sweep_stale_sessions() -> int:
    """Delete session dirs untouched for MAX_AGE_HOURS; returns count."""
    if not WORKSPACE_ROOT.is_dir():
        return 0
    cutoff = time.time() - MAX_AGE_HOURS * 3600
    n = 0
    for p in WORKSPACE_ROOT.iterdir():
        if p.is_dir() and p.stat().st_mtime < cutoff:
            shutil.rmtree(p, ignore_errors=True)
            n += 1
    return n
