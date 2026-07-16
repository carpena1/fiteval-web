import numpy as np
import pytest

from fiteval_core.kde import KDEError, ksdensity_cdf


def test_cdf_monotone_and_bounded():
    rng = np.random.default_rng(4)
    dist = np.clip(rng.normal(0.8, 0.05, 5000), 0.5, 0.999)
    xi = np.linspace(0, 1, 1001)
    lo = dist.min() - 0.05
    fi = ksdensity_cdf(dist, xi, (lo, 1.001))
    assert fi.shape == xi.shape
    assert np.all(np.diff(fi) >= -1e-12)
    assert fi[0] == 0.0            # xi=0 typically below support start? not always
    assert 0.0 <= fi.min() and fi.max() <= 1.0


def test_cdf_median_location():
    rng = np.random.default_rng(8)
    dist = np.clip(rng.normal(0.8, 0.03, 20000), 0.6, 0.999)
    xi = np.linspace(0, 1, 1001)
    fi = ksdensity_cdf(dist, xi, (dist.min() - 0.05, 1.001))
    med = np.median(dist)
    i = np.argmin(np.abs(xi - med))
    assert abs(fi[i] - 0.5) < 0.02


def test_cdf_outside_support():
    dist = np.array([0.7, 0.75, 0.8, 0.85])
    xi = np.array([0.0, 0.5, 1.0005, 1.001])
    fi = ksdensity_cdf(dist, xi, (0.65, 1.001))
    assert fi[0] == 0.0
    assert fi[-1] == 1.0


def test_inf_values_raise():
    with pytest.raises(KDEError):
        ksdensity_cdf(np.array([-np.inf, 0.5, 0.6]), np.linspace(0, 1, 11),
                      (-np.inf, 1.001))


def test_probability_mass_matches_empirical():
    """Kernel CDF should be close to the ECDF for a big smooth sample."""
    rng = np.random.default_rng(12)
    dist = np.clip(rng.beta(8, 2, 50000) * 0.6 + 0.4, None, 0.9999)
    xi = np.linspace(0, 1, 1001)
    fi = ksdensity_cdf(dist, xi, (dist.min() - 0.05, 1.001))
    for q in (0.7, 0.8, 0.9):
        i = np.argmin(np.abs(xi - q))
        emp = np.mean(dist <= q)
        assert abs(fi[i] - emp) < 0.01
