"""Evaluation pipeline - port of fitevaluation (FITEVAL_GUI.m L3334-3927).

evaluate_case() performs one evaluation (one output set); evaluate() is the
fiteval_2-level driver that handles repeated-row removal and, in Phase 2,
runs twice (with and without uncertainty).
"""

from __future__ import annotations

import numpy as np

from .bootstrap import bca_ci
from .config import FitevalConfig
from .dataio import DataError, drop_repeated_rows
from .indices import (INDEX_LABELS, OutlierResult, dixon_outliers, gof_indexes,
                      kge_nse_imbalance, kge_to_nse_threshold, relative_bias,
                      rounddec)
from .kde import KDEError, ksdensity_cdf
from .results import EvalCase, EvalResult

BENCHMARK_NOTE = (
    "Modified version of NSE using a benchmark series instead",
    "of the observation mean (Seibert, 2001)                 ",
)
BSTYPE_NOTE = {
    0: ("using Politis and Romano (1994) block bootstrap method",
        "for stationary dependent data.                        "),
    1: ("using Efron and Tibshirani (1993) bootstrap method",
        "for independent data.                             "),
}


class EngineError(RuntimeError):
    """User-facing evaluation failure (message mirrors the desktop app)."""


def _index_selection(flag: int, meas_unc: float) -> tuple[str, str, int, int, int]:
    """Port of L3366-3377: (label, sec_label, jexp, pri_pos, sec_pos).

    pri/sec_pos are 0-based positions in [rmse, ceff, kge_star, kge].
    """
    if flag <= 1:
        label, sec, jexp, pri, sec_pos = "NSE", "KGE*", 2, 1, 2
    elif flag == 2:
        label, sec, jexp, pri, sec_pos = "KGE*", "NSE", 2, 2, 1
    elif flag == 3:
        label, sec, jexp, pri, sec_pos = "KGE", "NSE", 2, 3, 1
    else:
        label, sec, jexp, pri, sec_pos = "E_1", "KGE*", 1, 1, 2
    if meas_unc != 0 and flag in (2, 3):
        label, sec, jexp, pri, sec_pos = "NSE", "KGE*", 2, 1, 2
    return label, sec, jexp, pri, sec_pos


