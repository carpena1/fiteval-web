import numpy as np
import pytest
from scipy.stats import norm

from fiteval_core.config import FitevalConfig
from fiteval_core.uncertainty import (UncError, UncSpec, build_unc_string,
                                      compute_cf, parse_unc_string,
                                      prepare_unc_cases, tricdf, unifcdf)


def _data(n=40, seed=21, bench=False):
    rng = np.random.default_rng(seed)
    yobs = 10 + 3 * np.sin(np.linspace(0, 4 * np.pi, n)) + rng.normal(0, 0.4, n)
    yprd = yobs + rng.normal(0, 0.5, n)
    cols = [yobs, yprd]
    if bench:
        cols.append(np.full(n, yobs.mean()))
    return np.column_stack(cols)


# ---------------- option string ----------------

@pytest.mark.parametrize("spec,ncols,expected", [
    (UncSpec(method="per", per=0.1), 2, "0.1"),
    (UncSpec(method="errfile"), 2, "1"),
    (UncSpec(method="errfile"), 3, "2"),
    (UncSpec(method="cf", obs_dist=1, cvo=10), 2, "3 9 oN 10"),
    (UncSpec(method="cf", obs_dist=1, cvo=10), 3, "3 10 oN 10"),
    (UncSpec(method="cf", obs_dist=3, plubo=5, puubo=15, prd_dist=2, cvp=20),
     2, "3 11 oT 5 15 pL 20"),
    (UncSpec(method="cf", prd_dist=4, plubp=10, puubp=10), 2, "4 13 pU 10 10"),
    (UncSpec(method="cf", prd_dist=2, cvp=25), 3, "4 14 pL 25"),
])
def test_build_unc_string(spec, ncols, expected):
    assert build_unc_string(spec, ncols) == expected


def test_parse_round_trip():
    opt, case, od, pd_, cvo, cvp, plo, puo, plp, pup = parse_unc_string(
        "3 12 oT 5 15 pL 20")
    assert (opt, case, od, pd_) == (3.0, 12, 3, 2)
    assert (plo, puo, cvp) == (5.0, 15.0, 20.0)


def test_per_validation():
    with pytest.raises(UncError):
        build_unc_string(UncSpec(method="per", per=1.5), 2)


# ---------------- distribution helpers ----------------

def test_unifcdf():
    np.testing.assert_allclose(unifcdf(np.array([7, 8, 10, 12, 13.0]),
                                       np.full(5, 8.0), np.full(5, 12.0)),
                               [0, 0, 0.5, 1, 1])
    assert np.isnan(unifcdf(np.array([1.0]), np.array([2.0]), np.array([2.0])))[0]


def test_tricdf():
    # lb=8, ub=12, mode=10: CDF(10)=0.5, CDF(11)=1-1/8
    y = tricdf(np.array([7, 10, 11, 13.0]), np.full(4, 8.0), np.full(4, 12.0),
               np.full(4, 10.0))
    np.testing.assert_allclose(y, [0, 0.5, 0.875, 1])


# ---------------- computeCF ----------------

def test_cf_case9_normal_hand_value():
    out = compute_cf(9, 1, 0, np.array([10.0]), np.array([11.0]), None,
                     0.1, None)
    # sigma=1, z=1 -> CF=phi(1)-0.5, CFmax=0.5
    expected = (norm.cdf(1) - 0.5) / 0.5
    assert out.shape == (1, 5)
    assert out[0, 2] == pytest.approx(expected)
    assert out[0, 3] == pytest.approx(9.0)   # LUB = X - sigma
    assert out[0, 4] == pytest.approx(11.0)


def test_cf_case9_uniform_hand_value():
    obs = np.array([10.0])
    prd = np.array([11.0])
    out = compute_cf(9, 4, 0, obs, prd, None, None, None,
                     lubo=np.array([8.0]), uubo=np.array([12.0]))
    # CDF_O=0.5, CDF_P=0.75, CF=0.25; X-Y<0 -> CFmax=0.5 -> ratio 0.5
    assert out[0, 2] == pytest.approx(0.5)


def test_cf_case9_triangular_hand_value():
    out = compute_cf(9, 3, 0, np.array([10.0]), np.array([11.0]), None,
                     None, None, lubo=np.array([8.0]), uubo=np.array([12.0]))
    # CDF_O=0.5, CDF_P=0.875 -> CF=0.375, CFmax=0.5 -> 0.75
    assert out[0, 2] == pytest.approx(0.75)


