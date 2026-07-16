import numpy as np
import pytest

from fiteval_core.bootstrap import (BootstrapError, bca_ci, efron_bootstrap_indices,
                                    matlab_prctile, opt_block_length,
                                    stationary_bootstrap_indices)
from fiteval_core.indices import gof_indexes


def test_matlab_prctile():
    # MATLAB: prctile([1 2 3 4],50)=2.5; prctile([1 2 3 4 5],25)=1.75
    assert matlab_prctile(np.array([1, 2, 3, 4.0]), 50) == 2.5
    assert matlab_prctile(np.array([1, 2, 3, 4, 5.0]), 25) == 1.75
    assert matlab_prctile(np.array([1, 2, 3, 4, 5.0]), 75) == 4.25
    # clamped at the ends
    assert matlab_prctile(np.array([1, 2, 3, 4, 5.0]), 1) == 1.0
    assert matlab_prctile(np.array([1, 2, 3, 4, 5.0]), 99) == 5.0


def test_opt_block_length_white_noise_vs_ar1():
    rng = np.random.default_rng(42)
    white = rng.standard_normal(500)
    ar1 = np.empty(500)
    ar1[0] = 0.0
    for i in range(1, 500):
        ar1[i] = 0.9 * ar1[i - 1] + rng.standard_normal()
    b_white = opt_block_length(white)
    b_ar1 = opt_block_length(ar1)
    assert b_ar1 > b_white          # persistent series need longer blocks
    assert b_ar1 <= np.ceil(min(3 * np.sqrt(500), 500 / 3))  # Bmax cap
    assert b_white >= 1.0


def test_opt_block_length_deterministic():
    rng = np.random.default_rng(0)
    x = rng.standard_normal(200)
    assert opt_block_length(x) == opt_block_length(x)


def test_stationary_bootstrap_indices_valid():
    rng = np.random.default_rng(1)
    idx = stationary_bootstrap_indices(50, 200, 5.0, rng)
    assert idx.shape == (50, 200)
    assert idx.min() >= 0 and idx.max() < 50
    # blocks: consecutive indices mostly increment by 1
    diffs = np.diff(idx, axis=0) == 1
    frac_continue = diffs.mean()
    assert 0.6 < frac_continue < 0.95  # p_new=0.2 -> ~80% continuations


def test_efron_indices_uniform():
    rng = np.random.default_rng(2)
    idx = efron_bootstrap_indices(10, 5000, rng)
    counts = np.bincount(idx.ravel(), minlength=10)
    assert abs(counts.mean() - 5000) < 1e-9
    assert counts.std() / counts.mean() < 0.05


def _sample_data(n=60, seed=3):
    rng = np.random.default_rng(seed)
    yobs = np.sin(np.linspace(0, 6 * np.pi, n)) * 3 + 5 + rng.normal(0, 0.3, n)
    yprd = np.sin(np.linspace(0, 6 * np.pi, n)) * 2.8 + 5.1 + rng.normal(0, 0.3, n)
    yben = np.full(n, yobs.mean())
    return yobs, yprd, yben, yobs - yprd


@pytest.mark.parametrize("bstype", [0, 1])
def test_bca_ci_brackets_stat(bstype):
    yobs, yprd, yben, yerr = _sample_data()
    stat = gof_indexes(yobs, yprd, yben, yerr, 2)
    ci, bstat, used = bca_ci(yobs, yprd, yben, yerr, 2, 5000, bstype,
                             rng=np.random.default_rng(7))
    assert ci.shape == (2, 4)
    assert used == bstype
    for k in range(4):
        assert ci[0, k] <= ci[1, k]
        assert ci[0, k] <= stat[k] <= ci[1, k]
    # NSE CI must stay <= 1
    assert ci[1, 1] <= 1.0


def test_bca_ci_seeded_reproducible():
    yobs, yprd, yben, yerr = _sample_data()
    ci1, _, _ = bca_ci(yobs, yprd, yben, yerr, 2, 2000, 0,
                       rng=np.random.default_rng(11))
    ci2, _, _ = bca_ci(yobs, yprd, yben, yerr, 2, 2000, 0,
                       rng=np.random.default_rng(11))
    np.testing.assert_array_equal(ci1, ci2)


def test_bca_ci_block_vs_efron_similar():
    """For independent data both methods should give similar CIs."""
    yobs, yprd, yben, yerr = _sample_data(n=200)
    ci_b, _, _ = bca_ci(yobs, yprd, yben, yerr, 2, 10000, 0,
                        rng=np.random.default_rng(5))
    ci_e, _, _ = bca_ci(yobs, yprd, yben, yerr, 2, 10000, 1,
                        rng=np.random.default_rng(5))
    np.testing.assert_allclose(ci_b[:, 1], ci_e[:, 1], atol=0.05)  # NSE CI


def test_bca_nonfinite_stat_raises():
    yobs = np.array([0.0, 0.0, 0.0, 0.0])  # mean 0 -> KGE beta = inf
    yprd = np.array([1.0, 2.0, 3.0, 4.0])
    yben = np.full(4, yobs.mean())
    with pytest.raises(BootstrapError):
        bca_ci(yobs, yprd, yben, yobs - yprd, 2, 100, 1)


def test_bstat_matches_direct_evaluation():
    """Vectorized column evaluation must equal per-resample gof_indexes."""
    from fiteval_core.bootstrap import _eval_indices_columns
    yobs, yprd, yben, yerr = _sample_data(n=25)
    rng = np.random.default_rng(9)
    idx = efron_bootstrap_indices(25, 50, rng)
    fast = _eval_indices_columns(yobs, yprd, yben, yerr, 2, idx)
    for b in range(50):
        direct = gof_indexes(yobs[idx[:, b]], yprd[idx[:, b]],
                             yben[idx[:, b]], yerr[idx[:, b]], 2)
        np.testing.assert_allclose(fast[b], direct, rtol=1e-10)
