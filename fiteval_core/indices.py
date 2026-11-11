"""Goodness-of-fit indices and diagnostics.

Direct port of fun_GoF_Indexes (FITEVAL_GUI.m L4072-4097), the bias block
(L3609-3638), Dixon's Q-test (L3650-3678) and the KGE/NSE imbalance
diagnostic (L3476-3512).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

INDEX_LABELS = {1: "NSE", 2: "KGE*", 3: "KGE", 4: "E_1"}


def rounddec(value, dec: int):
    """MATLAB round(value*10^dec)/10^dec (round-half-away-from-zero)."""
    value = np.asarray(value, dtype=float)
    scaled = value * 10.0**dec
    out = np.sign(scaled) * np.floor(np.abs(scaled) + 0.5) / 10.0**dec
    return float(out) if out.ndim == 0 else out


def gof_indexes(yobs, yprd, yben, yerr, j) -> np.ndarray:
    """Return [RMSE, Ceff, KGE*, KGE].

    Ceff is NSE (j=2) or Legates-McCabe E1 (j=1); benchmark series yben
    replaces the observation mean (Seibert 2001).  yerr is the (possibly
    uncertainty-corrected) residual used for both Ceff and RMSE.
    """
    yobs = np.asarray(yobs, dtype=float)
    yprd = np.asarray(yprd, dtype=float)
    yben = np.asarray(yben, dtype=float)
    yerr = np.asarray(yerr, dtype=float)

    ssq = np.sum(np.abs(yerr) ** j)
    ss = np.sum(np.abs(yobs - yben) ** j)
    with np.errstate(divide="ignore", invalid="ignore"):
        ceff = 1.0 - ssq / ss

    n = yobs.size
    rmse = math.sqrt(np.sum(yerr**2) / n)

    std_o = np.std(yobs, ddof=1)
    std_p = np.std(yprd, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        alpha = std_p / std_o
        if std_o == 0 or std_p == 0:
            r = np.nan
        else:
            r = float(np.corrcoef(yprd, yobs)[1, 0])

        beta = np.mean(yprd) / np.mean(yobs)  # Gupta et al. 2009
        kge = 1.0 - math.sqrt((r - 1) ** 2 + (alpha - 1) ** 2 + (beta - 1) ** 2) \
            if np.isfinite(r) and np.isfinite(beta) and np.isfinite(alpha) else np.nan

        beta_star = 1.0 + (np.mean(yprd) - np.mean(yobs)) / std_o  # Knobel/Clark
        kge_star = 1.0 - math.sqrt((r - 1) ** 2 + (alpha - 1) ** 2 + (beta_star - 1) ** 2) \
            if np.isfinite(r) and np.isfinite(beta_star) and np.isfinite(alpha) else np.nan

    return np.array([rmse, ceff, kge_star, kge])


def nse_to_kge_threshold(nse_thr: float) -> float:
    """KGEthr = 1 - sqrt(2)*(1 - sqrt(NSEthr))  (GoFIndexSelection L326)."""
    return 1.0 - math.sqrt(2.0) * (1.0 - math.sqrt(nse_thr))


def kge_to_nse_threshold(kge_thr: float) -> float:
    """NSEthr = 0.5*(sqrt(2) - (1 - KGEthr))^2  (GoFIndexSelection L328)."""
    return 0.5 * (math.sqrt(2.0) - (1.0 - kge_thr)) ** 2


def nse_to_e1_threshold(nse_thr: float) -> float:
    """E1thr = 1 - sqrt(1 - NSEthr).

    E1 (Legates-McCabe) and NSE are NOT on the same scale: E1 uses absolute
    errors (j=1) where NSE uses squared errors (j=2), giving
    E1 = 1 - sqrt(1 - NSE).  The desktop app treats the two scales as equal,
    which understates the E1 thresholds; the port converts them.
    """
    return 1.0 - math.sqrt(1.0 - nse_thr)


def e1_to_nse_threshold(e1_thr: float) -> float:
    """NSEthr = 1 - (1 - E1thr)^2  (inverse of nse_to_e1_threshold)."""
    return 1.0 - (1.0 - e1_thr) ** 2


def relative_bias(yobs, yprd, bias_value: float, index_label: str
                  ) -> tuple[float, str, str]:
    """Model bias evaluation (L3609-3638).

    Returns (rel_bias %, bias_txt1, bias_txt2); bias_txt2 uses the plain-text
    form of the MATLAB TeX annotation.
    """
    yobs = np.asarray(yobs, dtype=float)
    yprd = np.asarray(yprd, dtype=float)
    aux = min(yobs.min(), yprd.min())
    if aux < 0:
        shf_yp, shf_yo = yprd - aux, yobs - aux
    else:
        shf_yp, shf_yo = yprd, yobs
    m = np.mean(shf_yo)
    if m == 0:
        rel_bias = rounddec(np.sum(shf_yp - shf_yo) / shf_yo.size * 100, 1)
    else:
        rel_bias = rounddec(np.sum(shf_yp - shf_yo) / shf_yo.size / m * 100, 1)

    txt2 = f" ({index_label} may be influenced by model bias)"
    if rel_bias < -bias_value:
        txt1 = f"Model bias: Underprediction by {rel_bias:g}% of the mean"
        if rel_bias < -500:
            txt1 = "Model bias: Underprediction by <-500% of the mean"
    elif rel_bias > bias_value:
        txt1 = f"Model bias: Overprediction by {rel_bias:g}% of the mean"
        if rel_bias > 500:
            txt1 = "Model bias: Overprediction by >500% of the mean"
    else:
        txt1, txt2 = "Model bias: NO", ""
    return rel_bias, txt1, txt2


@dataclass
class OutlierResult:
    text: str = "Presence of outliers (Q-test): NO"
    points: np.ndarray = field(default_factory=lambda: np.empty((0, 2)))  # [Yprd Yobs]
    indices: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=int))

    @property
    def present(self) -> bool:
        return self.points.size > 0


def dixon_outliers(yobs, yprd) -> OutlierResult:
    """Dixon's Q-test on residuals at alpha=0.05 (L3650-3678)."""
    yobs = np.asarray(yobs, dtype=float)
    yprd = np.asarray(yprd, dtype=float)
    err_ns = yobs - yprd
    err = np.sort(err_ns)
    span = err[-1] - err[0]
    if span == 0 or err.size < 3:
        return OutlierResult()
    q_low = (err[1] - err[0]) / span
    q_upp = (err[-1] - err[-2]) / span
    q_crit = 0.187 + (2.242 - 0.187) * err.size**-0.862

    idx: list[int] = []
    if q_low > q_crit:
        idx.extend(np.flatnonzero(err_ns == err[0]).tolist())
    if q_upp > q_crit:
        idx.extend(np.flatnonzero(err_ns == err[-1]).tolist())
    if not idx:
        return OutlierResult()
    pts = np.column_stack([yprd[idx], yobs[idx]])
    return OutlierResult(
        "Presence of outliers (Q-test): present and maybe affecting indicators",
        pts, np.asarray(idx, dtype=int))