def evaluate_case(case: EvalCase, cfg: FitevalConfig,
                  rng: np.random.Generator | None = None) -> EvalResult:
    """One fitevaluation run on prepared data."""
    yobs = np.asarray(case.yobs, dtype=float).ravel()
    yprd = np.asarray(case.yprd, dtype=float).ravel()

    # ---- NaN removal over [yobs yprd yben] (L3347-3361)
    cols = [yobs, yprd]
    if case.yben is not None:
        cols.append(np.asarray(case.yben, dtype=float).ravel())
    keep = ~np.isnan(np.column_stack(cols).sum(axis=1))
    yobs, yprd = yobs[keep], yprd[keep]
    yben = (np.asarray(case.yben, dtype=float).ravel()[keep]
            if case.yben is not None else np.full(yobs.size, yobs.mean()))
    if case.yerr is not None:
        yerr = np.asarray(case.yerr, dtype=float).ravel()[keep]
    else:
        yerr = yobs - yprd

    def _sub(a):
        return None if a is None else np.asarray(a, dtype=float).ravel()[keep]

    ub_omin, ub_omax = _sub(case.ub_omin), _sub(case.ub_omax)
    ub_pmin, ub_pmax = _sub(case.ub_pmin), _sub(case.ub_pmax)

    n = yobs.size
    if n < 3:
        raise EngineError("Load [Yprd Yobs] data first!")
    if np.std(yobs, ddof=1) == 0 or np.std(yprd, ddof=1) == 0:
        raise EngineError(
            "With equal Yprd values (horizontal line) or Yobs values "
            "(vertical line) bootstrapping is not possible")

    flag = cfg.gof_index_effective
    label, sec_label, jexp, pri, sec_pos = _index_selection(flag, case.meas_unc)
    forced_to_nse = flag in (2, 3) and label == "NSE"

    # ---- indices on the full data (L3381-3385)
    gof = gof_indexes(yobs, yprd, yben, yerr, jexp)
    main_idx = float(gof[pri])
    sec_idx = float(gof[sec_pos])
    rmse = float(gof[0])
    nrmse_pct = 100.0 * rmse / np.std(yobs, ddof=1)

    # ---- bootstrap CI (L3387-3407)
    ci, bstat, bstype_used = bca_ci(yobs, yprd, yben, yerr, jexp,
                                    cfg.n_resamples, cfg.bstype, rng=rng)
    main_ci = ci[:, pri].copy()
    sec_ci = (float(ci[0, sec_pos]), float(ci[1, sec_pos]))
    rmse_ci = ci[:, 0].copy()
    main_dstr = bstat[:, pri]

    # ---- rounding rules (L3409-3434)
    main_fmt = "%1.3f"
    if flag == 3:
        if abs(main_idx) > 10:
            main_fmt = "%1.0e"
        elif abs(main_idx) > 1:
            main_fmt = "%1.1f"
    else:
        main_ci = rounddec(main_ci, 3)

    if rmse / 10000 > 1:
        decim = 0
    elif rmse / 1000 > 1:
        decim = 1
    elif rmse / 100 > 1:
        decim = 2
    else:
        decim = 3
    aux_rmse = rounddec(rmse, decim - 1)
    if aux_rmse != 0:
        rmse = float(aux_rmse)
        rmse_ci = rounddec(rmse_ci, decim - 1)
        rmse_fmt = "%1.3f"
    else:
        rmse_fmt = "%1.3e"

    # ---- imbalance diagnostic (L3453-3489; see indices.py note).  v4.0 also
    # skips it under measurement uncertainty (MeasUncertValue==0, L3455),
    # where Yprd/Yobs no longer carry the plain spread the envelope assumes.
    imbalance = ""
    if jexp == 2 and case.meas_unc == 0:
        imbalance = kge_nse_imbalance(yobs, yprd, float(gof[1]), float(gof[2]))

    # ---- index probability function & classification (L3476-3548)
    if forced_to_nse:
        # KGE*/KGE class limits are stored in that index's scale
        # (GoFIndexSelection); a run forced back to NSE by active
        # uncertainty must be classified against the NSE-scale limits.
        # Round to 2 decimals like the Configuration dialog, so 0.73 -> 0.65.
        class_lim = tuple(round(kge_to_nse_threshold(t), 2)
                          for t in cfg.class_lim)
    else:
        class_lim = cfg.class_lim
    xi = np.linspace(0, 1, 1001)
    kde_failed = False
    if np.nansum(main_dstr) != main_dstr.size:
        lowerb = float(np.min(main_dstr)) - 0.05
        try:
            fi = ksdensity_cdf(main_dstr, xi, (lowerb, 1.001))
        except KDEError:
            fi = np.full(xi.size, np.nan)
            kde_failed = True
    else:
        fi = np.zeros(xi.size)  # Yobs is exactly Yprd

    cdf_x = rounddec(100 * xi, 1)
    aux = rounddec(100 * np.asarray(class_lim) - 0.1, 1)

    def _cdf_at(v: float) -> float:
        hit = np.flatnonzero(cdf_x == v)
        return float(fi[hit[0]]) if hit.size else np.nan

    verygood = rounddec(100 * (1 - _cdf_at(aux[2])), 1)
    good = rounddec(100 * (1 - _cdf_at(aux[1])) - verygood, 1)
    acceptable = rounddec(100 * (1 - _cdf_at(aux[0])) - good - verygood, 1)
    unsatisfactory = rounddec(100 - acceptable - good - verygood, 1)

    reglim = {
        "R1": f"{class_lim[2]:.3f} - {1:.3f}",
        "R2": f"{class_lim[1]:.3f} - {class_lim[2] - 0.001:.3f}",
        "R3": f"{class_lim[0]:.3f} - {class_lim[1] - 0.001:.3f}",
        "R4": f"< {class_lim[0]:.3f}",
    }

    lo, hi = float(main_ci[0]), float(main_ci[1])
    l1, l2, l3 = class_lim
    if lo < l1 and hi < l1:
        rating = "UNSATISFACTORY"
    elif lo >= l1 and hi < l2:
        rating = "ACCEPTABLE"
    elif lo >= l2 and hi < l3:
        rating = "GOOD"
    elif lo >= l3 and hi >= l3:
        rating = "VERY GOOD"
    else:
        t1 = t2 = ""
        if lo < l1:
            t1 = "UNSATISFACTORY"
        elif l1 <= lo < l2:
            t1 = "ACCEPTABLE"
        elif l2 <= lo < l3:
            t1 = "GOOD"
        if l1 <= hi < l2:
            t2 = "ACCEPTABLE"
        elif l2 <= hi < l3:
            t2 = "GOOD"
        elif hi >= l3:
            t2 = "VERY GOOD"
        rating = f"From {t1} to {t2}"

    # ---- bias & outliers (L3553-3624)
    bias_rel, bias1, bias2 = relative_bias(yobs, yprd, cfg.bias_value, label)
    out = dixon_outliers(yobs, yprd)

    return EvalResult(
        index_label=label, sec_label=sec_label, jexp=jexp, n=n,
        gof=gof, ci_all=ci.copy(),
        main_idx=main_idx, main_ci=(float(main_ci[0]), float(main_ci[1])),
        main_fmt=main_fmt, sec_idx=sec_idx, sec_ci=sec_ci,
        rmse=rmse, rmse_ci=(float(rmse_ci[0]), float(rmse_ci[1])),
        rmse_fmt=rmse_fmt, nrmse_pct=nrmse_pct,
        xi=xi, fi=fi, kde_failed=kde_failed,
        class_probs={"verygood": verygood, "good": good,
                     "acceptable": acceptable, "unsatisfactory": unsatisfactory},
        reglim=reglim, rating_text=rating,
        p_value=float(unsatisfactory) / 100.0,
        bias_rel=bias_rel, bias_txt1=bias1, bias_txt2=bias2,
        imbalance_txt=imbalance, outliers=out, outlier_indices=out.indices,
        yobs=yobs, yprd=yprd, ub_omin=ub_omin, ub_omax=ub_omax,
        ub_pmin=ub_pmin, ub_pmax=ub_pmax, nrcol=case.nrcol,
        bstype_used=bstype_used, class_lim=class_lim,
        benchmark_used=case.yben is not None, meas_unc=case.meas_unc,
        repeated_cases=case.repeated_cases,
        unc_type_lines=case.unc_lines,
    )


def prepare_case(data: np.ndarray, no_repeated: bool = False) -> EvalCase:
    """Interpret a no-uncertainty [Yobs Yprd (Yben)] array (fiteval_2 L3193)."""
    data = np.atleast_2d(np.asarray(data, dtype=float))
    repeated = 0
    if no_repeated:
        data, repeated = drop_repeated_rows(data)
    ncol = data.shape[1]
    if ncol < 2:
        raise DataError("Input data must contain at least 2 columns (at maximum 5)!")
    yben = data[:, 2] if ncol >= 3 else None
    return EvalCase(yobs=data[:, 0], yprd=data[:, 1], yben=yben,
                    nrcol=ncol, repeated_cases=repeated)


def evaluate(data: np.ndarray, cfg: FitevalConfig, no_repeated: bool = False,
             rng: np.random.Generator | None = None) -> EvalResult:
    """Phase-1 driver: no-uncertainty evaluation of [Yobs Yprd (Yben)]."""
    return evaluate_case(prepare_case(data, no_repeated), cfg, rng=rng)
