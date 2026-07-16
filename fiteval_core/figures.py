"""Matplotlib reproduction of the FITEVAL figures (FITEVAL_GUI.m L3647-3925).

Pure Figure objects on the Agg backend - no pyplot, no global state, safe
for multi-threaded serving.  Sizes replicate the desktop pixel dimensions
(figure pixels / 100 -> inches at dpi=100).
"""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")  # noqa: E402  (must precede figure imports)

import numpy as np
from matplotlib.figure import Figure
from matplotlib.offsetbox import AnnotationBbox, HPacker, TextArea, VPacker
from matplotlib.ticker import ScalarFormatter

from .config import FitevalConfig
from .report import summary_segments
from .results import EvalResult

# font-size scaling: desktop uses +2 on Windows, +3 on macOS (L3650-3654);
# the web app renders identically everywhere, macOS flavor chosen
SCLFTSZ = 3
FONTS = ["Arial", "Helvetica", "DejaVu Sans"]

# MATLAB -> matplotlib marker symbols (colors r b m g c y k map 1:1)
MARKER_MAP = {"o": "o", ".": ".", "x": "x", "+": "+", "*": "*", "s": "s",
              "d": "D", "v": "v", "^": "^", "<": "<", ">": ">",
              "p": "p", "h": "h"}


def _sizes(cfg: FitevalConfig) -> dict[str, float]:
    inc0 = cfg.font_size + SCLFTSZ
    return {
        "mk": cfg.marker_size + SCLFTSZ,      # GoF_MkSz
        "inc0": inc0, "inc1": inc0 + 1, "inc2": inc0 + 2,
        "red0": cfg.font_size, "red1": inc0 - 1, "red2": inc0 - 2,
        "red3": inc0 - 3,
    }


def _italic(label: str) -> str:
    """Mathtext italic form of an index label ('NSE' -> '$\\mathit{NSE}$')."""
    if label == "E_1":
        return r"$\mathit{E_1}$"
    star = label.endswith("*")
    base = label.rstrip("*")
    return rf"$\mathit{{{base}}}$" + ("*" if star else "")


def _fmt(spec: str, v: float) -> str:
    return "NaN" if (isinstance(v, float) and np.isnan(v)) else spec % v


def _sci_axis(ax, which: str, offset_size: float) -> None:
    """Use a shared 10^k multiplier for large/small axes (like MATLAB).

    Keeps tick labels short and aligned when values span several orders of
    magnitude; plain formatting is kept for values in ~[1e-3, 1e4].
    """
    for name in which:
        axis = ax.xaxis if name == "x" else ax.yaxis
        fmt = ScalarFormatter(useMathText=True)
        fmt.set_powerlimits((-3, 4))
        axis.set_major_formatter(fmt)
        axis.get_offset_text().set_fontsize(offset_size)


def draw_scatter(ax, res: EvalResult, cfg: FitevalConfig,
                 fig_text: str = "") -> None:
    """Observed vs computed panel (fig01, L3665-3722)."""
    s = _sizes(cfg)
    yobs, yprd = res.yobs, res.yprd
    minv = min(yobs.min(), yprd.min())
    maxv = max(yobs.max(), yprd.max())
    ext = 0.1 * (maxv - minv)
    rg = (minv - ext, maxv + ext)

    ax.plot(rg, rg, "k--", linewidth=1)

    show_obs_err = res.meas_unc != 0 and res.meas_unc != 4
    show_prd_err = ((res.meas_unc not in (0, 4) and res.nrcol in (7, 8))
                    or (res.meas_unc == 4 and res.nrcol in (5, 6)))
    if show_obs_err:
        ax.errorbar(yprd, yobs, yerr=[yobs - res.ub_omin, res.ub_omax - yobs],
                    fmt="o", color="b", markersize=s["mk"], linewidth=1)
    if show_prd_err:
        ax.errorbar(yprd, yobs, xerr=[yprd - res.ub_pmin, res.ub_pmax - yprd],
                    fmt="o" if not show_obs_err else "none",
                    color="b", markersize=s["mk"], linewidth=1)
    if not show_obs_err and not show_prd_err:
        ax.plot(yprd, yobs, "o", color="b", markersize=s["mk"],
                markerfacecolor="none")

    if res.outlier_indices.size:
        oi = res.outlier_indices
        ax.plot(yprd[oi], yobs[oi], "o", color="b", markerfacecolor="blue",
                markersize=s["mk"])
        step = (rg[1] - rg[0]) / 100
        pt = res.outliers.points[0]
        ax.text(pt[0] - 5 * step, pt[1] + 5 * step,
                f"({pt[0]:g}, {pt[1]:g})", fontsize=s["red3"], family=FONTS)

    ax.set_ylabel("Observed values", fontsize=s["inc2"], fontweight="bold",
                  family=FONTS)
    ax.set_xlabel("Computed values", fontsize=s["inc2"], fontweight="bold",
                  family=FONTS)
    ax.set_xlim(rg)
    ax.set_ylim(rg)
    ax.tick_params(labelsize=s["inc1"])
    _sci_axis(ax, "xy", s["red1"])

    lines = [
        _italic(res.index_label) + " = " + _fmt("%1.3f", res.main_idx)
        + " [" + _fmt("%1.3f", res.main_ci[0]) + " \N{EN DASH} "
        + _fmt("%1.3f", res.main_ci[1]) + "]",
        _italic("RMSE") + "= " + _fmt(res.rmse_fmt, res.rmse)
        + " [" + _fmt(res.rmse_fmt, res.rmse_ci[0]) + " \N{EN DASH} "
        + _fmt(res.rmse_fmt, res.rmse_ci[1]) + "]",
    ]
    ax.text(0.98, 0.12, "\n".join(lines), transform=ax.transAxes,
            ha="right", va="center", fontsize=s["red2"], family=FONTS)
    if fig_text:
        ax.text(0.05, 0.93, fig_text, transform=ax.transAxes, ha="left",
                va="center", fontsize=s["inc1"] - 2, fontstyle="italic",
                family=FONTS)