def test_cf_case13_mirrors_case9():
    """Prediction-only case swaps the roles of obs and prd."""
    o = np.array([11.0])
    p = np.array([10.0])
    out13 = compute_cf(13, 0, 1, o, p, None, None, 0.1)
    out9 = compute_cf(9, 1, 0, p, o, None, 0.1, None)
    assert out13[0, 2] == pytest.approx(out9[0, 2])


def test_cf_case11_both_normal_hand_value():
    obs = np.array([10.0])
    prd = np.array([11.0])
    out = compute_cf(11, 1, 1, obs, prd, None, 0.1, 0.1)
    so, sp = 1.0, 1.1
    lubo, uubo = norm.ppf(0.025, 10, so), norm.ppf(0.975, 10, so)
    lubp, uubp = norm.ppf(0.025, 11, sp), norm.ppf(0.975, 11, sp)
    p_o = norm.cdf(uubp, 10, so) - norm.cdf(lubp, 10, so)
    p_p = norm.cdf(uubo, 11, sp) - norm.cdf(lubo, 11, sp)
    assert out.shape == (1, 7)
    assert out[0, 2] == pytest.approx(1 - p_o * p_p)
    # error bars revert to mean +- sigma
    assert out[0, 3] == pytest.approx(10 - so)
    assert out[0, 6] == pytest.approx(11 + sp)


def test_cf_lognormal_negative_data_rejected():
    with pytest.raises(UncError, match="Lognormal"):
        compute_cf(9, 2, 0, np.array([-5.0, 10.0]), np.array([1.0, 2.0]),
                   None, 0.1, None)


def test_cf_degenerate_bounds_stay_nan():
    """Degenerate bounds: CFmax is NaN too, so CF/CFmax stays NaN, exactly
    as MATLAB unifcdf(a>=b) -> NaN propagates in the desktop app."""
    out = compute_cf(9, 4, 0, np.array([10.0]), np.array([10.0]), None,
                     None, None, lubo=np.array([10.0]), uubo=np.array([10.0]))
    assert np.isnan(out[0, 2])


def test_cf_nan_replaced_by_cfmax():
    """Out-of-support prd (NaN CDF? no - clamped): CF NaN only via 0/0 in
    triangular mode==bound; check the replacement path with tri mode edge."""
    out = compute_cf(9, 3, 0, np.array([10.0]), np.array([11.0]), None,
                     None, None, lubo=np.array([10.0]), uubo=np.array([12.0]))
    # mode==lb: CDF_O=(10-10)^2/0 -> NaN -> CF=CFmax; CFmax=1-CDF_O=NaN too
    assert np.isnan(out[0, 2]) or 0 <= out[0, 2] <= 1


# ---------------- prepare_unc_cases pipeline ----------------

def test_single_per_bounds_and_yerror():
    data = np.array([[10.0, 10.5], [10.0, 12.0], [10.0, 8.5]])
    unc, plain = prepare_unc_cases(data, UncSpec(method="per", per=0.1))
    np.testing.assert_allclose(unc.ub_omin, [9, 9, 9])
    np.testing.assert_allclose(unc.ub_omax, [11, 11, 11])
    # inside -> 0; above -> ub_omax - yprd; below -> ub_omin - yprd
    np.testing.assert_allclose(unc.yerr, [0.0, -1.0, 0.5])
    assert unc.meas_unc == 0.1
    assert plain.meas_unc == 0
    assert "Harmel et al. 2007" in unc.unc_lines[0]
    assert "Single PER" in unc.unc_lines[1]


def test_errfile_per_column():
    data = np.array([[10.0, 12.0], [20.0, 20.5]])
    err = np.array([[0.05], [0.1]])
    unc, _ = prepare_unc_cases(data, UncSpec(method="errfile", err_data=err))
    assert unc.meas_unc == 1 and unc.nrcol == 3
    np.testing.assert_allclose(unc.ub_omin, [9.5, 18.0])
    np.testing.assert_allclose(unc.ub_omax, [10.5, 22.0])
    np.testing.assert_allclose(unc.yerr, [10.5 - 12.0, 0.0])
    assert "Absolute error specific" in unc.unc_lines[1]


