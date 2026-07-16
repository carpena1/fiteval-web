"""Bootstrap confidence intervals: BCa with stationary block bootstrap.

Ports of bootstrapBca/bootbca (FITEVAL_GUI.m L4080-4222), blockbootstrap
(L4228-4483), stationary_bootstrap (Kevin Sheppard, L4636-4707) and
opt_block_length (Politis & White 2001 w/ Nordman 2007 correction, Patton's
code, L4711-4885).

RNG streams differ from MATLAB, so CIs are statistically (not bit-)
equivalent; everything deterministic (opt_block_length, jackknife, BCa
percentile math, prctile definition) is ported exactly.
"""

from __future__ import annotations

import math
import warnings

import numpy as np
from scipy.stats import norm

from .indices import gof_indexes


class BootstrapError(RuntimeError):
    pass


def matlab_prctile(x: np.ndarray, p: float) -> float:
    """MATLAB prctile: Hazen plotting positions (k-0.5)/n, linear interp."""
    return float(np.percentile(x, p, method="hazen"))


def _mlag(x: np.ndarray, n: int) -> np.ndarray:
    """James LeSage's mlag: matrix of 1..n lags, zeros for initial values."""
    nobs = x.shape[0]
    out = np.zeros((nobs, n))
    for j in range(1, n + 1):
        out[j:, j - 1] = x[: nobs - j]
    return out


def _lam(kk: np.ndarray) -> np.ndarray:
    """Flat-top kernel weights (opt_block_length helper, L4830-4833)."""
    a = np.abs(kk)
    return (a < 0.5) * 1.0 + 2.0 * (1.0 - a) * ((a >= 0.5) & (a <= 1.0))


def opt_block_length(data: np.ndarray) -> float:
    """Optimal average block length for the stationary bootstrap (BstarSB).

    Exact port of opt_block_length (L4711-4834) for a single column.
    """
    data = np.asarray(data, dtype=float).ravel()
    n = data.size
    # MATLAB: KN=max(5,sqrt(log10(n))) - equals 5 for any practical n
    kn_i = int(max(5, math.sqrt(math.log10(n))))
    mmax = int(math.ceil(math.sqrt(n))) + kn_i
    bmax = math.ceil(min(3 * math.sqrt(n), n / 3))
    c = 2.0

    # FIRST STEP: mhat = largest lag with significant autocorrelation
    lags = _mlag(data, mmax)[mmax:, :]
    base = data[mmax:]
    full = np.column_stack([base, lags])
    cc = np.corrcoef(full, rowvar=False)
    acf = cc[1:, 0]  # autocorrelations lag 1..mmax

    crit = c * math.sqrt(math.log10(n) / n)
    # windows of KN consecutive autocorrelations starting at lag m (1-based)
    n_win = mmax - kn_i + 1
    insignif = np.empty(n_win, dtype=bool)
    for m in range(n_win):
        insignif[m] = bool(np.all(np.abs(acf[m:m + kn_i]) < crit))
    hits = np.flatnonzero(insignif)
    if hits.size:
        mhat = int(hits[0]) + 1  # smallest m (1-based)
    else:
        signif = np.flatnonzero(np.abs(acf) > crit)
        if signif.size == 0:
            return 1.0  # MATLAB: mhat empty -> M empty -> Bstar=[1;1]
        mhat = int(signif[-1]) + 1

    m_big = mmax if 2 * mhat > mmax else 2 * mhat
    if m_big <= 0:
        return 1.0

    # SECOND STEP: autocovariances -M..M and kernel sums
    lags = _mlag(data, m_big)[m_big:, :]
    base = data[m_big:]
    cov = np.cov(np.column_stack([base, lags]), rowvar=False)
    acv = cov[:, 0]  # lag 0..M
    kk = np.arange(-m_big, m_big + 1, dtype=float)
    acv_sym = np.concatenate([acv[1:][::-1], acv])  # lag -M..M
    lam_w = _lam(kk / m_big)
    ghat = float(np.sum(lam_w * np.abs(kk) * acv_sym))
    dsbhat = 2.0 * float(np.sum(lam_w * acv_sym)) ** 2
    if dsbhat == 0:
        return 1.0
    bstar = (2.0 * ghat**2 / dsbhat) ** (1.0 / 3.0) * n ** (1.0 / 3.0)
    return float(min(bstar, bmax))


def stationary_bootstrap_indices(t: int, nboot: int, w: float,
                                 rng: np.random.Generator) -> np.ndarray:
    """(t, nboot) matrix of 0-based resampling indices (L4636-4707 + wrap).

    Column b is one resample; geometric mean block length w; indices that ran
    past the end are wrapped (blockbootstrap L4406-4413).
    """
    p = 1.0 / w
    idx = np.zeros((t, nboot), dtype=np.int64)
    idx[0, :] = rng.integers(1, t + 1, size=nboot)
    select = rng.random((t, nboot)) < p
    idx[select] = rng.integers(1, t + 1, size=int(select.sum()))
    for i in range(1, t):
        stay = ~select[i, :]
        idx[i, stay] = idx[i - 1, stay] + 1
    idx[idx > t] -= t
    return idx - 1


def efron_bootstrap_indices(t: int, nboot: int,
                            rng: np.random.Generator) -> np.ndarray:
    """(t, nboot) IID uniform resampling indices (Efron & Tibshirani 1993)."""
    return rng.integers(0, t, size=(t, nboot))