def draw_cdf(ax, res: EvalResult, cfg: FitevalConfig) -> None:
    """Cumulative-probability panel (fig02, L3746-3812)."""
    s = _sizes(cfg)
    l1, l2, l3 = res.class_lim
    if res.main_ci[0] > 0.5:
        xax = (0.5, 1.001)
    else:
        xax = (max(0.0, 0.9 * res.main_ci[0]), 1.001)
    xperc = (xax[1] - xax[0]) / 100

    ax.plot([l2, 1, 1], [1, 1, 0], "k-", linewidth=1)
    ax.plot([xax[0], xax[0]], [0, 1], "k-", linewidth=2)
    for lo, hi, grey in ((xax[0], l1, 0.7), (l1, l2, 0.8), (l2, l3, 0.9)):
        ax.fill([lo, lo, hi, hi], [0, 1, 1, 0], color=(grey,) * 3,
                edgecolor="black", linewidth=0.5, zorder=1.5)

    ax.plot(res.xi, res.fi, "b-", linewidth=2)
    for y in (0.10, 0.50, 0.90):
        ax.plot(xax, [y, y], "k:", linewidth=1.5)

    labels = (("U.", (l1 - xax[0]) / 2 + xax[0]), ("A.", (l2 - l1) / 2 + l1),
              ("G.", (l3 - l2) / 2 + l2), ("V.G.", (1 - l3) / 2 + l3))
    for txt, xc in labels:
        ax.text(xc, 1.05, txt, ha="center", va="center", fontsize=s["red0"],
                fontstyle="italic", family=FONTS)

    ax.plot(res.main_ci, [0.5, 0.5], "k+-", linewidth=1, markersize=8)
    ax.plot([res.main_idx], [0.5], "ko", markersize=5,
            markerfacecolor="white", zorder=5)

    for y, lab in ((0.91, "90%"), (0.51, "50%"), (0.11, "10%")):
        ax.text(1 + 2 * xperc, y, lab, fontsize=s["red0"], family=FONTS)

    ax.set_xlim(xax)
    ax.set_ylim(0, 1.05)
    ax.set_yticks(np.arange(0, 1.01, 0.25))
    ax.set_xlabel(_italic(res.index_label), fontsize=s["inc2"], family=FONTS)
    ax.set_ylabel("Cumulative Probability", fontsize=s["inc2"], family=FONTS)
    ax.tick_params(labelsize=s["inc1"], direction="out")
    ax.minorticks_on()
    ax.set_facecolor("none")  # MATLAB axes 'color','none' (L3748)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def draw_series(ax, res: EvalResult, cfg: FitevalConfig) -> None:
    """Observed & computed series panel (fig03, L3815-3851)."""
    s = _sizes(cfg)
    yobs, yprd = res.yobs, res.yprd
    xs = np.arange(1, yobs.size + 1)
    color = cfg.marker_color
    marker = MARKER_MAP.get(cfg.marker_symbol, "o")

    ax.plot(xs, yprd, "k-", linewidth=1)
    show_obs_err = res.meas_unc != 0 and res.meas_unc != 4
    show_prd_err = ((res.meas_unc not in (0, 4) and res.nrcol in (7, 8))
                    or (res.meas_unc == 4 and res.nrcol in (5, 6)))
    if show_obs_err:
        ax.errorbar(xs, yobs, yerr=[yobs - res.ub_omin, res.ub_omax - yobs],
                    fmt="none", ecolor=color, linewidth=1)
    if show_prd_err:
        ax.errorbar(xs, yprd, yerr=[yprd - res.ub_pmin, res.ub_pmax - yprd],
                    fmt="none", ecolor="k", linewidth=1)
    ax.plot(xs, yobs, linestyle="none", marker=marker, color=color,
            markersize=cfg.marker_size + 3, markerfacecolor=(0.7, 0.7, 0.7))
    if res.outlier_indices.size:
        oi = res.outlier_indices
        ax.plot(xs[oi], yobs[oi], linestyle="none", marker=marker,
                color=color, markersize=cfg.marker_size + 4,
                markerfacecolor="blue")

    ax.set_xlim(0, xs[-1] + 0.5)
    _sci_axis(ax, "y", s["red1"])
    ax.set_xlabel("Position within the series", fontsize=s["inc2"],
                  family=FONTS)
    ax.set_ylabel("Observed and Computed values", fontsize=s["inc2"],
                  family=FONTS)
    ax.tick_params(labelsize=s["inc1"], direction="out")
    ax.minorticks_on()
    ax.set_facecolor("none")  # MATLAB axes 'color','none' (L3817)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def draw_text_panel(ax, res: EvalResult, cfg: FitevalConfig) -> None:
    """GOODNESS-OF-FIT EVALUATION text block (txstr, L3853-3896).

    Rendered as stacked segments so the three MATLAB \\bf emphases (rating,
    p-value, secondary index+CI) come out bold inline.
    """
    s = _sizes(cfg)
    fs = s["red3"]
    ax.axis("off")

    def _ta(text: str, bold: bool) -> TextArea:
        return TextArea(text, textprops=dict(
            fontsize=fs, family=FONTS,
            fontweight="bold" if bold else "normal"))

    rows = []
    for segs in summary_segments(res):
        if len(segs) == 1:
            rows.append(_ta(*segs[0]))
        else:
            rows.append(HPacker(children=[_ta(t, b) for t, b in segs],
                                align="baseline", pad=0, sep=0))
    box = VPacker(children=rows, align="left", pad=0, sep=fs * 0.12)
    ax.add_artist(AnnotationBbox(
        box, (0, 0.42), xycoords=ax.transAxes, box_alignment=(0, 0.5),
        frameon=False, pad=0))


