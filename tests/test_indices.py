import math

import numpy as np
import pytest

from fiteval_core.indices import (dixon_outliers, gof_indexes, kge_nse_imbalance,
                                  e1_to_nse_threshold, kge_to_nse_threshold,
                                  nse_to_e1_threshold, nse_to_kge_threshold,
                                  relative_bias, rounddec)


def _idx(yobs, yprd, yben=None, j=2):
    yobs = np.asarray(yobs, float)
    yprd = np.asarray(yprd, float)
    yben = np.full_like(yobs, yobs.mean()) if yben is None else np.asarray(yben, float)
    yerr = yobs - yprd
    return gof_indexes(yobs, yprd, yben, yerr, j)


def test_perfect_fit():
    y = [1.0, 2.0, 3.0, 4.0]
    rmse, nse, kge_star, kge = _idx(y, y)
    assert rmse == 0
    assert nse == 1
    assert kge_star == pytest.approx(1)
    assert kge == pytest.approx(1)


def test_mean_prediction_nse_zero():
    yobs = np.array([1.0, 2.0, 3.0, 4.0])
    yprd = np.full(4, yobs.mean())
    # std(yprd)=0 -> corrcoef undefined; NSE still defined
    res = gof_indexes(yobs, yprd, np.full(4, yobs.mean()), yobs - yprd, 2)
    assert res[1] == pytest.approx(0.0)


def test_known_values_vs_matlab():
    """Hand-checked against the MATLAB formulas."""
    yobs = np.array([2.0, 4.0, 6.0, 8.0, 10.0])
    yprd = np.array([2.5, 3.5, 6.5, 7.5, 10.5])
    rmse, nse, kge_star, kge = _idx(yobs, yprd)
    assert rmse == pytest.approx(0.5)
    assert nse == pytest.approx(1 - (5 * 0.25) / np.sum((yobs - 6) ** 2))
    r = np.corrcoef(yprd, yobs)[1, 0]
    alpha = np.std(yprd, ddof=1) / np.std(yobs, ddof=1)
    beta = yprd.mean() / yobs.mean()
    assert kge == pytest.approx(1 - math.sqrt((r - 1) ** 2 + (alpha - 1) ** 2 + (beta - 1) ** 2))
    beta_star = 1 + (yprd.mean() - yobs.mean()) / np.std(yobs, ddof=1)
    assert kge_star == pytest.approx(1 - math.sqrt((r - 1) ** 2 + (alpha - 1) ** 2 + (beta_star - 1) ** 2))


def test_e1_index():
    yobs = np.array([1.0, 2.0, 3.0, 4.0])
    yprd = np.array([1.5, 2.5, 2.5, 4.5])
    res = _idx(yobs, yprd, j=1)
    expected = 1 - np.sum(np.abs(yobs - yprd)) / np.sum(np.abs(yobs - yobs.mean()))
    assert res[1] == pytest.approx(expected)


def test_benchmark_series():
    yobs = np.array([1.0, 2.0, 3.0, 4.0])
    yprd = np.array([1.1, 2.1, 2.9, 3.9])
    yben = np.array([0.5, 1.5, 2.5, 3.5])
    res = _idx(yobs, yprd, yben=yben)
    expected = 1 - np.sum((yobs - yprd) ** 2) / np.sum((yobs - yben) ** 2)
    assert res[1] == pytest.approx(expected)


def test_threshold_conversion_round_trip():
    for nse in (0.65, 0.8, 0.9):
        assert kge_to_nse_threshold(nse_to_kge_threshold(nse)) == pytest.approx(nse)
    assert nse_to_kge_threshold(0.65) == pytest.approx(1 - math.sqrt(2) * (1 - math.sqrt(0.65)))


def test_e1_threshold_conversion():
    """E1 = 1 - sqrt(1 - NSE); E1 is its own scale, not equal to NSE."""
    assert nse_to_e1_threshold(0.65) == pytest.approx(1 - math.sqrt(1 - 0.65))
    # the default NSE limits map to these E1 limits (2-decimal display)
    assert [round(nse_to_e1_threshold(t), 2) for t in (0.65, 0.80, 0.90)] \
        == [0.41, 0.55, 0.68]
    for nse in (0.65, 0.8, 0.9):
        assert e1_to_nse_threshold(nse_to_e1_threshold(nse)) == pytest.approx(nse)
    # E1 thresholds are stricter-looking than NSE: they must not be equal
    assert nse_to_e1_threshold(0.65) != pytest.approx(0.65)


def test_rounddec_matlab_halfaway():
    assert rounddec(0.125, 2) == 0.13   # MATLAB rounds half away from zero
    assert rounddec(-0.125, 2) == -0.13
    assert rounddec(2.5, 0) == 3


