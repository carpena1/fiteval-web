"""Result containers shared by engine, report and figures."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .indices import OutlierResult


@dataclass
class EvalCase:
    """One evaluation input set, observed-first, after column interpretation.

    Phase 1 uses only yobs/yprd/yben; the uncertainty arrays are filled by
    Phase 2 (fiteval_2 L3187-3294 column layouts).
    """
    yobs: np.ndarray
    yprd: np.ndarray
    yben: np.ndarray | None = None
    yerr: np.ndarray | None = None          # uncertainty-corrected residual
    ub_omin: np.ndarray | None = None       # observation uncertainty bounds
    ub_omax: np.ndarray | None = None
    ub_pmin: np.ndarray | None = None       # prediction uncertainty bounds
    ub_pmax: np.ndarray | None = None
    meas_unc: float = 0.0                   # MeasUncertValue
    nrcol: int = 2                          # on-disk column count
    repeated_cases: int = 0
    unc_lines: tuple[str, str] | None = None  # OU_TypeTxt for the report


@dataclass
class EvalResult:
    """Everything fitevaluation computes for one run (one output set)."""
    # index identification
    index_label: str            # primary index name ('NSE','KGE*','KGE','E_1')
    sec_label: str              # secondary index name
    jexp: int
    n: int
    # values
    gof: np.ndarray             # [rmse, ceff, kge_star, kge] on the full data
    main_idx: float
    main_ci: tuple[float, float]        # rounded per MATLAB
    main_fmt: str               # printf format for main index in NUMOUT
    sec_idx: float
    sec_ci: tuple[float, float]         # unrounded CI of secondary index
    rmse: float                 # possibly rounded per magnitude rule
    rmse_ci: tuple[float, float]
    rmse_fmt: str               # '%1.3f' or '%1.3e'
    nrmse_pct: float            # 100*rmse/std(yobs)
    # classification
    xi: np.ndarray
    fi: np.ndarray              # kernel CDF of the main-index distribution
    class_probs: dict[str, float]       # verygood/good/acceptable/unsatisfactory
    reglim: dict[str, str]              # R1..R4 range strings
    rating_text: str            # txtMainIdx
    p_value: float
    kde_failed: bool = False
    # diagnostics
    bias_rel: float = 0.0
    bias_txt1: str = ""
    bias_txt2: str = ""
    imbalance_txt: str = ""
    outliers: OutlierResult = field(default_factory=OutlierResult)
    outlier_indices: np.ndarray = field(default_factory=lambda: np.empty(0, int))
    # cleaned data (NaN rows removed) for plotting
    yobs: np.ndarray = field(default_factory=lambda: np.empty(0))
    yprd: np.ndarray = field(default_factory=lambda: np.empty(0))
    ub_omin: np.ndarray | None = None
    ub_omax: np.ndarray | None = None
    ub_pmin: np.ndarray | None = None
    ub_pmax: np.ndarray | None = None
    nrcol: int = 2
    # full BCa CI [lower; upper] for every index [rmse, ceff, kge*, kge],
    # so the multi-run summary can report NSE and KGE*/KGE regardless of
    # which one is the selected primary
    ci_all: np.ndarray | None = None
    # provenance
    bstype_used: int = 0
    class_lim: tuple[float, float, float] = (0.65, 0.80, 0.90)
    benchmark_used: bool = False
    meas_unc: float = 0.0
    repeated_cases: int = 0
    unc_type_lines: tuple[str, str] | None = None   # OU_TypeTxt (Phase 2)