def kge_nse_imbalance(yobs, yprd, nse: float, kge_star: float) -> str:
    """Correlation/variability imbalance diagnostic (L3476-3512).

    Returns '' when the fit sits inside the KGE* envelope, else one of the
    four v4.0 classes:
      class 1   rho ~ alpha, so the gap to the envelope is bias-driven
      class 2a  rho higher than alpha
      class 2b  alpha higher than rho, and underestimated (alpha < 1)
      class 2c  alpha higher than rho, and overestimated  (alpha >= 1)

    The caller applies the two outer gates MATLAB keeps in the same `if`:
    j=2 (so not E1) and no measurement uncertainty.

    NSE=GoF_IDXS(2), KGE_star=GoF_IDXS(3), i.e. nse=GoF_IDXS[1],
    kge_star=GoF_IDXS[2] (0-based), matching the envelope formulas
    (comments "KGE* lower/upper bound"), which are functions of NSE.
    Where an envelope argument turns negative MATLAB continues silently in
    complex arithmetic and compares real parts; cmath reproduces that.
    """
    import cmath

    yobs = np.asarray(yobs, dtype=float)
    yprd = np.asarray(yprd, dtype=float)
    # MATLAB gate NSE>0 (L3478); a NaN index fails it there and here
    if not np.isfinite(nse) or not np.isfinite(kge_star) or nse <= 0:
        return ""
    sq_nse = cmath.sqrt(nse)
    y_lb = (1 - cmath.sqrt(1.911 * nse - 3.909 * sq_nse + 2)).real
    y_ub = (1 - cmath.sqrt(2.114 * nse - 4.111 * sq_nse + 2)).real
    if not (kge_star < 0.95 and (kge_star > y_ub or kge_star < y_lb)):
        return ""

    r = float(np.corrcoef(yprd, yobs)[1, 0])
    # keep alpha a numpy scalar: a zero spread must give inf/nan, not raise
    alpha = np.std(yprd, ddof=1) / np.std(yobs, ddof=1)
    r2a = r / alpha

    rho = "\N{GREEK SMALL LETTER RHO}"
    al = "\N{GREEK SMALL LETTER ALPHA}"
    # tested in MATLAB's order, so a NaN ratio falls through to class 1
    # the mismatch text is broken after the colon so it fits the figure's
    # left column; MATLAB breaks it too (L3497), and the report file joins
    # it back into one line, as MATLAB does at L4017
    if abs(1 - r2a) > 0.05:
        head = f"Variability ({al}) - correlation ({rho}) mismatch:\n   "
        if r2a > 1.05:
            return head + f"{rho} higher than {al} ({r:.2f} > {alpha:.2f})"
        tail = "underestimated" if alpha < 1 else "overestimated"
        return (head + f"{al} higher than {rho} ({alpha:.2f} > {r:.2f})"
                f" and {tail}")
    return (f"Correlation ({rho}) \N{ALMOST EQUAL TO} variability ({al}), "
            f"but bias is non-negligible")