def _eval_indices_columns(yobs, yprd, yben, yerr, j, idx: np.ndarray,
                          chunk: int = 2000) -> np.ndarray:
    """Evaluate fun_GoF_Indexes for every resample column of idx, vectorized.

    Returns (nboot, 4) array [rmse, ceff, kge_star, kge] per resample.
    """
    t, nboot = idx.shape
    out = np.empty((nboot, 4))
    with np.errstate(divide="ignore", invalid="ignore"):
        for s in range(0, nboot, chunk):
            cols = idx[:, s:s + chunk]
            o = yobs[cols]
            pr = yprd[cols]
            b = yben[cols]
            e = yerr[cols]
            ssq = np.sum(np.abs(e) ** j, axis=0)
            ss = np.sum(np.abs(o - b) ** j, axis=0)
            ceff = 1.0 - ssq / ss
            rmse = np.sqrt(np.sum(e**2, axis=0) / t)

            mo = o.mean(axis=0)
            mp = pr.mean(axis=0)
            so = o.std(axis=0, ddof=1)
            sp = pr.std(axis=0, ddof=1)
            alpha = sp / so
            r = np.sum((o - mo) * (pr - mp), axis=0) / ((t - 1) * so * sp)
            beta = mp / mo
            kge = 1.0 - np.sqrt((r - 1) ** 2 + (alpha - 1) ** 2 + (beta - 1) ** 2)
            beta_star = 1.0 + (mp - mo) / so
            kge_star = 1.0 - np.sqrt((r - 1) ** 2 + (alpha - 1) ** 2
                                     + (beta_star - 1) ** 2)
            out[s:s + cols.shape[1], :] = np.column_stack(
                [rmse, ceff, kge_star, kge])
    return out


def _jackknife(yobs, yprd, yben, yerr, j) -> np.ndarray:
    """Leave-one-out fun_GoF_Indexes values, (n, 4)."""
    n = yobs.size
    jstat = np.empty((n, 4))
    keep = np.ones(n, dtype=bool)
    for i in range(n):
        keep[i] = False
        jstat[i] = gof_indexes(yobs[keep], yprd[keep], yben[keep], yerr[keep], j)
        keep[i] = True
    return jstat


def bca_ci(yobs, yprd, yben, yerr, j, nboot: int, bstype: int,
           rng: np.random.Generator | None = None, alpha: float = 0.05,
           ) -> tuple[np.ndarray, np.ndarray, int]:
    """95% BCa bootstrap CI for [RMSE, Ceff, KGE*, KGE].

    Returns (ci, bootstat, bstype_used): ci is (2, 4) [lower; upper],
    bootstat is (<=nboot, 4) with NaN rows dropped, and bstype_used reports
    whether the block bootstrap fell back to Efron (as the desktop app does).
    """
    yobs = np.asarray(yobs, dtype=float).ravel()
    yprd = np.asarray(yprd, dtype=float).ravel()
    yben = np.asarray(yben, dtype=float).ravel()
    yerr = np.asarray(yerr, dtype=float).ravel()
    rng = rng or np.random.default_rng()
    t = yobs.size

    stat = gof_indexes(yobs, yprd, yben, yerr, j)
    if not np.all(np.isfinite(stat)):
        raise BootstrapError(
            "Nonfinite result from the goodness-of-fit function "
            "(stats:bootci:NonfiniteBootfun)")

    bstype_used = bstype
    idx = None
    if bstype == 0:
        try:
            w = opt_block_length(yobs)
            idx = stationary_bootstrap_indices(t, nboot, w, rng)
        except Exception:
            warnings.warn("Problem using Politis and Romano (1994) block "
                          "bootstrap; Efron and Tibshirani (1993) bootstrap "
                          "will be used instead")
            bstype_used = 1
    if idx is None:
        idx = efron_bootstrap_indices(t, nboot, rng)

    bstat = _eval_indices_columns(yobs, yprd, yben, yerr, j, idx)
    bstat = bstat[~np.any(np.isnan(bstat), axis=1), :]

    # bias correction z0 per column (fz0, L4218-4222)
    with np.errstate(divide="ignore"):
        z0 = norm.ppf(np.mean(bstat < stat, axis=0)
                      + np.mean(bstat == stat, axis=0) / 2.0)

    # acceleration via jackknife, per index (bootbca L4164-4188, fixed
    # MATLAB): drop jackknife rows containing any NaN, then compute a
    # separate acceleration constant for each of the four indices.
    jstat = _jackknife(yobs, yprd, yben, yerr, j)
    jstat = jstat[~np.any(np.isnan(jstat), axis=1), :]
    n_j = jstat.shape[0]
    weights = np.full(n_j, 1.0 / n_j)
    mjstat = np.sum(jstat * weights[:, None], axis=0)          # (4,)
    score = mjstat - jstat                                     # (n_j, 4)
    iszero = np.all(score == 0, axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        skew = (np.sum(score**3 * weights[:, None], axis=0)
                / np.sum(score**2 * weights[:, None], axis=0) ** 1.5
                / math.sqrt(n_j))
    skew[iszero] = 0.0
    acc = skew / 6.0                                           # (4,)

    z_a1 = norm.ppf(alpha / 2.0)
    z_a2 = -z_a1
    with np.errstate(invalid="ignore"):
        pct1 = 100.0 * norm.cdf(z0 + (z0 + z_a1) / (1.0 - acc * (z0 + z_a1)))
        pct2 = 100.0 * norm.cdf(z0 + (z0 + z_a2) / (1.0 - acc * (z0 + z_a2)))
    pct1 = np.where(z0 == np.inf, 100.0, np.where(z0 == -np.inf, 0.0, pct1))
    pct2 = np.where(z0 == np.inf, 100.0, np.where(z0 == -np.inf, 0.0, pct2))

    lower = np.array([matlab_prctile(bstat[:, i], pct2[i]) for i in range(4)])
    upper = np.array([matlab_prctile(bstat[:, i], pct1[i]) for i in range(4)])
    ci = np.sort(np.vstack([lower, upper]), axis=0)
    return ci, bstat, bstype_used