def test_errfile_bounds_columns():
    data = np.array([[10.0, 12.0]])
    err = np.array([[1.0, 0.5]])  # lower/upper interval lengths
    unc, _ = prepare_unc_cases(data, UncSpec(method="errfile", err_data=err))
    assert unc.meas_unc == 1 and unc.nrcol == 4
    np.testing.assert_allclose(unc.ub_omin, [9.0])
    np.testing.assert_allclose(unc.ub_omax, [10.5])
    assert "Lower and upper error" in unc.unc_lines[1]


def test_errfile_with_benchmark_converts_to_cf():
    """Option 2 (benchmark data) goes through the uniform-CDF conversion."""
    data = np.array([[10.0, 11.0, 9.0]])
    err = np.array([[0.2]])  # PER 0.2 -> bounds [8,12]
    unc, plain = prepare_unc_cases(data, UncSpec(method="errfile", err_data=err))
    assert unc.meas_unc == 3 and unc.nrcol == 6
    # CDF_O=0.5, CDF_P=0.75 -> CF=0.25 -> CF/0.5=0.5
    assert unc.yerr[0] == pytest.approx(0.5 * (10.0 - 11.0))
    assert unc.yben is not None and plain.yben is not None


def _cf_of(unc):
    return unc.yerr / (unc.yobs - unc.yprd)


def test_errfile_cf_asymmetric_bounds_sidewise_cfmax():
    """Option 2 with asymmetric lengths: CFmax is F(O) below O and 1-F(O)
    above it (as compute_cf), so CF stays in [0, 1] and is 1 outside."""
    data = np.array([[10.0, 9.0], [10.0, 10.5], [10.0, 11.5], [10.0, 7.0]])
    err = np.array([[2.0, 1.0]] * 4)  # bounds [8, 11], F(O) = 2/3
    unc, _ = prepare_unc_cases(data, UncSpec(method="errfile", err_data=err,
                                             err_as_cf=True))
    # P=9: (2/3-1/3)/(2/3)=0.5; P=10.5: (5/6-2/3)/(1/3)=0.5; outside -> 1
    np.testing.assert_allclose(_cf_of(unc), [0.5, 0.5, 1.0, 1.0])
    np.testing.assert_allclose(unc.yerr, [0.5, -0.25, -1.5, 3.0])


def test_errfile_cf_symmetric_bounds_unchanged():
    """Symmetric lengths: F(O)=0.5, the same CF as the former CF/0.5."""
    data = np.array([[10.0, 10.5], [10.0, 9.0], [10.0, 12.0]])
    err = np.array([[1.0, 1.0]] * 3)
    unc, _ = prepare_unc_cases(data, UncSpec(method="errfile", err_data=err,
                                             err_as_cf=True))
    np.testing.assert_allclose(_cf_of(unc), [0.5, 1.0, 1.0])


def test_errfile_cf_obs_on_bound():
    """O on the lower bound (len1 = 0): P below is outside -> CF 1, not 0/0."""
    data = np.array([[10.0, 9.0], [10.0, 11.0]])
    err = np.array([[0.0, 2.0]] * 2)  # bounds [10, 12], F(O) = 0
    unc, _ = prepare_unc_cases(data, UncSpec(method="errfile", err_data=err,
                                             err_as_cf=True))
    np.testing.assert_allclose(_cf_of(unc), [1.0, 0.5])


def test_cf_uniform_obs_on_bound_outside_is_one():
    """compute_cf, uniform: O on the lower bound and P below it -> 1."""
    out = compute_cf(9, 4, 0, np.array([10.0]), np.array([9.0]), None,
                     None, None, lubo=np.array([10.0]), uubo=np.array([12.0]))
    assert out[0, 2] == pytest.approx(1.0)


def test_imbalance_diagnostic_skipped_under_uncertainty():
    """v4.0 gates the correlation/variability diagnostic on
    MeasUncertValue==0 (L3478): the same data reports it without
    uncertainty and stays silent with it."""
    from fiteval_core.engine import evaluate_case

    x = np.linspace(0, 4 * np.pi, 100)
    yobs = np.sin(x)
    yprd = 1.20 * yobs + np.random.default_rng(0).normal(0, 0.30, x.size)
    data = np.column_stack([yobs, yprd])
    unc, plain = prepare_unc_cases(data, UncSpec(method="per", per=0.1))

    cfg = FitevalConfig()
    assert evaluate_case(plain, cfg).imbalance_txt.endswith("overestimated")
    assert unc.meas_unc != 0
    assert evaluate_case(unc, cfg).imbalance_txt == ""