def test_bias_no():
    yobs = np.array([1.0, 2.0, 3.0])
    rel, t1, t2 = relative_bias(yobs, yobs * 1.01, 5.0, "NSE")
    assert t1 == "Model bias: NO" and t2 == ""


def test_bias_over_under():
    yobs = np.array([1.0, 2.0, 3.0])
    rel, t1, _ = relative_bias(yobs, yobs * 1.2, 5.0, "NSE")
    assert "Overprediction" in t1 and rel == pytest.approx(20.0)
    rel, t1, _ = relative_bias(yobs, yobs * 0.8, 5.0, "NSE")
    assert "Underprediction" in t1 and rel == pytest.approx(-20.0)


def test_bias_negative_shift():
    """Series with negatives are shifted non-negative before the ratio."""
    yobs = np.array([-1.0, 0.0, 1.0])
    yprd = np.array([-1.0, 0.5, 1.0])
    rel, _, _ = relative_bias(yobs, yprd, 5.0, "NSE")
    # shift by +1: mean(shifted obs)=1, sum(P-O)=0.5 -> 0.5/3/1*100
    assert rel == pytest.approx(rounddec(0.5 / 3 * 100, 1))


def test_dixon_outlier_detected():
    yobs = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 20.0])
    yprd = np.array([1.1, 2.1, 2.9, 4.1, 5.0, 6.1, 6.9, 7.0])
    res = dixon_outliers(yobs, yprd)
    assert res.present
    np.testing.assert_array_equal(res.points, [[7.0, 20.0]])


def test_dixon_no_outlier():
    yobs = np.array([1.0, 2.0, 3.0, 4.0])
    yprd = np.array([1.1, 2.2, 2.9, 4.1])
    assert not dixon_outliers(yobs, yprd).present


_X = np.linspace(0, 4 * np.pi, 100)
_OBS = np.sin(_X)


def _imbalance(yprd):
    idx = _idx(_OBS, yprd)
    return kge_nse_imbalance(_OBS, yprd, idx[1], idx[2])


def test_imbalance_class_2a_rho_higher_than_alpha():
    """Damped amplitude: alpha = 0.3, rho = 1, so rho/alpha > 1.05 (L3463)."""
    txt = _imbalance(0.3 * _OBS)
    assert txt == ("Variability (\N{GREEK SMALL LETTER ALPHA}) - correlation "
                   "(\N{GREEK SMALL LETTER RHO}) mismatch: "
                   "\N{GREEK SMALL LETTER RHO} higher than "
                   "\N{GREEK SMALL LETTER ALPHA} (1.00 > 0.30)")


def test_imbalance_class_2b_underestimated():
    """alpha < 1 and rho/alpha < 0.95 -> 'and underestimated' (L3470-3474)."""
    yprd = 0.80 * _OBS + np.random.default_rng(0).normal(0, 0.40, _OBS.size)
    txt = _imbalance(yprd)
    assert "higher than \N{GREEK SMALL LETTER RHO}" in txt
    assert txt.endswith("(0.90 > 0.80) and underestimated")


def test_imbalance_class_2c_overestimated():
    """alpha >= 1 and rho/alpha < 0.95 -> 'and overestimated' (L3476-3480)."""
    yprd = 1.20 * _OBS + np.random.default_rng(0).normal(0, 0.30, _OBS.size)
    txt = _imbalance(yprd)
    assert txt.endswith("(1.21 > 0.94) and overestimated")


def test_imbalance_class_1_bias_driven():
    """rho == alpha == 1 with a pure offset: the gap is bias (L3485-3486)."""
    txt = _imbalance(_OBS + 0.5)
    assert txt == ("Correlation (\N{GREEK SMALL LETTER RHO}) "
                   "\N{ALMOST EQUAL TO} variability "
                   "(\N{GREEK SMALL LETTER ALPHA}), but bias is non-negligible")


def test_imbalance_silent_when_nse_not_positive():
    """MATLAB gate NSE>0 (L3455): 3x amplitude gives NSE=-3, so no text."""
    assert _idx(_OBS, 3.0 * _OBS)[1] < 0
    assert _imbalance(3.0 * _OBS) == ""


def test_imbalance_silent_inside_envelope():
    """A good fit sits inside the KGE* envelope and says nothing."""
    assert _imbalance(_OBS + 0.01 * np.cos(_X)) == ""


def test_imbalance_silent_for_good_fit():
    x = np.linspace(0, 4 * np.pi, 100)
    yobs = np.sin(x)
    yprd = yobs + 0.01
    idx = _idx(yobs, yprd)
    assert kge_nse_imbalance(yobs, yprd, idx[1], idx[2]) == ""
