"""Measurement-uncertainty methods (Phase 2).

Ports of:
- readsUncertParam / InterpretDistInput (FITEVAL_GUI.m L5168-5237) - the
  encoded option string '<opt> <case> [oX v1 v2] [pX v1 v2]'
- UncString / ReadUncOptions (L2471-2575) - building that string
- computeCF (L5240-5462) + tricdf (L5465-5525) - correction factors
- the fiteval_2 uncertainty pipeline (L3015-3294): PER/error-file bounds,
  the option-2 uniform-CDF conversion, column interpretation and the
  uncertainty-corrected residual Yerror.

All arrays here are observed-first: [Yobs Yprd (Yben) ...extra columns].
MATLAB quirks are replicated deliberately (see inline notes) so outputs
match the desktop app; revisit together with the desktop fixes later.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import norm

from .dataio import DataError, drop_repeated_rows
from .results import EvalCase

DIST_LETTERS = {1: "N", 2: "L", 3: "T", 4: "U"}
DIST_NUMBERS = {v: k for k, v in DIST_LETTERS.items()}
DIST_NAMES = {1: "Normal", 2: "Lognormal", 3: "Triangular", 4: "Uniform"}

# OU_TypeTxt texts (fiteval_2 L3165-3181), padded exactly as the source
HARMEL_2010_BOTH = "Observations and model uncertainty included (Harmel et al. 2010):"
HARMEL_2010_OBS = "Uncertainty in observations included (Harmel et al. 2010):       "
HARMEL_2010_PRD = "Model uncertainty included (Harmel et al. 2010):                 "
HARMEL_2007_OBS = "Uncertainty in observations included (Harmel et al. 2007):       "
OU_OPTION_LINES = {
    1: "Single PER common to all observations.                           ",
    2: "Absolute error specific to each observed value.                  ",
    3: "Lower and upper error specific to each observed value.           ",
    4: "Using a correction factor based on probability distributions.    ",
}


class UncError(ValueError):
    """User-facing uncertainty-option problem (desktop-app wording)."""


@dataclass
class UncSpec:
    """Uncertainty options as selected in the GUI panel."""
    method: str                     # 'per' | 'per_mixed' | 'errfile' | 'cf'
    per: float | None = None        # single PER, 0<per<1
    err_data: np.ndarray | None = None  # (n,1) PER values | (n,2) bound lengths
    err_as_cf: bool = False         # option '2': force error file -> CF method
    obs_dist: int = 0               # 0 none, 1 N, 2 L, 3 T, 4 U
    prd_dist: int = 0
    cvo: float | None = None        # CV (%) for N/L
    cvp: float | None = None
    plubo: float | None = None      # lower/upper bound (%) for T/U
    puubo: float | None = None
    plubp: float | None = None
    puubp: float | None = None


# ---------------------------------------------------------------------------
# Option string encode / decode
# ---------------------------------------------------------------------------

def _dist_part(prefix: str, dist: int, v1: float, v2: float | None) -> str:
    letter = DIST_LETTERS[dist]
    if dist in (1, 2):
        return f" {prefix}{letter} {v1:g}"
    return f" {prefix}{letter} {v1:g} {v2:g}"


def build_unc_string(spec: UncSpec, data_ncols: int) -> str:
    """UncString port (L2559-2575); data_ncols is 2 or 3 (benchmark)."""
    if spec.method == "per":
        if spec.per is None or not (0 < spec.per < 1):
            raise UncError("PER must >0 and <1")
        return f"{spec.per:g}"
    if spec.method == "errfile":
        return "1" if data_ncols == 2 else "2"
    if spec.method == "cf":
        obs_on = spec.obs_dist in (1, 2, 3, 4)
        prd_on = spec.prd_dist in (1, 2, 3, 4)
        if obs_on:
            case = (11 if prd_on else 9) + (data_ncols - 2)
            txt = f"3 {case}"
            txt += _dist_part("o", spec.obs_dist,
                              spec.plubo if spec.obs_dist in (3, 4) else spec.cvo,
                              spec.puubo)
            if prd_on:
                txt += _dist_part("p", spec.prd_dist,
                                  spec.plubp if spec.prd_dist in (3, 4) else spec.cvp,
                                  spec.puubp)
            return txt
        if prd_on:
            case = 13 + (data_ncols - 2)
            return f"4 {case}" + _dist_part(
                "p", spec.prd_dist,
                spec.plubp if spec.prd_dist in (3, 4) else spec.cvp, spec.puubp)
        raise UncError("Select Obs and/or Prd uncertainty!")
    raise UncError("Unknown uncertainty method")


def parse_unc_string(s: str):
    """readsUncertParam port (L5168-5237).

    Returns (option, case, obs_dist, prd_dist, cvo, cvp,
             plubo, puubo, plubp, puubp); distributions 0 when absent.
    """
    s = s.strip()
    option = float(s.split()[0])
    parts = s.split()
    case = int(parts[1]) if len(parts) > 1 else None

    obs_dist = prd_dist = 0
    cvo = cvp = plubo = puubo = plubp = puubp = None

    def read_block(block: str):
        letter = block[0]
        if letter not in DIST_NUMBERS:
            raise UncError("Invalid ditribution notation! Use N, L, T or U")
        vals = [float(v) for v in block[1:].split()]
        return DIST_NUMBERS[letter], vals

    o_pos = s.find("o")
    p_pos = s.find("p")
    if o_pos != -1:
        end = p_pos - 1 if p_pos != -1 else len(s)
        obs_dist, vals = read_block(s[o_pos + 1:end].strip())
        if obs_dist in (1, 2):
            cvo = vals[0]
        else:
            if len(vals) < 2:
                raise UncError("Wrong Obs ditribution notation!")
            plubo, puubo = vals[0], vals[1]
    if p_pos != -1:
        prd_dist, vals = read_block(s[p_pos + 1:].strip())
        if prd_dist in (1, 2):
            cvp = vals[0]
        else:
            if len(vals) < 2:
                raise UncError("Wrong Prd ditribution notation!")
            plubp, puubp = vals[0], vals[1]
    return option, case, obs_dist, prd_dist, cvo, cvp, plubo, puubo, plubp, puubp


# ---------------------------------------------------------------------------
# Distribution helpers
# ---------------------------------------------------------------------------

def unifcdf(x, a, b):
    """MATLAB unifcdf: NaN when b<=a, clamped linear otherwise."""
    x = np.asarray(x, dtype=float)
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        y = np.clip((x - a) / (b - a), 0.0, 1.0)
    return np.where(b <= a, np.nan, y)


def tricdf(x, lb, ub, mode):
    """Triangular CDF, mode-parameterized (tricdf_scalar, L5472-5525)."""
    t = np.asarray(x, dtype=float)
    a = np.asarray(lb, dtype=float) + np.zeros_like(t)
    b = np.asarray(ub, dtype=float) + np.zeros_like(t)
    c = np.asarray(mode, dtype=float) + np.zeros_like(t)
    bad = (b <= a) | (c < a) | (c > b)
    with np.errstate(divide="ignore", invalid="ignore"):
        y = np.where(t <= c,
                     (t - a) ** 2 / ((b - a) * (c - a)),
                     1.0 - (b - t) ** 2 / ((b - a) * (b - c)))
    y = np.where(t < a, 0.0, y)
    y = np.where(t > b, 1.0, y)
    return np.where(bad, np.nan, y)


def _logn_check(x, label="data"):
    if np.any(np.asarray(x) + 1e-9 < 0):
        raise UncError("Lognormal distribution incompatible with data!")


# ---------------------------------------------------------------------------
# computeCF (L5240-5462)
# ---------------------------------------------------------------------------

def compute_cf(case: int, obs_dist: int, prd_dist: int,
               obs: np.ndarray, prd: np.ndarray, bch: np.ndarray | None,
               cvo: float | None, cvp: float | None,
               lubo=None, uubo=None, lubp=None, uubp=None,
               perprob: float = 95.0) -> np.ndarray:
    """Returns WRITEDATA = [OBS PRD (BCH) CF(/CFmax) bounds...] obs-first.

    cvo/cvp are FRACTIONS here (already divided by 100, as at L3075).
    """
    obs = np.asarray(obs, dtype=float).ravel()
    prd = np.asarray(prd, dtype=float).ravel()

    if case in (9, 10, 13, 14):
        if case in (9, 10):
            x, y, cv, lub, uub, dist = obs, prd, cvo, lubo, uubo, obs_dist
        else:
            x, y, cv, lub, uub, dist = prd, obs, cvp, lubp, uubp, prd_dist
        x = x.copy()
        y = y.copy()

        if dist in (1, 2):
            if dist == 1:
                sigma = np.abs(cv * x)
            else:
                sigma = np.full(x.size, np.sqrt(np.log(cv**2 + 1)))
                _logn_check(x)
                x = np.log(x + 1e-9) - 0.5 * sigma**2
                y = np.log(y + 1e-9)
            with np.errstate(divide="ignore", invalid="ignore"):
                z = np.abs((y - x) / sigma)
            cf = norm.cdf(z) - 0.5
            cfmax = np.full(x.size, 0.5)
            # NOTE - for lognormal these bounds live in ln-space (L5284-5285)
            lub = x - sigma
            uub = x + sigma
        elif dist == 3:
            cdf_o = tricdf(x, lub, uub, x)
            cf = np.abs(cdf_o - tricdf(y, lub, uub, x))
            cfmax = np.where(x - y < 0, 1.0 - cdf_o, cdf_o)
        elif dist == 4:
            cdf_o = unifcdf(x, lub, uub)
            cf = np.abs(cdf_o - unifcdf(y, lub, uub))
            cfmax = np.where(x - y < 0, 1.0 - cdf_o, cdf_o)
        else:
            raise UncError("Wrong distribution notation of Obs or Prd!")

        nan_ix = np.isnan(cf)
        cf[nan_ix] = cfmax[nan_ix]
        with np.errstate(divide="ignore", invalid="ignore"):
            cf_cfmax = cf / cfmax
        if dist in (3, 4):
            # prediction outside the support [lub, uub]: CF/CFmax = 1 (the
            # limit of the ratio); avoids 0/0 when the observation lies on a
            # bound (CFmax = 0). Degenerate bounds (uub <= lub) stay NaN.
            out_ix = (uub > lub) & ((y < lub) | (y > uub))
            cf_cfmax = np.where(out_ix, 1.0, cf_cfmax)
        cols = [obs, prd] + ([bch] if bch is not None else []) \
            + [cf_cfmax, lub, uub]
        return np.column_stack(cols)

    if case in (11, 12):
        prob_inf = 0.01 * (100 - perprob) / 2
        prob_sup = 0.01 * (50 + perprob / 2)

        sigma_o = sigma_p = None
        if obs_dist in (1, 2):
            if obs_dist == 1:
                sigma_o = np.abs(cvo * obs)
                mu_o = obs
                lubo = norm.ppf(prob_inf, loc=mu_o, scale=sigma_o)
                uubo = norm.ppf(prob_sup, loc=mu_o, scale=sigma_o)
            else:
                sigma_o = np.full(obs.size, np.sqrt(np.log(cvo**2 + 1)))
                _logn_check(obs)
                mu_o = np.log(obs + 1e-9) - 0.5 * sigma_o**2
                lubo = np.exp(sigma_o * norm.ppf(prob_inf) + mu_o)
                uubo = np.exp(sigma_o * norm.ppf(prob_sup) + mu_o)
        if prd_dist in (1, 2):
            if prd_dist == 1:
                sigma_p = np.abs(cvp * prd)
                mu_p = prd
                lubp = norm.ppf(prob_inf, loc=mu_p, scale=sigma_p)
                uubp = norm.ppf(prob_sup, loc=mu_p, scale=sigma_p)
            else:
                sigma_p = np.full(prd.size, np.sqrt(np.log(cvp**2 + 1)))
                _logn_check(prd)
                mu_p = np.log(prd + 1e-9) - 0.5 * sigma_p**2
                lubp = np.exp(sigma_p * norm.ppf(prob_inf) + mu_p)
                uubp = np.exp(sigma_p * norm.ppf(prob_sup) + mu_p)

        # P[O < bound]; NOTE - N/LN use the RAW series as the location
        # parameter here (L5390-5391), replicated deliberately
        if obs_dist == 1:
            p_o_upp = norm.cdf(uubp, loc=obs, scale=sigma_o)
            p_o_low = norm.cdf(lubp, loc=obs, scale=sigma_o)
        elif obs_dist == 2:
            with np.errstate(divide="ignore", invalid="ignore"):
                p_o_upp = norm.cdf((np.log(np.maximum(uubp, 0)) - obs) / sigma_o)
                p_o_low = norm.cdf((np.log(np.maximum(lubp, 0)) - obs) / sigma_o)
        elif obs_dist == 3:
            p_o_upp = tricdf(uubp, lubo, uubo, obs)
            p_o_low = tricdf(lubp, lubo, uubo, obs)
        elif obs_dist == 4:
            p_o_upp = unifcdf(uubp, lubo, uubo)
            p_o_low = unifcdf(lubp, lubo, uubo)
        else:
            raise UncError("Wrong distribution notation of Obs!")

        if prd_dist == 1:
            p_p_upp = norm.cdf(uubo, loc=prd, scale=sigma_p)
            p_p_low = norm.cdf(lubo, loc=prd, scale=sigma_p)
        elif prd_dist == 2:
            with np.errstate(divide="ignore", invalid="ignore"):
                p_p_upp = norm.cdf((np.log(np.maximum(uubo, 0)) - prd) / sigma_p)
                p_p_low = norm.cdf((np.log(np.maximum(lubo, 0)) - prd) / sigma_p)
        elif prd_dist == 3:
            p_p_upp = tricdf(uubo, lubp, uubp, prd)
            p_p_low = tricdf(lubo, lubp, uubp, prd)
        elif prd_dist == 4:
            p_p_upp = unifcdf(uubo, lubp, uubp)
            p_p_low = unifcdf(lubo, lubp, uubp)
        else:
            raise UncError("Wrong distribution notation of Prd!")

        cf = 1.0 - (p_o_upp - p_o_low) * (p_p_upp - p_p_low)  # CFmax = 1

        # error bars for N/LN revert to mean +- sigma (L5430-5441);
        # for LN sigma is the ln-space value applied to the raw series
        if obs_dist in (1, 2):
            lubo, uubo = obs - sigma_o, obs + sigma_o
        if prd_dist in (1, 2):
            lubp, uubp = prd - sigma_p, prd + sigma_p

        cols = [obs, prd] + ([bch] if bch is not None else []) \
            + [cf, lubo, uubo, lubp, uubp]
        return np.column_stack(cols)

    raise UncError("Indicate Case number (9,10,11,12,13 or 14)!")


# ---------------------------------------------------------------------------
# fiteval_2 uncertainty pipeline (L3015-3294)
# ---------------------------------------------------------------------------

def _per_to_cf(data: np.ndarray, len1: np.ndarray, len2: np.ndarray
               ) -> np.ndarray:
    """Uniform-PDF CF conversion (L3023-3058); data obs-first 2-3 cols."""
    yobs = data[:, 0]
    yprd = data[:, 1]
    lb = yobs - len1
    ub = yobs + len2
    cdf_o = unifcdf(yobs, lb, ub)
    cf = np.abs(cdf_o - unifcdf(yprd, lb, ub))
    # CFmax on the side of the prediction, as in compute_cf: F(O) below O and
    # 1 - F(O) above it. The former constant 0.5 holds only for symmetric
    # bounds (len1 == len2), where F(O) = 0.5 and the result is unchanged;
    # with asymmetric bounds it gave CF > 1 inside the interval and CF < 1
    # outside it. A prediction outside [lb, ub] gets CF/CFmax = 1 (the limit
    # of the ratio; avoids 0/0 when O lies on a bound).
    cfmax = np.where(yprd > yobs, 1.0 - cdf_o, cdf_o)
    with np.errstate(divide="ignore", invalid="ignore"):
        cf_cfmax = cf / cfmax
    valid = ub > lb                      # degenerate bounds stay NaN (unifcdf)
    cf_cfmax = np.where(valid & (yprd == yobs), 0.0, cf_cfmax)
    cf_cfmax = np.where(valid & ((yprd < lb) | (yprd > ub)), 1.0, cf_cfmax)
    if data.shape[1] == 2:
        return np.column_stack([yobs, yprd, cf_cfmax, lb, ub])
    return np.column_stack([yobs, yprd, data[:, 2], cf_cfmax, lb, ub])


def _ou_lines(meas: float, nrcol: int) -> tuple[str, str]:
    """OU_TypeTxt selection (L3165-3266)."""
    if meas == 3:
        head = HARMEL_2010_BOTH if nrcol in (7, 8) else HARMEL_2010_OBS
        return head, OU_OPTION_LINES[4]
    if meas == 4:
        return HARMEL_2010_PRD, OU_OPTION_LINES[4]
    head = HARMEL_2007_OBS
    if 0 < meas < 1:
        return head, OU_OPTION_LINES[1]
    if meas == 1:
        return head, OU_OPTION_LINES[2] if nrcol == 3 else OU_OPTION_LINES[3]
    if meas == 2:
        return head, OU_OPTION_LINES[2] if nrcol == 4 else OU_OPTION_LINES[3]
    return head, OU_OPTION_LINES[1]


def prepare_unc_cases(data: np.ndarray, spec: UncSpec,
                      no_repeated: bool = False
                      ) -> tuple[EvalCase, EvalCase]:
    """Build the (with-uncertainty, without-uncertainty) case pair.

    `data` is obs-first [Yobs Yprd (Yben)], 2 or 3 columns.  Returns the two
    EvalCases evaluated as fiteval_2 runs fitevaluation twice (L3307, L3335).
    """
    data = np.atleast_2d(np.asarray(data, dtype=float))
    ncol = data.shape[1]
    if ncol < 2 or ncol > 3:
        raise DataError("Input data must contain at least 2 columns (at maximum 5)!")

    # ---- augment columns per method ------------------------------------
    if spec.method == "per":
        if spec.per is None or not (0 < spec.per < 1):
            raise UncError("PER must >0 and <1")
        aux = data.copy()
        meas = spec.per
    elif spec.method == "per_mixed":
        # multi-run common PER (MR_MixedMethod=2, L3021-3058): converted to
        # correction factors through the uniform CDF, unlike the single-run
        # PER bounds method
        if spec.per is None or not (0 < spec.per < 1):
            raise UncError("PER must >0 and <1")
        blen = np.abs(data[:, 0] * spec.per)
        aux = _per_to_cf(data, blen, blen)
        meas = 3.0
    elif spec.method == "errfile":
        err = np.atleast_2d(np.asarray(spec.err_data, dtype=float))
        if err.shape[0] != data.shape[0]:
            raise UncError(
                f"Error data rows ({err.shape[0]}) differ from data rows "
                f"({data.shape[0]})")
        if err.shape[1] not in (1, 2):
            raise UncError("Error data must have 1 (PER) or 2 (bounds) columns")
        # bounds (PER) method unless the CF conversion is forced: option '2'
        # (MR_MixedMethod=1) always, or a benchmark column present
        # (MeasUncertValue==2 enters the mixed block, fiteval_2 L3016-3060).
        if not spec.err_as_cf and ncol == 2:
            aux = np.column_stack([data, err])
            meas = 1.0
        else:
            if err.shape[1] == 1:
                len1 = np.abs(data[:, 0] * err[:, 0])
                len2 = len1
            else:
                len1, len2 = err[:, 0], err[:, 1]
            aux = _per_to_cf(data, len1, len2)
            meas = 3.0
    elif spec.method == "cf":
        obs, prd = data[:, 0], data[:, 1]
        bch = data[:, 2] if ncol == 3 else None
        obs_on = spec.obs_dist in (1, 2, 3, 4)
        prd_on = spec.prd_dist in (1, 2, 3, 4)
        if not obs_on and not prd_on:
            raise UncError("Select Obs and/or Prd uncertainty!")
        if obs_on:
            case = (11 if prd_on else 9) + (ncol - 2)
            meas = 3.0
        else:
            case = 13 + (ncol - 2)
            meas = 4.0
        cvo = spec.cvo / 100.0 if spec.cvo is not None else None
        cvp = spec.cvp / 100.0 if spec.cvp is not None else None
        lubo = uubo = lubp = uubp = None
        if spec.obs_dist in (3, 4) and case in (9, 10, 11, 12):
            lubo = obs * (1 - spec.plubo / 100.0)
            uubo = obs * (1 + spec.puubo / 100.0)
            lo = np.minimum(lubo, uubo)
            uubo = np.maximum(lubo, uubo)
            lubo = lo
        if spec.prd_dist in (3, 4) and case in (11, 12, 13, 14):
            lubp = prd * (1 - spec.plubp / 100.0)
            uubp = prd * (1 + spec.puubp / 100.0)
            lo = np.minimum(lubp, uubp)
            uubp = np.maximum(lubp, uubp)
            lubp = lo
        aux = compute_cf(case, spec.obs_dist, spec.prd_dist, obs, prd, bch,
                         cvo, cvp, lubo, uubo, lubp, uubp, 95.0)
    else:
        raise UncError("Unknown uncertainty method")

    # ---- repeated-case removal on the augmented array (L3145-3159) -----
    repeated = 0
    if no_repeated:
        aux, repeated = drop_repeated_rows(aux)

    # ---- column interpretation (L3187-3266) -----------------------------
    nrcol = aux.shape[1]
    yobs = aux[:, 0]
    yprd = aux[:, 1]
    yben = None
    cf_cfmax = None
    ub_omin = ub_omax = ub_pmin = ub_pmax = None

    if meas == 1:
        if nrcol == 3:
            symm = yobs * aux[:, 2]
            ub_omin, ub_omax = yobs - symm, yobs + symm
        elif nrcol == 4:
            ub_omin, ub_omax = yobs - aux[:, 2], yobs + aux[:, 3]
        else:
            raise DataError("Input data must contain at least 3 columns (at maximum 4)!")
    elif meas == 2:
        yben = aux[:, 2]
        if nrcol == 4:
            symm = yobs * aux[:, 3]
            ub_omin, ub_omax = yobs - symm, yobs + symm
        elif nrcol == 5:
            ub_omin, ub_omax = yobs - aux[:, 3], yobs + aux[:, 4]
        else:
            raise DataError("Input data must contain at least 4 columns (at maximum 5)!")
    elif meas == 3:
        if nrcol == 5:
            cf_cfmax, ub_omin, ub_omax = aux[:, 2], aux[:, 3], aux[:, 4]
        elif nrcol == 6:
            yben = aux[:, 2]
            cf_cfmax, ub_omin, ub_omax = aux[:, 3], aux[:, 4], aux[:, 5]
        elif nrcol == 7:
            cf_cfmax = aux[:, 2]
            ub_omin, ub_omax, ub_pmin, ub_pmax = (aux[:, 3], aux[:, 4],
                                                  aux[:, 5], aux[:, 6])
        elif nrcol == 8:
            yben = aux[:, 2]
            cf_cfmax = aux[:, 3]
            ub_omin, ub_omax, ub_pmin, ub_pmax = (aux[:, 4], aux[:, 5],
                                                  aux[:, 6], aux[:, 7])
        else:
            raise DataError("Input data must contain at least 5 columns (at maximum 8)!")
    elif meas == 4:
        if nrcol == 5:
            cf_cfmax, ub_pmin, ub_pmax = aux[:, 2], aux[:, 3], aux[:, 4]
        elif nrcol == 6:
            yben = aux[:, 2]
            cf_cfmax, ub_pmin, ub_pmax = aux[:, 3], aux[:, 4], aux[:, 5]
        else:
            raise DataError("Input data must contain at least 5 columns (at maximum 6)!")
    elif 0 < meas < 1:  # single PER
        if nrcol == 3:
            yben = aux[:, 2]
        blen = np.abs(yobs * meas)
        ub_omin, ub_omax = yobs - blen, yobs + blen
    else:
        raise UncError("Wrong option value provided!")

    # ---- uncertainty-corrected residual Yerror (L3270-3294) -------------
    if meas < 3:
        yerr = np.zeros(yobs.size)
        below = yprd < ub_omin
        above = yprd > ub_omax
        yerr[below] = ub_omin[below] - yprd[below]
        yerr[above] = ub_omax[above] - yprd[above]
    else:
        yerr = cf_cfmax * (yobs - yprd)

    unc_case = EvalCase(
        yobs=yobs, yprd=yprd, yben=yben, yerr=yerr,
        ub_omin=ub_omin, ub_omax=ub_omax, ub_pmin=ub_pmin, ub_pmax=ub_pmax,
        meas_unc=meas, nrcol=nrcol, repeated_cases=repeated,
        unc_lines=_ou_lines(meas, nrcol))

    plain_case = EvalCase(yobs=yobs, yprd=yprd, yben=yben,
                          meas_unc=0.0, nrcol=2 if yben is None else 3,
                          repeated_cases=repeated)
    return unc_case, plain_case