def fig_match(res, cfg, fig_text="") -> Figure:
    fig = Figure(figsize=(4.0, 3.5), dpi=100, facecolor="white")
    ax = fig.add_axes([0.14, 0.12, 0.8, 0.85])
    draw_scatter(ax, res, cfg, fig_text)
    return fig


def fig_cdf(res, cfg) -> Figure:
    fig = Figure(figsize=(4.6, 3.0), dpi=100, facecolor="white")
    ax = fig.add_axes([0.12, 0.15, 0.8, 0.82])
    draw_cdf(ax, res, cfg)
    return fig


def fig_series(res, cfg) -> Figure:
    fig = Figure(figsize=(4.6, 3.0), dpi=100, facecolor="white")
    ax = fig.add_axes([0.12, 0.15, 0.8, 0.82])
    draw_series(ax, res, cfg)
    return fig


def fig_combined(res, cfg, fig_text="") -> Figure:
    """2x2 combined layout (fig00, L3879-3897): 800x440 px landscape."""
    fig = Figure(figsize=(8.0, 4.4), dpi=100, facecolor="white")
    lg_x = 0.43
    ax1 = fig.add_axes([0.08, 0.53, lg_x / 1.1, lg_x])
    ax2 = fig.add_axes([0.60, 0.62, 0.352, 0.35])
    ax3 = fig.add_axes([0.60, 0.12, 0.352, 0.42])
    ax4 = fig.add_axes([0.07, 0.05, lg_x, 0.40])
    draw_scatter(ax1, res, cfg, fig_text)
    draw_cdf(ax2, res, cfg)
    draw_series(ax3, res, cfg)
    draw_text_panel(ax4, res, cfg)
    # combined panels use the reduced font (ftszred1, L3889); axis labels
    # are shrunk with the axes so the tight 2x2 layout doesn't collide
    s = _sizes(cfg)
    for ax in (ax1, ax2, ax3):
        ax.tick_params(labelsize=s["red1"] - 1)
        ax.xaxis.label.set_size(s["red1"])
        ax.yaxis.label.set_size(s["red1"])
        ax.xaxis.labelpad = 2
        ax.yaxis.labelpad = 2
    return fig


def save_figure(fig: Figure, path: str, dpi: int | None = None,
                tight: bool = False) -> None:
    """SaveFigure equivalent: extension decides the format; dpi = figres.

    tight=True trims to a snug bounding box so axis labels of the individual
    "split" figures are never clipped, even with wide scientific-notation
    offsets on large-value data.
    """
    ext = str(path).rsplit(".", 1)[-1].lower()
    fmt = {"jpg": "jpeg", "tif": "tiff"}.get(ext, ext)
    fig.savefig(str(path), format=fmt, dpi=dpi or "figure",
                facecolor=fig.get_facecolor(),
                bbox_inches="tight" if tight else None)