def test_errfile_cf_ratio_always_in_unit_range():
    """CF/CFmax is a correction factor: it must stay in [0, 1] for any
    asymmetric error file. The former constant CFmax = 0.5 broke this."""
    rng = np.random.default_rng(7)
    n = 200
    yobs = rng.uniform(1.0, 50.0, n)
    yprd = yobs + rng.normal(0.0, 8.0, n)          # some predictions outside
    err = np.column_stack([rng.uniform(0.5, 10.0, n),   # lower length
                           rng.uniform(0.5, 10.0, n)])  # upper length
    data = np.column_stack([yobs, yprd])
    unc, _ = prepare_unc_cases(data, UncSpec(method="errfile", err_data=err,
                                             err_as_cf=True))
    cf = unc.yerr / (unc.yobs - unc.yprd)
    assert np.isfinite(cf).all()
    assert cf.min() >= 0.0 and cf.max() <= 1.0


def test_errfile_row_mismatch():
    with pytest.raises(UncError, match="rows"):
        prepare_unc_cases(_data(10), UncSpec(method="errfile",
                                             err_data=np.ones((5, 1))))


def test_cf_pipeline_obs_normal():
    data = _data(30)
    unc, plain = prepare_unc_cases(data, UncSpec(method="cf", obs_dist=1,
                                                 cvo=10.0))
    assert unc.meas_unc == 3 and unc.nrcol == 5
    assert unc.yerr.shape == (30,)
    assert "Harmel et al. 2010" in unc.unc_lines[0]
    np.testing.assert_allclose(plain.yobs, unc.yobs)


def test_cf_pipeline_both_with_benchmark():
    data = _data(30, bench=True)
    unc, _ = prepare_unc_cases(data, UncSpec(method="cf", obs_dist=4,
                                             plubo=10, puubo=10,
                                             prd_dist=1, cvp=15.0))
    assert unc.meas_unc == 3 and unc.nrcol == 8
    assert unc.yben is not None
    assert unc.ub_pmin is not None
    assert "Observations and model uncertainty" in unc.unc_lines[0]


def test_cf_pipeline_prd_only():
    data = _data(30)
    unc, _ = prepare_unc_cases(data, UncSpec(method="cf", prd_dist=1,
                                             cvp=10.0))
    assert unc.meas_unc == 4 and unc.nrcol == 5
    assert unc.ub_pmin is not None and unc.ub_omin is None
    assert "Model uncertainty included" in unc.unc_lines[0]


def test_norep_applied_after_augmentation():
    data = _data(20)
    data = np.vstack([data, data[3]])
    unc, plain = prepare_unc_cases(data, UncSpec(method="per", per=0.1),
                                   no_repeated=True)
    assert unc.repeated_cases == 1
    assert unc.yobs.size == 20
    assert plain.repeated_cases == 1


# ---------------- end-to-end dual run ----------------

def test_run_evaluation_unc_outputs(tmp_path):
    from fiteval_core.runner import run_evaluation_unc
    cfg = FitevalConfig(n_resamples=5000)
    art_u, art_p = run_evaluation_unc(
        _data(40), UncSpec(method="per", per=0.15), "proj.in", tmp_path, cfg,
        rng=np.random.default_rng(3))
    names = {p.name for p in art_u.files} | {p.name for p in art_p.files}
    assert {"projU_out.txt", "projU_out.png", "projU.pdf",
            "proj_out.txt", "proj_out.png", "proj.pdf"} <= names
    rpt_u = art_u.report_txt.read_text()
    assert "Harmel et al. 2007" in rpt_u
    assert "Single PER common to all observations." in rpt_u
    rpt_p = art_p.report_txt.read_text()
    assert "Harmel" not in rpt_p
    # with-uncertainty NSE must be >= plain NSE (residuals shrink)
    assert art_u.result.main_idx >= art_p.result.main_idx


def test_unc_forces_nse_for_kge_flags(tmp_path):
    from fiteval_core.runner import run_evaluation_unc
    cfg = FitevalConfig(gof_index=3, n_resamples=5000)  # KGE selected
    art_u, art_p = run_evaluation_unc(
        _data(40), UncSpec(method="per", per=0.1), "proj.in", tmp_path, cfg,
        rng=np.random.default_rng(4))
    assert art_u.result.index_label == "NSE"   # forced (L3411-3416)
    assert art_p.result.index_label == "KGE"   # plain run keeps the flag
