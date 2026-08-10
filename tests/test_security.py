"""Security regression tests: path-traversal confinement and cost clamps.

These guard the fixes in docs/security_review.md — a future refactor that
silently drops the basename reduction or the config clamps should fail here.
"""

import numpy as np
import pytest

from fiteval_app.session import session_dir, session_file
from fiteval_core.config import MAX_DPI, MAX_RESAMPLES, FitevalConfig
from fiteval_core.dataio import DataError, safe_join
from fiteval_core.multirun import run_multi

# Values that must never escape the target directory.
TRAVERSALS = [
    "/etc/passwd",
    "../../../../etc/passwd",
    "../secret.txt",
    "..\\..\\windows\\win.ini",
    "sub/dir/file.in",
    "/absolute/name.in",
]
# Values with no usable basename.
EMPTY_NAMES = ["", ".", "..", "/", "../"]


# --------------------------------------------------------------------------
# fiteval_core.dataio.safe_join
# --------------------------------------------------------------------------

@pytest.mark.parametrize("attack", TRAVERSALS)
def test_safe_join_confines_to_directory(tmp_path, attack):
    p = safe_join(tmp_path, attack)
    # Result is a direct child of the directory, never outside it.
    assert p.resolve().parent == tmp_path.resolve()
    assert p.name == attack.replace("\\", "/").rstrip("/").split("/")[-1]


@pytest.mark.parametrize("attack", EMPTY_NAMES)
def test_safe_join_rejects_empty(tmp_path, attack):
    with pytest.raises(DataError):
        safe_join(tmp_path, attack)


def test_safe_join_passes_plain_name(tmp_path):
    assert safe_join(tmp_path, "data.in") == tmp_path / "data.in"


# --------------------------------------------------------------------------
# fiteval_app.session.session_file / session_dir
# --------------------------------------------------------------------------

@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """Point the session workspace at a temp dir for the duration of a test."""
    import fiteval_app.session as session
    monkeypatch.setattr(session, "WORKSPACE_ROOT", tmp_path)
    return tmp_path


@pytest.mark.parametrize("attack", TRAVERSALS)
def test_session_file_confines_to_session_dir(workspace, attack):
    wdir = session_dir("deadbeef")
    p = session_file("deadbeef", attack)
    assert p.resolve().parent == wdir.resolve()


@pytest.mark.parametrize("attack", EMPTY_NAMES)
def test_session_file_rejects_empty(workspace, attack):
    with pytest.raises(ValueError):
        session_file("deadbeef", attack)


def test_session_file_cannot_read_outside(workspace, tmp_path):
    """A crafted absolute path collapses to a basename that does not exist."""
    secret = tmp_path.parent / "secret.txt"
    secret.write_text("top secret")
    p = session_file("deadbeef", str(secret))
    assert session_dir("deadbeef") in p.parents
    assert not p.exists()  # points inside the (empty) session dir, misses


@pytest.mark.parametrize("bad_sid", ["../../etc", "a/b", "", "２３４", "sid.1"])
def test_session_dir_rejects_bad_ids(workspace, bad_sid):
    with pytest.raises(ValueError):
        session_dir(bad_sid)


def test_session_dir_accepts_ascii_alnum(workspace):
    assert session_dir("abc123DEF").is_dir()


# --------------------------------------------------------------------------
# Config cost clamps (DoS)
# --------------------------------------------------------------------------

def test_validated_clamps_upper_bounds():
    cfg = FitevalConfig(n_resamples=10 ** 9, dpi=100000,
                        marker_size=1e6, font_size=1e6).validated()
    assert cfg.n_resamples == MAX_RESAMPLES
    assert cfg.dpi == MAX_DPI
    assert cfg.marker_size <= 50.0
    assert cfg.font_size <= 40.0


def test_validated_keeps_floor():
    cfg = FitevalConfig(n_resamples=10, dpi=1).validated()
    assert cfg.n_resamples == 5000
    assert cfg.dpi == 72


def test_cfg_from_store_clamps_client_values():
    """A hand-edited config store must be bounded before use."""
    from fiteval_app.callbacks.helpers import cfg_from_store
    cfg = cfg_from_store({"n_resamples": 10 ** 9, "dpi": 100000})
    assert cfg.n_resamples == MAX_RESAMPLES
    assert cfg.dpi == MAX_DPI


# --------------------------------------------------------------------------
# End-to-end: a traversal file field in a multi-run must not read outside
# --------------------------------------------------------------------------

def test_run_multi_ignores_traversal_file_field(workspace, tmp_path):
    secret = tmp_path.parent / "outside.in"
    secret.write_text("1 2\n3 4\n5 6\n")  # valid numeric data, but outside
    wdir = session_dir("deadbeef")
    out = run_multi([("../../outside.in", "0")], wdir, FitevalConfig())
    # The row fails (file not found inside the workspace), no summary written.
    assert out.summary_path is None
    assert out.logs and "not found" in out.logs[0].lower()
