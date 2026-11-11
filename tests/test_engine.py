import numpy as np
import pytest

from fiteval_core.config import FitevalConfig
from fiteval_core.engine import EngineError, evaluate
from fiteval_core.report import build_numout_row, numerical_report


def _data(n=80, noise=0.4, seed=6):
    rng = np.random.default_rng(seed)
    yobs = 5 + 3 * np.sin(np.linspace(0, 6 * np.pi, n)) + rng.normal(0, noise, n)
    yprd = yobs + rng.normal(0, noise, n)
    return np.column_stack([yobs, yprd])


def test_good_fit_pipeline():
    cfg = FitevalConfig(n_resamples=5000)
    res = evaluate(_data(noise=0.2), cfg, rng=np.random.default_rng(1))
    assert res.index_label == "NSE"
    assert res.sec_label == "KGE*"
    assert res.main_idx > 0.9
    assert res.main_ci[0] <= res.main_idx <= res.main_ci[1]
    probs = res.class_probs
    total = sum(probs.values())
    assert total == pytest.approx(100.0, abs=0.2)
    assert res.rating_text in ("VERY GOOD", "GOOD",
                               "From GOOD to VERY GOOD")
    assert res.p_value == probs["unsatisfactory"] / 100


def test_poor_fit_unsatisfactory():
    rng = np.random.default_rng(3)
    yobs = rng.normal(10, 2, 60)
    yprd = rng.normal(10, 2, 60)  # uncorrelated noise
    cfg = FitevalConfig(n_resamples=5000)
    res = evaluate(np.column_stack([yobs, yprd]), cfg,
                   rng=np.random.default_rng(2))
    assert res.main_idx < 0.65
    assert res.class_probs["unsatisfactory"] > 50


def test_kge_star_primary():
    cfg = FitevalConfig(gof_index=2, n_resamples=5000)
    res = evaluate(_data(), cfg, rng=np.random.default_rng(4))
    assert res.index_label == "KGE*" and res.sec_label == "NSE"
    assert res.main_idx == pytest.approx(res.gof[2])


def test_e1_primary():
    cfg = FitevalConfig(gof_index=4, n_resamples=5000)
    res = evaluate(_data(), cfg, rng=np.random.default_rng(4))
    assert res.index_label == "E_1" and res.jexp == 1


def test_benchmark_column():
    data = _data()
    bench = np.full(data.shape[0], data[:, 0].mean() + 1.0)
    cfg = FitevalConfig(n_resamples=5000)
    res = evaluate(np.column_stack([data, bench]), cfg,
                   rng=np.random.default_rng(5))
    assert res.benchmark_used


def test_constant_series_refused():
    yobs = np.linspace(1, 10, 20)
    yprd = np.full(20, 5.0)
    with pytest.raises(EngineError, match="bootstrapping is not possible"):
        evaluate(np.column_stack([yobs, yprd]), FitevalConfig())


def test_nan_rows_removed():
    data = _data(n=50)
    data[3, 0] = np.nan
    data[7, 1] = np.nan
    cfg = FitevalConfig(n_resamples=5000)
    res = evaluate(data, cfg, rng=np.random.default_rng(6))
    assert res.n == 48


def test_report_structure():
    cfg = FitevalConfig(n_resamples=5000)
    res = evaluate(_data(noise=0.2), cfg, rng=np.random.default_rng(7))
    rpt = numerical_report(res)
    assert rpt.startswith("   =============== GOODNESS-OF-FIT EVALUATION ==")
    assert "       RMSE= " in rpt
    assert "       NSE = " in rpt
    assert f"Evaluation of NSE: {res.rating_text}" in rpt
    assert "- Very good (NSE = 0.900 - 1.000):" in rpt
    assert "- Good (NSE = 0.800 - 0.899):" in rpt
    assert "- Acceptable (NSE = 0.650 - 0.799):" in rpt
    assert "- Unsatisfactory (NSE < 0.650):" in rpt
    assert "p-value:" in rpt
    # the TeX-length>90 rule (L3520) compresses '= ' to '=' in practice
    assert "NRMSE=100*RMSE/SD=" in rpt
    assert "Presence of outliers (Q-test):" in rpt
    assert "Model bias:" in rpt
    assert "*: 95% Confidence interval obtained from Bca bootstrapping" in rpt
    assert "Politis and Romano (1994)" in rpt


def test_report_efron_note():
    cfg = FitevalConfig(bstype=1, n_resamples=5000)
    res = evaluate(_data(), cfg, rng=np.random.default_rng(8))
    assert "Efron and Tibshirani (1993)" in numerical_report(res)


def test_numout_row():
    cfg = FitevalConfig(n_resamples=5000)
    res = evaluate(_data(noise=0.2), cfg, rng=np.random.default_rng(9))
    row = build_numout_row(res)
    assert len(row) == 12
    assert row[0] == "%1.3f" % res.main_idx
    assert row[-1] == str(res.n)
    assert row[8].endswith("%")


def test_repeated_rows_reported():
    data = _data(n=30)
    data = np.vstack([data, data[5], data[10]])
    cfg = FitevalConfig(n_resamples=5000)
    res = evaluate(data, cfg, no_repeated=True, rng=np.random.default_rng(10))
    assert res.repeated_cases == 2
    assert "2 repeated cases were removed" in numerical_report(res)
