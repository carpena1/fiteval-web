"""Configuration parameters and fitevalconfig.txt IO.

File format is byte-compatible with the desktop app (WriteConfigFile,
FITEVAL_GUI.m L1680-1702; ReadConfigFile L1745-1800): 12 lines, value(s)
first, then a %-comment.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

MARKER_COLORS = "rbmgcyk"
MARKER_SYMBOLS = "o.x+*sdv^<>ph"

DEFAULT_UNC_STRING = "0 %"


@dataclass
class FitevalConfig:
    class_lim: tuple[float, float, float] = (0.65, 0.80, 0.90)
    bias_value: float = 5.0
    gof_index: int = 1          # 1=NSE, 2=KGE*, 3=KGE, 4=E1 (values <=1 mean NSE)
    bstype: int = 0             # 0=block bootstrap (Politis-Romano), 1=Efron IID
    n_resamples: int = 20000
    font_size: float = 10.0
    show_figure: int = 1        # 1 = do not display figure windows (kept for file compat)
    unc_string: str = DEFAULT_UNC_STRING  # line 9, encoded uncertainty options
    marker: str = "bo"          # color+symbol, MATLAB codes
    marker_size: float = 5.0
    dpi: int = 100

    @property
    def gof_index_effective(self) -> int:
        """Desktop app treats flag <=1 (incl. the legacy 0) as NSE."""
        return self.gof_index if self.gof_index in (2, 3, 4) else 1

    @property
    def marker_color(self) -> str:
        return self.marker[0] if self.marker else "b"

    @property
    def marker_symbol(self) -> str:
        return self.marker[1] if len(self.marker) > 1 else "o"

    def validated(self) -> "FitevalConfig":
        """Clamp values the way the desktop Configuration dialog does."""
        cfg = replace(self)
        cfg.n_resamples = max(5000, int(cfg.n_resamples))
        cfg.dpi = max(72, int(cfg.dpi))
        cfg.marker_size = max(1.0, float(cfg.marker_size))
        cfg.font_size = max(1.0, float(cfg.font_size))
        return cfg


def check_class_limits(class_lim) -> str | None:
    """Return an error message (or None) per CheckClassLimits (L472-483)."""
    l1, l2, l3 = class_lim
    if l1 > 1 or l2 > 1 or l3 > 1 or l1 >= l2 or l2 >= l3:
        return "Incorrect values for class limits in Configuration!"
    return None


def _first_float(line: str, default: float) -> float:
    try:
        return float(line.split()[0])
    except (ValueError, IndexError):
        return default


def read_config(path: str | Path) -> FitevalConfig:
    """Tolerant parser mirroring ReadConfigFile: any failure -> defaults."""
    cfg = FitevalConfig(marker_size=3.0)  # ReadConfigFile fallback marker size is 3
    path = Path(path)
    if not path.is_file():
        return FitevalConfig()
    try:
        lines = path.read_text().splitlines()
        cl = list(cfg.class_lim)
        for m in range(3):
            cl[m] = _first_float(lines[m], cl[m])
        cfg.class_lim = tuple(cl)
        cfg.bias_value = _first_float(lines[3], cfg.bias_value)
        cfg.gof_index = int(_first_float(lines[4], cfg.gof_index))
        parts = lines[5].split()
        cfg.bstype = int(parts[0])
        cfg.n_resamples = int(parts[1])
        cfg.font_size = _first_float(lines[6], cfg.font_size)
        cfg.show_figure = int(_first_float(lines[7], cfg.show_figure))
        # line 9 (uncertainty options) is skipped by the desktop reader too
        cfg.unc_string = DEFAULT_UNC_STRING
        marker = lines[9].split()[0]
        cfg.marker = marker[:2]
        cfg.marker_size = _first_float(lines[10], cfg.marker_size)
        cfg.dpi = int(_first_float(lines[11], cfg.dpi))
    except (IndexError, ValueError):
        return FitevalConfig()
    return cfg


def write_config(cfg: FitevalConfig, path: str | Path) -> None:
    """Write the 12-line fitevalconfig.txt exactly as WriteConfigFile does."""
    def fmt(x: float) -> str:
        return f"{x:g}"

    lines = [
        f"{cfg.class_lim[0]:.2f} %Acceptable NSE threshold value",
        f"{cfg.class_lim[1]:.2f} %Good NSE threshold value",
        f"{cfg.class_lim[2]:.2f} %Very good NSE threshold value",
        f"{fmt(cfg.bias_value)} %BiasValue",
        f"{cfg.gof_index} %Select GoF Main Index (1=NSE, 2=KGE*, 3=KGE, 4= E1)",
        f"{cfg.bstype} {cfg.n_resamples} % Bootstrap method (1= Efrons ' bootstrapping,"
        " 0= block boostrapping); Nr of resamples",
        f"{fmt(cfg.font_size)} % FontSizeValue",
        "1 % Do not display graphical output (1=accept)",
        f"{cfg.unc_string} % Take into account observations uncertainty (>0,1,2,3 or 4= yes)",
        f"{cfg.marker} % Color and symbol of the series marker",
        f"{fmt(cfg.marker_size)} % Size of the series marker",
        f"{cfg.dpi} % Resolution of figures in dpi ",
    ]
    Path(path).write_text("\n".join(lines[:-1]) + "\n" + lines[-1])
