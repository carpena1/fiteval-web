import numpy as np
import pytest

from fiteval_core.config import FitevalConfig, check_class_limits, read_config, write_config


def test_defaults():
    cfg = FitevalConfig()
    assert cfg.class_lim == (0.65, 0.80, 0.90)
    assert cfg.bias_value == 5.0
    assert cfg.gof_index_effective == 1
    assert cfg.bstype == 0
    assert cfg.n_resamples == 20000
    assert cfg.marker_color == "b" and cfg.marker_symbol == "o"


def test_round_trip(tmp_path):
    cfg = FitevalConfig(class_lim=(0.5, 0.7, 0.85), bias_value=10, gof_index=2,
                        bstype=1, n_resamples=8000, font_size=12, marker="r*",
                        marker_size=4, dpi=150)
    p = tmp_path / "fitevalconfig.txt"
    write_config(cfg, p)
    back = read_config(p)
    assert back == cfg


def test_read_desktop_config(tmp_path):
    """Parse a file in the exact format the desktop app writes."""
    p = tmp_path / "fitevalconfig.txt"
    p.write_text(
        "0.65 %Acceptable NSE threshold value\n"
        "0.80 %Good NSE threshold value\n"
        "0.90 %Very good NSE threshold value\n"
        "5 %BiasValue\n"
        "0 %Select GoF Main Index (1=NSE, 2=KGE*, 3=KGE, 4= E1)\n"
        "0 20000 % Bootstrap method (1= Efrons ' bootstrapping, 0= block boostrapping); Nr of resamples\n"
        "10 % FontSizeValue\n"
        "1 % Do not display graphical output (1=accept)\n"
        "0 % % Take into account observations uncertainty (>0,1,2,3 or 4= yes)\n"
        "bo % Color and symbol of the series marker\n"
        "5 % Size of the series marker\n"
        "100 % Resolution of figures in dpi ")
    cfg = read_config(p)
    assert cfg.class_lim == (0.65, 0.80, 0.90)
    assert cfg.gof_index == 0 and cfg.gof_index_effective == 1  # legacy 0 -> NSE
    assert cfg.bstype == 0 and cfg.n_resamples == 20000
    assert cfg.marker == "bo" and cfg.marker_size == 5 and cfg.dpi == 100


def test_missing_file_gives_defaults(tmp_path):
    assert read_config(tmp_path / "nope.txt") == FitevalConfig()


def test_garbage_file_gives_defaults(tmp_path):
    p = tmp_path / "fitevalconfig.txt"
    p.write_text("hello\nworld\n")
    assert read_config(p) == FitevalConfig()


@pytest.mark.parametrize("lims,ok", [
    ((0.65, 0.8, 0.9), True),
    ((0.9, 0.8, 0.65), False),
    ((0.65, 0.65, 0.9), False),
    ((0.65, 0.8, 1.1), False),
])
def test_class_limits(lims, ok):
    assert (check_class_limits(lims) is None) == ok


def test_validated_clamps():
    cfg = FitevalConfig(n_resamples=100, dpi=30).validated()
    assert cfg.n_resamples == 5000 and cfg.dpi == 72
